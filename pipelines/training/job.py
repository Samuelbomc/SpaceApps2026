"""Actualiza snapshots y evalúa tareas regionales sin volver a consultar NASA."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


class ModelTrainingJob:
    def __init__(self, regions, pipeline):
        self.regions, self.pipeline = regions, pipeline

    def run(self):
        cutoff = datetime.now(ZoneInfo("America/Bogota")).date() - timedelta(days=1)
        outcomes = []
        for region in self.regions.regions():
            outcomes.extend(self.pipeline.run(region, cutoff))
        self.pipeline.registry.record_outcomes([outcome.model_dump(mode="json") for outcome in outcomes])
        # El estado es informativo: pending_configuration no es una caída de red.
        return {"status": "ok", "published": sum(outcome.status == "published" for outcome in outcomes),
                "outcomes": [outcome.model_dump(mode="json") for outcome in outcomes]}
