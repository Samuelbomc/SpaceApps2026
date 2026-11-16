import { TestBed } from '@angular/core/testing';
import type { Analysis, Forecast, ProbabilityEstimate } from '@agrogeo/api-client';
import { AnalysisSummary } from './analysis-summary';

const unavailable: ProbabilityEstimate = { status: 'unavailable', value: null };
function result(): Analysis {
  const forecast = (kind: 'climate' | 'soil'): Forecast => {
    const values: Forecast['values'] =
      kind === 'climate'
        ? [
            {
              variable: 'temperature_mean',
              value: 18,
              unit: 'C',
              statistic: 'mean',
              aggregation: 'Media sintética',
            },
            {
              variable: 'temperature_min',
              value: 14,
              unit: 'C',
              statistic: 'mean',
              aggregation: 'Media sintética',
            },
            {
              variable: 'temperature_max',
              value: 22,
              unit: 'C',
              statistic: 'mean',
              aggregation: 'Media sintética',
            },
            {
              variable: 'precipitation',
              value: 70,
              unit: 'mm',
              statistic: 'sum',
              aggregation: 'Suma sintética',
            },
          ]
        : [
            {
              variable: 'surface_soil_moisture',
              value: 0.25,
              unit: 'm3/m3',
              statistic: 'mean',
              aggregation: 'Media sintética',
            },
          ];
    return {
      model_kind: kind,
      model_version: 'test-only',
      region_id: 'test-only',
      reference_date: '2026-11-13',
      forecast_start_date: '2026-11-16',
      horizon_days: 7,
      values,
      daily: Array.from({ length: 7 }, (_, day) => ({
        date: '2026-11-' + (16 + day),
        values: values.map((value) => ({
          ...value,
          value: value.variable === 'precipitation' ? 10 : value.value,
        })),
      })),
    };
  };
  return {
    status: 'pending_recommendations',
    request: {
      region_id: 'test-only',
      reference_date: '2026-11-13',
      forecast_start_date: '2026-11-16',
      horizon_days: 7,
    },
    climate: forecast('climate'),
    soil: forecast('soil'),
    rotation_assessment: {
      status: 'pending_agronomic_requirements',
      engine_version: 'test-only',
      catalog_version: 'test-only',
      rules_version: 'test-only',
      input_snapshot_id: 'test-only',
      region_id: 'test-only',
      forecast_start_date: '2026-11-16',
      horizon_days: 7,
      limitations: [],
      candidates: [
        {
          crop_id: 'a',
          crop_name: 'Frijol arbustivo',
          family: 'Fabaceae',
          status: 'pending_requirements',
          temperature_fit: 'optimal',
          probability: unavailable,
          checks: [],
        },
        {
          crop_id: 'b',
          crop_name: 'Frijol voluble',
          family: 'Fabaceae',
          status: 'pending_requirements',
          temperature_fit: 'optimal',
          probability: unavailable,
          checks: [],
        },
        {
          crop_id: 'excluded',
          crop_name: 'Cultivo excluido',
          family: 'test',
          status: 'excluded',
          checks: [],
        },
      ],
      scenarios: [
        {
          stages: [
            {
              crop_id: 'a',
              crop_name: 'Frijol arbustivo',
              family: 'Fabaceae',
              forecast_evaluated: true,
            },
            { crop_id: 'c', crop_name: 'Maíz', family: 'Poaceae', forecast_evaluated: false },
          ],
          status: 'conditional',
          explanation: 'Solo fixture sintético',
          probability: unavailable,
        },
      ],
    },
  };
}

