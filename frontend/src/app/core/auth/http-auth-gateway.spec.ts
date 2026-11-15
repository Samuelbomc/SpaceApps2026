import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { HttpAuthGateway } from './http-auth-gateway';
import { AuthGateway } from './auth-gateway';
import { AuthService } from './auth.service';

const fixture = {
  user: {
    user_id: 'test-only',
    display_name: 'Ana real',
    email: 'ana@example.com',
    created_at: '2026-01-01T00:00:00Z',
  },
  csrf_token: 'test-csrf',
  expires_at: '2026-11-20T00:00:00Z',
};
describe('FastAPI authentication gateway', () => {
  afterEach(() => vi.unstubAllGlobals());
  it('restores asynchronously and maps server fields without storing a token', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json(fixture)),
    );
    TestBed.configureTestingModule({
      providers: [{ provide: AuthGateway, useClass: HttpAuthGateway }],
    });
    const auth = TestBed.inject(AuthService);
    expect(auth.isAuthenticated()).toBe(false);
    await auth.ready;
    expect(auth.user()?.name).toBe('Ana real');
    expect(auth.isDemo()).toBe(false);
    expect(auth.csrfHeaders()['X-CSRF-Token']).toBe('test-csrf');
  });
  it('registers with the real payload, sends CSRF on logout and handles 204', async () => {
    const requests: { url: string; options: RequestInit }[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, options: RequestInit) => {
        requests.push({ url, options });
        if (url.endsWith('/auth/me'))
          return Response.json({ detail: 'Sin sesión' }, { status: 401 });
        if (url.endsWith('/auth/logout')) return new Response(null, { status: 204 });
        return Response.json(fixture, { status: 201 });
      }),
    );
    TestBed.configureTestingModule({
      providers: [{ provide: AuthGateway, useClass: HttpAuthGateway }],
    });
    const auth = TestBed.inject(AuthService);
    await auth.ready;
    await auth.register({
      name: 'Ana real',
      email: 'ana@example.com',
      password: 'Una frase larga de prueba',
    });
    expect(JSON.parse(requests[1].options.body as string)).toEqual({
      display_name: 'Ana real',
      email: 'ana@example.com',
      password: 'Una frase larga de prueba',
    });
    await auth.logout();
    expect((requests.at(-1)!.options.headers as Record<string, string>)['X-CSRF-Token']).toBe(
      'test-csrf',
    );
    expect(auth.isAuthenticated()).toBe(false);
  });
  it('a 401 is not silently converted into a demonstration login', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json({ detail: 'Credenciales inválidas' }, { status: 401 })),
    );
    const gateway = new HttpAuthGateway();
    expect(await gateway.restore()).toBeNull();
    await expect(gateway.login({ email: 'ana@example.com', password: 'invalid' })).rejects.toThrow(
      'Credenciales inválidas',
    );
  });
});
