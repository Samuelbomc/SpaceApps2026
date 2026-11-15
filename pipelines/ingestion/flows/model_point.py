"""Construcción de entradas reales para las coordenadas solicitadas, fuera de HTTP."""

import hashlib
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ml.features.recipe import features_for_point, soil_features
from packages.contracts.pretrained import DailyFeatures
from pipelines.ingestion.download import file_digest
from pipelines.ingestion.http import IngestionError, write_json
from pipelines.ingestion.sources.nasa.model_inputs import ModelPointSources
from pipelines.ingestion.storage.power import PowerParquetRepository
from pipelines.processing.cleaning.power_point import process_power_point
from pipelines.processing.geospatial.model_point import NativePointReader, power_frame


class ModelPointPreparation:
    def __init__(
        self, root, bundle, store, *, sources=None, reader=None, observations=None, archive=None
    ):
        self.root, self.bundle, self.store = Path(root), bundle, store
        self.sources = sources if sources is not None else ModelPointSources(self.root)
        self.reader = reader if reader is not None else NativePointReader()
        self.observations = observations
        self.archive = (
            archive
            if archive is not None
            else PowerParquetRepository(self.root / "observations/nasa_power_lst")
        )

    def prepare(self, region, issue_date):
        """Conserva progreso y faltantes; solo publica vectores finitos y completos."""
        key = hashlib.sha256(region["region_id"].encode()).hexdigest()
        directory = self.root / "point-inputs" / key / issue_date.isoformat()
        directory.mkdir(parents=True, exist_ok=True)
        payload, status = self.sources.acquire(region, issue_date, directory)
        report = {
            "recipe_version": "daily-direct-1-60-v1",
            "region_id": region["region_id"],
            "latitude": region["latitude"],
            "longitude": region["longitude"],
            "issue_date": issue_date.isoformat(),
            "sources": status,
            "state": "waiting_inputs",
            "retry_after_seconds": max(
                (item.get("retry_after_seconds", 0) for item in status.values()), default=0
            ),
        }
        delays = [
            item["retry_after_seconds"]
            for item in status.values()
            if item.get("state") != "downloaded" and item.get("retry_after_seconds", 0) > 0
        ]
        if delays:
            report["next_attempt_seconds"] = min(delays)
        try:
            if payload is None:
                return report
            point = payload["point"]
            if any(abs(point[field] - region[field]) > 1e-7 for field in ("latitude", "longitude")):
                raise ValueError("POWER no corresponde al punto solicitado.")
            index = pd.date_range(issue_date - timedelta(days=60), issue_date)
            power = power_frame(payload, index)
            if self.observations is not None:
                report.update(self.persist_observations(region, issue_date, payload))
            rain, smap, counts, recommended, terrain, provenance = self.reader.read(
                self.root,
                region,
                index,
                smap_root=directory / "SMAP" if (directory / "SMAP").is_dir() else None,
            )
            if not np.isfinite(terrain.get("elevation_m", np.nan)):
                report["missing"] = ["SRTM: elevación válida en el punto"]
                return report
            frame = features_for_point(power, rain, terrain["elevation_m"])
            frame["static_imputed_fields"] = 0.0
            contract = self.bundle.input_contract()
            if set(frame.columns) != set(contract.climate_features):
                raise ValueError("La receta construida no coincide con el contrato climático.")
            # soil_features conserva el orden de entrenamiento; se compara por nombre.
            soil_frame = soil_features(frame, smap, counts, recommended, terrain)
            if set(soil_frame.columns) - set(contract.soil_features):
                raise ValueError("La receta construida no coincide con el contrato de suelo.")
            for entry in provenance:
                entry["sha256"] = file_digest(Path(entry["path"]))
            report["provenance"] = provenance
            report["power_sha256"] = hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode()
            ).hexdigest()
            report["evaluated_issues"] = []
            climate_saved = False
            # La referencia admite hasta siete días desde la consulta: emisión
            # solicitada D-1 y seis cortes anteriores, todos en el mismo punto.
            for age in range(7):
                selected = issue_date - timedelta(days=age)
                climate = frame.loc[pd.Timestamp(selected)].to_dict()
                soil = soil_frame.loc[pd.Timestamp(selected)].to_dict()
                missing = sorted(key for key, value in climate.items() if not np.isfinite(value))
                missing_soil = sorted(set(contract.soil_features) - set(soil))
                missing_soil += sorted(key for key, value in soil.items() if not np.isfinite(value))
                report["evaluated_issues"].append(
                    {
                        "issue_date": selected.isoformat(),
                        "missing": missing,
                        "missing_soil": missing_soil,
                    }
                )
                if age == 0:
                    report["missing"] = missing
                    report["missing_soil"] = missing_soil
                if missing:
                    continue
                if missing_soil and climate_saved:
                    continue
                manifest = {
                    **report,
                    "requested_issue_date": issue_date.isoformat(),
                    "issue_date": selected.isoformat(),
                    "state": "climate_ready" if missing_soil else "completed",
                    "missing": missing,
                    "missing_soil": missing_soil,
                    "observation_cutoff": (selected - timedelta(days=2)).isoformat(),
                    "radiation_observation_cutoff": (selected - timedelta(days=7)).isoformat(),
                }
                digest = hashlib.sha256(
                    (
                        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
                    ).encode()
                ).hexdigest()
                snapshot = DailyFeatures(
                    region_id=region["region_id"],
                    point_id=region["region_id"],
                    latitude=region["latitude"],
                    longitude=region["longitude"],
                    issue_date=selected,
                    observation_cutoff=selected - timedelta(days=2),
                    radiation_observation_cutoff=selected - timedelta(days=7),
                    source_sha256=digest,
                    climate=climate,
                    soil=None if missing_soil else soil,
                )
                self.bundle.validate_inputs(snapshot)
                # No se cambia la emisión de una entrada antigua para hacerla actual.
                write_json(directory / f"{digest}.json", manifest)
                self.store.save(snapshot)
                climate_saved = True
                if age == 0:
                    report["state"] = "climate_ready" if missing_soil else "completed"
                    report["source_sha256"] = digest
                if not missing_soil:
                    report["latest_complete_issue_date"] = selected.isoformat()
                    report["latest_complete_source_sha256"] = digest
                    break
            return report
        except (ImportError, OSError, ValueError, KeyError, IngestionError) as exc:
            report["preparation_error"] = (
                str(exc)
                if not isinstance(exc, ImportError)
                else "Instala el extra processing para extraer NetCDF y GeoTIFF."
            )
            return report
        finally:
            write_json(directory / "status.json", report)

    def persist_observations(self, region, issue_date, payload):
        """Recupera observaciones verificadas del punto sin exigir otros sensores."""
        if self.observations is None:
            return {}
        if any(
            abs(payload["point"][field] - region[field]) > 1e-7
            for field in ("latitude", "longitude")
        ):
            raise ValueError("Las observaciones no corresponden al punto solicitado.")
        power = power_frame(payload, pd.date_range(issue_date - timedelta(days=60), issue_date))
        key = hashlib.sha256(region["region_id"].encode()).hexdigest()
        directory = self.root / "point-inputs" / key / issue_date.isoformat()
        report = {}
        raw_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        raw_path = directory / f"power-{raw_hash}.json"
        write_json(raw_path, payload)
        records = process_power_point(payload, expected_time_standard="LST")
        for record in records:
            record["raw_path"] = str(raw_path)
            if record["value"] is not None and not np.isfinite(
                power.loc[pd.Timestamp(record["date"]), record["variable"]]
            ):
                record.update(value=None, quality="out_of_range")
        try:
            self.archive.upsert(records)
            report["observation_archive"] = "saved"
        except (IngestionError, OSError):
            # El original inmutable permite reconstruir Parquet al reintentar.
            report["observation_archive"] = "pending"
        self.observations.store_recent(
            region["region_id"], records, issue_date - timedelta(days=60)
        )
        report["observations_saved"] = sum(record["value"] is not None for record in records)
        return report
