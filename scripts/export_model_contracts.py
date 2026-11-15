"""Sincroniza hashes y referencias de entrenamiento sin modificar artefactos científicos."""

import argparse
import hashlib
import json
from pathlib import Path

from ml.configs.forecasting import BASELINES, HORIZONS, UNITS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    config_path = root / "ml/configs/expanded-training.json"
    lock_path = root / "ml/configs/pretrained-bundle.json"
    config = json.loads(config_path.read_text())
    original = json.loads(config_path.read_text())
    index = json.loads((root / "ml/artifacts/forecasts/models.json").read_text())
    lock = {}
    if set(index) != {str(horizon) for horizon in HORIZONS}:
        raise ValueError("El índice no contiene los cuatro horizontes canónicos.")
    for horizon in HORIZONS:
        lock[str(horizon)] = {}
        if set(index[str(horizon)]) != set(BASELINES):
            raise ValueError("El índice no contiene las cinco salidas canónicas.")
        for name in BASELINES:
            folder = root / "ml/artifacts/forecasts" / f"{horizon}d" / name
            meta = json.loads((folder / "training.json").read_text())
            spec = config["sources"][str(horizon)][name]
            if (
                meta["model_name"] != name
                or meta["horizon_days"] != horizon
                or meta["training_pipeline"] != config["split_strategy"]
                or meta["features"] != spec["features"]
                or meta["units"] != UNITS[name]
                or meta["baseline_feature"] != BASELINES[name]
                or meta["prediction_mode"] != spec["prediction_mode"]
                or meta["baseline_scale"] != spec["baseline_scale"]
                or [row["parameters"] for row in meta["candidates"]]
                != [{**config["params"], **choice} for choice in config["candidates"]]
            ):
                raise ValueError(f"El contrato o protocolo difiere del modelo {horizon}d/{name}.")
            for filename in ("model.json", "evaluation_model.json"):
                model = json.loads((folder / filename).read_text())
                if model["learner"]["feature_names"] != spec["features"]:
                    raise ValueError(f"Columnas incompatibles en {horizon}d/{name}/{filename}.")
            lock[str(horizon)][name] = {
                filename: hashlib.sha256((folder / filename).read_bytes()).hexdigest()
                for filename in ("training.json", "model.json", "evaluation_model.json")
            }
            spec.update(
                original_source_sha256=meta["source_sha256"],
                original_selected_rounds=meta["selected_rounds"],
                reference_baseline_mae=meta["test_metrics"]["persistence"]["mae"],
            )
    if args.check:
        if json.loads(lock_path.read_text()) != lock or config != original:
            print("Contratos de modelos desactualizados: python -m scripts.export_model_contracts")
            return 1
        print(
            "Veinte modelos, columnas, parámetros, métricas de referencia y hashes sincronizados."
        )
        return 0
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")
    print("Contratos de modelos generados; revisar el diff antes de integrar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
