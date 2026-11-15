"""Resultados, catálogo agronómico y registro ML. Nunca contiene contraseñas o CSV privados."""

from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache

from packages.contracts.training import ModelRelease


class DocumentStoreUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=8)
def mongo_client(uri):
    try:
        from pymongo import MongoClient
    except ImportError:
        raise DocumentStoreUnavailable("Instala el extra mongo para usar el repositorio de resultados.") from None
    return MongoClient(uri, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000, tz_aware=True)


class MongoResultsRepository:
    def __init__(self, uri, database_name):
        self.uri, self.database_name = uri, database_name
        self._indexed = False

    @contextmanager
    def _database(self):
        try:
            from pymongo.errors import PyMongoError
        except ImportError:
            raise DocumentStoreUnavailable("Instala el extra mongo para usar el repositorio de resultados.") from None
        try:
            database = mongo_client(self.uri)[self.database_name]
            if not self._indexed:
                database.analyses.create_index([("region_id", 1), ("created_at", -1)])
                database.analyses.create_index([("request_key", 1), ("created_at", -1)])
                self._indexed = True
            yield database
        except PyMongoError:
            raise DocumentStoreUnavailable("MongoDB no está disponible; se conserva el estado anterior y el job debe reintentarse.") from None

    def current(self, slot):
        with self._database() as db:
            row = db.published_models.find_one({"_id": slot})
            return ModelRelease.model_validate(row["body"]) if row else None

    def published_models(self):
        with self._database() as db:
            return [ModelRelease.model_validate(row["body"]) for row in db.published_models.find().sort("_id", 1)]

    def attempt(self, fingerprint):
        with self._database() as db:
            row = db.training_attempts.find_one({"_id": fingerprint})
            return row["body"] if row else None

    def record_attempt(self, fingerprint, body):
        with self._database() as db:
            db.training_attempts.update_one({"_id": fingerprint}, {"$setOnInsert": {"body": body}}, upsert=True)

    def publish(self, release, expected_version):
        from pymongo.errors import DuplicateKeyError
        body = release.model_dump(mode="json")
        with self._database() as db:
            db.model_versions.update_one({"_id": release.version}, {"$setOnInsert": {"body": body}}, upsert=True)
            if expected_version is None:
                try:
                    db.published_models.insert_one({"_id": release.slot, "body": body})
                    return True
                except DuplicateKeyError:
                    return False
            updated = db.published_models.update_one({"_id": release.slot, "body.version": expected_version}, {"$set": {"body": body}})
            return updated.matched_count == 1

    def record_outcomes(self, outcomes):
        with self._database() as db:
            db.pipeline_status.replace_one({"_id": "training"}, {"_id": "training", "outcomes": outcomes}, upsert=True)

    def recent_training(self):
        with self._database() as db:
            return (db.pipeline_status.find_one({"_id": "training"}) or {}).get("outcomes", [])

    @staticmethod
    def _request_key(request):
        from pipelines.training.snapshots import fingerprint
        return fingerprint(request.model_dump(mode="json"))

    def save_analysis(self, analysis):
        with self._database() as db:
            db.analyses.update_one({"_id": analysis.analysis_id}, {"$setOnInsert": {
                "region_id": analysis.request.region_id, "request_key": self._request_key(analysis.request),
                "body": analysis.model_dump(mode="json"), "created_at": datetime.now(timezone.utc)}}, upsert=True)

    def analysis_for(self, request):
        with self._database() as db:
            row = db.analyses.find_one({"request_key": self._request_key(request)}, sort=[("created_at", -1)])
            return row["body"] if row else None

    def analysis_for_period(self, region_id, horizon, target_start):
        with self._database() as db:
            query = {'region_id': region_id, 'body.request.horizon_days': horizon,
                     'body.request.forecast_start_date': target_start.isoformat()}
            row = db.analyses.find_one({**query, 'body.climate': {'$ne': None}}, sort=[('created_at', -1)])
            row = row or db.analyses.find_one(query, sort=[('created_at', -1)])
            return row['body'] if row else None

    def analyses(self, region_id, limit=10):
        with self._database() as db:
            return [row["body"] for row in db.analyses.find({"region_id": region_id}).sort("created_at", -1).limit(limit)]

    def catalog(self):
        with self._database() as db:
            return [row["body"] for row in db.crop_catalog.find({"active": True}).sort("_id", 1)]

    def save_catalog_entry(self, key, body, *, active=False):
        # Publicación explícita después de revisión agronómica; no hay cultivos ficticios precargados.
        from pipelines.training.snapshots import fingerprint
        with self._database() as db:
            db.crop_catalog_versions.update_one({"_id": fingerprint({"key": key, "body": body})},
                {"$setOnInsert": {"crop_key": key, "body": body}}, upsert=True)
            db.crop_catalog.replace_one({"_id": key}, {"_id": key, "body": body, "active": active}, upsert=True)
