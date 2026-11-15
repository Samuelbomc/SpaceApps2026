"""Worker público de áreas, independiente del entrenamiento y de las sesiones."""

import argparse
import logging
import signal
import threading

from apps.api.app.config import Settings
from apps.api.app.db.postgres import Database
from apps.api.app.repositories.operational import OperationalRepository
from ml.features.prepared_daily import PreparedDailyInputs
from ml.features.regional_reference import RegionalReferenceInputs
from pipelines.ingestion.flows.model_point import ModelPointPreparation
from pipelines.ingestion.sources.nasa.model_inputs import ModelPointSources
from pipelines.recommendations.geographic import GeographicAnalysisJob
from scripts.migrate import migrate
from scripts.runtime import build_job


def build_geographic_job(database, settings):
    observations = OperationalRepository(database)
    recommendations = build_job("recommendations", database, settings)
    inputs = PreparedDailyInputs(
        settings.training_data_directory,
        recommendations.bundled_models,
        recommendations.feature_store,
        max_distance_km=settings.nearest_input_max_distance_km,
    )
    return GeographicAnalysisJob(
        database,
        observations,
        inputs,
        recommendations,
        build_job("ingestion", database, settings),
        references=RegionalReferenceInputs(
            inputs, settings.pretrained_model_directory.parent / "examples"
        ),
        preparation=ModelPointPreparation(
            settings.model_source_directory,
            recommendations.bundled_models,
            recommendations.feature_store,
            observations=observations,
            sources=ModelPointSources(
                settings.model_source_directory,
                max_bytes=settings.model_download_max_mb * 1024**2,
                max_lag_days=settings.source_fallback_max_lag_days,
            ),
        ),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    settings = Settings.from_env()
    database = Database(settings.database_url)
    migrate(database)
    job = build_geographic_job(database, settings)
    if args.once:
        print(job.run())
        return 0
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        try:
            state = job.run()
        except Exception as exc:
            logging.error("Cola geográfica no disponible (%s)", type(exc).__name__)
            state = "retry_scheduled"
        stop.wait(1 if state == "completed" else 5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
