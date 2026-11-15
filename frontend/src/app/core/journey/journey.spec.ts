import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AuthGateway } from '../auth/auth-gateway';
import { MockAuthGateway } from '../../testing/mock-auth-gateway';
import { AuthService } from '../auth/auth.service';
import { AnalysisJourneyStore } from './analysis-journey.store';
import { JOURNEY } from './journey';
import { PlotSelection } from './journey.models';
import { JourneySteps } from '../../shared/ui/journey-steps/journey-steps';
import { PILOT_TERRITORY } from '../catalog/pilot-territory';

const plotIn = (code: string): PlotSelection => ({
  municipalityCode: code,
  geometry: {
    type: 'Polygon',
    coordinates: [
      [
        [-75.36, 5.97],
        [-75.35, 5.97],
        [-75.35, 5.98],
        [-75.36, 5.97],
      ],
    ],
  },
  areaM2: 5000,
  perimeterM: 300,
  centroid: [-75.355, 5.975],
  vertexCount: 3,
  withinMunicipality: 'inside',
  drawnAt: '2026-11-15T00:00:00Z',
});

describe('Analysis journey', () => {
  let store: AnalysisJourneyStore;

  beforeEach(async () => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthGateway, useClass: MockAuthGateway }],
    });
    store = TestBed.inject(AnalysisJourneyStore);
    await TestBed.inject(AuthService).login({ email: 'ana@correo.co', password: '12345678' });
  });

  it('has five steps, with municipality and plot merged into one', () => {
    expect(JOURNEY.map((s) => s.id)).toEqual([
      'cuenta',
      'explorar',
      'lote',
      'caracterizacion',
      'analisis',
    ]);
    expect(JOURNEY[2].label).toBe('Municipio y lote');
    expect(JOURNEY.some((s) => (s.id as string) === 'municipio')).toBe(false);
  });

  it('pilot region holds exactly the 23 verified Oriente municipalities, with a cited source', () => {
    const r = PILOT_TERRITORY.pilotRegion;
    expect(r.municipalityCodes.length).toBe(23);
    expect(new Set(r.municipalityCodes).size).toBe(23);
    expect(r.municipalityCodes.every((c) => /^05\d{3}$/.test(c))).toBe(true);
    expect(
      r.membershipSource?.urls.every((u) => u.startsWith('https://www.antioquia.gov.co/')),
    ).toBe(true);
  });

  it('derives support from the verified list and sets department and region', () => {
    store.selectMunicipality({ code: '05400', name: 'La Unión' });
    expect(store.municipality()?.supported).toBe(true);
    expect(store.department()).toEqual({ code: '05', name: 'Antioquia' });
    expect(store.region()?.id).toBe('oriente-antioqueno');

    store.selectMunicipality({ code: '05001', name: 'Medellín' }); // Valle de Aburrá
    expect(store.municipality()?.supported).toBe(false);
    expect(store.region()).toBeNull();
  });

  it('only confirms a plot in a supported municipality, matching the selection', () => {
    store.selectMunicipality({ code: '05001', name: 'Medellín' });
    store.setPlot(plotIn('05001'));
    expect(store.confirmPlot()).toBe(false);

    store.selectMunicipality({ code: '05400', name: 'La Unión' });
    expect(store.plot()).toBeNull(); // changing municipality discarded the plot
    store.setPlot(plotIn('05615')); // plot from another municipality
    expect(store.confirmPlot()).toBe(false);

    store.setPlot(plotIn('05400'));
    expect(store.confirmPlot()).toBe(true);
    expect(store.nextStep()).toBe('caracterizacion');
  });

  it('editing or changing municipality un-confirms the plot', () => {
    store.selectMunicipality({ code: '05400', name: 'La Unión' });
    store.setPlot(plotIn('05400'));
    store.confirmPlot();
    store.setPlot({ ...plotIn('05400'), areaM2: 6000 });
    expect(store.plotConfirmed()).toBe(false);

    store.confirmPlot();
    store.selectMunicipality({ code: '05615', name: 'Rionegro' });
    expect(store.plotConfirmed()).toBe(false);
    expect(store.plot()).toBeNull();
  });

  it('stepper shows five steps and marks current and completed ones accessibly', async () => {
    store.selectMunicipality({ code: '05400', name: 'La Unión' });
    const fixture = TestBed.createComponent(JourneySteps);
    fixture.componentRef.setInput('current', 'lote');
    await fixture.whenStable();
    const items = (fixture.nativeElement as HTMLElement).querySelectorAll('li');

    expect(items.length).toBe(5);
    expect(items[0].classList).toContain('step--done');
    expect(items[1].classList).toContain('step--done');
    expect(items[2].querySelector('a')?.getAttribute('aria-current')).toBe('step');
    expect(items[2].textContent).toContain('Municipio y lote');
    expect(items[3].classList).toContain('step--upcoming');
  });
});
