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
  const request = vi.fn(async (path: string) =>
    path === 'automation/refresh'
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
      expect(harness.routeNativeElement?.textContent).toContain('Faltan datos recientes');
    });
    expect(TestBed.inject(AuthService).isAuthenticated()).toBe(false);
    expect(TestBed.inject(Router).url).toBe('/explorar');
    expect(harness.routeNativeElement?.querySelector('app-analysis')).not.toBeNull();
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
    map.shapeChange.emit(null);
    harness.detectChanges();
    expect(TestBed.inject(AnalysisJourneyStore).plot()).toBeNull();
    const horizon = harness.routeNativeElement!.querySelector<HTMLSelectElement>(
      'select[aria-label="Plazo"]',
    )!;
    horizon.value = '30';
    horizon.dispatchEvent(new Event('change'));
    await vi.waitFor(() => {
      harness.detectChanges();
      expect(request.mock.calls.some(([path]) => path.includes('horizon_days=30'))).toBe(true);
    });
    expect(harness.routeNativeElement?.textContent).toContain('Crear cuenta para guardar');
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
    const oldAnalysis = harness.routeNativeElement!.querySelector('app-analysis');
    const button = [
      ...harness.routeNativeElement!.querySelectorAll<HTMLButtonElement>('button'),
    ].find((item) => item.textContent?.includes('Nuevo análisis'))!;
    button.click();
    await vi.waitFor(() => {
      harness.detectChanges();
      expect(TestBed.inject(Router).url).toBe('/explorar');
      expect(harness.routeNativeElement!.querySelector('app-plot-map')).toBeNull();
      expect(harness.routeNativeElement!.querySelector('app-analysis')).not.toBe(oldAnalysis);
    });
    expect(TestBed.inject(AnalysisJourneyStore).municipality()).toBeNull();
    expect(TestBed.inject(AuthService).isAuthenticated()).toBe(true);
    await harness.navigateByUrl('/analisis');
    expect(TestBed.inject(Router).url).toBe('/explorar#resultados');
    expect(harness.routeNativeElement!.querySelector('app-analysis')).not.toBeNull();
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
    const resultsWhileLoading = harness.routeNativeElement!.querySelector('app-analysis');
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
    expect(harness.routeNativeElement!.querySelector('app-analysis')).toBe(resultsWhileLoading);
  });
});
