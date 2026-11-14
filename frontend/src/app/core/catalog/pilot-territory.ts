/**
 * Pilot territory configuration.
 *
 * Geography is data, not component logic, so the platform can expand to other
 * departments by adding configuration. Pilot municipalities are intentionally
 * empty: per CLAUDE.md they must be selected after reviewing data availability
 * and agronomic relevance — do not fill this list by familiarity.
 */
export interface TerritoryConfig {
  country: string;
  department: string;
  /** Official subregions of the department. */
  subregions: readonly string[];
  pilotMunicipalities: readonly string[];
  selectionCriteria: readonly string[];
}

export const PILOT_TERRITORY: TerritoryConfig = {
  country: 'Colombia',
  department: 'Antioquia',
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
  pilotMunicipalities: [],
  selectionCriteria: [
    'Disponibilidad y calidad de datos satelitales e institucionales.',
    'Relevancia agrícola y presencia de sistemas de cultivo con potencial de rotación.',
    'Diversidad de condiciones de clima, relieve y agua.',
    'Posibilidad de validar resultados con agricultores y asistencia técnica local.',
  ],
};

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
    description: 'Información de una finca, solo cuando la resolución de la fuente lo permite.',
    example: 'Historial de cultivos, análisis de suelo, vegetación a 30 m.',
  },
];
