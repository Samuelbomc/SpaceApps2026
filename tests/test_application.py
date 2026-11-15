"""Contrato HTTP y puertos de modelos; todas las salidas sintéticas son fixtures de test."""

import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock

from fastapi.testclient import TestClient

from apps.api.app.db.postgres import DatabaseUnavailable
from apps.api.app.main import create_app
from apps.api.app.services.analysis import AnalysisService
from packages.contracts.api import AnalysisRequest, Forecast, ForecastValue, Recommendations, Rotation
from scripts.worker import next_slot


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.repo = Mock()
        self.repo.regions.return_value = [{"region_id": "test", "name": "Solo test", "latitude": 6, "longitude": -75}]
        self.repo.region.return_value = self.repo.regions.return_value[0]
        self.repo.schedule.return_value = None
        self.repo.recent_runs.return_value = []
        self.repo.observations.return_value = []
        self.repo.analyses.return_value = []
        self.repo.analysis_for.return_value = None
        self.client = TestClient(create_app(self.repo))
        self.request = {"region_id": "test", "reference_date": "2024-01-01", "horizon_days": 7}

    def test_pending_models_are_explicit_and_never_persist_fake_predictions(self):
        response = self.client.post("/api/v1/analyses", json=self.request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "pending_model")
        self.assertIsNone(response.json()["climate"])
        self.repo.save_analysis.assert_not_called()

    def test_read_request_does_not_run_configured_models(self):
        service = AnalysisService(self.repo, Mock(), Mock())
        client = TestClient(create_app(self.repo, service))
        response = client.post("/api/v1/analyses", json=self.request)
        self.assertEqual(response.json()["status"], "pending_run")
        service.climate.predict.assert_not_called()

    def test_validation_limits_dates_and_unknown_regions(self):
        self.assertEqual(self.client.post("/api/v1/analyses", json={**self.request, "horizon_days": 0}).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/analyses", json={**self.request, "reference_date": "2999-01-01"}).status_code, 422)
        self.assertEqual(self.client.get("/api/v1/regions/test/observations?start=2024-02-01&end=2024-01-01").status_code, 422)
        self.repo.region.return_value = None
        self.assertEqual(self.client.post("/api/v1/analyses", json=self.request).status_code, 404)

    def test_database_error_is_actionable_without_leaking_connection_string(self):
        self.repo.regions.side_effect = DatabaseUnavailable("PostgreSQL no está disponible.")
        response = self.client.get("/api/v1/regions")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "database_unavailable")

    def test_openapi_contains_shared_contracts(self):
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/api/v1/regions/{region_id}/observations", schema["paths"])
        self.assertIn("AnalysisResult", schema["components"]["schemas"])

    def test_generated_contracts_match_the_current_api(self):
        import json
        from pathlib import Path
        from scripts.export_openapi import generate_typescript
        from apps.api.app.main import app
        schema = app.openapi()
        self.assertEqual(json.loads(Path("packages/contracts/openapi.json").read_text()), schema)
        self.assertEqual(Path("packages/contracts/api.generated.ts").read_text(), generate_typescript(schema))

    def test_inference_order_context_and_idempotent_identity(self):
        events = []
        request = AnalysisRequest(**self.request)
        self.repo.observations.return_value = [{"date": "2024-01-01", "variable": "T2M", "value": 20,
                                                "quality": "provider_value_unvalidated"}]
        def climate(req, observations):
            events.append("climate")
            return Forecast(model_kind="climate", model_version="test-only-v1", region_id=req.region_id,
                            reference_date=req.reference_date, horizon_days=req.horizon_days,
                            values=[ForecastValue(variable="temperature", value=20, unit="C", aggregation="mean")])
        def soil(req, observations, forecast):
            self.assertEqual(forecast.model_kind, "climate")
            events.append("soil")
            return Forecast(model_kind="soil", model_version="test-only-v1", region_id=req.region_id,
                            reference_date=req.reference_date, horizon_days=req.horizon_days,
                            values=[ForecastValue(variable="moisture", value=.3, unit="m3/m3", aggregation="mean")])
        engine = Mock()
        engine.recommend.return_value = Recommendations(engine_version="test-only-v1", alternatives=[
            Rotation(name=f"Fixture {i}", crops=["test-crop"], reasons=["Solo prueba del contrato"])
            for i in range(3)])
        climate_adapter, soil_adapter = Mock(), Mock()
        climate_adapter.predict.side_effect, soil_adapter.predict.side_effect = climate, soil
        service = AnalysisService(self.repo, climate_adapter, soil_adapter, engine)
        first, second = service.run(request), service.run(request)
        self.assertEqual(events, ["climate", "soil", "climate", "soil"])
        self.assertEqual(first.analysis_id, second.analysis_id)
        self.assertEqual(first.status, "ready")

    def test_model_cannot_return_another_region(self):
        self.repo.observations.return_value = [{"date": "2024-01-01", "variable": "T2M", "value": 20,
                                                "quality": "provider_value_unvalidated"}]
        climate = Mock()
        climate.predict.return_value = Forecast(model_kind="climate", model_version="test-only", region_id="wrong",
            reference_date=date(2024, 1, 1), horizon_days=7,
            values=[ForecastValue(variable="temperature", value=20, unit="C", aggregation="mean")])
        with self.assertRaises(ValueError):
            AnalysisService(self.repo, climate, Mock()).run(AnalysisRequest(**self.request))
        self.repo.save_analysis.assert_not_called()

    def test_schedule_is_168_hours_and_skips_missed_slots_without_drift(self):
        due = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(next_slot(due, due, 604800), due + timedelta(days=7))
        finished = due + timedelta(days=20)
        self.assertEqual(next_slot(due, finished, 604800), due + timedelta(days=21))

    def test_latest_analysis_uses_available_history_without_date_filters(self):
        self.repo.latest_observation_date.return_value = date(2025, 12, 31)
        response = self.client.get('/api/v1/regions/test/latest-analysis?as_of=2026-01-05')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['request']['reference_date'], '2025-12-31')
        self.assertEqual(response.json()['status'], 'pending_model')
        self.repo.observations.assert_not_called()
        self.repo.analysis_for.assert_called_once_with(AnalysisRequest(
            region_id='test', reference_date=date(2025, 12, 31), horizon_days=7, forecast_start_date=date(2026, 1, 5)))
        self.repo.save_analysis.assert_not_called()

    def test_latest_analysis_without_observations_returns_no_reference(self):
        self.repo.latest_observation_date.return_value = None
        response = self.client.get('/api/v1/regions/test/latest-analysis?as_of=2026-01-05')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json())
        self.repo.analysis_for.assert_not_called()

    def test_latest_analysis_returns_exact_stored_context_without_running_models(self):
        self.repo.latest_observation_date.return_value = date(2025, 12, 31)
        request = {'region_id': 'test', 'reference_date': '2025-12-31', 'horizon_days': 7, 'forecast_start_date': '2026-01-05'}
        self.repo.analysis_for.return_value = {'status': 'pending_recommendations', 'request': request,
                                             'analysis_id': 'fixture-context'}
        service = AnalysisService(self.repo, Mock(), Mock())
        response = TestClient(create_app(self.repo, service)).get('/api/v1/regions/test/latest-analysis?as_of=2026-01-05')
        self.assertEqual(response.json()['analysis_id'], 'fixture-context')
        service.climate.predict.assert_not_called()
        service.soil.predict.assert_not_called()

    def test_latest_analysis_validates_horizon_and_region(self):
        self.assertEqual(self.client.get('/api/v1/regions/test/latest-analysis?horizon_days=0').status_code, 422)
        self.repo.region.return_value = None
        self.assertEqual(self.client.get('/api/v1/regions/missing/latest-analysis').status_code, 404)

    def test_planning_horizons_query_the_exact_selected_result(self):
        self.repo.latest_observation_date.return_value = date(2025, 12, 31)
        for days in (7, 15, 30, 60):
            with self.subTest(days=days):
                response = self.client.get(f'/api/v1/regions/test/latest-analysis?horizon_days={days}&as_of=2026-01-05')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['request']['horizon_days'], days)
                self.assertEqual(response.json()['request']['reference_date'], '2025-12-31')
                self.assertEqual(response.json()['status'], 'pending_model')
                self.repo.analysis_for.assert_called_with(AnalysisRequest(
                    region_id='test', reference_date=date(2025, 12, 31), horizon_days=days, forecast_start_date=date(2026, 1, 5)))
        self.repo.save_analysis.assert_not_called()

    def test_query_date_is_separate_from_old_satellite_observations(self):
        self.repo.latest_observation_date.return_value = date(2024, 1, 1)
        response = self.client.get('/api/v1/regions/test/latest-analysis?horizon_days=30&as_of=2026-01-05')
        self.assertEqual(response.json()['request']['reference_date'], '2024-01-01')
        self.assertEqual(response.json()['request']['forecast_start_date'], '2026-01-05')
        self.assertEqual(response.json()['request']['horizon_days'], 30)
        self.repo.latest_observation_date.assert_called_with('test', date(2026, 1, 5))
        self.assertIsNone(response.json()['climate'])
        self.assertEqual(self.client.get('/api/v1/regions/test/latest-analysis?as_of=2999-01-01').status_code, 422)

    def test_prediction_start_must_follow_inputs_and_model_must_honor_it(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            AnalysisRequest(region_id='test', reference_date=date(2024, 1, 1), forecast_start_date=date(2024, 1, 1))
        request = AnalysisRequest(region_id='test', reference_date=date(2024, 1, 1), forecast_start_date=date(2024, 1, 5))
        forecast = Forecast(model_kind='climate', model_version='test-only', region_id='test',
                            reference_date=date(2024, 1, 1), horizon_days=7,
                            values=[ForecastValue(variable='temperature', value=20, unit='C', aggregation='mean')])
        with self.assertRaisesRegex(ValueError, 'periodo objetivo'):
            AnalysisService._validate_forecast(forecast, request, 'climate')
        forecast.forecast_start_date = date(2024, 1, 5)
        AnalysisService._validate_forecast(forecast, request, 'climate')

    def test_unfiltered_observation_query_reads_all_database_history_with_metadata(self):
        self.repo.observation_page.return_value = {'total': 0, 'first_date': None, 'last_date': None,
                                                   'last_updated_at': None, 'items': []}
        response = self.client.get('/api/v1/regions/test/observations?limit=1000&offset=2000')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['offset'], 2000)
        self.assertEqual(response.json()['total'], 0)
        self.assertIsNone(response.json()['last_updated_at'])
        self.repo.observation_page.assert_called_once_with('test', 1000, 2000)
        self.repo.observations.assert_not_called()
        self.assertEqual(self.client.get('/api/v1/regions/test/observations?offset=-1').status_code, 422)
        self.assertEqual(self.client.get('/api/v1/regions/test/observations?start=2020-01-01').status_code, 422)
