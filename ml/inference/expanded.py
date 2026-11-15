"""Cinco artefactos XGBoost del equipo, con features ordenadas y humedad residual."""

import hashlib
import json
import math
from datetime import timedelta
from pathlib import Path

from packages.contracts.api import AnalysisRequest, AnalysisResult, Forecast, ForecastValue
from packages.contracts.pretrained import ModelCatalog, ModelInfo
from pipelines.training.snapshots import fingerprint

CLIMATE = ('temperature_mean', 'temperature_min', 'temperature_max', 'precipitation')
LIMITATIONS = [
    'Modelos experimentales del equipo; no equivalen a una publicación validada del registro operativo.',
    'Solo predicen los siete días posteriores a la emisión, con entradas hasta dos días antes de emitir.',
    'Faltan validación independiente y evaluación de transferencia a otras regiones.',
    'La precipitación usa GPM Late; los mínimos y máximos son medias de extremos diarios.',
    'La humedad es superficial y requiere SMAP y SoilGrids; no representa toda la zona radicular.',
    'No se extrapolan plazos de 15, 30 o 60 días ni se rellenan variables faltantes.',
]


class ExpandedModelBundle:
    def __init__(self, root=Path('ml/artifacts')):
        self.root = Path(root)
        self._boosters = {}

    def _directory(self, name):
        return self.root / ('moisture_change_experiment' if name == 'moisture' else f'expanded_xgboost_experiment/{name}')

    def _metadata(self):
        lock = json.loads((Path(__file__).parents[1] / 'configs/pretrained-bundle.json').read_text())
        records = {}
        for name in (*CLIMATE, 'moisture'):
            directory = self._directory(name)
            for filename, digest in lock[name].items():
                if hashlib.sha256((directory/filename).read_bytes()).hexdigest() != digest:
                    raise ValueError(f'El artefacto {name}/{filename} no coincide con la versión integrada.')
            config = json.loads((directory/'training.json').read_text())
            records[name] = (config, fingerprint(lock[name])[:32])
        return records

    def catalog(self):
        if not self.root.is_dir():
            return ModelCatalog(models=[], supported_horizons=[], limitations=LIMITATIONS)
        models = []
        for name, (config, version) in self._metadata().items():
            residual = name == 'moisture'
            test = config['partitions']['test'] if residual else config
            models.append(ModelInfo(model_id=name, model_kind='soil' if residual else 'climate', version=version,
                unit=config['units'], features=config['features'],
                formula=config['formula'] if residual else 'XGBoost(features)',
                evaluation_mae=test['change_model' if residual else 'test_xgboost']['mae'],
                baseline_mae=test['persistence' if residual else 'test_persistence']['mae']))
        return ModelCatalog(models=models, supported_horizons=[7], limitations=LIMITATIONS)

    def _predict(self, name, features, config, version):
        import xgboost as xgb
        names = config['features']
        missing = [key for key in names if key not in features]
        if missing:
            raise ValueError('Faltan variables: '+', '.join(missing))
        values = [float(features[key]) for key in names]
        if not all(math.isfinite(value) for value in values):
            raise ValueError('Las variables deben ser finitas.')
        if (name, version) not in self._boosters:
            booster = xgb.Booster(params={'nthread': 1})
            booster.load_model(self._directory(name)/'model.json')
            if booster.feature_names != names:
                raise ValueError('El orden de variables del modelo difiere del contrato.')
            self._boosters[name, version] = booster
        value = float(self._boosters[name, version].predict(xgb.DMatrix([values], feature_names=names))[0])
        if name == 'moisture':
            if config.get('baseline_feature') != 'smap_mean_7d':
                raise ValueError('Baseline de humedad no compatible.')
            value += features['smap_mean_7d']
        if not math.isfinite(value):
            raise ValueError('El modelo devolvió un valor no finito.')
        return value

    def predict(self, snapshot):
        records = self._metadata()
        start = snapshot.issue_date + timedelta(days=1)
        request = AnalysisRequest(region_id=snapshot.region_id, reference_date=snapshot.observation_cutoff,
            forecast_start_date=start, horizon_days=7)
        climate_version = fingerprint({name: records[name][1] for name in CLIMATE})[:32]
        def forecast(kind, version, values):
            return Forecast(model_kind=kind, model_version=version, region_id=snapshot.region_id,
                reference_date=snapshot.observation_cutoff, forecast_start_date=start, horizon_days=7,
                validation_status='experimental', values=values, limitations=LIMITATIONS)
        climate_values = [ForecastValue(variable=name, value=self._predict(name, snapshot.climate, *records[name]),
            unit=records[name][0]['units'], aggregation='acumulado de 7 días' if name == 'precipitation' else 'media de 7 días') for name in CLIMATE]
        climate = forecast('climate', climate_version, climate_values)
        soil = None
        if snapshot.soil is not None:
            config, version = records['moisture']
            soil = forecast('soil', version, [ForecastValue(variable='surface_soil_moisture',
                value=self._predict('moisture', snapshot.soil, config, version), unit=config['units'],
                aggregation='media de observaciones válidas de los próximos 7 días')])
        return AnalysisResult(status='pending_recommendations' if soil else 'insufficient_data', request=request,
            analysis_id=fingerprint({'snapshot': snapshot.model_dump(mode='json'), 'versions': {k:v[1] for k,v in records.items()}}),
            input_snapshot_id=fingerprint(snapshot.model_dump(mode='json')), climate=climate, soil=soil,
            messages=['Inferencia experimental; las reglas de recomendaciones siguen pendientes.'] if soil else
                ['Predicción climática disponible. Faltan variables procesadas de SMAP/SoilGrids para suelo.'])
