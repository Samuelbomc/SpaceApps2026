import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { GeoBoundariesService } from './geo-boundaries.service';
import { PILOT_TERRITORY } from '../../../core/catalog/pilot-territory';

const feature = (id: number, code: string, name: string) => ({
  type: 'Feature',
  id,
  properties: {
    code,
    name,
    departmentCode: '05',
    type: 'MUNICIPIO',
    areaKm2: 10,
    labelLon: -75,
    labelLat: 6,
  },
  geometry: {
    type: 'Polygon',
    coordinates: [
      [
        [-76, 5],
        [-75, 5],
        [-75, 6],
        [-76, 5],
      ],
    ],
  },
});

describe('GeoBoundariesService', () => {
  let service: GeoBoundariesService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(GeoBoundariesService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads municipalities once and returns sorted display-ready summaries', async () => {
    const first = service.municipalitySummaries();
    const second = service.municipalitySummaries();
    http.expectOne(PILOT_TERRITORY.boundaries.municipalities).flush({
      type: 'FeatureCollection',
      features: [
        feature(5400, '05400', 'LA UNIÓN'),
        feature(5001, '05001', 'MEDELLÍN'),
        feature(5002, '05002', 'ABEJORRAL'),
      ],
    });
    const list = await first;
    await second; // served from the same cached request (expectOne would fail otherwise)
    expect(list.map((m) => m.name)).toEqual(['Abejorral', 'La Unión', 'Medellín']);
    expect(list[1].bbox).toEqual([-76, 5, -75, 6]);
  });

  it('does not cache failures, so the user can retry', async () => {
    const failed = service.departments();
    http
      .expectOne(PILOT_TERRITORY.boundaries.departments)
      .flush('down', { status: 503, statusText: 'Unavailable' });
    await expect(failed).rejects.toBeTruthy();

    const retry = service.departments();
    http
      .expectOne(PILOT_TERRITORY.boundaries.departments)
      .flush({ type: 'FeatureCollection', features: [] });
    await expect(retry).resolves.toEqual({ type: 'FeatureCollection', features: [] });
  });
});
