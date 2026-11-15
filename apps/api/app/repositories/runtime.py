"""Selección explícita del almacenamiento; nunca cae silenciosamente a otra base."""

from apps.api.app.repositories.model_registry import PostgreSQLModelRegistry
from apps.api.app.repositories.mongo import MongoResultsRepository


def runtime_stores(settings, operational):
    if settings.results_backend == "postgresql":
        return operational, PostgreSQLModelRegistry(operational.database)
    if settings.results_backend == "mongodb":
        store = MongoResultsRepository(settings.mongodb_uri, settings.mongodb_database)
        return store, store
    raise ValueError("RESULTS_BACKEND debe ser postgresql o mongodb.")
