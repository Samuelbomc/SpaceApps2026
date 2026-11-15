import assert from 'node:assert/strict';
import test from 'node:test';
import { squareArea, rectangleArea, areaGeoJSON, squareSideMetres, convertSquareSize } from '../src/area.ts';
const center = { latitude: 6.2442, longitude: -75.5812 };

test('10 m square retains metre-sized dimensions and approximately 100 square metres', () => {
  const area = squareArea(center, 10);
  assert(Math.abs(area.widthM - 10) < .001);
  assert(Math.abs(area.heightM - 10) < .001);
  assert(Math.abs(area.areaM2 - 100) < .01);
  assert(area.west < center.longitude && area.east > center.longitude);
  assert(area.south < center.latitude && area.north > center.latitude);
});
test('rectangle is independent of corner order and GeoJSON uses longitude then latitude', () => {
  const a = { latitude: 6.244, longitude: -75.582 };
  const b = { latitude: 6.245, longitude: -75.581 };
  const area = rectangleArea(a, b);
  assert.deepEqual(rectangleArea(b, a), area);
  const ring = areaGeoJSON(area).geometry.coordinates[0];
  assert.deepEqual(ring[0], [area.west, area.south]);
  assert.deepEqual(ring[0], ring.at(-1));
  assert.equal(ring.length, 5);
  assert.equal(areaGeoJSON(area).properties.selection_only, true);
});
test('submetre, oversized, invalid and dateline-crossing areas fail explicitly', () => {
  assert.throws(() => rectangleArea(center, center));
  assert.throws(() => squareArea(center, NaN));
  assert.throws(() => rectangleArea(center, { latitude: 7, longitude: -74 }));
  assert.throws(() => squareArea({ latitude: 6, longitude: 179.99999 }, 1000));
});

test('all selectable units express the surface rather than the side length', () => {
  const metres = squareArea(center, squareSideMetres(10000, 'm2'));
  assert.deepEqual(squareArea(center, squareSideMetres(.01, 'km2')), metres);
  assert.deepEqual(squareArea(center, squareSideMetres(1, 'ha')), metres);
  assert(Math.abs(metres.areaM2 - 10000) < .01);
  const decimalArea = squareArea(center, squareSideMetres(2.5, 'ha'));
  assert(Math.abs(decimalArea.areaM2 - 25000) < .1);
  assert(Math.abs(decimalArea.widthM - decimalArea.heightM) < .001);
});

test('switching units preserves the selected size in both directions', () => {
  assert.equal(convertSquareSize(10000, 'm2', 'ha'), 1);
  assert.equal(convertSquareSize(1, 'ha', 'km2'), .01);
  assert.equal(convertSquareSize(1, 'km2', 'ha'), 100);
  assert.equal(convertSquareSize(.01, 'km2', 'm2'), 10000);
  assert.equal(convertSquareSize(2.5, 'ha', 'ha'), 2.5);
});

test('free sizes accept decimals and boundaries while invalid values fail in every unit', () => {
  for (const unit of ['m2', 'km2', 'ha']) {
    for (const invalid of [0, -1, NaN, Infinity]) assert.throws(() => squareSideMetres(invalid, unit));
  }
  for (const [value, unit] of [[.99, 'm2'], [.0000009, 'km2'], [.00009, 'ha'], [100000001, 'm2'], [100.01, 'km2'], [10001, 'ha']]) {
    assert.throws(() => squareSideMetres(value, unit));
  }
  assert.throws(() => squareSideMetres(10, 'acres'));
  assert.throws(() => convertSquareSize(100, 'm2', 'acres'));
  const smallest = squareArea(center, squareSideMetres(.0001, 'ha'));
  assert(Math.abs(smallest.areaM2 - 1) < .001);
  const largest = squareArea(center, squareSideMetres(10000, 'ha'));
  assert(Math.abs(largest.widthM - 10000) < .001);
  assert.equal(squareSideMetres(156.25, 'm2'), 12.5);
});


test('1000 square metres is 31.62 m per side and equivalent to 0.1 ha or 0.001 km2', () => {
  const side = squareSideMetres(1000, 'm2');
  assert(Math.abs(side - 31.622776601683793) < 1e-10);
  const area = squareArea(center, side);
  assert(Math.abs(area.areaM2 - 1000) < .001);
  assert.deepEqual(squareArea(center, squareSideMetres(.1, 'ha')), area);
  assert.deepEqual(squareArea(center, squareSideMetres(.001, 'km2')), area);
  assert.equal(convertSquareSize(1000, 'm2', 'ha'), .1);
  assert.equal(convertSquareSize(1000, 'm2', 'km2'), .001);
  assert(Math.abs(squareSideMetres(10000, 'm2') / side - Math.sqrt(10)) < 1e-10);
});
