import { Component, input } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import type { GeographicAnalysis as State, GeographicAnalysisRequest } from '@agrogeo/api-client';
import { Backend } from '../../../../core/api/backend';
import { Analysis } from '../../../farm/analysis/analysis';
import { GeographicAnalysis } from './geographic-analysis';

@Component({ selector: 'app-analysis', template: '<p>Resultado de la selección</p>' })
class AnalysisStub {
  embedded = input(false);
  historyEnabled = input(false);
  geographicMode = input(false);
  referenceMode = input(false);
  geographic = input<State | null>(null);
}
const geometry: GeographicAnalysisRequest['geometry'] = {
  type: 'Polygon',
  coordinates: [
    [
      [-75.31, 6.1],
      [-75.3, 6.1],
      [-75.3, 6.11],
      [-75.31, 6.1],
    ],
  ],
};
const state = (status: State['status'] = 'queued'): State => ({
  request_id: '00000000-0000-4000-8000-000000000001',
  area_id: 'test-only',
  geometry,
  sampling_point: { type: 'Point', coordinates: [-75.305, 6.105] },
  sampling_method: 'interior_reference_point',
  horizon_days: 30,
  forecast_start_date: '2026-11-15',
  status,
  attempts: 0,
  created_at: '2026-11-15T15:00:00Z',
  updated_at: '2026-11-15T15:00:00Z',
  messages: [],
  result: null,
});

