import { BBox, BoundaryFeature, BoundaryGeometry } from '../models/geo.models';
import { centroid, LngLat, pointInPolygons } from '../../../shared/geo/geodesy';

/** Prefer the official label point when inside; handle concavity, holes and islands. */
export function municipalityReferencePoint(
  geometry: BoundaryGeometry,
  preferred?: LngLat,
): LngLat | null {
  const polygons = (
    geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates
  ).filter((polygon) => polygon[0]?.length >= 4);
  const inside = (point: LngLat) =>
    point.every(Number.isFinite) && pointInPolygons(point, polygons);
  if (preferred && inside(preferred)) return preferred;
  let best: { width: number; point: LngLat } | null = null;
  for (const polygon of polygons) {
    if (!polygon[0]?.length) continue;
    const center = centroid(polygon[0]);
    if (inside(center)) return center;
    const levels = [...new Set(polygon.flatMap((ring) => ring.map((point) => point[1])))].sort(
      (a, b) => a - b,
    );
    for (let level = 1; level < levels.length; level++) {
      const latitude = (levels[level - 1] + levels[level]) / 2;
      const intersections: number[] = [];
      for (const ring of polygon) {
        for (let index = 0; index < ring.length; index++) {
          const a = ring[index],
            b = ring[(index + 1) % ring.length];
          if (a[1] > latitude !== b[1] > latitude)
            intersections.push(a[0] + ((latitude - a[1]) * (b[0] - a[0])) / (b[1] - a[1]));
        }
      }
      intersections.sort((a, b) => a - b);
      for (let index = 0; index + 1 < intersections.length; index += 2) {
        const width = intersections[index + 1] - intersections[index];
        const point: LngLat = [(intersections[index] + intersections[index + 1]) / 2, latitude];
        if (width > 0 && (!best || width > best.width) && inside(point)) best = { width, point };
      }
    }
  }
  return best?.point ?? null;
}

/** Bounding box of one geometry. */
export function geometryBBox(geometry: BoundaryGeometry): BBox {
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  let w = Infinity;
  let s = Infinity;
  let e = -Infinity;
  let n = -Infinity;
  for (const poly of polygons) {
    for (const [lon, lat] of poly[0]) {
      if (lon < w) w = lon;
      if (lon > e) e = lon;
      if (lat < s) s = lat;
      if (lat > n) n = lat;
    }
  }
  return [w, s, e, n];
}

/** Union of the bounding boxes of several features. */
export function featuresBBox(features: readonly BoundaryFeature<unknown>[]): BBox {
  return features
    .map((f) => geometryBBox(f.geometry))
    .reduce<BBox>(
      (acc, b) => [
        Math.min(acc[0], b[0]),
        Math.min(acc[1], b[1]),
        Math.max(acc[2], b[2]),
        Math.max(acc[3], b[3]),
      ],
      [Infinity, Infinity, -Infinity, -Infinity],
    );
}

/**
 * DANE names are upper case ("LA UNIÓN"). Title-case them for display while
 * keeping Spanish particles lower case ("San José de la Montaña").
 */
const LOWER_WORDS = new Set(['de', 'del', 'la', 'las', 'los', 'el', 'y', 'e']);

export function displayName(raw: string): string {
  return raw
    .toLocaleLowerCase('es-CO')
    .split(/(\s+|-)/)
    .map((word, i) =>
      i > 0 && LOWER_WORDS.has(word)
        ? word
        : word.charAt(0).toLocaleUpperCase('es-CO') + word.slice(1),
    )
    .join('')
    .replace(/\bD\.c\./g, 'D.C.');
}

/** Accent- and case-insensitive key for matching names. */
export function normalizeName(value: string): string {
  return value
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .trim();
}
