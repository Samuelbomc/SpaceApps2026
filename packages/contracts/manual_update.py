"""Estado público de una actualización manual durable; sin datos de la sesión."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from packages.contracts.api import Contract

UpdatePhase = Literal["ingestion", "training", "recommendations"]


class UpdateStage(Contract):
    phase: UpdatePhase
    status: Literal["pending", "running", "completed", "retry_scheduled", "failed"]
    message: str
    counts: dict[str, int] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class ManualUpdate(Contract):
    request_id: UUID
    status: Literal[
        "queued", "running", "retry_scheduled", "completed", "completed_with_limitations", "failed"
    ]
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None
    retry_at: datetime | None = None
    phase: UpdatePhase
    message: str
    stages: list[UpdateStage]
