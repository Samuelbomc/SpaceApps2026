import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';
import { APP_IDENTITY } from './core/config/app-identity';
import { AuthGateway } from './core/auth/auth-gateway';
import { MockAuthGateway } from './testing/mock-auth-gateway';
import { AuthService } from './core/auth/auth.service';

describe('App shell', () => {
  beforeEach(async () => {
    sessionStorage.clear();
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([]), { provide: AuthGateway, useClass: MockAuthGateway }],
    }).compileComponents();
  });

  it('renders header with the placeholder name, main landmark and footer', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('header .brand__name')?.textContent).toContain(APP_IDENTITY.name);
    expect(el.querySelector('main#contenido')).not.toBeNull();
    expect(el.querySelector('footer')?.textContent).toContain('No está afiliado ni');
  });

  it('shows public navigation and account entry points to visitors', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const header = (fixture.nativeElement as HTMLElement).querySelector('header')!.textContent!;
    expect(header).toContain('Explorar el mapa');
    expect(header).toContain('Iniciar sesión');
    expect(header).toContain('Crear cuenta');
    expect(header).not.toContain('Mi panel');
  });

  it('groups Inicio, Cómo funciona and Fuentes y métodos in one dropdown (no duplicates)', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const header = (fixture.nativeElement as HTMLElement).querySelector('header')!;
    expect(header.querySelectorAll('app-nav-dropdown').length).toBe(1);
    const all = [...header.querySelectorAll('a')].map((a) => a.textContent?.trim());
    expect(all.filter((t) => t === 'Cómo funciona').length).toBe(1);
    expect(all.filter((t) => t === 'Fuentes y métodos').length).toBe(1);
  });

  it('switches to the personal navigation after signing in', async () => {
    const fixture = TestBed.createComponent(App);
    await TestBed.inject(AuthService).login({
      email: 'ana.gomez@correo.co',
      password: 'secreta123',
    });
    await fixture.whenStable();
    const header = (fixture.nativeElement as HTMLElement).querySelector('header')!.textContent!;
    expect(header).toContain('Mi panel');
    expect(header).toContain('Ana gomez');
    expect(header).not.toContain('Demo');
    expect(header).toContain('Cerrar sesión');
    expect(header).not.toContain('Crear cuenta');
  });

  it('toggles the mobile menu and exposes aria-expanded', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const toggle = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      '.menu-toggle',
    )!;
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    toggle.click();
    await fixture.whenStable();
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
  });
});
