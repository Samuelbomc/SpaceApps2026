import assert from 'node:assert/strict';
import test from 'node:test';
import { api, APIError, loadObservationHistory } from './api.ts';
const updated = '2026-11-14T12:00:00Z';
function response(offset, total, lastUpdated = updated) {
  return new Response(JSON.stringify({ region_id: 'test', limit: 1000, offset, total,
    first_date: total ? '2020-01-01' : null, last_date: total ? '2026-11-11' : null,
    last_updated_at: total ? lastUpdated : null,
    items: Array.from({ length: Math.min(1000, total - offset) }, (_, index) => ({ source: 'fixture', date: '2026-11-11', variable: `v${offset + index}`, value: offset + index, unit: 'test', quality: 'provider_value_unvalidated', resolution: 'test' })) }), { status: 200, headers: { 'Content-Type': 'application/json' } });
}
test('loads all history beyond 10000 records without sending date filters', async t => {
  const offsets = [];
  t.mock.method(globalThis, 'fetch', async url => {
    const query = new URL(url, 'http://localhost').searchParams;
    assert.equal(query.has('start'), false); assert.equal(query.has('end'), false);
    const offset = Number(query.get('offset')); offsets.push(offset);
    return response(offset, 10002);
  });
  const history = await loadObservationHistory('test');
  assert.equal(history.items.length, 10002);
  assert.equal(history.items.at(-1).value, 10001);
  assert.equal(history.last_updated_at, updated);
  assert.deepEqual(offsets, Array.from({ length: 11 }, (_, index) => index * 1000));
});
test('restarts once when ingestion changes during paging instead of mixing pages', async t => {
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async url => {
    const offset = Number(new URL(url, 'http://localhost').searchParams.get('offset'));
    calls++;
    return response(offset, 1001, calls === 1 ? '2026-11-13T12:00:00Z' : updated);
  });
  const history = await loadObservationHistory('test');
  assert.equal(calls, 4); assert.equal(history.items.length, 1001);
  assert.equal(history.last_updated_at, updated);
});
test('does not present partial data as a complete historical dataset', async t => {
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async url => {
    calls++;
    const offset = Number(new URL(url, 'http://localhost').searchParams.get('offset'));
    return response(offset, 1001, `2026-11-14T12:00:0${calls}Z`);
  });
  await assert.rejects(loadObservationHistory('test'), /Los datos cambiaron/);
});
test('empty database returns empty history and no invented update timestamp', async t => {
  t.mock.method(globalThis, 'fetch', async () => response(0, 0));
  const history = await loadObservationHistory('test');
  assert.equal(history.total, 0); assert.equal(history.last_updated_at, null);
  assert.deepEqual(history.items, []);
});

test('logout and private deletion accept an empty 204 response', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response(null, { status: 204 }));
  assert.equal(await api('auth/logout', { method: 'POST' }), undefined);
});
test('authentication failures preserve status without displaying submitted values', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ detail: 'Inicia sesión.' }), { status: 401 }));
  await assert.rejects(api('auth/me'), error => error instanceof APIError && error.status === 401 && error.message === 'Inicia sesión.');
});
