"""Configuración ejecutable versionada a partir de los veinte experimentos del equipo."""

import json
from importlib.resources import files
from pathlib import Path

from packages.contracts.training import TrainingPolicy
from pipelines.training.snapshots import fingerprint

TARGETS = ("temperature_mean", "temperature_min", "temperature_max", "precipitation", "moisture")
HORIZONS = (7, 15, 30, 60)


def load_training_config(path=None):
    text = (
        Path(path).read_text()
        if path
        else files("ml.configs").joinpath("expanded-training.json").read_text()
    )
    config = json.loads(text)
    canonical = json.loads(files("ml.configs").joinpath("expanded-training.json").read_text())
    if (
        config["schema_version"] != "expanded-training-v2"
        or config["recipe_version"] != "expanded-v1"
    ):
        raise ValueError("Configuración de entrenamiento no soportada.")
    if (
        config["input_lag_days"] != 2
        or config["label_lag_days"] < 0
        or config["split_strategy"] != "rolling_origin"
        or config["cv_train_fractions"] != [0.4, 0.55, 0.7, 0.85]
        or not config["candidates"]
        or config["max_rounds"] < 1
        or config["early_stopping_rounds"] < 1
        or config["params"]["objective"] != "reg:squarederror"
    ):
        raise ValueError("La configuración no respeta la receta de entrenamiento.")
    for horizon in HORIZONS:
        specs = config["sources"][str(horizon)]
        if set(specs) != set(TARGETS):
            raise ValueError("Faltan objetivos del entrenamiento.")
        climate_features = specs["temperature_mean"]["features"]
        for target, spec in specs.items():
            path = Path(spec["relative_path"])
            if path.is_absolute() or ".." in path.parts or path.suffix != ".csv":
                raise ValueError("Ruta de dataset no permitida.")
            if (
                len(spec["features"]) != len(set(spec["features"]))
                or spec["baseline_feature"] not in spec["features"]
            ):
                raise ValueError("Features o baseline inválidos.")
            if target != "moisture" and spec["features"] != climate_features:
                raise ValueError("El grupo climático requiere un esquema compartido.")
            if spec["prediction_mode"] != (
                "baseline_plus_change" if target == "moisture" else "absolute"
            ):
                raise ValueError("Modo de predicción incompatible.")
            if spec["baseline_scale"] != (horizon / 7 if target == "precipitation" else 1):
                raise ValueError("Escala de persistencia incompatible.")
            reference = canonical["sources"][str(horizon)][target]
            if spec["features"] != reference["features"] or spec["unit"] != reference["unit"]:
                raise ValueError("Cambiar columnas o unidades exige otra versión de receta.")
    allowed = {"max_depth", "min_child_weight", "reg_lambda"}
    if any(
        set(candidate) != allowed or any(value <= 0 for value in candidate.values())
        for candidate in config["candidates"]
    ):
        raise ValueError("Candidatos rolling-origin inválidos.")
    scope = config["spatial_scope"]
    if (
        scope["kind"] != "pooled_aoi"
        or not -180 <= scope["west"] < scope["east"] <= 180
        or not -90 <= scope["south"] < scope["north"] <= 90
    ):
        raise ValueError("Ámbito espacial de entrenamiento inválido.")
    return config


def training_policies(config):
    version = "expanded-policy-" + fingerprint(config)[:16]
    return {
        (kind, horizon): TrainingPolicy(
            version=version,
            split_strategy=config["split_strategy"],
            min_train_samples=config["min_train_samples"],
            min_validation_samples=config["min_validation_samples"],
            min_test_samples=config["min_test_samples"],
            min_new_labels=config["min_new_labels"],
            min_spatial_locations=2,
            min_relative_improvement=config["min_relative_improvement"],
            publication_allowed=config["publication_allowed"],
            # Cota de ingeniería tomada del baseline reportado; no es un umbral agronómico.
            max_mae={
                target: config["sources"][str(horizon)][target]["reference_baseline_mae"]
                for target in (TARGETS[:-1] if kind == "climate" else TARGETS[-1:])
            },
        )
        for kind in ("climate", "soil")
        for horizon in HORIZONS
    }
