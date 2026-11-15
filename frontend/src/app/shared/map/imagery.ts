/**
 * Background imagery providers. MapLibre only renders; the pixels come from these.
 * Both are free, need no API key or account, and send CORS headers.
 *
 * Neither is an analytical layer: they help users orient themselves and draw.
 */
export interface ImageryProvider {
  id: string;
  name: string;
  tiles: string[];
  tileSize: number;
  /** Highest native tile level; MapLibre stretches tiles beyond it. */
  maxzoom: number;
  /** Approximate ground resolution of the source pixels. */
  resolution: string;
  /** What it shows in time. */
  temporal: string;
  license: string;
  attribution: string;
  limitation: string;
}

/** Camera limit for local views; zoom above the source level magnifies existing pixels. */
export const LOCAL_MAP_MAX_ZOOM = 17;

/** NASA GIBS — Blue Marble shaded relief & bathymetry. Globe / country scale. */
export const NASA_BLUE_MARBLE: ImageryProvider = {
  id: 'nasa-gibs-blue-marble',
  name: 'NASA Blue Marble (NASA GIBS)',
  tiles: [
    'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg',
  ],
  tileSize: 256,
  maxzoom: 8,
  resolution: '≈ 500 m (nivel máximo 8)',
  temporal: 'Composición estática sin nubes',
  license: 'Datos abiertos de la NASA (política de uso de datos de NASA Earthdata)',
  attribution:
    'Imagen global: NASA Blue Marble vía <a href="https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/gibs-api" target="_blank" rel="noopener">NASA GIBS</a> (ESDIS)',
  limitation: 'Solo sirve como contexto a escala global o nacional; no permite ver fincas.',
};

/**
 * EOX Sentinel-2 cloudless 2025 — annual cloud-free mosaic of Copernicus Sentinel-2.
 * Licence (from the provider's WMTS capabilities): CC BY-NC-SA 4.0 — free for
 * NON-COMMERCIAL use with attribution; commercial use requires an EOX licence.
 */
export const SENTINEL2_CLOUDLESS: ImageryProvider = {
  id: 'eox-s2cloudless-2025',
  name: 'Sentinel-2 cloudless 2025 (EOX)',
  tiles: ['https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2025_3857/default/g/{z}/{y}/{x}.jpg'],
  tileSize: 256,
  maxzoom: 14,
  resolution: '10 m por píxel',
  temporal: 'Mosaico anual 2025 sin nubes (cada zona puede provenir de fechas distintas del año)',
  license: 'CC BY-NC-SA 4.0 (uso no comercial con atribución)',
  attribution:
    '<a href="https://s2maps.eu" target="_blank" rel="noopener">Sentinel-2 cloudless – s2maps.eu</a> by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2025)',
  limitation:
    'Con 10 m por píxel se distinguen lotes, vías y construcciones, pero no linderos finos: el contorno que dibujes es aproximado.',
};
