import {
  displayName,
  featuresBBox,
  geometryBBox,
  normalizeName,
  municipalityReferencePoint,
} from './geo-utils';
import { BoundaryFeature } from '../models/geo.models';
import { pointInPolygons, LngLat } from '../../../shared/geo/geodesy';

describe('geo-utils', () => {
  it('uses a verified municipal reference point and falls back inside a polygon with a hole', () => {
    const rings: LngLat[][] = [
      [
        [0, 0],
        [10, 0],
        [10, 10],
        [0, 10],
        [0, 0],
      ],
      [
        [4, 4],
        [6, 4],
        [6, 6],
        [4, 6],
        [4, 4],
      ],
    ];
    const geometry = { type: 'Polygon' as const, coordinates: rings };
    expect(municipalityReferencePoint(geometry, [2, 2])).toEqual([2, 2]);
    const fallback = municipalityReferencePoint(geometry, [5, 5]);
    expect(fallback).not.toBeNull();
    expect(pointInPolygons(fallback!, [rings])).toBe(true);
    expect(municipalityReferencePoint(geometry, [NaN, NaN])).toEqual(fallback);
  });
  it('finds an interior point for a concave municipality or a multipolygon', () => {
    const ring: LngLat[] = [
      [0, 0],
      [4, 0],
      [4, 1],
      [1, 1],
      [1, 4],
      [0, 4],
      [0, 0],
    ];
    const point = municipalityReferencePoint({ type: 'Polygon', coordinates: [ring] });
    expect(pointInPolygons(point!, [[ring]])).toBe(true);
    const multi = { type: 'MultiPolygon' as const, coordinates: [[], [ring]] };
    expect(pointInPolygons(municipalityReferencePoint(multi)!, [[ring]])).toBe(true);
    expect(municipalityReferencePoint({ type: 'MultiPolygon', coordinates: [] })).toBeNull();
  });
  it('title-cases DANE names keeping Spanish particles lower case', () => {
    expect(displayName('LA UNIÓN')).toBe('La Unión');
    expect(displayName('SAN JOSÉ DE LA MONTAÑA')).toBe('San José de la Montaña');
    expect(displayName('EL CARMEN DE VIBORAL')).toBe('El Carmen de Viboral');
    expect(displayName('BOGOTÁ, D.C.')).toBe('Bogotá, D.C.');
  });

  it('normalizes names ignoring accents and case', () => {
    expect(normalizeName('  Medellín ')).toBe('medellin');
    expect(normalizeName('LA UNIÓN')).toBe(normalizeName('la union'));
  });

  it('computes bounding boxes for polygons and multipolygons', () => {
    const square: BoundaryFeature<unknown> = {
      type: 'Feature',
      id: 1,
      properties: {},
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [-76, 5],
            [-75, 5],
            [-75, 6],
            [-76, 6],
            [-76, 5],
          ],
        ],
      },
    };
    const multi: BoundaryFeature<unknown> = {
      type: 'Feature',
      id: 2,
      properties: {},
      geometry: {
        type: 'MultiPolygon',
        coordinates: [
          [
            [
              [-74, 4],
              [-73, 4],
              [-73, 5],
              [-74, 4],
            ],
          ],
          [
            [
              [-72, 7],
              [-71, 7],
              [-71, 8],
              [-72, 7],
            ],
          ],
        ],
      },
    };
    expect(geometryBBox(square.geometry)).toEqual([-76, 5, -75, 6]);
    expect(geometryBBox(multi.geometry)).toEqual([-74, 4, -71, 8]);
    expect(featuresBBox([square, multi])).toEqual([-76, 4, -71, 8]);
  });
});
