import { DataNature, IntegrationStatus } from './data-nature';

/**
 * Descriptive catalog of the data sources the platform PLANS to integrate.
 *
 * This file contains no data values — only nominal product characteristics
 * as documented by each provider. Resolutions are nominal; they must be
 * re-verified against the exact product/version when each connector is built.
 * `status` must only be changed to 'available' once real data flows end to end.
 */
export interface DataSourceSummary {
  id: string;
  name: string;
  provider: string;
  isNasa: boolean;
  nature: DataNature;
  variables: string[];
  spatialResolution: string;
  temporalResolution: string;
  /** What this source contributes to agricultural analysis. */
  contribution: string;
  /** The key limitation users must understand. */
  caveat: string;
  status: IntegrationStatus;
  url: string;
}

export const DATA_SOURCES: readonly DataSourceSummary[] = [
  {
    id: 'nasa-power',
    name: 'NASA POWER',
    provider: 'NASA Langley Research Center',
    isNasa: true,
    nature: 'modeled',
    variables: ['Temperatura del aire', 'Humedad relativa', 'Radiación solar', 'Precipitación'],
    spatialResolution: '0,5° × 0,625° (meteorología) · 1° (solar)',
    temporalResolution: 'Diaria, mensual (series desde 1981)',
    contribution: 'Caracterización agroclimática e históricos de largo plazo.',
    caveat: 'Estimaciones en malla gruesa: no son observaciones de estación ni de finca.',
    status: 'planned',
    url: 'https://power.larc.nasa.gov/',
  },
  {
    id: 'gpm-imerg',
    name: 'GPM IMERG',
    provider: 'NASA / JAXA',
    isNasa: true,
    nature: 'satellite',
    variables: ['Tasa de precipitación', 'Precipitación acumulada'],
    spatialResolution: '0,1° (≈ 11 km)',
    temporalResolution: '30 min; agregados diarios y mensuales',
    contribution: 'Patrones y anomalías de lluvia, periodos secos y lluvias intensas.',
    caveat:
      'Estimación multisatelital con mayor incertidumbre en terreno montañoso; conviene contrastar con estaciones del IDEAM.',
    status: 'planned',
    url: 'https://gpm.nasa.gov/data',
  },
  {
    id: 'smap',
    name: 'SMAP',
    provider: 'NASA JPL',
    isNasa: true,
    nature: 'satellite',
    variables: ['Humedad superficial del suelo'],
    spatialResolution: '36 km (L3) · 9 km (producto mejorado)',
    temporalResolution: 'Revisita de 2–3 días',
    contribution: 'Condiciones regionales de humedad superficial y su variación temporal.',
    caveat:
      'Mide los primeros ~5 cm del suelo: no equivale a la humedad en la zona de raíces. La vegetación densa reduce la calidad de la estimación.',
    status: 'planned',
    url: 'https://www.earthdata.nasa.gov/data/platforms/space-based-platforms/smap',
  },
  {
    id: 'hls',
    name: 'Harmonized Landsat Sentinel-2 (HLS)',
    provider: 'NASA (con datos de USGS y ESA)',
    isNasa: true,
    nature: 'satellite',
    variables: ['Reflectancia superficial', 'NDVI y otros índices de vegetación'],
    spatialResolution: '30 m',
    temporalResolution: 'Revisita combinada de 2–3 días (sin nubes, menos)',
    contribution: 'Dinámica de la vegetación y cobertura del suelo a lo largo del año.',
    caveat:
      'La nubosidad frecuente en Antioquia limita las observaciones útiles. El NDVI no mide la salud del suelo ni el rendimiento.',
    status: 'planned',
    url: 'https://hls.gsfc.nasa.gov/',
  },
  {
    id: 'ecostress',
    name: 'ECOSTRESS',
    provider: 'NASA JPL',
    isNasa: true,
    nature: 'satellite',
    variables: ['Temperatura de superficie terrestre', 'Evapotranspiración'],
    spatialResolution: '≈ 70 m',
    temporalResolution: 'Irregular (órbita de la Estación Espacial Internacional)',
    contribution: 'Estrés térmico y patrones de evapotranspiración.',
    caveat:
      'La temperatura de superficie no es la temperatura del aire. La evapotranspiración es un producto modelado con incertidumbre.',
    status: 'planned',
    url: 'https://ecostress.jpl.nasa.gov/data',
  },
  {
    id: 'srtm',
    name: 'SRTM',
    provider: 'NASA / NGA',
    isNasa: true,
    nature: 'satellite',
    variables: ['Elevación', 'Pendiente (derivada)'],
    spatialResolution: '1 segundo de arco (≈ 30 m)',
    temporalResolution: 'Una sola época (2000)',
    contribution: 'Relieve y pendiente como contexto de escorrentía y erosión.',
    caveat:
      'La pendiente es un indicador indirecto de riesgo de erosión, no una medición de erosión.',
    status: 'planned',
    url: 'https://www.earthdata.nasa.gov/data/instruments/srtm',
  },
  {
    id: 'fao-gaez',
    name: 'FAO GAEZ v4',
    provider: 'FAO / IIASA',
    isNasa: false,
    nature: 'modeled',
    variables: ['Aptitud agroecológica por cultivo', 'Rendimiento potencial'],
    spatialResolution: 'Mayormente 5 minutos de arco (≈ 9 km)',
    temporalResolution: 'Periodos climáticos de referencia y escenarios',
    contribution: 'Preselección de cultivos candidatos para las rotaciones.',
    caveat:
      'La aptitud y el rendimiento potencial son modelos bajo supuestos; no garantizan producción real.',
    status: 'planned',
    url: 'https://gaez.fao.org/',
  },
  {
    id: 'soilgrids',
    name: 'SoilGrids',
    provider: 'ISRIC',
    isNasa: false,
    nature: 'modeled',
    variables: ['pH', 'Carbono orgánico', 'Textura del suelo'],
    spatialResolution: '250 m',
    temporalResolution: 'Estática',
    contribution: 'Contexto de propiedades del suelo cuando no hay análisis de laboratorio.',
    caveat:
      'Predicciones estadísticas con incertidumbre; no reemplazan un análisis de suelo de la finca.',
    status: 'planned',
    url: 'https://soilgrids.org/',
  },
  {
    id: 'upra-eva',
    name: 'Evaluaciones Agropecuarias Municipales (EVA)',
    provider: 'UPRA · Colombia',
    isNasa: false,
    nature: 'institutional',
    variables: ['Área sembrada y cosechada', 'Producción', 'Rendimiento'],
    spatialResolution: 'Municipal',
    temporalResolution: 'Anual',
    contribution: 'Contexto agrícola oficial: qué se cultiva y cuánto en cada municipio.',
    caveat: 'Estadísticas agregadas por municipio: no describen fincas individuales.',
    status: 'planned',
    url: 'https://upra.gov.co/es-co/eva',
  },
  {
    id: 'ideam-dhime',
    name: 'IDEAM — DHIME',
    provider: 'IDEAM · Colombia',
    isNasa: false,
    nature: 'ground',
    variables: ['Precipitación', 'Temperatura', 'Variables hidrológicas'],
    spatialResolution: 'Puntual (estaciones)',
    temporalResolution: 'Diaria o subdiaria, según la estación',
    contribution: 'Referencia en tierra para contrastar las estimaciones satelitales.',
    caveat: 'Densidad de estaciones desigual y series con vacíos.',
    status: 'planned',
    url: 'https://www.ideam.gov.co/dhime',
  },
];
