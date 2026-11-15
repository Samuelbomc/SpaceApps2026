import { Component, input, model, output } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { vi } from 'vitest';
import { routes } from '../../app.routes';
import { AuthGateway } from '../../core/auth/auth-gateway';
import { AuthService } from '../../core/auth/auth.service';
import { MockAuthGateway } from '../../testing/mock-auth-gateway';
import { AnalysisJourneyStore } from '../../core/journey/analysis-journey.store';
import { Backend } from '../../core/api/backend';
import { Explorer } from './explorer';
import { GeoBoundariesService } from './services/geo-boundaries.service';
import { InteractiveMap } from './components/interactive-map/interactive-map';
import { MapProvenance } from './components/map-provenance/map-provenance';
import { PlotMap, PlotMunicipality, PlotShape } from '../farm/plot/components/plot-map/plot-map';
import type { BoundaryGeometry } from './models/geo.models';

@Component({ selector: 'app-interactive-map', template: '' })
class MapStub {
  selectedCode = model<string | null>(null);
  focusTarget = input<unknown>(null);
}
@Component({ selector: 'app-map-provenance', template: '' })
class ProvenanceStub {}
@Component({ selector: 'app-plot-map', template: '<p>Delimitar terreno</p>' })
class PlotMapStub {
  municipality = input.required<PlotMunicipality>();
  initialRing = input<unknown>(null);
  shapeChange = output<PlotShape | null>();
}
const geometry: BoundaryGeometry = {
  type: 'Polygon',
  coordinates: [
    [
      [-75.4, 5.9],
      [-75.3, 5.9],
      [-75.3, 6],
      [-75.4, 6],
      [-75.4, 5.9],
    ],
  ],
};
const municipal = (code = '05002') => ({
  type: 'Feature',
  properties: { code, name: code === '05002' ? 'Abejorral' : 'Rionegro' },
  geometry,
});

