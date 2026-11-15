"""Cinco modelos diarios; los periodos de la aplicación se derivan de sus días."""

import hashlib
import json
import math
from datetime import timedelta
from pathlib import Path

from ml.configs.forecasting import BASELINES, UNITS
from packages.contracts.api import (
    AnalysisRequest,
    AnalysisResult,
    DailyForecastDay,
    Forecast,
    ForecastValue,
)
from packages.contracts.pretrained import DailyFeatures, ModelCatalog, ModelInfo, ModelInputContract
from pipelines.training.snapshots import fingerprint

CLIMATE = ("temperature_mean", "temperature_min", "temperature_max", "precipitation")
HORIZONS = (7, 15, 30, 60)
RECIPE = "daily-direct-1-60-v1"
DERIVED = ("lead_days", "target_day_of_year_sin", "target_day_of_year_cos", "target_week_of_year")
LIMITATIONS = [
    "Modelos diarios experimentales; no equivalen a campeones publicados y validados.",
    "Los datos deben respetar la receta diaria, sus rellenos causales y contadores de calidad.",
    "POWER usa días LST; GPM y SMAP días UTC. Meteorología hasta t-2 y radiación hasta t-7.",
    "Los resultados por periodo son medias de estimaciones diarias o suma de lluvia diaria; sus métricas no son las métricas de un día aislado.",
    "Las métricas publicadas pertenecen al ajuste pre-test local; los pesos distribuidos se reajustaron con todos los pares observados.",
    "No hay evaluación prospectiva independiente ni precisión acreditada de parcela.",
]


