import { TestBed } from '@angular/core/testing';
import { Router, UrlTree, provideRouter } from '@angular/router';
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
      TestBed.runInInjectionContext(() => guard({} as never, { url } as never));

    const redirect = (await run(requireSession, '/finca/lote')) as UrlTree;
    expect(TestBed.inject(Router).serializeUrl(redirect)).toBe('/acceso?volver=%2Ffinca%2Flote');
    expect(await run(requireGuest, '/acceso')).toBe(true);

    await auth.login({ email: 'ana@correo.co', password: '12345678' });
    expect(await run(requireSession, '/panel')).toBe(true);
    expect(
      TestBed.inject(Router).serializeUrl((await run(requireGuest, '/acceso')) as UrlTree),
    ).toBe('/panel');
  });

  it('only accepts internal return URLs', () => {
    expect(safeReturnUrl('/finca/lote')).toBe('/finca/lote');
    expect(safeReturnUrl('https://evil.example')).toBe('/panel');
    expect(safeReturnUrl('//evil.example')).toBe('/panel');
    expect(safeReturnUrl(null)).toBe('/panel');
  });
});