describe('Public map workspace', () => {
  const municipality = vi.fn(async (code: string) => municipal(code));
  const request = vi.fn(async (path: string, options?: RequestInit) =>
    path === 'geographic-analyses'
      ? {
          request_id: '00000000-0000-4000-8000-000000000001',
          area_id: 'test-only',
          geometry: JSON.parse(options!.body as string).geometry,
          sampling_point: { type: 'Point', coordinates: [-75.375, 5.925] },
          sampling_method: 'interior_reference_point',
          horizon_days: JSON.parse(options!.body as string).horizon_days,
          status: 'completed',
          attempts: 1,
          forecast_start_date: '2026-11-15',
          created_at: '2026-11-15T15:00:00Z',
          updated_at: '2026-11-15T15:00:00Z',
          messages: [],
          result: null,
        }
      : path === 'automation/refresh'
        ? null
        : path === 'regions'
          ? [
              {
                region_id: 'test-only',
                name: 'Referencia de prueba',
                latitude: 5.95,
                longitude: -75.35,
              },
            ]
          : {
              status: 'insufficient_data',
              messages: [],
              climate: null,
              soil: null,
              recommendations: null,
            },
  );
  beforeEach(() => {
    sessionStorage.clear();
    request.mockClear();
    municipality.mockReset().mockImplementation(async (code) => municipal(code));
    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        { provide: AuthGateway, useClass: MockAuthGateway },
        {
          provide: Backend,
          useValue: {
            client: {
              request,
              loadObservationHistory: async () => ({ items: [], total: 0, last_updated_at: null }),
            },
          },
        },
        {
          provide: GeoBoundariesService,
          useValue: {
            municipality,
            municipalitySummaries: async () => [
              {
                id: 5002,
                code: '05002',
                name: 'Abejorral',
                areaKm2: 100,
                bbox: [-75.4, 5.9, -75.3, 6],
              },
              {
                id: 5615,
                code: '05615',
                name: 'Rionegro',
                areaKm2: 100,
                bbox: [-75.4, 5.9, -75.3, 6],
              },
            ],
            departmentSummaries: async () => [],
          },
        },
      ],
    });
    TestBed.overrideComponent(Explorer, {
      remove: { imports: [InteractiveMap, MapProvenance, PlotMap] },
      add: { imports: [MapStub, ProvenanceStub, PlotMapStub] },
    });
  });
  it('a visitor selects a municipality and reads analysis on the same page without a session', async () => {
    const harness = await RouterTestingHarness.create('/explorar');
    await vi.waitFor(() => {
      harness.detectChanges();
      expect(harness.routeNativeElement?.querySelectorAll('#municipio-select option').length).toBe(
        3,
      );
    });
    const select =
      harness.routeNativeElement!.querySelector<HTMLSelectElement>('#municipio-select')!;
    select.value = '05002';
    select.dispatchEvent(new Event('change'));
    await vi.waitFor(() => {
      harness.detectChanges();
      expect(harness.routeNativeElement?.querySelector('app-plot-map')).not.toBeNull();
      expect(harness.routeNativeElement?.textContent).toContain('Analizar municipio');
    });
    expect(TestBed.inject(AuthService).isAuthenticated()).toBe(false);
    expect(TestBed.inject(Router).url).toBe('/explorar');
    expect(harness.routeNativeElement?.querySelector('app-analysis')).toBeNull();
    const map = harness.routeDebugElement!.query(
      (node) => node.componentInstance instanceof PlotMapStub,
    ).componentInstance as PlotMapStub;
    map.shapeChange.emit({
      ring: [
        [-75.38, 5.92],
        [-75.37, 5.92],
        [-75.37, 5.93],
        [-75.38, 5.93],
      ],
      closed: true,
    });
    await vi.waitFor(() => {
      harness.detectChanges();
      expect(TestBed.inject(AnalysisJourneyStore).plotConfirmed()).toBe(true);
    });
    expect(TestBed.inject(AuthService).isAuthenticated()).toBe(false);
    const horizon = harness.routeNativeElement!.querySelector<HTMLSelectElement>(
      'select[aria-label="Periodo del terreno"]',
    )!;
    horizon.value = '30';
    horizon.dispatchEvent(new Event('change'));
    harness.detectChanges();
    [...harness.routeNativeElement!.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Analizar esta área'))!
      .click();
    await vi.waitFor(() => {
      harness.detectChanges();
      const sent = request.mock.calls.find(([path]) => path === 'geographic-analyses');
      expect(sent).toBeDefined();
      const body = JSON.parse(sent![1]!.body as string);
      expect(body.horizon_days).toBe(30);
      expect(body.geometry.coordinates[0][0]).toEqual([-75.38, 5.92]);
      expect(harness.routeNativeElement?.querySelector('app-analysis')).toBeNull();
    });
    expect(harness.routeNativeElement?.textContent).toContain('Crear cuenta para guardar');
    expect(request.mock.calls.some(([path]) => path.includes('/latest-analysis'))).toBe(false);
    map.shapeChange.emit(null);
    harness.detectChanges();
    expect(TestBed.inject(AnalysisJourneyStore).plot()).toBeNull();
    expect(harness.routeNativeElement?.querySelector('app-analysis')).toBeNull();
  });
  it('submits the selected municipality without drawing and restores it after clearing a plot', async () => {
    const harness = await RouterTestingHarness.create('/explorar?municipio=05002');
    await vi.waitFor(() => {
      harness.detectChanges();
      expect(harness.routeNativeElement?.textContent).toContain('Análisis de Abejorral');
      expect(harness.routeNativeElement?.textContent).toContain('Analizar municipio');
    });
    [...harness.routeNativeElement!.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.trim() === 'Analizar municipio')!
      .click();
    await vi.waitFor(() => {
      harness.detectChanges();
      expect(request.mock.calls.some(([path]) => path === 'geographic-analyses')).toBe(true);
    });
    const body = JSON.parse(
      request.mock.calls.find(([path]) => path === 'geographic-analyses')![1]!.body as string,
    );
    expect(body.geometry.type).toBe('Point');
    expect(body.geometry.coordinates[0]).toBeCloseTo(-75.35, 6);
    expect(body.geometry.coordinates[1]).toBeCloseTo(5.95, 6);
    expect(body.horizon_days).toBe(7);
    expect(TestBed.inject(AuthService).isAuthenticated()).toBe(false);
    expect(TestBed.inject(AnalysisJourneyStore).plot()).toBeNull();
    const map = harness.routeDebugElement!.query(
      (node) => node.componentInstance instanceof PlotMapStub,
    ).componentInstance as PlotMapStub;
    map.shapeChange.emit({
      ring: [
        [-75.38, 5.92],
        [-75.37, 5.92],
        [-75.37, 5.93],
      ],
      closed: false,
    });
    harness.detectChanges();
    expect(harness.routeNativeElement?.textContent).not.toContain('Analizar municipio');
    expect(
      [...harness.routeNativeElement!.querySelectorAll('button')].some((button) =>
        button.textContent?.includes('Analizar esta área'),
      ),
    ).toBe(false);
    map.shapeChange.emit(null);
    harness.detectChanges();
    expect(harness.routeNativeElement?.textContent).toContain('Analizar municipio');
    expect(request.mock.calls.filter(([path]) => path === 'geographic-analyses')).toHaveLength(1);
  });
  it('old plot and analysis links remain public while private farm management stays protected', async () => {
    const harness = await RouterTestingHarness.create('/finca/lote?municipio=05002');
    await vi.waitFor(() => {
      harness.detectChanges();
      expect(harness.routeNativeElement?.querySelector('app-plot-map')).not.toBeNull();
    });
    expect(TestBed.inject(Router).url).toBe('/explorar?municipio=05002');
    await harness.navigateByUrl('/explorar?municipio=05615');
    await vi.waitFor(() => {
      harness.detectChanges();
      expect(TestBed.inject(AnalysisJourneyStore).municipality()?.code).toBe('05615');
    });
    await harness.navigateByUrl('/finca/analisis');
    expect(TestBed.inject(Router).url).toBe('/explorar');
    await harness.navigateByUrl('/fincas');
    expect(TestBed.inject(Router).url).toBe('/acceso?volver=%2Ffincas');
  });
  it('skips the login and registration forms for legacy delimitation links without signing in', async () => {
    const harness = await RouterTestingHarness.create();
    for (const entry of ['acceso', 'registro', 'login']) {
      await harness.navigateByUrl(
        '/' + entry + '?volver=' + encodeURIComponent('/finca/lote?municipio=05002'),
      );
      await vi.waitFor(() => {
        harness.detectChanges();
        expect(harness.routeNativeElement?.querySelector('app-plot-map')).not.toBeNull();
      });
      expect(TestBed.inject(Router).url).toBe('/explorar?municipio=05002#lote');
      expect(TestBed.inject(AuthService).isAuthenticated()).toBe(false);
      expect(harness.routeNativeElement?.querySelector('app-login, app-register')).toBeNull();
    }
    await harness.navigateByUrl('/fincas');
    expect(TestBed.inject(Router).url).toBe('/acceso?volver=%2Ffincas');
  });
  it('signed-in users keep Exploration for old dashboard links and start a clean consultation in place', async () => {
    await TestBed.inject(AuthService).login({
      email: 'ana@correo.co',
      password: 'clave-de-prueba-larga',
    });
    const harness = await RouterTestingHarness.create('/panel?municipio=05002');
    await vi.waitFor(() => {
      harness.detectChanges();
      expect(harness.routeNativeElement?.querySelector('app-plot-map')).not.toBeNull();
    });
    expect(TestBed.inject(Router).url).toBe('/explorar?municipio=05002');
    const oldAnalysis = harness.routeNativeElement!.querySelector('app-geographic-analysis');
    const button = [
      ...harness.routeNativeElement!.querySelectorAll<HTMLButtonElement>('button'),
    ].find((item) => item.textContent?.includes('Nuevo análisis'))!;
    button.click();
    await vi.waitFor(() => {
      harness.detectChanges();
      expect(TestBed.inject(Router).url).toBe('/explorar');
      expect(harness.routeNativeElement!.querySelector('app-plot-map')).toBeNull();
      expect(harness.routeNativeElement!.querySelector('app-geographic-analysis')).not.toBe(
        oldAnalysis,
      );
    });
    expect(TestBed.inject(AnalysisJourneyStore).municipality()).toBeNull();
    expect(TestBed.inject(AuthService).isAuthenticated()).toBe(true);
    await harness.navigateByUrl('/analisis');
    expect(TestBed.inject(Router).url).toBe('/explorar#resultados');
    expect(harness.routeNativeElement!.querySelector('app-geographic-analysis')).not.toBeNull();
  });
  it('late municipality responses cannot replace the newest map selection', async () => {
    let resolveFirst!: (value: ReturnType<typeof municipal>) => void;
    municipality.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveFirst = resolve;
        }),
    );
    const harness = await RouterTestingHarness.create('/explorar?municipio=05002');
    await vi.waitFor(() => {
      harness.detectChanges();
      expect(municipality).toHaveBeenCalledWith('05002');
    });
    const resultsWhileLoading =
      harness.routeNativeElement!.querySelector('app-geographic-analysis');
    expect(resultsWhileLoading).not.toBeNull();
    expect(request.mock.calls.some(([path]) => path.includes('/latest-analysis'))).toBe(false);
    const select =
      harness.routeNativeElement!.querySelector<HTMLSelectElement>('#municipio-select')!;
    select.value = '05615';
    select.dispatchEvent(new Event('change'));
    await vi.waitFor(() => {
      harness.detectChanges();
      expect(TestBed.inject(AnalysisJourneyStore).municipality()?.code).toBe('05615');
      expect(harness.routeNativeElement?.querySelector('app-plot-map')).not.toBeNull();
    });
    resolveFirst(municipal());
    await Promise.resolve();
    harness.detectChanges();
    expect(
      harness.routeDebugElement
        ?.query((node) => node.componentInstance instanceof PlotMapStub)
        ?.componentInstance.municipality().code,
    ).toBe('05615');
    expect(harness.routeNativeElement!.querySelector('app-geographic-analysis')).toBe(
      resultsWhileLoading,
    );
  });
});
