import { BBox, BoundaryFeature, BoundaryGeometry } from '../models/geo.models';

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
