"""Snapshots procesados; nunca sustituye datos faltantes por filas históricas."""

import csv
import hashlib
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

from packages.contracts.pretrained import ExpandedFeatures
from pipelines.training.snapshots import fingerprint


class ExpandedFeatureStore:
    def __init__(self, root=Path('data/features/expanded-v1')):
        self.root = Path(root)

    def path(self, region_id, issue_date):
        key = hashlib.sha256(region_id.encode()).hexdigest()
        return self.root / key / f'{issue_date.isoformat()}.json'

    def save(self, snapshot: ExpandedFeatures):
        target = self.path(snapshot.region_id, snapshot.issue_date)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(snapshot.model_dump_json(indent=2))
        try:
            archive = self.root / 'versions' / f'{fingerprint(snapshot.model_dump(mode="json"))}.json'
            archive.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(temporary, archive)
            except FileExistsError:
                if ExpandedFeatures.model_validate_json(archive.read_text()) != snapshot:
                    raise ValueError('El snapshot de inferencia archivado fue alterado.')
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    def load(self, region, issue_date):
        path = self.path(region['region_id'], issue_date)
        if not path.is_file():
            return None
        snapshot = ExpandedFeatures.model_validate_json(path.read_text())
        if snapshot.region_id != region['region_id'] or snapshot.issue_date != issue_date:
            raise ValueError('El snapshot no corresponde a la región o fecha solicitada.')
        if any(abs(getattr(snapshot, key) - region[key]) > 1e-7 for key in ('longitude', 'latitude')):
            raise ValueError('Las coordenadas del snapshot no corresponden a la región.')
        return snapshot


def snapshot_from_csv(path, *, region_id, point_id, issue_date, climate_features, soil_features, horizon_days=7):
    """Importa una fila exacta; excluye target y cualquier observación futura."""
    path = Path(path)
    found = None
    with path.open(newline='', encoding='utf-8-sig') as handle:
        for row in csv.DictReader(handle):
            if row['point_id'] == point_id and row['issue_date'] == issue_date.isoformat():
                if found is not None:
                    raise ValueError('La fila de entrada está duplicada.')
                found = row
    if found is None:
        raise ValueError('No hay datos para esa celda y fecha exactas; no se reutiliza otra fecha.')
    if date.fromisoformat(found['target_start']) != issue_date+timedelta(days=1) or (date.fromisoformat(found['target_end'])-date.fromisoformat(found['target_start'])).days != horizon_days-1:
        raise ValueError('La fila no pertenece al horizonte t+1..t+H declarado.')
    return ExpandedFeatures(region_id=region_id, longitude=float(found['longitude']), latitude=float(found['latitude']),
        issue_date=issue_date, observation_cutoff=found['observation_cutoff'],
        source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        climate={key: float(found[key]) for key in climate_features},
        soil={key: float(found[key]) for key in soil_features} if all(key in found for key in soil_features) else None)
