/**
 * Pilot territory configuration.
 *
 * Geography is data, not component logic, so the platform can expand to other
 * regions by adding configuration.
 *
 * Two levels, never to be confused:
 *  - Explorable territory: Antioquia (navigation and geographic context only).
 *  - Functional pilot region: Oriente Antioqueño — the only area where the farm
 *    workflow (plot, questionnaire, analysis) may start.
 */
export interface MembershipSource {
  /** Citation shown to users. */
  citation: string;
  /** Official documents consulted (all must agree). */
  urls: readonly string[];
  /** How membership was matched to the boundary data. */
  method: string;
  verifiedOn: string;
}

export interface PilotRegion {
  /** Stable identifier (used in URLs, state and future API calls). */
  id: string;
  name: string;
  /** Subregion name as listed in `subregions`. */
  subregion: string;
  /**
   * DANE DIVIPOLA codes of the municipalities in the region. Only verified codes
   * belong here; a municipality not listed is never treated as supported.
   */
  municipalityCodes: readonly string[];
  membershipSource: MembershipSource | null;
}

export interface TerritoryConfig {
  country: string;
  department: string;
  /** DANE DIVIPOLA department code (Antioquia = '05'). */
  departmentCode: string;
  /**
   * Boundary files served from /public, produced by
   * pipelines/ingestion/sources/colombia/dane_mgn.py. Adding a department means
   * running the pipeline for it and adding its municipalities file here.
   */
  boundaries: {
    departments: string;
    municipalities: string;
    metadata: string;
  };
  /** Official subregions of the department. */
  subregions: readonly string[];
  pilotRegion: PilotRegion;
}

export const PILOT_TERRITORY: TerritoryConfig = {
  country: 'Colombia',
  department: 'Antioquia',
  departmentCode: '05',
  boundaries: {
    departments: 'geo/colombia-departamentos.geojson',
    municipalities: 'geo/municipios-05.geojson',
    metadata: 'geo/boundaries.metadata.json',
  },
  subregions: [
    'Valle de Aburrá',
    'Bajo Cauca',
    'Magdalena Medio',
    'Nordeste',
    'Norte',
    'Occidente',
    'Oriente',
    'Suroeste',
    'Urabá',
  ],
  pilotRegion: {
    id: 'oriente-antioqueno',
    name: 'Oriente Antioqueño',
    subregion: 'Oriente',
    // Subregion SR07 "Oriente" (Gobernación de Antioquia). 23 municipalities.
    // Names differ slightly between sources (e.g. "La Ceja del Tambo" / "La Ceja",
    // "San Vicente" / "San Vicente Ferrer"); matching is done by DANE code only.
    municipalityCodes: [
      '05002', // Abejorral
      '05021', // Alejandría
      '05055', // Argelia
      '05148', // El Carmen de Viboral
      '05197', // Cocorná
      '05206', // Concepción
      '05313', // Granada
      '05318', // Guarne
      '05321', // Guatapé
      '05376', // La Ceja
      '05400', // La Unión
      '05440', // Marinilla
      '05483', // Nariño
      '05541', // El Peñol
      '05607', // El Retiro
      '05615', // Rionegro
      '05649', // San Carlos
      '05652', // San Francisco
      '05660', // San Luis
      '05667', // San Rafael
      '05674', // San Vicente Ferrer
      '05697', // El Santuario
      '05756', // Sonsón
    ],
    membershipSource: {
      citation:
        'Gobernación de Antioquia, Departamento Administrativo de Planeación — Anuario Estadístico de Antioquia 2014 (subregión SR07 Oriente).',
      urls: [
        'https://www.antioquia.gov.co/images/pdf/anuario2014/es-CO/capitulos/fiscales/catastro/cp-8-3-3.html',
        'https://www.antioquia.gov.co/images/pdf/anuario2014/es-CO/capitulos/ambiente/impacto/suelo/cp-2-3-1-9.html',
      ],
      method:
        'Dos tablas oficiales independientes listan los mismos 23 municipios en SR07 con su código DANE; los 23 códigos coinciden con DANE MGN 2025.',
      verifiedOn: '2026-11-14',
    },
  },
};

/** The department as the journey stores it. */
export const PILOT_DEPARTMENT = { code: '05', name: 'Antioquia' } as const;

/** True only for municipalities verified as part of the functional pilot region. */
export function isSupportedMunicipality(code: string | null | undefined): boolean {
  return !!code && PILOT_TERRITORY.pilotRegion.municipalityCodes.includes(code);
}

export function isPilotRegionVerified(): boolean {
  return PILOT_TERRITORY.pilotRegion.membershipSource !== null;
}

/** Spatial levels the platform distinguishes. Never present one as another. */
export interface GeographicLevel {
  name: string;
  description: string;
  example: string;
}

export const GEOGRAPHIC_LEVELS: readonly GeographicLevel[] = [
  {
    name: 'Regional',
    description: 'Patrones amplios de clima, agua y vegetación.',
    example: 'Lluvia satelital, humedad superficial del suelo.',
  },
  {
    name: 'Municipal',
    description: 'Estadísticas agrícolas y resúmenes ambientales por municipio.',
    example: 'Área sembrada y producción por cultivo.',
  },
  {
    name: 'Finca / lote',
    description:
      'El lote que delimita el agricultor. Solo se le asocian datos cuya resolución lo permite; no es un predio catastral.',
    example: 'Respuestas del agricultor, análisis de suelo, vegetación a 30 m.',
  },
];
