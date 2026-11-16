/**
 * Shared MapLibre bootstrap for every map in the app.
 *
 * - MapLibre (≈250 kB gzipped) is imported lazily, only by pages that show a map.
 * - Its stylesheet and web worker are served as static assets (see angular.json):
 *   MapLibre 6 resolves its worker next to its own module URL, which no longer
 *   exists once bundled, so the worker URL is set explicitly.
 */
const WORKER_PATH = 'vendor/maplibre/maplibre-gl-worker.mjs';
const STYLESHEET_PATH = 'vendor/maplibre/maplibre-gl.css';

export type MapLibreModule = typeof import('maplibre-gl');

let loading: Promise<MapLibreModule> | undefined;

export class WebGLUnavailableError extends Error {}

export function supportsWebGL(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return !!(canvas.getContext('webgl2') || canvas.getContext('webgl'));
  } catch {
    return false;
  }
}

/** Loads MapLibre once per session. Throws WebGLUnavailableError when maps cannot render. */
export function loadMapLibre(): Promise<MapLibreModule> {
  if (!supportsWebGL()) {
    return Promise.reject(new WebGLUnavailableError('WebGL no disponible'));
  }
  ensureStylesheet();
  return (loading ??= import('maplibre-gl')
    .then((m) => {
      const workerUrl = new URL(WORKER_PATH, document.baseURI);
      workerUrl.searchParams.set('v', m.getVersion());
      m.setWorkerUrl(workerUrl.href);
      return m;
    })
    .catch((err) => {
      loading = undefined;
      throw err;
    }));
}

function ensureStylesheet(): void {
  if (document.querySelector('link[data-maplibre-css]')) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = STYLESHEET_PATH;
  link.dataset['maplibreCss'] = '';
  document.head.appendChild(link);
}

/** Spanish strings for MapLibre's built-in controls. */
export const MAP_LOCALE: Record<string, string> = {
  'Map.Title': 'Mapa interactivo',
  'NavigationControl.ZoomIn': 'Acercar',
  'NavigationControl.ZoomOut': 'Alejar',
  'NavigationControl.ResetBearing': 'Restablecer orientación al norte',
  'GlobeControl.Enable': 'Ver como globo',
  'GlobeControl.Disable': 'Ver como mapa plano',
  'AttributionControl.ToggleAttribution': 'Mostrar u ocultar atribuciones',
  'AttributionControl.MapFeedback': 'Comentarios sobre el mapa',
  'ScaleControl.Kilometers': 'km',
  'ScaleControl.Meters': 'm',
  'LogoControl.Title': 'Logotipo de MapLibre',
};
