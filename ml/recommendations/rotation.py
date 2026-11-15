"""Evaluación de rotación alimentada por inferencias, sin clima supuesto ni umbrales inventados."""

import json
import math
import unicodedata
from datetime import timedelta
from importlib.resources import files

from ml.recommendations.catalog import load_crop_catalog
from packages.contracts.api import RotationAssessment, RotationCandidate, RotationCheck, RotationScenario, RotationStage
from packages.contracts.rotation import RotationWaterRules
from pipelines.training.snapshots import fingerprint

ENGINE_VERSION = 'forecast-rotation-v1'


def normalized(value):
    return unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower().replace(' ', '_')


class ForecastRotationEngine:
    def __init__(self, catalog=None, water_rules=None):
        self.catalog = catalog if catalog is not None else load_crop_catalog()
        self.water_rules = water_rules if water_rules is not None else RotationWaterRules(
            version='unconfigured', review_status='pending')
        self.traits = json.loads(files('ml.configs').joinpath('rotation-traits.json').read_text())

    @property
    def rules_version(self):
        rules_identity = {'traits': self.traits, 'water': self.water_rules.model_dump(mode='json')}
        return f'{self.water_rules.version}:{fingerprint(rules_identity)[:12]}'

    @staticmethod
    def _values(request, climate, soil):
        start = request.forecast_start_date or request.reference_date + timedelta(days=1)
        for kind, forecast in [('climate', climate), ('soil', soil)]:
            if forecast is None:
                return None
            if (forecast.model_kind != kind or forecast.region_id != request.region_id or
                    forecast.reference_date != request.reference_date or forecast.horizon_days != request.horizon_days or
                    (forecast.forecast_start_date or forecast.reference_date + timedelta(days=1)) != start):
                raise ValueError('La predicción y la rotación deben compartir región, corte y periodo exactos.')
        required = [('temperature_mean', 'C', 'mean', climate), ('temperature_min', 'C', 'mean', climate),
                    ('temperature_max', 'C', 'mean', climate), ('precipitation', 'mm', 'sum', climate),
                    ('surface_soil_moisture', 'm3/m3', 'mean', soil)]
        values = {}
        for name, unit, statistic, forecast in required:
            matches = [value for value in forecast.values if value.variable == name]
            if not matches:
                return None
            if len(matches) != 1 or matches[0].unit != unit or matches[0].statistic != statistic:
                raise ValueError(f'Unidad o estadística incompatible para {name}.')
            values[name] = matches[0].value
        if (not all(math.isfinite(value) for value in values.values()) or
                not values['temperature_min'] <= values['temperature_mean'] <= values['temperature_max'] or
                values['precipitation'] < 0 or not 0 <= values['surface_soil_moisture'] <= 1):
            raise ValueError('Las predicciones no tienen coherencia física para evaluar la rotación.')
        return values

    def _trait(self, crop):
        matches = [row for row in self.traits['traits'] if row['scientific_name'] == crop.scientific_name]
        exact = [row for row in matches if normalized(row['chain']) == normalized(crop.chain)]
        return (exact or matches or [{'family':'unknown','legacy_id':''}])[0]

    def assess(self, request, climate, soil, *, previous_family=None, excluded_crops=()):
        values = self._values(request, climate, soil)
        start = request.forecast_start_date or request.reference_date + timedelta(days=1)
        identity = {'request':request.model_dump(mode='json'), 'climate':climate.model_dump(mode='json') if climate else None,
                    'soil':soil.model_dump(mode='json') if soil else None, 'catalog':self.catalog.model_dump(mode='json'),
                    'water_rules':self.water_rules.model_dump(mode='json'), 'traits':self.traits,
                    'previous_family':previous_family, 'excluded_crops':sorted(excluded_crops), 'engine':ENGINE_VERSION}
        limitations = [
            'Evaluación provisional: el catálogo ECOCROP y las reglas locales requieren revisión agronómica.',
            'La lluvia del periodo no equivale a precipitación anual; no se convierte ni se compara con mm/año.',
            'La humedad superficial no representa humedad radicular ni agua disponible para toda la planta.',
            'Las medias de mínimas y máximas diarias no permiten afirmar ausencia de heladas o extremos letales.',
            'Solo se evalúa el periodo pronosticado del primer cultivo; los siguientes requieren nueva inferencia.',
            'No se estima rendimiento, ingreso, fecha de cosecha ni probabilidad de éxito de siembra.',
            'El contexto regional no sustituye el pH, la altitud, el historial ni la validación del lote privado.',
        ]
        if not previous_family:
            limitations.append('Falta historial de cultivo para comprobar la primera transición de familia.')
        if any(f and f.validation_status != 'validated' for f in (climate, soil)):
            limitations.append('Las inferencias recibidas no están identificadas como modelos validados para publicación.')
        report = RotationAssessment(status='pending_forecasts' if values is None else 'pending_agronomic_requirements',
            engine_version=ENGINE_VERSION, catalog_version=self.catalog.version, rules_version=self.rules_version,
            input_snapshot_id=fingerprint(identity), region_id=request.region_id, forecast_start_date=start,
            horizon_days=request.horizon_days, climate_model_version=climate.model_version if climate else None,
            soil_model_version=soil.model_version if soil else None, forecast_values=values or {}, limitations=limitations)
        if values is None:
            return report
        rules = {(r.crop_id,r.horizon_days):r for r in self.water_rules.requirements}
        excluded = {normalized(value) for value in excluded_crops}
        for crop in self.catalog.crops:
            trait = self._trait(crop)
            temp = values['temperature_mean']
            fits = crop.temperature.absolute.minimum <= temp <= crop.temperature.absolute.maximum
            checks = [RotationCheck(variable='temperature', status='within_range' if fits else 'outside_range',
                value=temp, unit='C', explanation=f'Media XGBoost del periodo frente al rango absoluto ECOCROP '
                    f'{crop.temperature.absolute.minimum:g}–{crop.temperature.absolute.maximum:g} °C.')]
            rule = rules.get((crop.crop_id,request.horizon_days)) if self.water_rules.review_status == 'reviewed' else None
            for variable, unit, low, high in [('precipitation','mm',rule.precipitation_min_mm if rule else None,rule.precipitation_max_mm if rule else None),
                                             ('surface_soil_moisture','m3/m3',rule.surface_moisture_min if rule else None,rule.surface_moisture_max if rule else None)]:
                value = values[variable]
                status = 'unknown' if rule is None else 'within_range' if low <= value <= high else 'outside_range'
                checks.append(RotationCheck(variable=variable,status=status,value=value,unit=unit,
                    explanation=f'Falta un requisito revisado por cultivo para {request.horizon_days} días.' if rule is None else
                                f'Comparado con {low:g}–{high:g} {unit}; fuente: {rule.source}.'))
            family = trait['family']
            family_status = 'unknown' if previous_family is None or family == 'unknown' else 'outside_range' if normalized(family)==normalized(previous_family) else 'within_range'
            if any(normalized(value) in excluded for value in (crop.crop_id,crop.chain,crop.crop_name,trait['legacy_id'])):
                family_status='outside_range'
                reason='El agricultor excluyó este cultivo.'
            else:
                reason='Sin historial o familia identificados.' if family_status=='unknown' else 'No se debe repetir la familia precedente.' if family_status=='outside_range' else 'Familia diferente de la precedente.'
            checks.append(RotationCheck(variable='crop_family',status=family_status,unit='family',explanation=reason))
            state = 'excluded' if any(check.status=='outside_range' for check in checks) else 'pending_requirements' if any(check.status=='unknown' for check in checks) else 'within_checked_ranges'
            report.candidates.append(RotationCandidate(crop_id=crop.crop_id,crop_name=crop.crop_name,family=family,status=state,checks=checks))
        possible = [crop for crop in report.candidates if crop.status != 'excluded' and crop.family != 'unknown']
        # Las etapas posteriores son alternativas estructurales, no clima extrapolado.
        for first in possible[:3]:
            stages=[RotationStage(crop_id=first.crop_id,crop_name=first.crop_name,family=first.family,forecast_evaluated=True)]
            used={first.family}
            for crop in self.catalog.crops:
                trait=self._trait(crop)
                aliases=(crop.crop_id,crop.chain,crop.crop_name,trait['legacy_id'])
                if trait['family'] in used or trait['family']=='unknown' or any(normalized(v) in excluded for v in aliases):
                    continue
                stages.append(RotationStage(crop_id=crop.crop_id,crop_name=crop.crop_name,family=trait['family'],forecast_evaluated=False))
                used.add(trait['family'])
                if len(stages)==3:break
            report.scenarios.append(RotationScenario(stages=stages,explanation='Secuencia condicional por familias. '
                'Solo el primer cultivo tiene evaluación del periodo; los siguientes no tienen aptitud climática confirmada.'))
        if not possible:
            report.status='no_compatible_candidates'
        elif all(crop.status!='pending_requirements' for crop in report.candidates):
            report.status='evaluated'
        return report
