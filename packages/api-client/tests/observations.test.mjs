import assert from 'node:assert/strict';
import test from 'node:test';
import { dailySegments, latestFor, summarizeObservations } from '../src/observations.ts';

const row = (date, value = 20, extra = {}) => ({ date, value, source: 'NASA_POWER', variable: 'T2M', unit: 'C', resolution: 'native', quality: 'provider_value_unvalidated', ...extra });

test('coverage counts received days, keeps invalid and missing records distinct', () => {
  const summary = summarizeObservations([row('2026-01-02'), row('2026-01-02', null, { quality: 'missing' }), row('2026-01-04', 200, { quality: 'out_of_range' })]);
  assert.equal(summary.days, 2);
  assert.equal(summary.usable, 1);
  assert.equal(summary.missing, 1);
  assert.equal(summary.quality.out_of_range, 1);
  assert.equal(summary.firstDate, '2026-01-02');
  assert.equal(summary.lastDate, '2026-01-04');
});
test('series do not combine different sources, units or resolutions', () => {
  const summary = summarizeObservations([row('2026-01-02'), row('2026-01-03', 68, { unit: 'F' }), row('2026-01-03', 21, { source: 'other' }), row('2026-01-03', 21, { resolution: 'other' })]);
  assert.equal(summary.series.length, 4);
});
test('latest condition is based on date, never a missing or flagged value', () => {
  const rows = [row('2026-01-01'), row('2026-01-04', null), row('2026-01-03', 22), row('2026-01-05', 200, { quality: 'out_of_range' })];
  assert.equal(latestFor(rows, ['T2M']).date, '2026-01-03');
  assert.equal(latestFor(rows, ['RH2M']), null);
});
test('charts break across missing values and days without records', () => {
  const segments = dailySegments([row('2026-01-01'), row('2026-01-02'), row('2026-01-03', null), row('2026-01-04'), row('2026-01-08')]);
  assert.deepEqual(segments.map(segment => segment.map(point => point.date)), [['2026-01-01', '2026-01-02'], ['2026-01-04'], ['2026-01-08']]);
});
test('empty input has no invented coverage, latest value or chart', () => {
  const result = summarizeObservations([]);
  assert.equal(result.firstDate, null);
  assert.equal(result.lastDate, null);
  assert.equal(result.usable, 0);
  assert.equal(result.days, 0);
  assert.equal(latestFor([], ['T2M']), null);
  assert.deepEqual(dailySegments([]), []);
});
