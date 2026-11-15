import { displayName, featuresBBox, geometryBBox, normalizeName } from './geo-utils';
import { BoundaryFeature } from '../models/geo.models';

describe('geo-utils', () => {
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
      geometry: { type: 'Polygon', coordinates: [[[-76, 5], [-75, 5], [-75, 6], [-76, 6], [-76, 5]]] },
    };
    const multi: BoundaryFeature<unknown> = {
      type: 'Feature',
      id: 2,
      properties: {},
      geometry: {
        type: 'MultiPolygon',
        coordinates: [
          [[[-74, 4], [-73, 4], [-73, 5], [-74, 4]]],
          [[[-72, 7], [-71, 7], [-71, 8], [-72, 7]]],
        ],
      },
    };
    expect(geometryBBox(square.geometry)).toEqual([-76, 5, -75, 6]);
    expect(geometryBBox(multi.geometry)).toEqual([-74, 4, -71, 8]);
    expect(featuresBBox([square, multi])).toEqual([-76, 4, -71, 8]);
  });
});
