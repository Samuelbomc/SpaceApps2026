"""Geometrías y cola reales en PostgreSQL aislado; HTTP nunca ejecuta NASA/ML."""

import csv
import os
import shutil
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo
from pydantic import ValidationError

from apps.api.app.config import Settings
from apps.api.app.db.postgres import Database
from apps.api.app.main import create_app
from apps.api.app.repositories.geographic_analyses import RUN_LOCK, GeographicAnalysisRepository
from apps.api.app.repositories.operational import OperationalRepository
from apps.api.app.services.geographic_selection import selection
from ml.features.expanded import ExpandedFeatureStore
from ml.features.prepared_daily import PreparedDailyInputs
from ml.features.regional_reference import RegionalReferenceInputs
from ml.inference.daily import DailyModelBundle
from ml.recommendations.rotation import ForecastRotationEngine
from packages.contracts.geographic_analysis import GeographicAnalysisRequest
from pipelines.recommendations.geographic import GeographicAnalysisJob
from pipelines.recommendations.job import CropRecommendationJob
from scripts.migrate import migrate

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 16, 15, tzinfo=UTC)  # Reloj aislado: entradas públicas emitidas el 15.


def point(lon=-75.3, lat=6.1):
    return {"type": "Point", "coordinates": [lon, lat]}


