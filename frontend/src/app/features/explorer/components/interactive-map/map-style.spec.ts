import { validateStyleMin, type StyleSpecification } from '@maplibre/maplibre-gl-style-spec';
import {
  baseStyle,
  departmentLayers,
  departmentLabelLayers,
  municipalityLayers,
  municipalityLabelLayers,
  regionLabelLayer,
  SOURCE,
} from './map-style';

describe('Territorial boundary rendering', () => {
  it('accepts all boundary and casing expressions in the MapLibre renderer', () => {
    const style = baseStyle();
    const data = { type: 'FeatureCollection' as const, features: [] };
    for (const source of [
      SOURCE.departments,
      SOURCE.departmentLabels,
      SOURCE.municipalities,
      SOURCE.municipalityLabels,
      SOURCE.regionLabel,
    ]) {
      style.sources[source] = { type: 'geojson', data };
    }
    style.layers = [
      ...style.layers,
      ...departmentLayers(),
      ...departmentLabelLayers(),
      ...municipalityLayers(),
      ...municipalityLabelLayers(),
      regionLabelLayer(),
    ] as StyleSpecification['layers'];
    expect(validateStyleMin(style as StyleSpecification).map((error) => error.message)).toEqual([]);
  });
});
