/** Stages and compatibility identifiers for the public workspace and optional private actions. */
export type JourneyStepId = 'cuenta' | 'explorar' | 'lote' | 'caracterizacion' | 'analisis';

export interface JourneyStep {
  id: JourneyStepId;
  label: string;
  path: string;
  summary: string;
}

export const PLOT_STEP_PATH = '/explorar';

/** Public workspace stages. Account and farm characterization are optional private actions. */
export const JOURNEY: readonly JourneyStep[] = [
  { id: 'explorar', label: 'Ubicación', path: '/explorar', summary: 'Selecciona el municipio.' },
  {
    id: 'lote',
    label: 'Terreno opcional',
    path: '/explorar',
    summary: 'Delimita el terreno en el mismo mapa si lo deseas.',
  },
  {
    id: 'analisis',
    label: 'Resultados',
    path: '/explorar',
    summary: 'Consulta los resultados disponibles sin crear una cuenta.',
  },
];

export type StepStatus = 'done' | 'current' | 'upcoming';
