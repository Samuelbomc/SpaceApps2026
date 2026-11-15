"""Importar una fila exacta de los datasets del equipo como snapshot de inferencia."""

import argparse
from datetime import date
from pathlib import Path

from ml.features.expanded import ExpandedFeatureStore, snapshot_from_csv
from ml.inference.expanded import ExpandedModelBundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--point-id', required=True)
    parser.add_argument('--region-id', required=True)
    parser.add_argument('--issue-date', type=date.fromisoformat, required=True)
    parser.add_argument('--horizon-days', type=int, choices=(7,15,30,60), default=7)
    parser.add_argument('--output-root', type=Path, default=Path('data/features/expanded-v1'))
    parser.add_argument('--models', type=Path, default=Path('ml/artifacts'))
    parser.add_argument('--preview', action='store_true', help='Calcular y mostrar la inferencia sin escribir en las bases')
    args = parser.parse_args(argv)
    if args.issue_date >= date.today():
        parser.error('Se exige una fecha de emisión histórica completada.')
    bundle = ExpandedModelBundle(args.models)
    catalog = bundle.catalog()
    climate = next(model.features for model in catalog.models if model.model_kind == 'climate' and model.horizon_days == args.horizon_days)
    soil = next(model.features for model in catalog.models if model.model_kind == 'soil' and model.horizon_days == args.horizon_days)
    snapshot = snapshot_from_csv(args.dataset, region_id=args.region_id, point_id=args.point_id,
        issue_date=args.issue_date, climate_features=climate, soil_features=soil, horizon_days=args.horizon_days)
    if args.preview:
        print(bundle.predict(snapshot, horizon_days=args.horizon_days).model_dump_json(indent=2))
    else:
        print(ExpandedFeatureStore(args.output_root).save(snapshot))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
