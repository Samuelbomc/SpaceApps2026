"""Modelos del equipo por horizonte, con features ordenadas y humedad residual."""

import hashlib
import json
import math
from datetime import timedelta
from pathlib import Path

from packages.contracts.api import AnalysisRequest, AnalysisResult, Forecast, ForecastValue
from packages.contracts.pretrained import ModelCatalog, ModelInfo
from pipelines.training.snapshots import fingerprint

CLIMATE = ('temperature_mean', 'temperature_min', 'temperature_max', 'precipitation')
HORIZONS = (7, 15, 30, 60)
LIMITATIONS = [
    'Modelos experimentales del equipo; no equivalen a una publicación validada del registro operativo.',
    'Cada horizonte usa modelos propios y agrega t+1..t+H, con entradas hasta t-2.',
    'Son medias o acumulados del periodo, no condiciones de un día concreto ni trayectorias diarias.',
    'Faltan validación independiente y evaluación de transferencia a otras regiones.',
    'La precipitación usa GPM Late; los mínimos y máximos son medias de extremos diarios.',
    'La humedad es superficial, requiere SMAP y SoilGrids y no representa toda la zona radicular.',
    'La humedad a 30 días no supera la persistencia en el test completo del equipo.',
    'No se rellenan variables faltantes ni se extrapola un modelo de siete días.',
]


class ExpandedModelBundle:
    def __init__(self, root=Path('ml/artifacts')):
        self.root = Path(root)
        self._boosters = {}

    def _directory(self, name, horizon=7):
        if horizon == 7:
            return self.root / ('soil_moisture' if name == 'moisture' else f'environmental_conditions/{name}')
        return self.root / f'forecasts/{horizon}d/{name}'

    def _metadata(self, horizon=7):
        if horizon not in HORIZONS:
            raise ValueError('Horizonte no soportado; se admiten 7, 15, 30 y 60 días.')
        lock = json.loads((Path(__file__).parents[1] / 'configs/pretrained-bundle.json').read_text())[str(horizon)]
        records = {}
        for name in (*CLIMATE, 'moisture'):
            directory = self._directory(name, horizon)
            for filename, digest in lock[name].items():
                if hashlib.sha256((directory / filename).read_bytes()).hexdigest() != digest:
                    raise ValueError(f'El artefacto {horizon}d/{name}/{filename} no coincide con la versión integrada.')
            config = json.loads((directory / 'training.json').read_text())
            if config.get('horizon_days', 7) != horizon:
                raise ValueError('El horizonte declarado por el artefacto no coincide.')
            expected_mode = 'baseline_plus_change' if name == 'moisture' else 'absolute'
            if config.get('prediction_mode', expected_mode) != expected_mode:
                raise ValueError('La semántica de la salida del modelo no coincide.')
            records[name] = (config, fingerprint(lock[name])[:32])
        return records

    def catalog(self):
        if not self.root.is_dir():
            return ModelCatalog(models=[], supported_horizons=[], limitations=LIMITATIONS)
        models = []
        for horizon in HORIZONS:
            for name, (config, version) in self._metadata(horizon).items():
                residual = name == 'moisture'
                legacy_residual = residual and horizon == 7
                test = config['partitions']['test'] if legacy_residual else config
                models.append(ModelInfo(
                    model_id=name, model_kind='soil' if residual else 'climate', version=version,
                    horizon_days=horizon, unit=config['units'], features=config['features'],
                    formula='smap_mean_7d + XGBoost(features)' if residual else 'XGBoost(features)',
                    evaluation_mae=test['change_model' if legacy_residual else 'test_xgboost']['mae'],
                    baseline_mae=test['persistence' if legacy_residual else 'test_persistence']['mae'],
                ))
        return ModelCatalog(models=models, supported_horizons=list(HORIZONS), limitations=LIMITATIONS)

    def _predict(self, name, features, config, version, horizon=7):
        import xgboost as xgb
        names = config['features']
        missing = [key for key in names if key not in features]
        if missing:
            raise ValueError('Faltan variables: ' + ', '.join(missing))
        values = [float(features[key]) for key in names]
        if not all(math.isfinite(value) for value in values):
            raise ValueError('Las variables deben ser finitas.')
        key = (horizon, name, version)
        if key not in self._boosters:
            booster = xgb.Booster(params={'nthread': 1})
            booster.load_model(self._directory(name, horizon) / 'model.json')
            if booster.feature_names != names:
                raise ValueError('El orden de variables del modelo difiere del contrato.')
            self._boosters[key] = booster
        value = float(self._boosters[key].predict(xgb.DMatrix([values], feature_names=names))[0])
        if name == 'moisture':
            if config.get('baseline_feature') != 'smap_mean_7d' or config.get('baseline_scale', 1) != 1:
                raise ValueError('Baseline de humedad no compatible.')
            value += features['smap_mean_7d']
        if not math.isfinite(value):
            raise ValueError('El modelo devolvió un valor no finito.')
        return value

    def predict(self, snapshot, *, horizon_days=7):
        records = self._metadata(horizon_days)
        start = snapshot.issue_date + timedelta(days=1)
        request = AnalysisRequest(
            region_id=snapshot.region_id, reference_date=snapshot.observation_cutoff,
            forecast_start_date=start, horizon_days=horizon_days,
        )
        climate_version = fingerprint({name: records[name][1] for name in CLIMATE})[:32]

        def forecast(kind, version, values):
            return Forecast(
                model_kind=kind, model_version=version, region_id=snapshot.region_id,
                reference_date=snapshot.observation_cutoff, forecast_start_date=start,
                horizon_days=horizon_days, validation_status='experimental', values=values,
                limitations=LIMITATIONS,
            )

        climate_values = [ForecastValue(
            variable=name, value=self._predict(name, snapshot.climate, *records[name], horizon_days),
            unit=records[name][0]['units'],
            aggregation=f'acumulado de {horizon_days} días' if name == 'precipitation' else f'media de {horizon_days} días',
        ) for name in CLIMATE]
        climate = forecast('climate', climate_version, climate_values)
        soil = None
        if snapshot.soil is not None:
            config, version = records['moisture']
            soil = forecast('soil', version, [ForecastValue(
                variable='surface_soil_moisture',
                value=self._predict('moisture', snapshot.soil, config, version, horizon_days),
                unit=config['units'], aggregation=f'media de observaciones válidas de los próximos {horizon_days} días',
            )])
        identity = {'snapshot': snapshot.model_dump(mode='json'), 'horizon_days': horizon_days,
                    'versions': {k: v[1] for k, v in records.items()}}
        return AnalysisResult(
            status='pending_recommendations' if soil else 'insufficient_data', request=request,
            analysis_id=fingerprint(identity), input_snapshot_id=fingerprint(snapshot.model_dump(mode='json')),
            climate=climate, soil=soil,
            messages=['Inferencia experimental; las reglas de recomendaciones siguen pendientes.'] if soil else
                     ['Predicción climática disponible. Faltan variables procesadas de SMAP/SoilGrids para suelo.'],
        )
