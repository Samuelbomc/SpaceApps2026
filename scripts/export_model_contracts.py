"""Verifica los cinco modelos diarios y sincroniza hashes sin alterar pesos científicos."""

import argparse
import hashlib
import json
from pathlib import Path

from ml.configs.forecasting import BASELINES, HORIZONS, UNITS
from ml.training.daily_config import load_daily_training_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    config_path = root / "ml/configs/daily-training.json"
    lock_path = root / "ml/configs/pretrained-bundle.json"
    config = load_daily_training_config()
    original = json.loads(config_path.read_text())
    index = json.loads((root / "ml/artifacts/forecasts/models.json").read_text())
    if set(index) != set(BASELINES):
        raise ValueError("El índice debe contener las cinco salidas diarias canónicas.")
    lock = {}
    for name in BASELINES:
        folder = root / "ml/artifacts/forecasts" / name
        meta = json.loads((folder / "training.json").read_text())
        spec = config["models"][name]
        if (
            meta["model_name"] != name
            or meta["forecast_type"] != "direct_daily"
            or meta["supported_leads"] != list(HORIZONS)
            or meta["preparation_recipe_version"] != config["recipe_version"]
            or meta["training_pipeline"] != config["split_strategy"]
            or meta["features"] != spec["features"]
            or meta["units"] != UNITS[name]
            or meta["baseline_feature"] != BASELINES[name]
            or meta["prediction_mode"] != spec["prediction_mode"]
            or [row["parameters"] for row in meta["candidates"]]
            != [{**config["params"], **choice} for choice in config["candidates"]]
        ):
            raise ValueError(f"Contrato o protocolo incompatible: {name}.")
        model = json.loads((folder / "model.json").read_text())
        if model["learner"]["feature_names"] != spec["features"]:
            raise ValueError(f"Orden de columnas incompatible: {name}.")
        lock[name] = {
            filename: hashlib.sha256((folder / filename).read_bytes()).hexdigest()
            for filename in ("training.json", "model.json")
        }
        spec.update(
            original_source_sha256=meta["source_sha256"],
            reference_baseline_mae=meta["test_metrics"]["persistence"]["mae"],
        )
    if args.check:
        if json.loads(lock_path.read_text()) != lock or config != original:
            print("Contratos desactualizados: python -m scripts.export_model_contracts")
            return 1
        print("Cinco modelos diarios, columnas, parámetros y hashes sincronizados.")
        return 0
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