class DailyModelBundle:
    forecast_type = "direct_daily"

    def __init__(self, root=Path("ml/artifacts"), *, registry=None, artifacts=None):
        self.root = Path(root)
        self.registry, self.artifacts = registry, artifacts
        self._predictors = {}

    def _directory(self, name, horizon=None):
        return self.root / "forecasts" / name

    def _metadata(self, horizon=None):
        lock = json.loads(
            (Path(__file__).parents[1] / "configs/pretrained-bundle.json").read_text()
        )
        records = {}
        for name in BASELINES:
            directory = self._directory(name)
            for filename, digest in lock[name].items():
                if hashlib.sha256((directory / filename).read_bytes()).hexdigest() != digest:
                    raise ValueError(
                        f"El artefacto diario {name}/{filename} no coincide con la versión integrada."
                    )
            config = json.loads((directory / "training.json").read_text())
            if (
                config["model_name"] != name
                or config["forecast_type"] != "direct_daily"
                or config["preparation_recipe_version"] != RECIPE
                or config["supported_leads"] != list(range(1, 61))
                or config["baseline_feature"] != BASELINES[name]
                or config["units"] != UNITS[name]
                or config["features"][-4:] != list(DERIVED)
            ):
                raise ValueError("La identidad o receta del artefacto diario no coincide.")
            records[name] = (config, fingerprint(lock[name])[:32])
        return records

    def supports(self, horizon):
        return self.root.is_dir() and horizon in range(1, 61)

    def input_contract(self):
        records = self._metadata()
        climate, soil = (
            records[CLIMATE[0]][0]["features"][:-4],
            records["moisture"][0]["features"][:-4],
        )
        if any(records[name][0]["features"][:-4] != climate for name in CLIMATE):
            raise ValueError("Los modelos climáticos no comparten una receta de entrada.")
        return ModelInputContract(climate_features=climate, soil_features=soil)

    def catalog(self):
        if not self.root.is_dir():
            return ModelCatalog(models=[], supported_horizons=[], limitations=LIMITATIONS)
        models = []
        for name, (config, version) in self._metadata().items():
            models.append(
                ModelInfo(
                    model_id=name,
                    model_kind="soil" if name == "moisture" else "climate",
                    version=version,
                    horizon_days=60,
                    forecast_type="direct_daily",
                    supported_leads=list(range(1, 61)),
                    unit=config["units"],
                    features=config["features"],
                    formula="smap_mean_7d + XGBoost(features, lead_days)"
                    if name == "moisture"
                    else "XGBoost(features, lead_days)",
                    evaluation_mae=config["test_metrics"]["model"]["mae"],
                    baseline_mae=config["test_metrics"]["persistence"]["mae"],
                    evaluation_note="MAE diario conjunto de leads 1–60 sobre evaluation_model.json local. Los pesos model.json incluyen el reajuste con todas las etiquetas; no tienen evaluación posterior independiente. No es un MAE del resumen de 7/15/30/60 días.",
                )
            )
        return ModelCatalog(
            models=models,
            supported_horizons=list(HORIZONS),
            limitations=LIMITATIONS,
            input_contract=self.input_contract(),
        )

    def validate_inputs(self, snapshot, *, horizon_days=7):
        if horizon_days not in range(1, 61):
            raise ValueError("Horizonte no soportado: se admiten días 1 a 60.")
        snapshot = DailyFeatures.model_validate(snapshot.model_dump())
        contract = self.input_contract()
        for kind, values, names in (
            ("clima", snapshot.climate, contract.climate_features),
            ("suelo", snapshot.soil, contract.soil_features),
        ):
            if values is None:
                continue
            missing, extra = set(names) - values.keys(), values.keys() - set(names)
            if missing or extra:
                raise ValueError(
                    f"Entradas de {kind} incompatibles: faltan {sorted(missing)}; sobran {sorted(extra)}."
                )
        return snapshot

    def predict(self, snapshot, *, horizon_days=7, analysis_region_id=None):
        import pandas as pd

        from ml.inference.forecast import ForecastPredictor

        snapshot = self.validate_inputs(snapshot, horizon_days=horizon_days)
        region_id = analysis_region_id or snapshot.region_id
        records = self._metadata()
        series, versions, validated = {}, {}, {}
        releases = {
            name: self.registry.current(f"{region_id}:daily:{name}")
            if self.registry is not None
            else None
            for name in BASELINES
        }
        for name, (config, version) in records.items():
            features = snapshot.soil if name == "moisture" else snapshot.climate
            if features is None:
                continue
            release = releases[name]
            directory = None
            if release is not None:
                if (
                    release.recipe_version != RECIPE
                    or release.validation_status != "validated"
                    or release.target_units != {name: UNITS[name]}
                    or release.trained_through > snapshot.issue_date
                ):
                    raise ValueError(
                        "El campeón diario no es compatible con el contexto temporal y la receta."
                    )
                scope = release.spatial_scope
                if scope and not (
                    scope["west"] <= snapshot.longitude <= scope["east"]
                    and scope["south"] <= snapshot.latitude <= scope["north"]
                ):
                    raise ValueError("La ubicación está fuera del alcance del campeón diario.")
                directory = self.artifacts.verify(release)
                version = release.version
            key = name, version
            if key not in self._predictors:
                self._predictors[key] = ForecastPredictor(
                    name, artifact_root=self.root / "forecasts", directory=directory
                )
            frame = pd.DataFrame(
                [
                    {**features, "issue_date": snapshot.issue_date.isoformat(), "lead_days": lead}
                    for lead in range(1, horizon_days + 1)
                ]
            )
            series[name] = [float(value) for value in self._predictors[key].predict(frame)]
            versions[name], validated[name] = version, release is not None
        start = snapshot.issue_date + timedelta(days=1)
        request = AnalysisRequest(
            region_id=region_id,
            reference_date=snapshot.observation_cutoff,
            forecast_start_date=start,
            horizon_days=horizon_days,
        )

        def values_for(names, index=None):
            return [
                ForecastValue(
                    variable="surface_soil_moisture" if name == "moisture" else name,
                    value=series[name][index]
                    if index is not None
                    else math.fsum(series[name]) / (1 if name == "precipitation" else horizon_days),
                    unit=UNITS[name],
                    statistic="sum" if name == "precipitation" else "mean",
                    aggregation="estimación diaria"
                    if index is not None
                    else (
                        f"acumulado de {horizon_days} días"
                        if name == "precipitation"
                        else f"media de {horizon_days} estimaciones diarias"
                    ),
                )
                for name in names
            ]

        def forecast(kind, names):
            component_versions = {name: versions[name] for name in names}
            return Forecast(
                model_kind=kind,
                model_version=fingerprint(component_versions)[:32],
                validation_status="validated"
                if all(validated[name] for name in names)
                else "experimental",
                region_id=region_id,
                reference_date=snapshot.observation_cutoff,
                forecast_start_date=start,
                horizon_days=horizon_days,
                values=values_for(names),
                daily=[
                    DailyForecastDay(
                        date=start + timedelta(days=index), values=values_for(names, index)
                    )
                    for index in range(horizon_days)
                ],
                component_versions=component_versions,
                limitations=LIMITATIONS,
            )

        identity = {
            "region_id": region_id,
            "snapshot": snapshot.model_dump(mode="json"),
            "horizon_days": horizon_days,
            "versions": versions,
        }
        return AnalysisResult(
            status="pending_recommendations" if "moisture" in series else "insufficient_data",
            request=request,
            analysis_id=fingerprint(identity),
            input_snapshot_id=fingerprint(snapshot.model_dump(mode="json")),
            climate=forecast("climate", CLIMATE),
            soil=forecast("soil", ["moisture"]) if "moisture" in series else None,
            messages=["Estimaciones diarias disponibles; evaluación agronómica pendiente."]
            if "moisture" in series
            else ["Clima diario disponible; faltan entradas procesadas de suelo."],
        )
