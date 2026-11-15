"""Contratos de arquitectura: XGBoost -> rotación, sin clima ni umbrales inventados."""

from copy import deepcopy
from datetime import date
import importlib.util
import tempfile
import unittest
from unittest.mock import Mock

from ml.recommendations.rotation import ForecastRotationEngine
from modulo_rotacion.motor_rotacion import recomendar
from packages.contracts.api import AnalysisRequest, AnalysisResult, Forecast, ForecastValue
from packages.contracts.rotation import RotationWaterRules, WaterRequirement
from pipelines.recommendations.pipeline import CropRecommendationPipeline


def fixtures(*, temperature=22, rain=50, moisture=.3, horizon=7, validation='experimental'):
    request=AnalysisRequest(region_id='test-only',reference_date=date(2026,1,1),
                            forecast_start_date=date(2026,1,4),horizon_days=horizon)
    def make(kind,values):
        return Forecast(model_kind=kind,model_version=f'test-only-{kind}',validation_status=validation,
            region_id=request.region_id,reference_date=request.reference_date,
            forecast_start_date=request.forecast_start_date,horizon_days=horizon,values=values)
    climate=make('climate',[
        ForecastValue(variable='temperature_mean',value=temperature,unit='C',aggregation='mean',statistic='mean'),
        ForecastValue(variable='temperature_min',value=temperature-3,unit='C',aggregation='mean',statistic='mean'),
        ForecastValue(variable='temperature_max',value=temperature+3,unit='C',aggregation='mean',statistic='mean'),
        ForecastValue(variable='precipitation',value=rain,unit='mm',aggregation='sum',statistic='sum')])
    soil=make('soil',[ForecastValue(variable='surface_soil_moisture',value=moisture,unit='m3/m3',aggregation='mean',statistic='mean')])
    return request,climate,soil


