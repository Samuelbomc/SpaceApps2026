"""Import compatible; la orquestación de ingesta vive en pipelines/ingestion/flows."""

from pipelines.ingestion.flows.weekly import WeeklyIngestionJob

__all__ = ["WeeklyIngestionJob"]
