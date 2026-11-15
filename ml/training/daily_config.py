"""Protocolo diario ejecutable, separado de configuraciones de agregados antiguos."""

import json
from importlib.resources import files
from pathlib import Path

from ml.configs.forecasting import BASELINES, UNITS


def load_daily_training_config(path=None):
    resource = files("ml.configs").joinpath("daily-training.json")
    canonical = json.loads(resource.read_text())
    config = json.loads(Path(path).read_text()) if path else canonical
    if (
        config["schema_version"] != "daily-training-v1"
        or config["recipe_version"] != "daily-direct-1-60-v1"
        or config["split_strategy"] != "rolling_origin"
        or config["input_lag_days"] != 2
        or config["radiation_lag_days"] != 7
        or set(config["models"]) != set(BASELINES)
        or not config["candidates"]
        or min(
            config[k]
            for k in (
                "max_rounds",
                "early_stopping_rounds",
                "min_train_samples",
                "min_validation_samples",
                "min_test_samples",
                "min_spatial_locations",
                "min_new_labels",
            )
        )
        < 1
        or config["label_lag_days"] < 0
        or not 0 <= config["min_relative_improvement"] < 1
    ):
        raise ValueError("Configuración de entrenamiento diario incompatible.")
    for name, spec in config["models"].items():
        if (
            spec["features"] != canonical["models"][name]["features"]
            or spec["base_features"] != spec["features"][:-4]
            or spec["unit"] != UNITS[name]
            or spec["baseline_feature"] != BASELINES[name]
            or spec["prediction_mode"]
            != ("baseline_plus_change" if name == "moisture" else "absolute")
        ):
            raise ValueError("Cambiar entradas, unidades o semántica requiere otra receta diaria.")
    return config
