import assert from 'node:assert/strict';
import test from 'node:test';
import { createAPIClient, APIError } from '../src/index.ts';

test('base URL can target a same-origin proxy or FastAPI with authenticated cookies', async () => {
  const calls = [];
  const client = createAPIClient({ baseURL: 'http://localhost:8000/api/v1', fetcher: async (url, options) => {
    calls.push({ url, options });
    return Response.json({ user: { display_name: 'test-only' } });
  }});
  const controller = new AbortController();
  await client.request('auth/me', { signal: controller.signal });
  assert.equal(calls[0].url, 'http://localhost:8000/api/v1/auth/me');
  assert.equal(calls[0].options.credentials, 'include');
  assert.equal(calls[0].options.cache, 'no-store');
  assert.equal(calls[0].options.signal, controller.signal);
});

test('CSRF and multipart body are preserved without inventing a content-type boundary', async () => {
  const form = new FormData(); form.append('file', new Blob(['date,variable,value,unit\n']), 'fixture.csv');
  const client = createAPIClient({ fetcher: async (url, options) => {
    assert.equal(options.headers['X-CSRF-Token'], 'test-token');
    assert.equal(options.headers['Content-Type'], undefined);
    assert.equal(options.body, form);
    return new Response(null, { status: 204 });
  }});
  assert.equal(await client.request('farms/test/datasets', { method: 'POST', body: form, headers: { 'X-CSRF-Token': 'test-token' } }), undefined);
});

test('downloads keep CSV bytes and propagate private access failures', async () => {
  const csv = 'date,variable,value,unit\n';
  const client = createAPIClient({ fetcher: async () => new Response(csv, { headers: { 'Content-Type': 'text/csv' } }) });
  assert.equal(await (await client.download('farms/test/datasets/test/download')).text(), csv);
  const denied = createAPIClient({ fetcher: async () => Response.json({ detail: 'Inicia sesión.' }, { status: 401 }) });
  await assert.rejects(denied.download('farms/test/datasets/test/download'), error => error instanceof APIError && error.status === 401);
});

test('invalid relative resource paths cannot escape the configured backend', async () => {
  const client = createAPIClient({ fetcher: async () => { throw new Error('No debe consultar'); } });
  for (const path of ['/auth/me', '../auth/me', '%2e%2e/auth/me', 'https://example.com/auth/me']) {
    await assert.rejects(client.request(path), /ruta de API/);
  }
  assert.throws(() => createAPIClient({ baseURL: '//example.com' }), /URL base/);
});
