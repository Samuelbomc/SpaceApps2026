"""Importar una fila exacta de los datasets del equipo como snapshot de inferencia."""

import argparse
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ml.features.daily import daily_snapshot_from_csv
from ml.features.expanded import ExpandedFeatureStore
from ml.inference.expanded import ExpandedModelBundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--point-id", required=True)
    parser.add_argument("--region-id", required=True)
    parser.add_argument("--issue-date", type=date.fromisoformat, required=True)
    parser.add_argument("--horizon-days", type=int, choices=(7, 15, 30, 60), default=7)
    parser.add_argument("--output-root", type=Path, default=Path("data/features/daily-direct-v1"))
    parser.add_argument("--models", type=Path, default=Path("ml/artifacts"))
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Calcular y mostrar la inferencia sin escribir en las bases",
    )
    args = parser.parse_args(argv)
    if args.issue_date > datetime.now(ZoneInfo("America/Bogota")).date():
        parser.error("La fecha de emisión no puede estar en el futuro.")
    bundle = ExpandedModelBundle(args.models)
    catalog = bundle.catalog()
    climate = catalog.input_contract.climate_features
    soil = catalog.input_contract.soil_features
    snapshot = daily_snapshot_from_csv(
        args.dataset,
        region_id=args.region_id,
        point_id=args.point_id,
        issue_date=args.issue_date,
        climate_features=climate,
        soil_features=soil,
        horizon_days=args.horizon_days,
    )
    bundle.validate_inputs(snapshot, horizon_days=args.horizon_days)
    if args.preview:
        print(bundle.predict(snapshot, horizon_days=args.horizon_days).model_dump_json(indent=2))
    else:
        print(ExpandedFeatureStore(args.output_root).save(snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
