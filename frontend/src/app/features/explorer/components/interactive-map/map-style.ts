import type { AddLayerObject, MapOptions } from 'maplibre-gl';
import { NASA_BLUE_MARBLE, SENTINEL2_CLOUDLESS } from '../../../../shared/map/imagery';

/**
 * Cartographic definition of the explorer map: sources, layers and colours.
 * Pure data — no component state — so styling can be reviewed in one place.
 *
 * Imagery transition: NASA Blue Marble (GIBS) for the globe and country views,
 * cross-fading into Sentinel-2 cloudless (EOX, 10 m) at department/municipal zoom.
 * Both are visual context only. Boundaries: DANE MGN 2025, added at runtime.
 * Glyphs (label fonts): OpenFreeMap public font server, no API key.
 */

export type MapStyle = Exclude<MapOptions['style'], string | undefined>;

export const SOURCE = {
  imagery: NASA_BLUE_MARBLE.id,
  sentinel: SENTINEL2_CLOUDLESS.id,
  departments: 'dane-departments',
  departmentLabels: 'dane-department-labels',
  municipalities: 'dane-municipalities',
  municipalityLabels: 'dane-municipality-labels',
  regionLabel: 'pilot-region-label',
} as const;

export const LAYER = {
  background: 'background',
  imagery: 'imagery',
  sentinel: 'sentinel',
  departmentFill: 'department-fill',
  departmentLine: 'department-line',
  departmentLabel: 'department-label',
  exploreLabel: 'explore-label',
  municipalityFill: 'municipality-fill',
  municipalityLineOther: 'municipality-line-other',
  municipalityLinePilot: 'municipality-line-pilot',
  municipalityLabel: 'municipality-label',
  municipalityLabelOther: 'municipality-label-other',
  regionLabel: 'region-label',
} as const;

/** Zoom at which municipal polygons start to appear (and are lazily loaded). */
export const MUNICIPAL_MIN_ZOOM = 5.8;

export const ATTRIBUTION = {
  boundaries:
    'Límites: <a href="https://geoportal.dane.gov.co/" target="_blank" rel="noopener">DANE – MGN 2025</a>; región piloto: Gobernación de Antioquia',
  glyphs:
    'Tipografía del mapa: <a href="https://openfreemap.org/" target="_blank" rel="noopener">OpenFreeMap</a>',
} as const;

/** Map palette (hex literals: WebGL paint cannot read CSS custom properties). */
export const MAP_COLOR = {
  ocean: '#183d32',
  boundary: '#f5f4ec',
  explore: '#a8c686',
  exploreOutline: '#e9f7e4',
  pilot: '#5fae80',
  selected: '#d5a85b',
  outside: '#f5f4ec',
} as const;

