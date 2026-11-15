"""Recibe tablas diarias locales sin etiquetas, mediante coincidencia espacial/temporal exacta."""

import csv
import logging
import math
from pathlib import Path

from ml.features.daily import daily_snapshot_from_csv
from ml.features.expanded import parse_snapshot
from ml.features.spatial import distance_km, matched_inputs
from packages.contracts.models import ANTIOQUIA_ORIENTE
from packages.contracts.pretrained import DailyFeatures
from pipelines.training.snapshots import fingerprint

LOG = logging.getLogger("agrogeo.spatial_inputs")


class PreparedDailyInputs:
    def __init__(self, root, bundle, store, *, max_distance_km=200):
        self.root, self.bundle, self.store = Path(root), bundle, store
        if not math.isfinite(max_distance_km) or max_distance_km < 0:
            raise ValueError("La distancia máxima de referencia debe ser finita y no negativa.")
        self.max_distance_km = max_distance_km

    @staticmethod
    def _in_scope(lon, lat):
        box = ANTIOQUIA_ORIENTE
        return (
            math.isfinite(lon)
            and math.isfinite(lat)
            and box.west <= lon <= box.east
            and box.south <= lat <= box.north
        )

    def resolve(self, region, issue_date, *, prefer_exact=True):
        """Prioriza el punto exacto, incluso con clima sin suelo; después referencias."""
        if not self._in_scope(region["longitude"], region["latitude"]):
            raise ValueError("La ubicación solicitada está fuera del ámbito de los modelos.")
        try:
            exact = self.prepare(region, issue_date)
        except (ValueError, OSError):
            LOG.warning("La entrada exacta no es válida; se buscan referencias compatibles.")
            exact = None
        if exact is not None and (prefer_exact or exact.soil is not None):
            return matched_inputs(region, exact)
        partial = matched_inputs(region, exact) if exact is not None else None
        contract = self.bundle.input_contract()
        candidates = []
        # Solo el almacén público configurado; no se buscan CSV privados de fincas.
        for path in sorted(self.store.root.glob(f"*/{issue_date.isoformat()}.json")):
            try:
                snapshot = parse_snapshot(path.read_text())
                if not isinstance(snapshot, DailyFeatures) or snapshot.issue_date != issue_date:
                    continue
                if not self._in_scope(snapshot.longitude, snapshot.latitude):
                    continue
                distance = distance_km(
                    region["longitude"], region["latitude"], snapshot.longitude, snapshot.latitude
                )
                if distance <= self.max_distance_km:
                    candidates.append((distance, str(path), None, snapshot))
            except (ValueError, OSError):
                LOG.warning("Se omitió un snapshot público no válido.")
        for name in ("moisture", "temperature_mean"):
            for filename in ("features.csv", "inference.csv"):
                path = self.root / name / filename
                if not path.is_file():
                    continue
                seen = set()
                with path.open(newline="", encoding="utf-8-sig") as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        if row.get("issue_date") != issue_date.isoformat():
                            continue
                        try:
                            lon, lat = float(row["longitude"]), float(row["latitude"])
                            point_id = row["point_id"]
                            if not self._in_scope(lon, lat) or point_id in seen:
                                continue
                            seen.add(point_id)
                            distance = distance_km(
                                region["longitude"], region["latitude"], lon, lat
                            )
                            if distance <= self.max_distance_km:
                                candidates.append((distance, str(path), point_id, None))
                        except (TypeError, ValueError, KeyError):
                            LOG.warning("Se omitió una fila con coordenadas no válidas.")
        for _, path, point_id, snapshot in sorted(
            candidates, key=lambda item: (item[0], item[1], item[2] or "")
        ):
            try:
                if snapshot is None:
                    snapshot = daily_snapshot_from_csv(
                        path,
                        region_id="native-"
                        + fingerprint({"path": path, "point_id": point_id})[:32],
                        point_id=point_id,
                        issue_date=issue_date,
                        climate_features=contract.climate_features,
                        soil_features=contract.soil_features,
                    )
                snapshot = self.bundle.validate_inputs(snapshot)
                match = matched_inputs(region, snapshot)
                if (
                    snapshot.issue_date != issue_date
                    or not self._in_scope(snapshot.longitude, snapshot.latitude)
                    or match.spatial.distance_km > self.max_distance_km
                ):
                    continue
                if snapshot.soil is not None:
                    self.store.save(snapshot)
                    return match
                if partial is None:
                    partial = match
            except (ValueError, OSError):
                LOG.warning("Se omitió una referencia cercana incompatible con la receta.")
        return partial

    def prepare(self, region, issue_date):
        snapshot = self.store.load(region, issue_date)
        if snapshot is not None:
            snapshot = self.bundle.validate_inputs(snapshot)
            if snapshot.soil is not None:
                return snapshot
        previous = snapshot
        contract = self.bundle.input_contract()
        # Suelo contiene también todas las columnas climáticas. Nunca unir filas de
        # dos celdas distintas ni emplear ejemplos empaquetados como datos vivos.
        for name in ("moisture", "temperature_mean"):
            path = self.root / name / "features.csv"
            if not path.is_file():
                continue
            matches = set()
            with path.open(newline="", encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    if row.get("issue_date") != issue_date.isoformat():
                        continue
                    if all(
                        abs(float(row[key]) - region[key]) <= 1e-7
                        for key in ("latitude", "longitude")
                    ):
                        matches.add(row["point_id"])
            if len(matches) > 1:
                raise ValueError(
                    "Hay varias celdas para la misma ubicación y fecha; revisa el productor."
                )
            if matches:
                snapshot = daily_snapshot_from_csv(
                    path,
                    region_id=region["region_id"],
                    point_id=matches.pop(),
                    issue_date=issue_date,
                    climate_features=contract.climate_features,
                    soil_features=contract.soil_features,
                )
                self.bundle.validate_inputs(snapshot)
                self.store.save(snapshot)
                return snapshot
        return previous
