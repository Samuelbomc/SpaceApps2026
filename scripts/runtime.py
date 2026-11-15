"""Composition root del worker: adapters reales se conectan aquí, fuera de HTTP."""

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


def build_jobs(
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
    operational = OperationalRepository(database)
    results, registry = runtime_stores(settings, operational)
    artifacts = ModelArtifactStore(settings.model_directory)
    config = load_training_config(settings.training_config_path)
    snapshots = (
        snapshots
        if snapshots is not None
        else ExpandedTrainingSnapshots(
            config, settings.training_data_directory, settings.dataset_directory
        )
    )
    builder = builder if builder is not None else ExpandedTrainingDatasetBuilder(config)
    trainer = trainer if trainer is not None else ExpandedXGBoostTrainer(config)
    policies = policies if policies is not None else training_policies(config)
    feature_store = ExpandedFeatureStore(settings.feature_directory)
    predictor_factory = (
        predictor_factory
        if predictor_factory is not None
        else RegisteredPredictorFactory(trainer, feature_store)
    )
    training = ModelTrainingPipeline(
        snapshots, artifacts, registry, builder=builder, trainer=trainer, policies=policies
    )
    water_rules = (
        RotationWaterRules.model_validate_json(settings.rotation_water_rules_path.read_text())
        if settings.rotation_water_rules_path
        else None
    )
    rotation_engine = (
        rotation_engine
        if rotation_engine is not None
        else ForecastRotationEngine(water_rules=water_rules)
    )
    # Sin recetas/etiquetas y reglas verificadas, los jobs informan que falta configuración.
    # No se autogenera ground truth ni se combina el catálogo público con datos privados.
    return {
        "ingestion": WeeklyIngestionJob(operational),
        "training": ModelTrainingJob(operational, training),
        "recommendations": CropRecommendationJob(
            operational,
            results,
            registry,
            artifacts,
            predictor_factory=predictor_factory,
            engine=engine,
            bundled_models=ExpandedModelBundle(settings.pretrained_model_directory),
            feature_store=feature_store,
            rotation_engine=rotation_engine,
        ),
    }
