import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';
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

  it('renders header with the AgroGeo name, main landmark and footer', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('header .brand__name')?.textContent).toContain('AgroGeo');
    expect(el.querySelector('main#contenido')).not.toBeNull();
    expect(el.querySelector('footer')?.textContent).toContain('No está afiliado ni');
  });

  it('shows public navigation and account entry points to visitors', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const header = (fixture.nativeElement as HTMLElement).querySelector('header')!.textContent!;
    expect(header).toContain('Exploración');
    expect(header).not.toContain('Resultados');
    expect(header).toContain('Iniciar sesión');
    expect(header).toContain('Crear cuenta');
    expect(header).not.toContain('Mi panel');
  });

  it('provides direct primary links without duplicate menus', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const header = (fixture.nativeElement as HTMLElement).querySelector('header')!;
    expect(header.querySelectorAll('app-nav-dropdown').length).toBe(0);
    const links = [...header.querySelectorAll('.nav__list a')];
    expect(links.map((link) => link.textContent?.trim())).toEqual(['Inicio', 'Exploración']);
    expect(links.map((link) => link.getAttribute('href'))).toEqual(['/', '/explorar']);
  });

  it('switches to the personal navigation after signing in', async () => {
    const fixture = TestBed.createComponent(App);
    await TestBed.inject(AuthService).login({
      email: 'ana.gomez@correo.co',
      password: 'secreta123',
    });
    await fixture.whenStable();
    const header = (fixture.nativeElement as HTMLElement).querySelector('header')!.textContent!;
    expect(header).toContain('Mis fincas');
    const links = [
      ...(fixture.nativeElement as HTMLElement).querySelectorAll('header .nav__list a'),
    ];
    expect(links.map((link) => link.textContent?.trim())).toEqual([
      'Inicio',
      'Exploración',
      'Mis fincas',
    ]);
    expect(links[0].getAttribute('href')).toBe('/');
    expect(header).toContain('Exploración');
    expect(header).not.toContain('Resultados');
    expect(header).not.toContain('Mi panel');
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('header .brand')?.getAttribute('href'),
    ).toBe('/');
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
