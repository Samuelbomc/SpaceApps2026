/**
 * The single user journey of the platform, in order.
 * Labels, routes and descriptions live here so the stepper, the home page
 * and the dashboard all describe the same flow.
 *
 * Municipality selection and plot delimitation are ONE step ('lote'): choosing a
 * supported municipality opens the satellite map directly.
 */
export type JourneyStepId = 'cuenta' | 'explorar' | 'lote' | 'caracterizacion' | 'analisis';

export interface JourneyStep {
  id: JourneyStepId;
  label: string;
  path: string;
  summary: string;
}

export const PLOT_STEP_PATH = '/finca/lote';

export const JOURNEY: readonly JourneyStep[] = [
  {
    id: 'cuenta',
    label: 'Cuenta',
    path: '/acceso',
    summary: 'Inicia sesión para guardar tus fincas y volver a tus análisis.',
  },
  {
    id: 'explorar',
    label: 'Explorar',
    path: '/explorar',
    summary: 'Recorre el globo hasta Colombia, Antioquia y el Oriente Antioqueño.',
  },
  {
    id: 'lote',
    label: 'Municipio y lote',
    path: PLOT_STEP_PATH,
    summary: 'Selecciona el municipio de tu finca y delimita el terreno que deseas analizar.',
  },
  {
    id: 'caracterizacion',
    label: 'Caracterización',
    path: '/finca/caracterizacion',
    summary: 'Cuéntanos sobre el suelo, el agua, el clima local y los cultivos del lote.',
  },
  {
    id: 'analisis',
    label: 'Análisis',
    path: '/finca/analisis',
    summary: 'Consulta la rotación de cultivos propuesta, series ambientales y recomendaciones.',
  },
];

export type StepStatus = 'done' | 'current' | 'upcoming';