export function baseStyle(): MapStyle {
  return {
    version: 8,
    projection: { type: 'globe' },
    glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
    sky: { 'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1, 5, 1, 7, 0] },
    sources: {
      [SOURCE.imagery]: {
        type: 'raster',
        tiles: NASA_BLUE_MARBLE.tiles,
        tileSize: NASA_BLUE_MARBLE.tileSize,
        maxzoom: NASA_BLUE_MARBLE.maxzoom,
        attribution: NASA_BLUE_MARBLE.attribution,
      },
      [SOURCE.sentinel]: {
        type: 'raster',
        tiles: SENTINEL2_CLOUDLESS.tiles,
        tileSize: SENTINEL2_CLOUDLESS.tileSize,
        maxzoom: SENTINEL2_CLOUDLESS.maxzoom,
        attribution: SENTINEL2_CLOUDLESS.attribution,
      },
    },
    layers: [
      { id: LAYER.background, type: 'background', paint: { 'background-color': MAP_COLOR.ocean } },
      {
        id: LAYER.imagery,
        type: 'raster',
        source: SOURCE.imagery,
        maxzoom: 9,
        paint: {
          'raster-opacity': ['interpolate', ['linear'], ['zoom'], 0, 1, 6, 0.85, 8.5, 0],
          'raster-saturation': -0.2,
          'raster-fade-duration': 150,
        },
      },
      {
        // Only requested from zoom 6.5, so the globe never downloads 10 m tiles.
        id: LAYER.sentinel,
        type: 'raster',
        source: SOURCE.sentinel,
        minzoom: 6.5,
        paint: {
          'raster-opacity': ['interpolate', ['linear'], ['zoom'], 6.5, 0, 7.8, 0.8, 11, 1],
          'raster-saturation': 0,
          'raster-fade-duration': 150,
        },
      },
    ],
  };
}

// Layer objects below are cast via `unknown`: MapLibre's expression typings cannot
// infer reusable expression fragments (hovered, selected…). MapLibre validates every
// layer at runtime and reports invalid expressions in the console.
const hovered = ['boolean', ['feature-state', 'hover'], false];
const selected = ['boolean', ['feature-state', 'selected'], false];
const isExplore = ['get', 'isPilot'];
const isPilot = ['==', ['get', 'pilot'], true];
const layer = (spec: object) => spec as unknown as AddLayerObject;

/** A dark casing keeps pale boundaries readable over clouds, cities and imagery. */
function outlinedBoundaries(layers: AddLayerObject[]): AddLayerObject[] {
  return layers.flatMap((spec) => {
    if (spec.type !== 'line') return [spec];
    const paint = (spec.paint ?? {}) as Record<string, unknown>;
    const width = paint['line-width'] ?? 1;
    // MapLibre requires zoom interpolation at the top level of a paint expression.
    const casingWidth =
      Array.isArray(width) && width[0] === 'interpolate'
        ? width.map((value, index) => (index >= 4 && index % 2 === 0 ? ['+', value, 2.5] : value))
        : ['+', width, 2.5];
    return [
      layer({
        ...spec,
        id: `${spec.id}-casing`,
        paint: {
          ...paint,
          'line-color': '#10251d',
          'line-opacity': 0.85,
          'line-width': casingWidth,
        },
      }),
      spec,
    ];
  });
}

export function departmentLayers(): AddLayerObject[] {
  return outlinedBoundaries([
    layer({
      id: LAYER.departmentFill,
      type: 'fill',
      source: SOURCE.departments,
      paint: {
        'fill-color': [
          'case',
          selected,
          MAP_COLOR.selected,
          isExplore,
          MAP_COLOR.explore,
          MAP_COLOR.boundary,
        ],
        // Antioquia (explorable) is highlighted at country scale and fades out as
        // municipal polygons take over.
        'fill-opacity': [
          'interpolate',
          ['linear'],
          ['zoom'],
          2,
          [
            'case',
            selected,
            0.5,
            isExplore,
            ['case', hovered, 0.75, 0.55],
            ['case', hovered, 0.28, 0.08],
          ],
          6,
          [
            'case',
            selected,
            0.35,
            isExplore,
            ['case', hovered, 0.45, 0.3],
            ['case', hovered, 0.22, 0.05],
          ],
          7.5,
          ['case', selected, 0.12, isExplore, 0, ['case', hovered, 0.18, 0.04]],
          12,
          0,
        ],
      },
    }),
    layer({
      id: LAYER.departmentLine,
      type: 'line',
      source: SOURCE.departments,
      layout: { 'line-join': 'round' },
      paint: {
        'line-color': [
          'case',
          selected,
          '#ffffff',
          isExplore,
          MAP_COLOR.exploreOutline,
          MAP_COLOR.boundary,
        ],
        'line-opacity': 1,
        'line-width': [
          'interpolate',
          ['linear'],
          ['zoom'],
          2,
          ['case', selected, 2, isExplore, 1.8, 1.1],
          6,
          ['case', selected, 3, isExplore, 2.6, 1.6],
          9,
          ['case', selected, 3.5, isExplore, 3.2, 2],
        ],
      },
    }),
  ]);
}

export function departmentLabelLayers(): AddLayerObject[] {
  const textBase = {
    'text-font': ['Noto Sans Bold'],
    'text-letter-spacing': 0.08,
    'text-max-width': 8,
  };
  return [
    layer({
      id: LAYER.departmentLabel,
      type: 'symbol',
      source: SOURCE.departmentLabels,
      minzoom: 4.6,
      maxzoom: 7.4,
      filter: ['!', isExplore],
      layout: { ...textBase, 'text-field': ['get', 'labelName'], 'text-size': 10 },
      paint: {
        'text-color': '#e8ece6',
        'text-halo-color': 'rgba(11,29,23,0.85)',
        'text-halo-width': 1.2,
      },
    }),
    layer({
      id: LAYER.exploreLabel,
      type: 'symbol',
      source: SOURCE.departmentLabels,
      minzoom: 2.6,
      maxzoom: 5.8,
      filter: isExplore,
      layout: {
        ...textBase,
        'text-field': [
          'format',
          ['upcase', ['get', 'labelName']],
          { 'font-scale': 1 },
          '\n',
          {},
          'Área de exploración',
          { 'font-scale': 0.78, 'text-font': ['literal', ['Noto Sans Regular']] },
        ],
        'text-size': ['interpolate', ['linear'], ['zoom'], 3, 12, 5.5, 15],
        'text-allow-overlap': true,
      },
      paint: {
        'text-color': '#ffffff',
        'text-halo-color': 'rgba(11,29,23,0.9)',
        'text-halo-width': 1.6,
      },
    }),
  ];
}

export function municipalityLayers(): AddLayerObject[] {
  const fade = (value: unknown) => [
    'interpolate',
    ['linear'],
    ['zoom'],
    MUNICIPAL_MIN_ZOOM,
    0.7,
    7,
    value,
  ];
  return outlinedBoundaries([
    layer({
      id: LAYER.municipalityFill,
      type: 'fill',
      source: SOURCE.municipalities,
      minzoom: MUNICIPAL_MIN_ZOOM,
      paint: {
        'fill-color': [
          'case',
          selected,
          MAP_COLOR.selected,
          isPilot,
          MAP_COLOR.pilot,
          MAP_COLOR.outside,
        ],
        // Preserve regional highlights at overview scale; reveal imagery when zooming in.
        'fill-opacity': [
          'interpolate',
          ['linear'],
          ['zoom'],
          MUNICIPAL_MIN_ZOOM,
          0,
          7,
          ['case', selected, 0.5, hovered, 0.45, isPilot, 0.3, 0.06],
          12,
          ['case', selected, 0.06, hovered, 0.04, isPilot, 0.02, 0],
          14,
          ['case', selected, 0.02, hovered, 0.01, 0],
        ],
      },
    }),
    // Outside the pilot region: thin dashed outline (status readable without colour).
    layer({
      id: LAYER.municipalityLineOther,
      type: 'line',
      source: SOURCE.municipalities,
      minzoom: MUNICIPAL_MIN_ZOOM,
      filter: ['!', isPilot],
      layout: { 'line-join': 'round' },
      paint: {
        'line-color': ['case', selected, '#ffffff', MAP_COLOR.boundary],
        'line-opacity': fade(['case', selected, 1, hovered, 1, 0.9]),
        'line-dasharray': [3, 2],
        'line-width': [
          'interpolate',
          ['linear'],
          ['zoom'],
          6,
          ['case', selected, 2.5, hovered, 2, 1.1],
          10,
          ['case', selected, 4, hovered, 2.6, 1.6],
        ],
      },
    }),
    // Pilot region: solid, brighter outline.
    layer({
      id: LAYER.municipalityLinePilot,
      type: 'line',
      source: SOURCE.municipalities,
      minzoom: MUNICIPAL_MIN_ZOOM,
      filter: isPilot,
      layout: { 'line-join': 'round' },
      paint: {
        'line-color': ['case', selected, '#ffffff', '#e9f7e4'],
        'line-opacity': fade(1),
        'line-width': [
          'interpolate',
          ['linear'],
          ['zoom'],
          6,
          ['case', selected, 3, hovered, 2.3, 1.5],
          10,
          ['case', selected, 4.5, hovered, 3.2, 2.2],
        ],
      },
    }),
  ]);
}

/** Pilot municipalities are named earlier (and bolder) than the rest. */
export function municipalityLabelLayers(): AddLayerObject[] {
  const base = (id: string, minzoom: number, pilot: boolean) =>
    layer({
      id,
      type: 'symbol',
      source: SOURCE.municipalityLabels,
      minzoom,
      filter: pilot ? isPilot : ['!', isPilot],
      layout: {
        'text-field': ['get', 'labelName'],
        'text-font': [pilot ? 'Noto Sans Bold' : 'Noto Sans Regular'],
        'text-size': ['interpolate', ['linear'], ['zoom'], 8, 10, 11, 13],
        'text-max-width': 7,
        'text-optional': true,
      },
      paint: {
        'text-color': '#ffffff',
        'text-halo-color': 'rgba(11,29,23,0.85)',
        'text-halo-width': 1.3,
      },
    });
  return [base(LAYER.municipalityLabel, 7.6, true), base(LAYER.municipalityLabelOther, 8.6, false)];
}

export function regionLabelLayer(): AddLayerObject {
  return layer({
    id: LAYER.regionLabel,
    type: 'symbol',
    source: SOURCE.regionLabel,
    minzoom: 5.6,
    maxzoom: 8.6,
    layout: {
      'text-field': [
        'format',
        ['upcase', ['get', 'name']],
        { 'font-scale': 1 },
        '\n',
        {},
        'Región piloto',
        { 'font-scale': 0.78, 'text-font': ['literal', ['Noto Sans Regular']] },
      ],
      'text-font': ['Noto Sans Bold'],
      'text-size': ['interpolate', ['linear'], ['zoom'], 6, 13, 8, 16],
      'text-letter-spacing': 0.08,
      'text-allow-overlap': true,
    },
    paint: {
      'text-color': '#ffffff',
      'text-halo-color': 'rgba(11,29,23,0.92)',
      'text-halo-width': 1.8,
    },
  });
}
