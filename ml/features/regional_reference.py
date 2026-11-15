"""Referencia adicional con su propia emisión; nunca modifica el periodo solicitado."""

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from ml.features.daily import daily_snapshot_from_csv
from ml.features.spatial import MatchedDailyInputs, matched_inputs
from pipelines.training.snapshots import fingerprint


@dataclass(frozen=True)
class AvailableReference:
    kind: Literal["prepared_reference", "bundled_public_snapshot"]
    matched: MatchedDailyInputs


class RegionalReferenceInputs:
    def __init__(self, inputs, examples_root, *, max_age_days=7):
        self.inputs, self.examples_root = inputs, Path(examples_root)
        self.max_age_days = max_age_days

    def resolve(self, region, today):
        dates = set()
        for path in self.inputs.store.root.glob("*/*.json"):
            try:
                dates.add(date.fromisoformat(path.stem))
            except ValueError:
                continue
        for name in ("moisture", "temperature_mean"):
            for filename in ("features.csv", "inference.csv"):
                path = self.inputs.root / name / filename
                if not path.is_file():
                    continue
                with path.open(newline="", encoding="utf-8-sig") as handle:
                    for row in csv.DictReader(handle):
                        try:
                            dates.add(date.fromisoformat(row["issue_date"]))
                        except (ValueError, KeyError):
                            continue
        partial, complete = None, None
        for issue in sorted(dates, reverse=True):
            if not 0 <= (today - issue).days <= self.max_age_days:
                continue
            # La referencia complementaria puede priorizar cobertura completa;
            # el resultado principal conserva siempre la ubicación exacta.
            match = self.inputs.resolve(region, issue, prefer_exact=False)
            if match is not None and match.snapshot.soil is not None:
                available = AvailableReference("prepared_reference", match)
                if match.spatial.method == "exact":
                    return available
                if complete is None:
                    complete = available
            if match is not None and partial is None:
                partial = AvailableReference("prepared_reference", match)
        return complete or self._public_snapshot(region, today) or partial

    def _public_snapshot(self, region, today):
        manifest_path = self.examples_root / "manifest.json"
        if not manifest_path.is_file():
            return None
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("recipe_version") != "daily-direct-1-60-v1":
            return None
        issue = date.fromisoformat(manifest["issue_date"])
        if not 0 <= (today - issue).days <= self.max_age_days:
            return None
        # La fila de suelo incluye el clima del mismo punto. No combinar los
        # CSV climáticos de power_0 con smap_0 ni copiarlo al almacén operativo.
        contract = self.inputs.bundle.input_contract()
        partial = None
        for name in ("moisture", "temperature_mean"):
            entry = manifest["models"].get(name)
            if entry is None:
                continue
            path = (self.examples_root / entry["path"]).resolve()
            if not path.is_relative_to(self.examples_root.resolve()):
                raise ValueError("La referencia debe permanecer dentro del catálogo público.")
            try:
                snapshot = daily_snapshot_from_csv(
                    path,
                    region_id="public-reference-" + fingerprint(entry)[:24],
                    point_id=entry["point_id"],
                    issue_date=issue,
                    climate_features=contract.climate_features,
                    soil_features=contract.soil_features,
                )
                self.inputs.bundle.validate_inputs(snapshot)
            except (ValueError, OSError):
                continue
            if not self.inputs._in_scope(snapshot.longitude, snapshot.latitude):
                continue
            match = matched_inputs(region, snapshot)
            if match.spatial.distance_km > self.inputs.max_distance_km:
                continue
            reference = AvailableReference("bundled_public_snapshot", match)
            if snapshot.soil is not None:
                return reference
            partial = reference
        return partial
