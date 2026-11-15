"""Composition root del worker: adapters reales se conectan aquí, fuera de HTTP."""

from apps.api.app.repositories.operational import OperationalRepository
from apps.api.app.repositories.runtime import runtime_stores
from ml.training.artifacts import ModelArtifactStore
from ml.inference.expanded import ExpandedModelBundle
from ml.features.expanded import ExpandedFeatureStore
from ml.recommendations.rotation import ForecastRotationEngine
from packages.contracts.rotation import RotationWaterRules
from pipelines.ingestion.flows.weekly import WeeklyIngestionJob
from pipelines.recommendations.job import CropRecommendationJob
from pipelines.training.job import ModelTrainingJob
from pipelines.training.pipeline import ModelTrainingPipeline
from pipelines.training.snapshots import HistoricalSnapshotStore


def build_jobs(database, settings, *, builder=None, trainer=None, policies=None, predictor_factory=None, engine=None, rotation_engine=None):
    operational = OperationalRepository(database)
    results, registry = runtime_stores(settings, operational)
    artifacts = ModelArtifactStore(settings.model_directory)
    training = ModelTrainingPipeline(HistoricalSnapshotStore(root=settings.dataset_directory), artifacts, registry,
                                     builder=builder, trainer=trainer, policies=policies)
    water_rules = RotationWaterRules.model_validate_json(settings.rotation_water_rules_path.read_text()) if settings.rotation_water_rules_path else None
    rotation_engine = rotation_engine if rotation_engine is not None else ForecastRotationEngine(water_rules=water_rules)
    # Sin recetas/etiquetas y reglas verificadas, los jobs informan que falta configuración.
    # No se autogenera ground truth ni se combina el catálogo público con datos privados.
    return {"ingestion": WeeklyIngestionJob(operational),
            "training": ModelTrainingJob(operational, training),
            "recommendations": CropRecommendationJob(operational, results, registry, artifacts,
                                                      predictor_factory=predictor_factory, engine=engine,
                                                      bundled_models=ExpandedModelBundle(settings.pretrained_model_directory),
                                                      feature_store=ExpandedFeatureStore(settings.feature_directory),
                                                      rotation_engine=rotation_engine)}
