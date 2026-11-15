/**
 * Geographic calculations on WGS84 longitude/latitude (EPSG:4326).
 *
 * Areas and lengths are computed on a sphere with the mean Earth radius
 * (IUGG R1 = 6 371 008.8 m), never by treating degrees as planar metres.
 * For farm-sized polygons the spherical approximation differs from an
 * ellipsoidal (WGS84) calculation by well under 1 % — far below the
 * uncertainty of a hand-drawn outline on 10 m imagery.
 */
export type LngLat = [number, number];

const EARTH_RADIUS_M = 6_371_008.8;
const rad = (deg: number) => (deg * Math.PI) / 180;

/** Returns the ring without a repeated closing vertex. */
export function openRing(ring: readonly LngLat[]): LngLat[] {
  const r = [...ring];
  if (r.length > 1 && r[0][0] === r[r.length - 1][0] && r[0][1] === r[r.length - 1][1]) r.pop();
  return r;
}

/** Returns the ring with the first vertex repeated at the end (GeoJSON convention). */
export function closeRing(ring: readonly LngLat[]): LngLat[] {
  const r = openRing(ring);
  return r.length ? [...r, r[0]] : r;
}

/**
 * Spherical polygon area in m² (Chamberlain & Duquette, 2007, JPL Publication 07-03).
 * Always positive, independent of vertex order.
 */
export function ringAreaM2(ring: readonly LngLat[]): number {
  const r = openRing(ring);
  if (r.length < 3) return 0;
  let total = 0;
  for (let i = 0; i < r.length; i++) {
    const [lon1, lat1] = r[i];
    const [lon2, lat2] = r[(i + 1) % r.length];
    total += rad(lon2 - lon1) * (2 + Math.sin(rad(lat1)) + Math.sin(rad(lat2)));
  }
  return Math.abs((total * EARTH_RADIUS_M * EARTH_RADIUS_M) / 2);
}

/** Great-circle distance in metres (haversine). */
export function distanceM(a: LngLat, b: LngLat): number {
  const dLat = rad(b[1] - a[1]);
  const dLon = rad(b[0] - a[0]);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[1])) * Math.cos(rad(b[1])) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Closed-ring perimeter in metres. */
export function perimeterM(ring: readonly LngLat[]): number {
  const r = openRing(ring);
  if (r.length < 2) return 0;
  let total = 0;
  for (let i = 0; i < r.length; i++) total += distanceM(r[i], r[(i + 1) % r.length]);
  return total;
}

/**
 * Area-weighted centroid computed in a local equirectangular frame centred on the
 * polygon (accurate for farm-sized polygons). Falls back to the vertex mean for
 * degenerate shapes.
 */
export function centroid(ring: readonly LngLat[]): LngLat {
  const r = openRing(ring);
  const meanLat = r.reduce((s, p) => s + p[1], 0) / r.length;
  const k = Math.cos(rad(meanLat));
  let a = 0;
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < r.length; i++) {
    const [x1, y1] = [r[i][0] * k, r[i][1]];
    const [x2, y2] = [r[(i + 1) % r.length][0] * k, r[(i + 1) % r.length][1]];
    const f = x1 * y2 - x2 * y1;
    a += f;
    cx += (x1 + x2) * f;
    cy += (y1 + y2) * f;
  }
  if (Math.abs(a) < 1e-18) {
    return [r.reduce((s, p) => s + p[0], 0) / r.length, meanLat];
  }
  return [cx / (3 * a) / k, cy / (3 * a)];
}

/** Ray-casting point-in-ring test (lon/lat treated as plane coordinates, fine for inclusion). */
export function pointInRing(point: LngLat, ring: readonly LngLat[]): boolean {
  const r = openRing(ring);
  let inside = false;
  for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
    const [xi, yi] = r[i];
    const [xj, yj] = r[j];
    if (
      yi > point[1] !== yj > point[1] &&
      point[0] < ((xj - xi) * (point[1] - yi)) / (yj - yi) + xi
    ) {
      inside = !inside;
    }
  }
  return inside;
}

/** Point inside a Polygon/MultiPolygon (outer rings minus holes). */
export function pointInPolygons(
  point: LngLat,
  polygons: readonly (readonly LngLat[][])[],
): boolean {
  return polygons.some(
    (poly) =>
      pointInRing(point, poly[0]) && !poly.slice(1).some((hole) => pointInRing(point, hole)),
  );
}

function segmentsCross(a: LngLat, b: LngLat, c: LngLat, d: LngLat): boolean {
  const o = (p: LngLat, q: LngLat, s: LngLat) =>
    Math.sign((q[0] - p[0]) * (s[1] - p[1]) - (q[1] - p[1]) * (s[0] - p[0]));
  return o(a, b, c) * o(a, b, d) < 0 && o(c, d, a) * o(c, d, b) < 0;
}

/** True when two non-adjacent edges of the ring cross (an invalid "bow-tie" polygon). */
export function selfIntersects(ring: readonly LngLat[]): boolean {
  const r = openRing(ring);
  const n = r.length;
  if (n < 4) return false;
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const adjacent = j === i + 1 || (i === 0 && j === n - 1);
      if (adjacent) continue;
      if (segmentsCross(r[i], r[(i + 1) % n], r[j], r[(j + 1) % n])) return true;
    }
  }
  return false;
}

/** Formats an area for farmers: hectares (and m² for small plots). */
export function formatArea(m2: number): string {
  const ha = m2 / 10_000;
  const nf = (v: number, d: number) =>
    v.toLocaleString('es-CO', { minimumFractionDigits: d, maximumFractionDigits: d });
  return ha < 1 ? `${nf(ha, 2)} ha (${nf(m2, 0)} m²)` : `${nf(ha, ha < 100 ? 2 : 0)} ha`;
}

/** Decimal-degree coordinate with hemisphere, e.g. "5,9731° N, 75,3612° O". */
export function formatLngLat([lon, lat]: LngLat, digits = 5): string {
  const f = (v: number) =>
    Math.abs(v).toLocaleString('es-CO', {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  return `${f(lat)}° ${lat >= 0 ? 'N' : 'S'}, ${f(lon)}° ${lon >= 0 ? 'E' : 'O'}`;
}
