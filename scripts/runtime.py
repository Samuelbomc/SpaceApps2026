"""Composition root del worker: construye solo las dependencias del job solicitado."""

from apps.api.app.repositories.operational import OperationalRepository
from apps.api.app.repositories.runtime import runtime_stores
from ml.features.expanded import ExpandedFeatureStore
from ml.inference.expanded import ExpandedModelBundle
from ml.inference.registered import RegisteredPredictorFactory
from ml.recommendations.rotation import ForecastRotationEngine
from ml.training.artifacts import ModelArtifactStore
from ml.training.expanded_config import load_training_config, training_policies
from ml.training.expanded_dataset import ExpandedTrainingDatasetBuilder, ExpandedTrainingSnapshots
from ml.training.xgboost import ExpandedXGBoostTrainer
from packages.contracts.rotation import RotationWaterRules
from pipelines.ingestion.flows.weekly import WeeklyIngestionJob
from pipelines.recommendations.job import CropRecommendationJob
from pipelines.training.job import ModelTrainingJob
from pipelines.training.pipeline import ModelTrainingPipeline

JOB_NAMES = ("ingestion", "training", "recommendations")


def build_job(
    name,
    database,
    settings,
    *,
    builder=None,
    trainer=None,
    policies=None,
    predictor_factory=None,
    engine=None,
    rotation_engine=None,
    snapshots=None,
):
    if name not in JOB_NAMES:
        raise ValueError("Job no soportado.")
    operational = OperationalRepository(database)
    if name == "ingestion":
        return WeeklyIngestionJob(operational)

    results, registry = runtime_stores(settings, operational)
    artifacts = ModelArtifactStore(settings.model_directory)
    if name == "training":
        config = load_training_config(settings.training_config_path)
        snapshots = (
            snapshots
            if snapshots is not None
            else ExpandedTrainingSnapshots(
                config, settings.training_data_directory, settings.dataset_directory
            )
        )
        pipeline = ModelTrainingPipeline(
            snapshots,
            artifacts,
            registry,
            builder=builder if builder is not None else ExpandedTrainingDatasetBuilder(config),
            trainer=trainer if trainer is not None else ExpandedXGBoostTrainer(config),
            policies=policies if policies is not None else training_policies(config),
        )
        return ModelTrainingJob(operational, pipeline)

    feature_store = ExpandedFeatureStore(settings.feature_directory)
    if predictor_factory is None:
        # La carga valida la receta del artefacto publicado. No necesita el override
        # de hiperparámetros/datasets utilizado para ajustar candidatos nuevos.
        loader = trainer if trainer is not None else ExpandedXGBoostTrainer(load_training_config())
        predictor_factory = RegisteredPredictorFactory(loader, feature_store)
    if rotation_engine is None:
        water_rules = (
            RotationWaterRules.model_validate_json(settings.rotation_water_rules_path.read_text())
            if settings.rotation_water_rules_path
            else None
        )
        rotation_engine = ForecastRotationEngine(water_rules=water_rules)
    return CropRecommendationJob(
        operational,
        results,
        registry,
        artifacts,
        predictor_factory=predictor_factory,
        engine=engine,
        bundled_models=ExpandedModelBundle(settings.pretrained_model_directory),
        feature_store=feature_store,
        rotation_engine=rotation_engine,
    )


def build_jobs(database, settings, **overrides):
    """Composición completa para consumidores que necesitan los tres jobs."""
    return {name: build_job(name, database, settings, **overrides) for name in JOB_NAMES}
