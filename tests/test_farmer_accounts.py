"""Integración de cuentas y archivos privados con PostgreSQL real y fixtures temporales."""

import hashlib
import hmac
import os
import tempfile
import unittest
import uuid
from datetime import date, datetime
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo

from apps.api.app.config import Settings
from apps.api.app.db.postgres import Database
from apps.api.app.main import create_app
from apps.api.app.repositories.farmers import FarmerRepository
from apps.api.app.repositories.operational import OperationalRepository
from apps.api.app.services.auth import (
    COOKIE_NAME,
    LEGACY_COOKIE_NAME,
    LEGACY_CSRF_CONTEXT,
    token_hash,
)
from apps.api.app.services.farm_datasets import MAX_FILE_BYTES, FarmDatasetService
from scripts.migrate import migrate

PASSWORD = "Una frase larga de prueba 2026"
FARM = {
    "name": "Finca de prueba",
    "municipality": "Solo fixture",
    "latitude": 6.2,
    "longitude": -75.4,
    "area_ha": 2.5,
    "soil_texture": "loam",
    "soil_ph": 6.2,
    "current_crops": ["maiz"],
    "irrigation": "rainfed",
}
CSV = b"date,variable,value,unit,crop\n2024-01-01,soil_ph,6.2,pH,\n2024-01-02,soil_moisture,0.3,m3/m3,\n"


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "Requiere PostgreSQL real")
class FarmerAccountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.environ["TEST_DATABASE_URL"]
        cls.schema = "farm_tests_" + uuid.uuid4().hex
        with psycopg.connect(cls.url, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(cls.schema)))
        cls.db = Database(make_conninfo(cls.url, options=f"-c search_path={cls.schema}"))
        migrate(cls.db)

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(cls.url, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(cls.schema)))

    def setUp(self):
        with self.db.connect() as conn:
            conn.execute("TRUNCATE farmer_users CASCADE")
            conn.execute("TRUNCATE auth_rate_limits")
        self.folder = tempfile.TemporaryDirectory(prefix="farm-files-")
        self.addCleanup(self.folder.cleanup)
        self.settings = Settings(
            database_url=self.db.url, farm_upload_directory=Path(self.folder.name)
        )
        self.app = create_app(OperationalRepository(self.db), settings=self.settings)
        self.client = TestClient(self.app)

    def register(self, client=None, email="farmer@example.com"):
        client = client or self.client
        response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "display_name": "Persona de prueba", "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json(), response

    def farm(self, session, client=None):
        response = (client or self.client).post(
            "/api/v1/farms", json=FARM, headers={"X-CSRF-Token": session["csrf_token"]}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def upload(self, session, farm, content=CSV, filename="mediciones.csv", client=None):
        return (client or self.client).post(
            f"/api/v1/farms/{farm['farm_id']}/datasets",
            headers={"X-CSRF-Token": session["csrf_token"]},
            files={"file": (filename, content, "text/csv")},
        )

    def test_register_cookie_private_hash_login_and_revocation(self):
        session, response = self.register(email="FARMER@example.com")
        self.assertEqual(session["user"]["email"], "farmer@example.com")
        header = response.headers["set-cookie"].lower()
        self.assertIn("httponly", header)
        self.assertIn("samesite=lax", header)
        token = self.client.cookies[COOKIE_NAME]
        with self.db.connect() as conn:
            user = conn.execute("SELECT * FROM farmer_users").fetchone()
            stored = conn.execute("SELECT token_hash FROM farmer_sessions").fetchone()["token_hash"]
        self.assertNotEqual(user["password_hash"], PASSWORD)
        self.assertEqual(stored, token_hash(token))
        self.assertNotEqual(stored, token)
        self.assertNotIn("password", self.client.get("/api/v1/auth/me").text)
        self.assertEqual(
            self.client.post(
                "/api/v1/auth/logout", headers={"X-CSRF-Token": session["csrf_token"]}
            ).status_code,
            204,
        )
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        self.client.cookies.set(COOKIE_NAME, token)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        self.client.cookies.clear()
        login = self.client.post(
            "/api/v1/auth/login", json={"email": "farmer@example.com", "password": PASSWORD}
        )
        self.assertEqual(login.status_code, 200)

    def test_legacy_session_migrates_without_extending_expiry_or_losing_farms(self):
        session, _ = self.register()
        farm = self.farm(session)
        token = self.client.cookies[COOKIE_NAME]
        legacy_csrf = hmac.new(token.encode(), LEGACY_CSRF_CONTEXT, hashlib.sha256).hexdigest()
        self.client.cookies.clear()
        self.client.cookies.set(LEGACY_COOKIE_NAME, token, domain="testserver.local", path="/")
        # Una pestaña abierta antes del cambio puede seguir escribiendo con su CSRF.
        self.farm({"csrf_token": legacy_csrf})
        refreshed = self.client.get("/api/v1/auth/me")
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        self.assertEqual(
            datetime.fromisoformat(refreshed.json()["expires_at"]),
            datetime.fromisoformat(session["expires_at"]),
        )
        self.assertEqual(refreshed.json()["user"], session["user"])
        self.assertEqual(self.client.cookies[COOKIE_NAME], token)
        self.assertNotIn(LEGACY_COOKIE_NAME, self.client.cookies)
        self.assertNotEqual(refreshed.json()["csrf_token"], legacy_csrf)
        self.assertEqual(self.client.get(f"/api/v1/farms/{farm['farm_id']}").status_code, 200)
        # El CSRF previo sigue siendo válido durante el despliegue gradual.
        self.assertEqual(
            self.client.post(
                "/api/v1/auth/logout", headers={"X-CSRF-Token": legacy_csrf}
            ).status_code,
            204,
        )
        self.assertNotIn(COOKIE_NAME, self.client.cookies)
        self.client.cookies.set(LEGACY_COOKIE_NAME, token)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_current_cookie_has_precedence_over_legacy_and_legacy_logout_revokes(self):
        _, _ = self.register()
        token = self.client.cookies[COOKIE_NAME]
        legacy_csrf = hmac.new(token.encode(), LEGACY_CSRF_CONTEXT, hashlib.sha256).hexdigest()
        self.client.cookies.clear()
        self.client.cookies.set(LEGACY_COOKIE_NAME, token, domain="testserver.local", path="/")
        self.client.cookies.set(COOKIE_NAME, "invalid", domain="testserver.local", path="/")
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        self.client.cookies.delete(COOKIE_NAME)
        self.assertEqual(
            self.client.post(
                "/api/v1/auth/logout", headers={"X-CSRF-Token": legacy_csrf}
            ).status_code,
            204,
        )
        self.assertNotIn(LEGACY_COOKIE_NAME, self.client.cookies)
        self.client.cookies.set(COOKIE_NAME, token)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_polygon_vertices_survive_private_create_reload_and_edit(self):
        session, _ = self.register()
        geometry = {
            "type": "Polygon",
            "coordinates": [[[-75.41, 6.19], [-75.39, 6.19], [-75.395, 6.21], [-75.41, 6.19]]],
        }
        response = self.client.post(
            "/api/v1/farms",
            json={**FARM, "geometry": geometry},
            headers={"X-CSRF-Token": session["csrf_token"]},
        )
        self.assertEqual(response.status_code, 201, response.text)
        saved = response.json()
        self.assertEqual(saved["geometry"], geometry)
        loaded = self.client.get(f"/api/v1/farms/{saved['farm_id']}").json()
        self.assertEqual(loaded["geometry"], geometry)
        edited = self.client.put(
            f"/api/v1/farms/{saved['farm_id']}?revision=1",
            json={**FARM, "geometry": geometry, "name": "Nuevo nombre"},
            headers={"X-CSRF-Token": session["csrf_token"]},
        )
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(edited.json()["geometry"], geometry)
        broken = {
            "type": "Polygon",
            "coordinates": [
                [[-75.41, 6.19], [-75.39, 6.21], [-75.41, 6.21], [-75.39, 6.19], [-75.41, 6.19]]
            ],
        }
        self.assertEqual(
            self.client.post(
                "/api/v1/farms",
                json={**FARM, "geometry": broken},
                headers={"X-CSRF-Token": session["csrf_token"]},
            ).status_code,
            422,
        )

    def test_csrf_cross_origin_and_expired_sessions_are_rejected(self):
        session, _ = self.register()
        self.assertEqual(self.client.post("/api/v1/farms", json=FARM).status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/v1/farms", json=FARM, headers={"X-CSRF-Token": "wrong"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/farms",
                json=FARM,
                headers={
                    "X-CSRF-Token": session["csrf_token"],
                    "Origin": "https://attacker.invalid",
                },
            ).status_code,
            403,
        )
        with self.db.connect() as conn:
            conn.execute("UPDATE farmer_sessions SET expires_at=now()-interval '1 second'")
        self.assertEqual(self.client.get("/api/v1/farms").status_code, 401)

    def test_owner_can_edit_with_revision_but_other_account_cannot_read_or_write(self):
        session, _ = self.register()
        farm = self.farm(session)
        other = TestClient(self.app)
        second, _ = self.register(other, "second@example.com")
        self.assertEqual(other.get("/api/v1/farms").json(), [])
        self.assertEqual(other.get(f"/api/v1/farms/{farm['farm_id']}").status_code, 404)
        self.assertEqual(
            other.put(
                f"/api/v1/farms/{farm['farm_id']}?revision=1",
                json=FARM,
                headers={"X-CSRF-Token": second["csrf_token"]},
            ).status_code,
            404,
        )
        response = self.client.put(
            f"/api/v1/farms/{farm['farm_id']}?revision=1",
            json={**FARM, "name": "Actualizada"},
            headers={"X-CSRF-Token": session["csrf_token"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["revision"], 2)
        stale = self.client.put(
            f"/api/v1/farms/{farm['farm_id']}?revision=1",
            json=FARM,
            headers={"X-CSRF-Token": session["csrf_token"]},
        )
        self.assertEqual(stale.status_code, 409)

    def test_csv_upload_persists_private_files_and_is_idempotent(self):
        session, _ = self.register()
        farm = self.farm(session)
        response = self.upload(session, farm)
        self.assertEqual(response.status_code, 201, response.text)
        dataset = response.json()["dataset"]
        self.assertEqual(dataset["row_count"], 2)
        self.assertNotIn("storage_key", dataset)
        self.assertEqual(len(list(Path(self.folder.name).rglob("*.csv"))), 1)
        self.assertEqual(self.upload(session, farm).status_code, 200)
        self.assertEqual(self.upload(session, farm).json()["duplicate"], True)
        self.assertEqual(
            len(self.client.get(f"/api/v1/farms/{farm['farm_id']}/datasets").json()), 1
        )
        path = f"/api/v1/farms/{farm['farm_id']}/datasets/{dataset['dataset_id']}/download"
        self.assertEqual(self.client.get(path).content, CSV)
        self.assertEqual(TestClient(self.app).get(path).status_code, 401)
        other = TestClient(self.app)
        other_session, _ = self.register(other, "second@example.com")
        self.assertEqual(other.get(path).status_code, 404)
        self.assertEqual(
            other.delete(
                path.removesuffix("/download"),
                headers={"X-CSRF-Token": other_session["csrf_token"]},
            ).status_code,
            404,
        )
        self.assertEqual(self.upload(other_session, farm, client=other).status_code, 404)
        repository = FarmerRepository(self.db)
        bundle = FarmDatasetService(repository, Path(self.folder.name)).bundle(
            uuid.UUID(session["user"]["user_id"]), uuid.UUID(farm["farm_id"]), date(2024, 1, 1)
        )
        self.assertEqual(bundle.context.observation_count, 1)
        self.assertFalse(bundle.context.model_ready)
        self.assertEqual(bundle.observations[0].source, "LOCAL_FARM")
        self.assertEqual(bundle.observations[0].quality, "format_validated_unverified")

    def test_validation_failure_does_not_create_dataset_or_local_file(self):
        session, _ = self.register()
        farm = self.farm(session)
        content = (
            b"date,variable,value,unit\n2024-01-01,soil_ph,6,pH\n2024-01-02,soil_moisture,30,%\n"
        )
        self.assertEqual(self.upload(session, farm, content).status_code, 422)
        self.assertEqual(self.upload(session, farm, filename="file.exe").status_code, 422)
        self.assertEqual(self.client.get(f"/api/v1/farms/{farm['farm_id']}/datasets").json(), [])
        self.assertEqual(list(Path(self.folder.name).rglob("*.csv")), [])
        with self.db.connect() as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) AS n FROM farm_observations").fetchone()["n"], 0
            )

    def test_upload_size_limit_and_anonymous_resource_protection(self):
        self.assertEqual(self.client.get("/api/v1/farms").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/farms/catalog").status_code, 401)
        session, _ = self.register()
        farm = self.farm(session)
        response = self.upload(session, farm, b"x" * (MAX_FILE_BYTES + 1))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(list(Path(self.folder.name).rglob("*.csv")), [])

    def test_overlapping_files_are_flagged_and_deleted_data_leave_model_context(self):
        session, _ = self.register()
        farm = self.farm(session)
        self.upload(session, farm)
        second = self.upload(
            session, farm, b"date,variable,value,unit\n2024-01-01,soil_ph,7,pH\n"
        ).json()["dataset"]
        path = f"/api/v1/farms/{farm['farm_id']}"
        context = self.client.get(path + "/model-context").json()
        self.assertEqual(context["conflict_count"], 1)
        self.assertEqual(context["observation_count"], 3)
        old_hash = context["snapshot_id"]
        removed = self.client.delete(
            path + f"/datasets/{second['dataset_id']}",
            headers={"X-CSRF-Token": session["csrf_token"]},
        )
        self.assertEqual(removed.status_code, 204)
        current = self.client.get(path + "/model-context").json()
        self.assertNotEqual(old_hash, current["snapshot_id"])
        self.assertEqual(current["observation_count"], 2)
        self.assertEqual(current["conflict_count"], 0)
        self.assertEqual(len(list(Path(self.folder.name).rglob("*.csv"))), 1)

    def test_invalid_password_is_not_echoed_and_bruteforce_is_limited(self):
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "farmer@example.com",
                "display_name": "Test",
                "password": "short-private",
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("short-private", response.text)
        results = [
            self.client.post(
                "/api/v1/auth/login", json={"email": "unknown@example.com", "password": PASSWORD}
            ).status_code
            for _ in range(11)
        ]
        self.assertEqual(results[:10], [401] * 10)
        self.assertEqual(results[-1], 429)

    def test_changed_original_file_is_not_served_as_the_uploaded_version(self):
        session, _ = self.register()
        farm = self.farm(session)
        dataset = self.upload(session, farm).json()["dataset"]
        path = next(Path(self.folder.name).rglob("*.csv"))
        path.write_bytes(b"changed outside the application")
        response = self.client.get(
            f"/api/v1/farms/{farm['farm_id']}/datasets/{dataset['dataset_id']}/download"
        )
        self.assertEqual(response.status_code, 409)

    def test_secure_cookie_setting_and_request_limits_before_validation(self):
        secure_app = create_app(
            OperationalRepository(self.db),
            settings=Settings(
                database_url=self.db.url,
                auth_cookie_secure=True,
                farm_upload_directory=Path(self.folder.name),
            ),
        )
        secure_client = TestClient(secure_app, base_url="https://testserver")
        session, response = self.register(secure_client)
        self.assertIn("; secure", response.headers["set-cookie"].lower())
        self.assertEqual(secure_client.get("/api/v1/auth/me").status_code, 200)
        too_large = self.client.post(
            "/api/v1/auth/login", content=b"x" * 65537, headers={"Content-Type": "application/json"}
        )
        self.assertEqual(too_large.status_code, 413)
