/**
 * Municipal data coverage — what the portal can honestly say about each municipality.
 *
 * Three states (never blur them):
 *  - 'integrated'         Real data loaded by the portal and queryable here.
 *  - 'processed-pending'  Real data processed by the team exists in the repo, but
 *                         the portal does not load it yet.
 *  - 'none'               No data integrated or processed for this municipality.
 *
 * Municipalities not listed are 'none'. Demo data is NOT a coverage state:
 * it lives in its own clearly labelled dataset and never marks a municipality as covered.
 * Keys are DANE DIVIPOLA municipality codes (MPIO_CDPMP).
 */
export type CoverageStatus = 'integrated' | 'processed-pending' | 'none';

export interface MunicipalCoverage {
  status: Exclude<CoverageStatus, 'none'>;
  /** Ids from DATA_SOURCES in data-sources.ts. */
  sourceIds: readonly string[];
  period: string;
  /** What the data represents spatially — never a farm-level measurement. */
  spatialSupport: string;
  note: string;
}

export const COVERAGE_LABEL: Record<CoverageStatus, string> = {
  integrated: 'Datos integrados',
  'processed-pending': 'Datos procesados, pendientes de conexión',
  none: 'Sin datos integrados',
};

export const MUNICIPAL_COVERAGE: Readonly<Record<string, MunicipalCoverage>> = {
  // La Unión — team climate module (Modulo_climatico/, see LEEME_datos_clima.md).
  '05400': {
    status: 'processed-pending',
    sourceIds: ['nasa-power', 'gpm-imerg', 'ideam-dhime'],
    period: '2000–2026 (diario y mensual)',
    spatialSupport:
      'Celda de NASA POWER en el punto 5,97° N, 75,36° O (≈ 55 km) y lluvia GPM IMERG (≈ 10 km), validadas con estaciones IDEAM del municipio.',
    note: 'Series procesadas por el equipo en el módulo climático; aún no se cargan en el portal.',
  },
};

export function coverageOf(code: string): CoverageStatus {
  return MUNICIPAL_COVERAGE[code]?.status ?? 'none';
}
