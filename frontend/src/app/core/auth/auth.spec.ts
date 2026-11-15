import { TestBed } from '@angular/core/testing';
import { Router, UrlTree, convertToParamMap, provideRouter } from '@angular/router';
import { AuthGateway } from './auth-gateway';
import { MockAuthGateway } from '../../testing/mock-auth-gateway';
import { AuthService } from './auth.service';
import { requireGuest, requireSession, safeReturnUrl } from './auth.guards';

describe('Session state with test gateway', () => {
  let auth: AuthService;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthGateway, useClass: MockAuthGateway }],
    });
    auth = TestBed.inject(AuthService);
  });

  it('starts a test session and never stores the password', async () => {
    await auth.login({ email: 'Maria@Correo.co', password: 'contraseña-secreta' });
    expect(auth.isAuthenticated()).toBe(true);
    expect(auth.user()?.email).toBe('maria@correo.co');

    const stored = JSON.stringify(sessionStorage);
    expect(stored).toContain('maria@correo.co');
    expect(stored).not.toContain('contraseña-secreta');
  });

  it('registers with the given name and signs out cleanly', async () => {
    await auth.register({ name: '  Luis Pérez ', email: 'luis@correo.co', password: '12345678' });
    expect(auth.user()?.name).toBe('Luis Pérez');
    await auth.logout();
    expect(auth.isAuthenticated()).toBe(false);
    expect(sessionStorage.length).toBe(0);
  });

  it('restores the test session after a reload (new service instance)', async () => {
    await auth.login({ email: 'ana@correo.co', password: '12345678' });
    const restored = new MockAuthGateway().restore();
    expect(restored?.user.email).toBe('ana@correo.co');
  });

  it('guards: redirects visitors to login keeping the return URL, and signed-in users away from login', async () => {
    const run = (guard: typeof requireSession, url: string) =>
      TestBed.runInInjectionContext(() =>
        guard({ queryParamMap: convertToParamMap({}) } as never, { url } as never),
      );

    const redirect = (await run(requireSession, '/fincas')) as UrlTree;
    expect(TestBed.inject(Router).serializeUrl(redirect)).toBe('/acceso?volver=%2Ffincas');
    expect(await run(requireGuest, '/acceso')).toBe(true);

    await auth.login({ email: 'ana@correo.co', password: '12345678' });
    expect(await run(requireSession, '/perfil')).toBe(true);
    expect(
      TestBed.inject(Router).serializeUrl((await run(requireGuest, '/acceso')) as UrlTree),
    ).toBe('/explorar');
  });

  it('sends legacy plot return links straight to the public map with the municipality', async () => {
    const router = TestBed.inject(Router);
    const result = await TestBed.runInInjectionContext(() =>
      requireGuest(
        { queryParamMap: convertToParamMap({ volver: '/finca/lote?municipio=05002' }) } as never,
        { url: '/acceso' } as never,
      ),
    );
    expect(router.serializeUrl(result as UrlTree)).toBe('/explorar?municipio=05002#lote');
    expect(auth.isAuthenticated()).toBe(false);
  });

  it('keeps explicit login and private or external return destinations on the login screen', async () => {
    for (const volver of [
      '/fincas',
      '/finca/caracterizacion',
      'https://example.invalid/finca/lote',
      '//example.invalid/finca/lote',
      '/finca/lote-extra',
    ]) {
      const result = await TestBed.runInInjectionContext(() =>
        requireGuest(
          { queryParamMap: convertToParamMap({ volver }) } as never,
          { url: '/acceso' } as never,
        ),
      );
      expect(result).toBe(true);
    }
  });

  it('only accepts internal return URLs', () => {
    expect(safeReturnUrl('/finca/lote')).toBe('/finca/lote');
    expect(safeReturnUrl('https://evil.example')).toBe('/explorar');
    expect(safeReturnUrl('//evil.example')).toBe('/explorar');
    expect(safeReturnUrl(null)).toBe('/explorar');
  });
});
