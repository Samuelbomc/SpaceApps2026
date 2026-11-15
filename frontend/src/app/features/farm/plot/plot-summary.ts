import {
  LngLat,
  centroid,
  closeRing,
  openRing,
  perimeterM,
  pointInPolygons,
  ringAreaM2,
  selfIntersects,
} from '../../../shared/geo/geodesy';
import { BoundaryGeometry } from '../../explorer/models/geo.models';
import { PlotSelection } from '../../../core/journey/journey.models';

export interface PlotIssue {
  level: 'error' | 'warning';
  message: string;
}

export interface PlotSummary {
  ring: LngLat[];
  areaM2: number;
  perimeterM: number;
  centroid: LngLat;
  vertexCount: number;
  within: 'inside' | 'partial' | 'outside';
  issues: PlotIssue[];
  valid: boolean;
}

/** Sentinel-2 pixel = 10 m × 10 m. Below ~10 pixels the outline is mostly guesswork. */
const SMALL_AREA_M2 = 1_000;
const LARGE_AREA_M2 = 20_000_000; // 2 000 ha

/**
 * Describes a closed, farmer-drawn polygon and checks it against the selected
 * municipality. Pure function: no map, no state.
 */
export function summarizePlot(
  ring: readonly LngLat[],
  municipality: { name: string; geometry: BoundaryGeometry },
): PlotSummary {
  const r = openRing(ring);
  const polygons = (
    municipality.geometry.type === 'Polygon'
      ? [municipality.geometry.coordinates]
      : municipality.geometry.coordinates
  ) as LngLat[][][];
  const insideCount = r.filter((p) => pointInPolygons(p, polygons)).length;
  const c = centroid(r);
  const within: PlotSummary['within'] =
    insideCount === r.length
      ? 'inside'
      : insideCount > 0 || pointInPolygons(c, polygons)
        ? 'partial'
        : 'outside';
  const areaM2 = ringAreaM2(r);

  const issues: PlotIssue[] = [];
  if (selfIntersects(r)) {
    issues.push({
      level: 'error',
      message:
        'Los lados del lote se cruzan. Mueve los puntos para que el contorno no se corte a sí mismo.',
    });
  }
  if (within === 'outside') {
    issues.push({
      level: 'error',
      message: `El lote está fuera de ${municipality.name}. Dibújalo dentro del límite municipal.`,
    });
  } else if (within === 'partial') {
    issues.push({
      level: 'warning',
      message: `Parte del lote queda fuera del límite de ${municipality.name} (límite simplificado, ±200 m). Revisa que sea tu terreno.`,
    });
  }
  if (areaM2 < SMALL_AREA_M2) {
    issues.push({
      level: 'warning',
      message:
        'El lote es muy pequeño frente al detalle de la imagen (10 m por píxel); su contorno será poco preciso.',
    });
  } else if (areaM2 > LARGE_AREA_M2) {
    issues.push({
      level: 'warning',
      message:
        'El área es muy grande para un lote. Verifica que dibujaste solo el terreno que quieres analizar.',
    });
  }

  return {
    ring: r,
    areaM2,
    perimeterM: perimeterM(r),
    centroid: c,
    vertexCount: r.length,
    within,
    issues,
    valid: !issues.some((i) => i.level === 'error'),
  };
}

/** Builds the journey record for a valid plot. */
export function toPlotSelection(summary: PlotSummary, municipalityCode: string): PlotSelection {
  return {
    municipalityCode,
    geometry: { type: 'Polygon', coordinates: [closeRing(summary.ring)] },
    areaM2: summary.areaM2,
    perimeterM: summary.perimeterM,
    centroid: summary.centroid,
    vertexCount: summary.vertexCount,
    withinMunicipality: summary.within === 'inside' ? 'inside' : 'partial',
    drawnAt: new Date().toISOString(),
  };
}