describe('Geographic analysis selection', () => {
  const request = vi.fn();
  beforeEach(() => {
    request.mockReset().mockResolvedValue(state());
    TestBed.configureTestingModule({
      providers: [{ provide: Backend, useValue: { client: { request } } }],
    });
    TestBed.overrideComponent(GeographicAnalysis, {
      remove: { imports: [Analysis] },
      add: { imports: [AnalysisStub] },
    });
  });
  it('automatically shows the available regional estimate and clears it for another municipality', async () => {
    const item = state('waiting_inputs');
    item.result = {
      status: 'insufficient_data',
      request: {
        region_id: 'geo-test-only',
        reference_date: '2026-11-12',
        forecast_start_date: '2026-11-15',
        horizon_days: 30,
      },
    };
    item.reference = {
      kind: 'bundled_public_snapshot',
      result: {
        status: 'pending_recommendations',
        request: {
          region_id: 'geo-reference-test-only',
          reference_date: '2026-11-13',
          forecast_start_date: '2026-11-16',
          horizon_days: 30,
        },
        climate: {
          model_kind: 'climate',
          model_version: 'test-only',
          validation_status: 'experimental',
          region_id: 'geo-reference-test-only',
          reference_date: '2026-11-13',
          forecast_start_date: '2026-11-16',
          horizon_days: 30,
          values: [
            {
              variable: 'temperature_mean',
              value: 18.25,
              unit: 'C',
              aggregation: 'Media de prueba',
              statistic: 'mean',
            },
          ],
          limitations: [],
        },
      },
    };
    request.mockResolvedValue(item);
    const fixture = TestBed.createComponent(GeographicAnalysis);
    fixture.componentRef.setInput('geometry', geometry);
    await fixture.whenStable();
    fixture.detectChanges();
    fixture.nativeElement.querySelector('button').click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).not.toContain('Referencia regional disponible');
    expect(fixture.nativeElement.textContent).not.toContain('conjunto público de referencia');
    expect(fixture.nativeElement.textContent).not.toContain('permanece pendiente');
    expect(fixture.nativeElement.querySelector('app-analysis')).not.toBeNull();
    const toggle = [...fixture.nativeElement.querySelectorAll('button')].find((button) =>
      (button as HTMLButtonElement).textContent?.includes('Ocultar referencia regional'),
    ) as HTMLButtonElement;
    toggle.click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-analysis')).toBeNull();
    toggle.click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Estimación con datos de referencia');
    const child = fixture.debugElement.query(
      (node) => node.componentInstance instanceof AnalysisStub,
    ).componentInstance as AnalysisStub;
    expect(child.referenceMode()).toBe(true);
    expect(child.geographic()?.result?.request.forecast_start_date).toBe('2026-11-16');
    expect(item.forecast_start_date).toBe('2026-11-15');
    fixture.componentRef.setInput('geometry', { type: 'Point', coordinates: [-75.2, 5.6] });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-analysis')).toBeNull();
    expect(fixture.nativeElement.textContent).not.toContain('Ocultar referencia regional');
    fixture.destroy();
  });
  it('shows local climate first while soil is pending even when a regional result is available', async () => {
    const item = state('waiting_inputs');
    item.result = {
      status: 'pending_recommendations',
      request: {
        region_id: 'geo-test-only',
        reference_date: '2026-11-12',
        forecast_start_date: '2026-11-15',
        horizon_days: 30,
      },
      climate: {
        model_kind: 'climate',
        model_version: 'test-only',
        validation_status: 'experimental',
        region_id: 'geo-test-only',
        reference_date: '2026-11-12',
        forecast_start_date: '2026-11-15',
        horizon_days: 30,
        values: [
          { variable: 'temperature_mean', value: 21, unit: 'C', aggregation: 'Media de prueba' },
        ],
        limitations: [],
      },
    };
    item.reference = {
      kind: 'prepared_reference',
      result: {
        ...item.result,
        climate: {
          ...item.result.climate!,
          values: [
            { variable: 'temperature_mean', value: 17, unit: 'C', aggregation: 'Media de prueba' },
          ],
        },
      },
    };
    request.mockResolvedValue(item);
    const fixture = TestBed.createComponent(GeographicAnalysis);
    fixture.componentRef.setInput('geometry', geometry);
    await fixture.whenStable();
    fixture.nativeElement.querySelector('button').click();
    await fixture.whenStable();
    fixture.detectChanges();
    const child = fixture.debugElement.query(
      (node) => node.componentInstance instanceof AnalysisStub,
    ).componentInstance as AnalysisStub;
    expect(child.referenceMode()).toBe(false);
    expect(child.geographic()?.result?.climate?.values[0].value).toBe(21);
    expect(fixture.nativeElement.textContent).toContain('Ver referencia regional');
    expect(fixture.nativeElement.textContent).not.toContain('Estimación con datos de referencia');
    fixture.destroy();
  });
  it('keeps spatial diagnostics out of the simple result view', async () => {
    const item = state('waiting_inputs');
    item.result = {
      status: 'insufficient_data',
      request: {
        region_id: 'geo-test-only',
        reference_date: '2026-11-12',
        forecast_start_date: '2026-11-15',
        horizon_days: 30,
      },
      spatial_match: {
        method: 'nearest',
        requested_longitude: -75.3,
        requested_latitude: 6.1,
        used_longitude: -75.35,
        used_latitude: 6.15,
        distance_km: 7.8,
        source_point_id: 'test-only',
        source_sha256: 'a'.repeat(64),
        issue_date: '2026-11-14',
      },
    };
    request.mockResolvedValue(item);
    const fixture = TestBed.createComponent(GeographicAnalysis);
    fixture.componentRef.setInput('geometry', geometry);
    await fixture.whenStable();
    fixture.detectChanges();
    fixture.nativeElement.querySelector('button').click();
    await fixture.whenStable();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent;
    expect(text).not.toContain('Usamos datos de un punto cercano');
    expect(text).not.toContain('Referencia utilizada:');
    expect(fixture.nativeElement.querySelector('details')).toBeNull();
    fixture.destroy();
  });
  it('automatically identifies a nearest-point prediction as regional even if the API says completed', async () => {
    const item = state('completed');
    item.result = {
      status: 'pending_recommendations',
      request: {
        region_id: 'geo-test-only',
        reference_date: '2026-11-12',
        forecast_start_date: '2026-11-15',
        horizon_days: 30,
      },
      climate: {
        model_kind: 'climate',
        model_version: 'test-only',
        validation_status: 'experimental',
        region_id: 'geo-test-only',
        reference_date: '2026-11-12',
        forecast_start_date: '2026-11-15',
        horizon_days: 30,
        values: [
          {
            variable: 'temperature_mean',
            value: 18.25,
            unit: 'C',
            aggregation: 'Media de prueba',
            statistic: 'mean',
          },
        ],
        limitations: [],
      },
      spatial_match: {
        method: 'nearest',
        requested_longitude: -75.305,
        requested_latitude: 6.105,
        used_longitude: -75.35,
        used_latitude: 6.15,
        distance_km: 7.8,
        source_point_id: 'test-only-nearest',
        source_sha256: 'b'.repeat(64),
        issue_date: '2026-11-14',
      },
    };
    request.mockResolvedValue(item);
    const fixture = TestBed.createComponent(GeographicAnalysis);
    fixture.componentRef.setInput('geometry', geometry);
    await fixture.whenStable();
    fixture.nativeElement.querySelector('button').click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-analysis')).not.toBeNull();
    const child = fixture.debugElement.query(
      (node) => node.componentInstance instanceof AnalysisStub,
    ).componentInstance as AnalysisStub;
    expect(child.referenceMode()).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('km de tu selección');
    fixture.destroy();
  });
  it('shows actual point observations even when no model prediction is available', async () => {
    const item = state('waiting_inputs');
    item.observations = [
      {
        source: 'NASA_POWER',
        date: '2026-11-12',
        variable: 'T2M',
        value: 18.36,
        unit: 'C',
        quality: 'provider_value_unvalidated',
        resolution: '0.5 x 0.625 degree',
        latitude: 6.105,
        longitude: -75.305,
        time_standard: 'LST',
        retrieved_at: '2026-11-15T15:00:00Z',
      },
    ];
    request.mockResolvedValue(item);
    const fixture = TestBed.createComponent(GeographicAnalysis);
    fixture.componentRef.setInput('geometry', geometry);
    await fixture.whenStable();
    fixture.nativeElement.querySelector('button').click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Datos observados en tu ubicación');
    expect(fixture.nativeElement.textContent).toContain('18.36');
    expect(fixture.nativeElement.textContent).toContain('NASA_POWER');
    expect(fixture.nativeElement.querySelector('app-analysis')).toBeNull();
    fixture.destroy();
  });
  it('submits the exact geometry and selected period without authentication calls', async () => {
    const fixture = TestBed.createComponent(GeographicAnalysis);
    fixture.componentRef.setInput('geometry', geometry);
    await fixture.whenStable();
    fixture.detectChanges();
    const select = fixture.nativeElement.querySelector('select') as HTMLSelectElement;
    select.value = '30';
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    fixture.nativeElement.querySelector('button').click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(request).toHaveBeenCalledOnce();
    const [path, options] = request.mock.calls[0];
    expect(path).toBe('geographic-analyses');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ geometry, horizon_days: 30 });
    expect(fixture.nativeElement.textContent).not.toMatch(/6[.,]105/);
    expect(fixture.nativeElement.querySelector('details')).toBeNull();
    expect(fixture.nativeElement.querySelector('app-analysis')).toBeNull();
    fixture.destroy();
  });
  it('aborts and ignores a late response when the area changes', async () => {
    let resolve!: (value: State) => void;
    request.mockImplementationOnce(() => new Promise((r) => (resolve = r)));
    const fixture = TestBed.createComponent(GeographicAnalysis);
    fixture.componentRef.setInput('geometry', geometry);
    await fixture.whenStable();
    fixture.detectChanges();
    fixture.nativeElement.querySelector('button').click();
    const signal = request.mock.calls[0][1].signal as AbortSignal;
    fixture.componentRef.setInput('geometry', { type: 'Point', coordinates: [-75.2, 6.2] });
    fixture.detectChanges();
    expect(signal.aborted).toBe(true);
    resolve(state('completed'));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-analysis')).toBeNull();
    expect(fixture.nativeElement.textContent).not.toContain('6,105');
    fixture.destroy();
  });
  it('reads progress without submitting another job and clears results on period changes', async () => {
    const fixture = TestBed.createComponent(GeographicAnalysis);
    fixture.componentRef.setInput('geometry', geometry);
    await fixture.whenStable();
    fixture.detectChanges();
    fixture.nativeElement.querySelector('button').click();
    await fixture.whenStable();
    fixture.detectChanges();
    request.mockResolvedValueOnce(state('completed'));
    fixture.componentInstance.refreshAvailableData();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(request.mock.calls[1][0]).toBe('geographic-analyses/' + state().request_id);
    expect(request.mock.calls.filter(([, o]) => o.method === 'POST')).toHaveLength(1);
    const select = fixture.nativeElement.querySelector('select') as HTMLSelectElement;
    select.value = '60';
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-analysis')).toBeNull();
    fixture.destroy();
  });
});
