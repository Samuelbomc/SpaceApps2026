/**
 * Classification of WHERE a piece of information comes from.
 *
 * Scientific-integrity requirement: every dataset or result shown in the UI
 * must be tagged with one of these so users can tell observations, models,
 * institutional statistics, farmer inputs and demo data apart.
 */
export type DataNature =
  'satellite' | 'modeled' | 'ground' | 'institutional' | 'literature' | 'farmer' | 'demo';

export interface DataNatureInfo {
  label: string;
  description: string;
}

export const DATA_NATURE: Record<DataNature, DataNatureInfo> = {
  satellite: {
    label: 'Observación satelital',
    description:
      'Medición o estimación derivada directamente de sensores en satélites. Tiene una resolución espacial y temporal concreta y puede verse afectada por nubes o vegetación densa.',
  },
  modeled: {
    label: 'Producto modelado',
    description:
      'Estimación generada por un modelo (reanálisis, asimilación, predicción de suelos o aptitud). Útil como contexto, pero no es una medición directa.',
  },
  ground: {
    label: 'Observación en tierra',
    description:
      'Medición de estaciones meteorológicas o hidrológicas. Precisa en su punto, pero no necesariamente representativa de toda la zona.',
  },
  institutional: {
    label: 'Dato institucional',
    description:
      'Estadística oficial (por ejemplo, agrícola municipal). Describe un territorio agregado, no una finca en particular.',
  },
  literature: {
    label: 'Evidencia bibliográfica',
    description:
      'Conocimiento agronómico publicado (estudios, guías técnicas) que respalda un criterio.',
  },
  farmer: {
    label: 'Aportado por el agricultor',
    description:
      'Información que la persona usuaria registra sobre su finca: historial, suelo, prioridades.',
  },
  demo: {
    label: 'Dato de demostración',
    description:
      'Valor ilustrativo usado mientras se integra la fuente real. Nunca representa una medición.',
  },
};

/** Development status of a capability or data integration. */
export type IntegrationStatus = 'available' | 'in-development' | 'planned';

export const INTEGRATION_STATUS_LABEL: Record<IntegrationStatus, string> = {
  available: 'Disponible',
  'in-development': 'En desarrollo',
  planned: 'Planificado',
};
