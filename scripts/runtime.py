"""Composition root del worker: adapters reales se conectan aquí, fuera de HTTP."""

from apps.api.app.repositories.operational import OperationalRepository
from apps.api.app.repositories.runtime import runtime_stores
from ml.training.artifacts import ModelArtifactStore
from pipelines.ingestion.flows.weekly import WeeklyIngestionJob
from pipelines.recommendations.job import CropRecommendationJob
from pipelines.training.job import ModelTrainingJob
from pipelines.training.pipeline import ModelTrainingPipeline
from pipelines.training.snapshots import HistoricalSnapshotStore


def build_jobs(database, settings, *, builder=None, trainer=None, policies=None, predictor_factory=None, engine=None):
    operational = OperationalRepository(database)
    results, registry = runtime_stores(settings, operational)
    artifacts = ModelArtifactStore(settings.model_directory)
    training = ModelTrainingPipeline(HistoricalSnapshotStore(root=settings.dataset_directory), artifacts, registry,
                                     builder=builder, trainer=trainer, policies=policies)
    # Sin recetas/etiquetas y reglas verificadas, los jobs informan que falta configuración.
    # No se autogenera ground truth ni se combina el catálogo público con datos privados.
    return {"ingestion": WeeklyIngestionJob(operational),
            "training": ModelTrainingJob(operational, training),
            "recommendations": CropRecommendationJob(operational, results, registry, artifacts,
                                                      predictor_factory=predictor_factory, engine=engine)}
