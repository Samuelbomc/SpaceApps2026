"""Comprueba los datasets reales y sus particiones sin entrenar ni publicar modelos."""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ml.evaluation.promotion import chronological_partitions
from ml.training.expanded_config import HORIZONS, load_training_config
from ml.training.expanded_dataset import ExpandedTrainingDatasetBuilder, ExpandedTrainingSnapshots


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path("data/prepared"))
    parser.add_argument("--snapshot-root", type=Path, default=Path("data/datasets"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--region-id", required=True)
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--longitude", type=float, required=True)
    args = parser.parse_args(argv)
    config = load_training_config(args.config)
    snapshots = ExpandedTrainingSnapshots(config, args.source_root, args.snapshot_root)
    cutoff = datetime.now(ZoneInfo("America/Bogota")).date() - timedelta(days=1)
    snapshot = snapshots.capture(
        {"region_id": args.region_id, "latitude": args.latitude, "longitude": args.longitude},
        cutoff,
    )
    if snapshot is None:
        parser.error(
            "Faltan datasets procesados completos o la región está fuera del ámbito configurado."
        )
    builder = ExpandedTrainingDatasetBuilder(config)
    results = []
    for kind in ("climate", "soil"):
        for horizon in HORIZONS:
            dataset = builder.build(snapshot, snapshots.path(snapshot), kind, horizon)
            partitions = chronological_partitions(dataset, cutoff)
            results.append(
                {
                    "kind": kind,
                    "horizon": horizon,
                    "samples": len(dataset.samples),
                    "spatial_locations": len({s.spatial_id for s in dataset.samples}),
                    "train_validation_test": [len(p) for p in partitions],
                    "samples_per_target": {
                        name: sum(name in s.targets for s in dataset.samples)
                        for name in dataset.target_units
                    },
                    "publication_ready": dataset.publication_ready,
                    "recipe": dataset.recipe_version,
                }
            )
    print(json.dumps({"snapshot": snapshot.model_dump(mode="json"), "tasks": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
