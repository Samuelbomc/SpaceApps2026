"""Espera persistente por proveedor; las pausas no bloquean el worker."""

import json
import math
import random
from datetime import datetime, timedelta

from pipelines.ingestion.http import write_json


class SourceRecovery:
    def __init__(self, path, context, now, *, jitter=random.uniform, clock=None):
        self.path, self.context, self.jitter = path, context, jitter
        self.clock = clock if clock is not None else lambda: now
        try:
            body = json.loads(path.read_text())
            self.entries = body["sources"] if body["context"] == context else {}
            if not isinstance(self.entries, dict):
                self.entries = {}
        except (OSError, ValueError, KeyError, TypeError):
            self.entries = {}

    @property
    def now(self):
        return self.clock()

    def entry(self, name):
        entry = self.entries.get(name, {})
        try:
            due = datetime.fromisoformat(entry["next_attempt_at"])
            if due.tzinfo is None or not isinstance(entry["status"], dict):
                return {}
            if entry["status"].get("state") not in (
                "downloaded",
                "unavailable",
                "subset_pending",
                "requires_earthdata",
            ):
                return {}
            if not isinstance(entry["attempts"], int) or entry["attempts"] < 0:
                return {}
            return entry
        except (ValueError, KeyError, TypeError):
            return {}

    def due(self, name, *, access_configured=False):
        entry = self.entry(name)
        if not entry or (
            access_configured and entry["status"].get("state") == "requires_earthdata"
        ):
            return True
        return self.now >= datetime.fromisoformat(entry["next_attempt_at"])

    def status(self, name):
        entry = self.entry(name)
        if not entry:
            return {"state": "unavailable", "retry_after_seconds": 60}
        delay = max(
            0,
            math.ceil(
                (datetime.fromisoformat(entry["next_attempt_at"]) - self.now).total_seconds()
            ),
        )
        return {
            **entry["status"],
            "attempts": entry["attempts"],
            "next_attempt_at": entry["next_attempt_at"],
            "retry_after_seconds": delay,
        }

    def record(self, name, status, **metadata):
        previous = self.entry(name)
        attempts = previous.get("attempts", 0) + 1 if status["state"] == "unavailable" else 0
        if attempts:
            base = min(3600, 60 * 2 ** min(attempts - 1, 6))
            delay = min(3600, base + self.jitter(0, base * 0.25))
        else:
            delay = {"downloaded": 900, "subset_pending": 300, "requires_earthdata": 3600}.get(
                status["state"], 3600
            )
        delay = max(delay, status.get("retry_after_seconds", 0))
        self.entries[name] = {
            **previous,
            **metadata,
            "status": status,
            "attempts": attempts,
            "next_attempt_at": (self.now + timedelta(seconds=delay)).isoformat(),
        }
        write_json(self.path, {"context": self.context, "sources": self.entries})
        return self.status(name)