class GeographicGeometryTests(unittest.TestCase):
    def test_coordinate_order_scope_horizon_and_nonfinite_are_validated(self):
        self.assertEqual(
            selection(GeographicAnalysisRequest(geometry=point()).geometry)[2]["coordinates"],
            [-75.3, 6.1],
        )
        for geometry in (point(6.1, -75.3), point(-76, 6), point(-75, 7)):
            with self.assertRaises(ValueError):
                selection(GeographicAnalysisRequest(geometry=geometry).geometry)
        for body in ({"geometry": point(), "horizon_days": 90}, {"geometry": point(float("nan"))}):
            with self.assertRaises(ValidationError):
                GeographicAnalysisRequest.model_validate(body)

    def test_polygon_identity_ignores_start_orientation_and_sample_stays_inside_concavity(self):
        ring = [[-75.4, 6], [-75.2, 6], [-75.2, 6.05], [-75.35, 6.05], [-75.35, 6.2], [-75.4, 6.2]]

        def derive(vertices):
            return selection(
                GeographicAnalysisRequest(
                    geometry={"type": "Polygon", "coordinates": [[*vertices, vertices[0]]]}
                ).geometry
            )

        original = derive(ring)
        self.assertEqual(original, derive(ring[2:] + ring[:2]))
        self.assertEqual(original, derive(list(reversed(ring))))
        lon, lat = original[2]["coordinates"]
        self.assertTrue(lon < -75.35 or lat < 6.05)
        self.assertEqual(original[3], "interior_reference_point")


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "Requiere PostgreSQL aislado")
class GeographicQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.environ["TEST_DATABASE_URL"]
        cls.schema = "geo_tests_" + uuid4().hex
        with psycopg.connect(cls.url, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(cls.schema)))
        cls.database = Database(make_conninfo(cls.url, options=f"-c search_path={cls.schema}"))
        migrate(cls.database)

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(cls.url, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(cls.schema)))

    def setUp(self):
        with self.database.connect() as conn:
            conn.execute("TRUNCATE geographic_analyses,geographic_areas,auth_rate_limits CASCADE")
        self.observations = OperationalRepository(self.database)
        self.queue = GeographicAnalysisRepository(self.database)
        self.client = TestClient(
            create_app(self.observations, settings=Settings(database_url=self.database.url))
        )
        self.addCleanup(self.client.close)

    def enqueue(self, geometry=None, horizon=7, today=NOW.date()):
        return self.queue.enqueue(
            GeographicAnalysisRequest(geometry=geometry or point(), horizon_days=horizon), today
        )

    def test_public_http_preserves_geometry_and_never_substitutes_reference_region(self):
        response = self.client.post(
            "/api/v1/geographic-analyses", json={"geometry": point(), "horizon_days": 30}
        )
        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body["status"], "queued")
        self.assertEqual(body["geometry"], point())
        self.assertEqual(body["sampling_point"], point())
        self.assertIsNone(body["result"])
        self.assertEqual(body["horizon_days"], 30)
        repeat = self.client.post(
            "/api/v1/geographic-analyses", json={"geometry": point(), "horizon_days": 30}
        )
        self.assertEqual(repeat.json()["request_id"], body["request_id"])
        self.assertEqual(
            self.client.get("/api/v1/geographic-analyses/" + body["request_id"]).json(), body
        )
        regions = self.client.get("/api/v1/regions").json()
        self.assertFalse(any(r["region_id"].startswith("geo-") for r in regions))
        denied = self.client.post(
            "/api/v1/geographic-analyses",
            json={"geometry": point()},
            headers={"Origin": "https://example.invalid"},
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(
            self.client.get("/api/v1/geographic-analyses/" + str(uuid4())).status_code, 404
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/geographic-analyses", json={"geometry": point(-76, 6)}
            ).status_code,
            422,
        )

    def test_concurrent_duplicates_coalesce_but_location_period_and_date_remain_distinct(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(lambda _: self.enqueue(), range(4)))
        self.assertEqual(len(set(ids)), 1)
        others = [
            self.enqueue(point(-75.2, 6.1)),
            self.enqueue(horizon=30),
            self.enqueue(today=NOW.date() + timedelta(days=1)),
        ]
        self.assertEqual(len(set([ids[0], *others])), 4)

    def test_limited_public_requests_and_body_size(self):
        with self.database.connect() as conn:
            conn.execute(
                "INSERT INTO auth_rate_limits(bucket,attempts) SELECT %s,60",
                ("geographic:" + __import__("hashlib").sha256(b"testclient").hexdigest(),),
            )
        response = self.client.post("/api/v1/geographic-analyses", json={"geometry": point()})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(
            self.client.post("/api/v1/geographic-analyses", content="x" * 65537).status_code, 413
        )

    def make_job(self, inputs=None, recommendations=None):
        inputs = inputs or Mock()
        inputs.resolve.return_value = None
        recommendations = recommendations or Mock()
        result = Mock(
            climate=None,
            soil=None,
            analysis_id="test-only",
            messages=["Faltan entradas de esta ubicación."],
        )

        # El doble conserva la misma identidad espacial/temporal que la tarea.
        def bundled(region, today, horizon, **kwargs):
            result.request = Mock(
                region_id=region["region_id"], forecast_start_date=today, horizon_days=horizon
            )
            return result

        recommendations._bundled.side_effect = bundled
        recommendations._bundled.return_value = result
        return GeographicAnalysisJob(
            self.database, self.observations, inputs, recommendations, Mock()
        )

    def test_missing_inputs_retry_only_selected_location_and_recover_interrupted_work(self):
        identifier = self.enqueue()
        job = self.make_job()
        self.assertEqual(job.run(now=NOW), "waiting_inputs")
        item = self.queue.get(identifier)
        self.assertEqual(item.attempts, 1)
        self.assertEqual(item.retry_at, NOW + timedelta(hours=1))
        expected_region = self.observations.region("geo-" + item.area_id)
        job.inputs.resolve.assert_called_with(expected_region, date(2026, 11, 15))
        job.ingestion.run.assert_called_once_with(region_id=expected_region["region_id"])
        self.assertEqual(job.run(now=NOW), "not_due")
        with self.database.connect() as conn:
            conn.execute(
                "UPDATE geographic_analyses SET status='running',retry_at=NULL WHERE request_id=%s",
                (identifier,),
            )
        self.assertEqual(job.run(now=NOW), "waiting_inputs")
        self.assertEqual(self.queue.get(identifier).attempts, 2)

    def test_transient_failure_is_durable_and_lock_prevents_duplicate_execution(self):
        identifier = self.enqueue()
        job = self.make_job()
        job.inputs.resolve.side_effect = TimeoutError()
        with self.database.connect(autocommit=True) as conn:
            conn.execute("SELECT pg_advisory_lock(%s)", (RUN_LOCK,))
            self.assertEqual(job.run(now=NOW), "locked")
            conn.execute("SELECT pg_advisory_unlock(%s)", (RUN_LOCK,))
        job.inputs.resolve.assert_not_called()
        self.assertEqual(job.run(now=NOW), "retry_scheduled")
        self.assertEqual(self.queue.get(identifier).retry_at, NOW + timedelta(seconds=60))

    def test_point_preparation_runs_before_fallback_and_retains_provider_retry_after(self):
        identifier = self.enqueue()
        job = self.make_job()
        job.preparation = Mock()
        job.preparation.prepare.return_value = {"retry_after_seconds": 7200}
        self.assertEqual(job.run(now=NOW), "waiting_inputs")
        item = self.queue.get(identifier)
        expected = self.observations.region("geo-" + item.area_id)
        job.preparation.prepare.assert_called_once_with(expected, date(2026, 11, 15))
        job.ingestion.run.assert_not_called()
        self.assertEqual(item.retry_at, NOW + timedelta(hours=2))

    def test_earliest_source_retry_can_progress_while_another_source_is_rate_limited(self):
        identifier = self.enqueue()
        job = self.make_job()
        job.preparation = Mock()
        job.preparation.prepare.return_value = {
            "retry_after_seconds": 7200,
            "next_attempt_seconds": 60,
        }
        self.assertEqual(job.run(now=NOW), "waiting_inputs")
        self.assertEqual(self.queue.get(identifier).retry_at, NOW + timedelta(seconds=60))

    def test_expired_request_does_not_receive_a_forecast_for_another_day(self):
        identifier = self.enqueue(today=NOW.date() - timedelta(days=1))
        job = self.make_job()
        self.assertEqual(job.run(now=NOW), "not_due")
        self.assertEqual(self.queue.get(identifier).status, "failed")
        job.inputs.resolve.assert_not_called()

    def test_wrong_location_result_is_never_attached_to_selected_area(self):
        identifier = self.enqueue()
        job = self.make_job()
        job.recommendations._bundled.side_effect = None
        job.recommendations._bundled.return_value.request = Mock(
            region_id="antioquia-reference", forecast_start_date=NOW.date(), horizon_days=7
        )
        self.assertEqual(job.run(now=NOW), "retry_scheduled")
        item = self.queue.get(identifier)
        self.assertEqual(item.status, "retry_scheduled")
        self.assertIsNone(item.result)

    def test_coordinate_queue_prepares_native_inputs_and_returns_five_real_model_outputs(self):
        from pipelines.ingestion.flows.model_point import ModelPointPreparation
        from tests.test_point_preparation import ISSUE, REGION, native_files, power_payload

        now = datetime(2026, 11, 15, 15, tzinfo=UTC)
        identifier = self.enqueue(point(REGION["longitude"], REGION["latitude"]), today=now.date())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native_files(root)
            store, bundle = ExpandedFeatureStore(root / "features"), DailyModelBundle()
            sources = Mock()
            sources.acquire.return_value = (power_payload(), {"POWER": {"state": "test-fixture"}})
            inputs = PreparedDailyInputs(root / "prepared", bundle, store)
            recommendations = CropRecommendationJob(
                self.observations,
                self.observations,
                Mock(),
                Mock(),
                bundled_models=bundle,
                feature_store=store,
            )
            recommendations.rotation_engine = ForecastRotationEngine()
            preparation = ModelPointPreparation(
                root, bundle, store, sources=sources, observations=self.observations
            )
            ingestion = Mock()
            job = GeographicAnalysisJob(
                self.database,
                self.observations,
                inputs,
                recommendations,
                ingestion,
                preparation=preparation,
            )
            self.assertEqual(job.run(now=now), "completed")
            item = self.queue.get(identifier, self.observations)
            expected = self.observations.region("geo-" + item.area_id)
            sources.acquire.assert_called_once()
            args = sources.acquire.call_args.args
            self.assertEqual(args[:2], (expected, ISSUE))
            self.assertEqual(item.result.spatial_match.method, "exact")
            self.assertEqual(item.result.request.forecast_start_date, now.date())
            self.assertEqual(len(item.result.climate.values) + len(item.result.soil.values), 5)
            self.assertIsNotNone(item.result.rotation_assessment)
            self.assertEqual(len(item.observations), 7)
            self.assertEqual(
                {observation.time_standard for observation in item.observations}, {"LST"}
            )
            ingestion.run.assert_not_called()

            # Otra selección puede tener clima local listo y suelo aún pendiente.
            # El resultado completo del primer punto queda como referencia separada.
            shutil.rmtree(root / "SOILGRIDS")
            other_id = self.enqueue(point(-75.31, REGION["latitude"]), today=now.date())
            other_task = self.queue.get(other_id)
            other_region = self.observations.region("geo-" + other_task.area_id)
            sources.acquire.return_value = (
                power_payload(other_region),
                {"POWER": {"state": "test-fixture"}},
            )
            job.references = RegionalReferenceInputs(inputs, root / "no-examples")

            self.assertEqual(job.run(now=now), "waiting_inputs")
            other = self.queue.get(other_id, self.observations)
            self.assertIsNotNone(other.result.climate)
            self.assertIsNone(other.result.soil)
            self.assertEqual(other.result.spatial_match.method, "exact")
            self.assertEqual(other.result.spatial_match.used_longitude, -75.31)
            self.assertEqual(other.result.request.forecast_start_date, now.date())
            self.assertEqual(len(other.result.climate.values), 4)
            self.assertIsNotNone(other.reference.result.soil)
            self.assertEqual(other.reference.result.spatial_match.method, "nearest")
            self.assertEqual(
                other.reference.result.spatial_match.used_longitude, REGION["longitude"]
            )
            self.assertEqual(len(other.observations), 7)

    def test_reference_and_local_observations_remain_available_when_other_sensors_are_missing(self):
        from pipelines.ingestion.flows.model_point import ModelPointPreparation
        from tests.test_point_preparation import REGION, power_payload

        now = datetime(2026, 11, 15, 15, tzinfo=UTC)
        identifier = self.enqueue(point(REGION["longitude"], REGION["latitude"]), today=now.date())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store, bundle = ExpandedFeatureStore(root / "features"), DailyModelBundle()
            sources = Mock()
            payload = power_payload()
            payload["raw_responses"][0]["response"]["properties"]["parameter"]["T2M"][
                "20261112"
            ] = -999
            sources.acquire.return_value = (payload, {"POWER": {"state": "downloaded"}})
            inputs = PreparedDailyInputs(root / "prepared", bundle, store)
            recommendations = CropRecommendationJob(
                self.observations,
                self.observations,
                Mock(),
                Mock(),
                bundled_models=bundle,
                feature_store=store,
                rotation_engine=ForecastRotationEngine(),
            )
            producer = ModelPointPreparation(
                root, bundle, store, sources=sources, observations=self.observations
            )

            def prepare(region, issue):
                # La referencia se puede leer antes de terminar las peticiones NASA.
                self.assertIsNotNone(self.queue.get(identifier, self.observations).reference)
                return producer.prepare(region, issue)

            job = GeographicAnalysisJob(
                self.database,
                self.observations,
                inputs,
                recommendations,
                Mock(),
                references=RegionalReferenceInputs(inputs, ROOT / "ml/examples"),
                preparation=Mock(prepare=prepare),
            )
            self.assertEqual(job.run(now=now), "waiting_inputs")
            item = self.queue.get(identifier, self.observations)
            self.assertEqual(len(item.observations), 7)
            temperature = next(row for row in item.observations if row.variable == "T2M")
            self.assertEqual(temperature.date, date(2026, 11, 11))
            self.assertEqual(temperature.value, 20.0)
            self.assertEqual(
                (temperature.latitude, temperature.longitude),
                (REGION["latitude"], REGION["longitude"]),
            )
            self.assertIsNotNone(item.reference.result.climate)
            self.assertIsNotNone(item.reference.result.soil)
            self.assertIsNotNone(item.retry_at)
            other = self.enqueue(point(-75.2, 6.2), today=now.date())
            self.assertEqual(self.queue.get(other).observations, [])

    def test_real_daily_models_complete_all_periods_for_exact_public_example_location(self):
        # Solo el entorno temporal usa el ejemplo, con su fecha/coordenadas originales.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "prepared/moisture/features.csv"
            target.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / "ml/examples/inputs/moisture.csv", target)
            with target.open() as handle:
                row = next(csv.DictReader(handle))
            geometry = point(float(row["longitude"]), float(row["latitude"]))
            store = ExpandedFeatureStore(root / "features")
            bundle = DailyModelBundle(ROOT / "ml/artifacts")
            inputs = PreparedDailyInputs(root / "prepared", bundle, store)
            recommendations = CropRecommendationJob(
                self.observations,
                self.observations,
                Mock(),
                Mock(),
                bundled_models=bundle,
                feature_store=store,
            )
            ingestion = Mock()
            job = GeographicAnalysisJob(
                self.database, self.observations, inputs, recommendations, ingestion
            )
            for horizon in (7, 15, 30, 60):
                identifier = self.enqueue(geometry, horizon)
                self.assertEqual(job.run(now=NOW), "completed")
                item = self.queue.get(identifier, self.observations)
                self.assertEqual(item.result.request.region_id, "geo-" + item.area_id)
                self.assertEqual(item.result.request.forecast_start_date, NOW.date())
                self.assertEqual(len(item.result.climate.daily), horizon)
                self.assertEqual(len(item.result.soil.daily), horizon)
                self.assertEqual(item.result.climate.validation_status, "experimental")
                rain = sum(day.values[3].value for day in item.result.climate.daily)
                self.assertAlmostEqual(item.result.climate.values[3].value, rain)
            ingestion.run.assert_not_called()

            other = {
                **self.observations.region("geo-" + item.area_id),
                "region_id": "test-other",
                "longitude": -75.3,
            }
            self.assertIsNone(inputs.prepare(other, date(2026, 11, 15)))
            self.assertIsNone(inputs.prepare(other, date(2026, 11, 14)))

            # Otro lote puede usar el mismo punto público como referencia, sin
            # reasignar sus coordenadas ni cambiar la emisión de los datos.
            selected = point(float(row["longitude"]) + 0.04, float(row["latitude"]))
            nearby_id = self.enqueue(selected, 7)
            self.assertEqual(job.run(now=NOW), "completed")
            nearby = self.queue.get(nearby_id, self.observations)
            self.assertEqual(nearby.result.request.region_id, "geo-" + nearby.area_id)
            self.assertEqual(nearby.result.spatial_match.method, "nearest")
            self.assertEqual(nearby.result.spatial_match.used_longitude, float(row["longitude"]))
            self.assertEqual(
                nearby.result.spatial_match.requested_longitude, selected["coordinates"][0]
            )
            self.assertGreater(nearby.result.spatial_match.distance_km, 4)
            self.assertEqual(nearby.result.request.forecast_start_date, NOW.date())
            self.assertEqual(nearby.result.climate.region_id, "geo-" + nearby.area_id)
            self.assertEqual(nearby.result.soil.region_id, "geo-" + nearby.area_id)
            ingestion.run.assert_not_called()

    def test_missing_current_period_returns_separate_real_reference_and_crop_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = DailyModelBundle(ROOT / "ml/artifacts")
            store = ExpandedFeatureStore(root / "features")
            inputs = PreparedDailyInputs(root / "prepared", bundle, store)
            references = RegionalReferenceInputs(inputs, ROOT / "ml/examples")
            recommendations = CropRecommendationJob(
                self.observations,
                self.observations,
                Mock(),
                Mock(),
                bundled_models=bundle,
                feature_store=store,
                rotation_engine=ForecastRotationEngine(),
            )
            ingestion = Mock()
            job = GeographicAnalysisJob(
                self.database,
                self.observations,
                inputs,
                recommendations,
                ingestion,
                references=references,
            )
            today = date(2026, 11, 15)
            identifier = self.enqueue(point(-74.80365, 5.80966), today=today)
            self.assertEqual(job.run(now=datetime(2026, 11, 15, 15, tzinfo=UTC)), "waiting_inputs")
            item = self.queue.get(identifier, self.observations)
            self.assertEqual(item.forecast_start_date, today)
            self.assertIsNone(item.result.climate)
            self.assertEqual(item.reference.kind, "bundled_public_snapshot")
            result = item.reference.result
            self.assertEqual(result.request.forecast_start_date, date(2026, 11, 16))
            self.assertEqual(result.request.region_id, "geo-reference-" + item.area_id)
            self.assertEqual(len(result.climate.values), 4)
            self.assertEqual(len(result.soil.values), 1)
            self.assertEqual(result.spatial_match.method, "nearest")
            self.assertEqual(len(result.rotation_assessment.candidates), 12)
            self.assertFalse(result.rotation_assessment.recommendation_ready)
            self.assertIsNone(
                self.observations.analysis_for_period("geo-" + item.area_id, 7, date(2026, 11, 16))
            )
            self.assertIsNone(
                inputs.resolve(self.observations.region("geo-" + item.area_id), date(2026, 11, 14))
            )
            ingestion.run.assert_not_called()
