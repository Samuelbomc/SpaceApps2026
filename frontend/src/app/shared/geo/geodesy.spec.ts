import { LngLat, centroid, closeRing, distanceM, openRing, perimeterM, pointInRing, ringAreaM2, selfIntersects } from './geodesy';

/** Square of `sideDeg` degrees anchored at (lon, lat). */
const square = (lon: number, lat: number, sideDeg: number): LngLat[] => [
  [lon, lat],
  [lon + sideDeg, lat],
  [lon + sideDeg, lat + sideDeg],
  [lon, lat + sideDeg],
];

describe('geodesy', () => {
  it('computes geodesic area, not degrees treated as metres', () => {
    // 0.01° × 0.01° at the equator ≈ 1113.2 m × 1105.7 m ≈ 123.1 ha (spherical).
    const eq = ringAreaM2(square(0, 0, 0.01));
    expect(eq / 10_000).toBeGreaterThan(122.5);
    expect(eq / 10_000).toBeLessThan(123.8);
    // Same square in degrees near La Unión (6° N) is smaller: meridians converge.
    const launion = ringAreaM2(square(-75.36, 5.97, 0.01));
    expect(launion).toBeLessThan(eq);
    expect(launion / eq).toBeCloseTo(Math.cos((5.975 * Math.PI) / 180), 3);
  });

  it('is independent of vertex order and of a repeated closing vertex', () => {
    const s = square(-75.36, 5.97, 0.002);
    expect(ringAreaM2([...s].reverse())).toBeCloseTo(ringAreaM2(s), 6);
    expect(ringAreaM2(closeRing(s))).toBeCloseTo(ringAreaM2(s), 6);
    expect(openRing(closeRing(s))).toEqual(s);
  });

  it('measures distance and perimeter in metres', () => {
    // 1° of latitude ≈ 111.2 km on the mean sphere.
    expect(distanceM([0, 0], [0, 1]) / 1000).toBeCloseTo(111.19, 1);
    const p = perimeterM(square(0, 0, 0.001));
    expect(p).toBeGreaterThan(440);
    expect(p).toBeLessThan(450);
  });

  it('finds the centroid of a square and tests point inclusion', () => {
    const s = square(-75.36, 5.97, 0.01);
    const [x, y] = centroid(s);
    expect(x).toBeCloseTo(-75.355, 5);
    expect(y).toBeCloseTo(5.975, 5);
    expect(pointInRing([-75.355, 5.975], s)).toBe(true);
    expect(pointInRing([-75.3, 5.975], s)).toBe(false);
  });

  it('detects bow-tie (self-intersecting) polygons', () => {
    expect(selfIntersects(square(0, 0, 1))).toBe(false);
    expect(selfIntersects([[0, 0], [1, 1], [1, 0], [0, 1]])).toBe(true);
  });
});