describe('Compact prediction and crop results', () => {
  it('identifies an older complete snapshot of the selected point with its original period', async () => {
    const analysis = result();
    analysis.spatial_match = {
      method: 'exact',
      requested_longitude: -75.3,
      requested_latitude: 6.1,
      used_longitude: -75.3,
      used_latitude: 6.1,
      distance_km: 0,
      source_point_id: 'test-only',
      source_sha256: 'a'.repeat(64),
      issue_date: '2026-11-15',
    };
    const fixture = TestBed.createComponent(AnalysisSummary);
    fixture.componentRef.setInput('result', analysis);
    fixture.componentRef.setInput('reference', true);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Último corte completo de esta ubicación');
    expect(fixture.nativeElement.textContent).not.toContain('Referencia regional');
    expect(analysis.request.forecast_start_date).toBe('2026-11-16');
  });
  it('shows all five model outputs and every daily variable without technical paragraphs', async () => {
    const fixture = TestBed.createComponent(AnalysisSummary);
    fixture.componentRef.setInput('result', result());
    fixture.componentRef.setInput('reference', true);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('.prediction')).toHaveLength(5);
    const text = fixture.nativeElement.textContent;
    for (const label of [
      'Temperatura media',
      'Temperatura mínima media',
      'Temperatura máxima media',
      'Lluvia acumulada',
      'Humedad superficial del suelo',
    ])
      expect(text).toContain(label);
    expect(text).toContain('m³/m³');
    expect(text).toContain('Referencia regional');
    expect(fixture.nativeElement.querySelectorAll('details tbody tr')).toHaveLength(7);
    expect(
      fixture.nativeElement.querySelectorAll('details tbody tr')[0].querySelectorAll('td'),
    ).toHaveLength(6);
    expect(text).not.toContain('daily-direct');
    expect(text).not.toContain('Por confirmar:');
  });
  it('lists crops and rotation sequences without probability columns', async () => {
    const fixture = TestBed.createComponent(AnalysisSummary);
    fixture.componentRef.setInput('result', result());
    await fixture.whenStable();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Frijol arbustivo');
    expect(text).toContain('Frijol voluble');
    expect(text).toContain('Frijol arbustivo → Maíz');
    expect(text).not.toContain('Cultivo excluido');
    expect(text).not.toMatch(/probabilidad/i);
    const tables = fixture.nativeElement.querySelectorAll('table');
    expect(tables[1].querySelectorAll('thead th')).toHaveLength(4);
    expect(tables[1].querySelector('tbody tr').querySelectorAll('td')).toHaveLength(4);
    expect(tables[2].querySelectorAll('thead th')).toHaveLength(1);
    expect(tables[2].querySelector('tbody tr').querySelectorAll('td')).toHaveLength(1);
    expect(text).not.toContain('100 %');
    expect(fixture.nativeElement.querySelectorAll('.crop-list tbody tr')).toHaveLength(2);
  });
  it('omits even calibrated probabilities and keeps missing daily data empty', async () => {
    const analysis = result();
    analysis.rotation_assessment!.candidates![0].probability = {
      status: 'calibrated',
      value: 0,
      event: 'SYNTHETIC TEST EVENT',
      model_version: 'test-only',
      calibration_version: 'test-only',
    };
    analysis.rotation_assessment!.candidates![1].probability = {
      status: 'calibrated',
      value: 0.72,
      event: 'SYNTHETIC TEST EVENT',
      model_version: 'test-only',
      calibration_version: 'test-only',
    };
    analysis.rotation_assessment!.scenarios![0].probability = {
      status: 'calibrated',
      value: 0.43,
      event: 'SYNTHETIC TEST EVENT',
      model_version: 'test-only',
      calibration_version: 'test-only',
    };
    analysis.soil!.daily = analysis.soil!.daily!.slice(1);
    const fixture = TestBed.createComponent(AnalysisSummary);
    fixture.componentRef.setInput('result', analysis);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).not.toMatch(/probabilidad|0 %|72 %|43 %/i);
    expect(
      fixture.nativeElement
        .querySelectorAll('details tbody tr')[0]
        .querySelectorAll('td')[5]
        .textContent.trim(),
    ).toBe('—');
  });
  it('shows forecast water values and reviewed ranges without treating missing limits as optimal', async () => {
    const analysis = result();
    const crop = analysis.rotation_assessment!.candidates![0];
    crop.temperature_optimal_min_c = 16;
    crop.temperature_optimal_max_c = 25;
    crop.checks = [
      {
        variable: 'precipitation',
        status: 'within_range',
        value: 0,
        unit: 'mm',
        minimum: 0,
        maximum: 100,
        explanation: 'Synthetic reviewed test rule',
      },
      {
        variable: 'surface_soil_moisture',
        status: 'unknown',
        value: 0.25,
        unit: 'm3/m3',
        explanation: 'No rule in test fixture',
      },
    ];
    const fixture = TestBed.createComponent(AnalysisSummary);
    fixture.componentRef.setInput('result', analysis);
    await fixture.whenStable();
    fixture.detectChanges();
    const row = fixture.nativeElement.querySelector('.crop-list tbody tr');
    expect(row.textContent).toContain('Óptimo: 16–25 °C');
    const water = row.querySelectorAll('app-crop-condition');
    expect(water[0].textContent).toContain('0.0 mm');
    expect(water[0].textContent).toContain('En rango');
    expect(water[0].textContent).toContain('Rango: 0–100 mm');
    expect(water[1].textContent).toContain('0.25 m³/m³');
    expect(water[1].textContent).toContain('Sin umbral definido');
    expect(water[1].textContent).not.toContain('Óptima');
    expect(row.querySelectorAll('td')).toHaveLength(4);
    crop.checks[0] = { ...crop.checks[0], status: 'outside_range' };
    fixture.componentRef.setInput('result', { ...analysis });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(water[0].textContent).toContain('Fuera de rango');
  });
});