class ForecastRotationTests(unittest.TestCase):
    def setUp(self):
        self.engine=ForecastRotationEngine()

    def test_legacy_motor_without_models_never_uses_interview_climate(self):
        for zone in ['fria','templada','calida']:
            result=recomendar({'finca':{'zona':zone,'lluvias':'bimodal'}})
            self.assertEqual(result['status'],'pending_forecasts')
            self.assertEqual(result['rotaciones'],[])
            self.assertNotIn('temperatura_supuesta_C',result)

    def test_same_forecasts_ignore_contradictory_interview_zone_and_preserve_responses(self):
        request,climate,soil=fixtures()
        analysis=AnalysisResult(status='pending_recommendations',request=request,climate=climate,soil=soil)
        responses={'finca':{'zona':'fria','region_id':'test-only'},'historial':{'ultimo':'papa','veces':3}}
        before=deepcopy(responses)
        first=recomendar(responses,analisis=analysis)
        self.assertEqual(responses,before)
        responses['finca']['zona']='calida'
        second=recomendar(responses,analisis=analysis)
        self.assertEqual(first['evaluacion_rotacion'],second['evaluacion_rotacion'])
        self.assertEqual(first['evaluacion_rotacion']['forecast_values']['temperature_mean'],22)

    def test_predicted_temperature_changes_candidates_and_no_three_options_are_fabricated(self):
        request,climate,soil=fixtures()
        mild=self.engine.assess(request,climate,soil)
        _,hot,_=fixtures(temperature=60)
        severe=self.engine.assess(request,hot,soil)
        self.assertTrue(mild.scenarios)
        self.assertEqual(severe.status,'no_compatible_candidates')
        self.assertEqual(severe.scenarios,[])
        self.assertNotEqual(mild.input_snapshot_id,severe.input_snapshot_id)

    def test_water_predictions_are_inputs_with_unknown_checks_until_rules_exist(self):
        for horizon in [7,15,30,60]:
            request,climate,soil=fixtures(rain=123,moisture=.271,horizon=horizon)
            report=self.engine.assess(request,climate,soil)
            self.assertEqual(report.status,'pending_agronomic_requirements')
            self.assertEqual(report.forecast_values['precipitation'],123)
            self.assertEqual(report.forecast_values['surface_soil_moisture'],.271)
            self.assertTrue(all(check.status=='unknown' for candidate in report.candidates for check in candidate.checks
                                if check.variable in ('precipitation','surface_soil_moisture')))
            self.assertFalse(report.recommendation_ready)

    def test_reviewed_crop_and_horizon_water_rules_change_eligibility(self):
        crop=self.engine.catalog.crops[0]
        rules=RotationWaterRules(version='test-only',review_status='reviewed',requirements=[WaterRequirement(
            crop_id=crop.crop_id,horizon_days=7,precipitation_min_mm=0,precipitation_max_mm=100,
            surface_moisture_min=.1,surface_moisture_max=.4,source='SYNTHETIC TEST FIXTURE, NOT AGRONOMIC ADVICE')])
        engine=ForecastRotationEngine(water_rules=rules)
        request,climate,soil=fixtures()
        normal=engine.assess(request,climate,soil,previous_family='Fabaceae').candidates[0]
        self.assertEqual(normal.status,'within_checked_ranges')
        _,wet,saturated=fixtures(rain=200,moisture=.7)
        rejected=engine.assess(request,wet,saturated,previous_family='Fabaceae').candidates[0]
        self.assertEqual(rejected.status,'excluded')
        self.assertEqual([check.status for check in rejected.checks[1:3]],['outside_range','outside_range'])
        later_request,later_climate,later_soil=fixtures(horizon=30)
        later=engine.assess(later_request,later_climate,later_soil)
        self.assertEqual(later.candidates[0].checks[1].status,'unknown')
        rules.review_status='pending'
        self.assertEqual(engine.assess(request,climate,soil).candidates[0].checks[1].status,'unknown')

    def test_forecasts_must_have_same_region_period_units_and_statistic(self):
        request,climate,soil=fixtures()
        for changes in [{'region_id':'other'},{'horizon_days':30},{'forecast_start_date':date(2026,1,5)}]:
            with self.assertRaisesRegex(ValueError,'compartir'):
                self.engine.assess(request,climate,soil.model_copy(update=changes))
        bad=climate.model_copy(deep=True)
        bad.values[-1].unit='mm/year'
        with self.assertRaisesRegex(ValueError,'Unidad'):
            self.engine.assess(request,bad,soil)
        bad.values[-1].unit='mm'
        bad.values[-1].statistic='mean'
        with self.assertRaisesRegex(ValueError,'estadística'):
            self.engine.assess(request,bad,soil)
        self.assertEqual(self.engine.assess(request,climate,None).status,'pending_forecasts')

    def test_no_forecast_is_extrapolated_to_later_crop_cycles(self):
        request,climate,soil=fixtures(horizon=60)
        report=self.engine.assess(request,climate,soil,previous_family='Solanaceae')
        for scenario in report.scenarios:
            self.assertTrue(scenario.stages[0].forecast_evaluated)
            self.assertTrue(all(not s.forecast_evaluated for s in scenario.stages[1:]))
            self.assertEqual(len({s.family for s in scenario.stages}),len(scenario.stages))
            self.assertEqual(scenario.status,'conditional')
        excluded=self.engine.assess(request,climate,soil,previous_family='Poaceae',excluded_crops=['maiz'])
        self.assertEqual(excluded.candidates[0].status,'excluded')

    def test_private_lot_requires_explicit_region_and_cannot_use_another_region(self):
        request,climate,soil=fixtures()
        analysis=AnalysisResult(status='pending_recommendations',request=request,climate=climate,soil=soil)
        self.assertEqual(recomendar({},analisis=analysis)['status'],'pending_region_context')
        with self.assertRaisesRegex(ValueError,'otra región'):
            recomendar({'finca':{'region_id':'wrong'}},analisis=analysis)

    def test_pipeline_uses_assessment_and_cannot_publish_experimental_or_incomplete_rules(self):
        for validation in ['experimental','validated']:
            request,climate,soil=fixtures(validation=validation)
            approved_engine,store=Mock(),Mock()
            pipeline=CropRecommendationPipeline(Mock(),recommendations=approved_engine,results_repository=store,rotation_engine=self.engine)
            result=pipeline.finalize(AnalysisResult(status='pending_recommendations',request=request,climate=climate,soil=soil,input_snapshot_id='test-only'))
            self.assertIsNotNone(result.rotation_assessment)
            self.assertIsNone(result.recommendations)
            self.assertEqual(result.status,'pending_recommendations')
            approved_engine.recommend.assert_not_called()
            self.assertEqual(store.save_analysis.call_args.args[0].analysis_id,result.analysis_id)

    @unittest.skipUnless(importlib.util.find_spec('xgboost'),'Requiere extra ml')
    def test_real_xgboost_outputs_feed_rotation_for_every_horizon(self):
        from tests.test_pretrained_models import PretrainedModelTests
        from ml.inference.expanded import ExpandedModelBundle
        fixture=PretrainedModelTests();fixture.setUp()
        for horizon in [7,15,30,60]:
            result=ExpandedModelBundle().predict(fixture.snapshot,horizon_days=horizon)
            report=self.engine.assess(result.request,result.climate,result.soil)
            self.assertEqual(report.forecast_values['precipitation'],result.climate.values[-1].value)
            self.assertEqual(report.forecast_values['surface_soil_moisture'],result.soil.values[0].value)
            self.assertEqual(report.climate_model_version,result.climate.model_version)
            self.assertEqual(report.soil_model_version,result.soil.model_version)
            self.assertEqual(report.horizon_days,horizon)

    @unittest.skipUnless(importlib.util.find_spec('xgboost'),'Requiere extra ml')
    def test_batch_job_persists_rotation_assessment_with_real_predictions(self):
        from datetime import timedelta
        from tests.test_pretrained_models import PretrainedModelTests
        from ml.inference.expanded import ExpandedModelBundle
        from ml.features.expanded import ExpandedFeatureStore
        from pipelines.recommendations.job import CropRecommendationJob
        fixture=PretrainedModelTests();fixture.setUp()
        with tempfile.TemporaryDirectory() as directory:
            features=ExpandedFeatureStore(directory)
            features.save(fixture.snapshot)
            observations,results,registry=Mock(),Mock(),Mock()
            observations.regions.return_value=[fixture.region]
            registry.current.return_value=None
            job=CropRecommendationJob(observations,results,registry,Mock(),bundled_models=ExpandedModelBundle(),
                                      feature_store=features,rotation_engine=self.engine)
            job.run(as_of=fixture.snapshot.issue_date+timedelta(days=1))
            self.assertEqual(results.save_analysis.call_count,4)
            for call in results.save_analysis.call_args_list:
                result=call.args[0]
                self.assertIsNotNone(result.rotation_assessment)
                self.assertEqual(result.rotation_assessment.status,'pending_agronomic_requirements')
                self.assertEqual(result.rotation_assessment.climate_model_version,result.climate.model_version)
                self.assertEqual(result.rotation_assessment.horizon_days,result.request.horizon_days)
                self.assertIsNone(result.recommendations)
