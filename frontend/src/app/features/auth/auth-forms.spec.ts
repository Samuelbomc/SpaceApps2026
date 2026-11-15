import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { AuthGateway } from '../../core/auth/auth-gateway';
import { MockAuthGateway } from '../../testing/mock-auth-gateway';
import { AuthService } from '../../core/auth/auth.service';
import { Login } from './login/login';
import { Register } from './register/register';

describe('Auth forms', () => {
  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthGateway, useClass: MockAuthGateway }],
    });
  });

  it('login: shows field errors and does not sign in when the form is invalid', async () => {
    const fixture = TestBed.createComponent(Login);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;

    el.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
    await fixture.whenStable();

    expect(el.querySelectorAll('.field-error').length).toBe(2);
    expect(el.querySelector('#login-email')?.getAttribute('aria-invalid')).toBe('true');
    expect(TestBed.inject(AuthService).isAuthenticated()).toBe(false);
  });

  it('register: requires matching passwords and account acknowledgement', async () => {
    const fixture = TestBed.createComponent(Register);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const type = (id: string, value: string) => {
      const input = el.querySelector<HTMLInputElement>(id)!;
      input.value = value;
      input.dispatchEvent(new Event('input'));
      input.dispatchEvent(new Event('blur'));
    };

    type('#reg-name', 'Ana');
    type('#reg-email', 'ana@correo.co');
    type('#reg-password', '12345678');
    type('#reg-confirm', '87654321');
    el.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
    await fixture.whenStable();

    expect(el.textContent).toContain('Las contraseñas no coinciden.');
    expect(el.textContent).toContain('Marca esta casilla para continuar.');
    expect(TestBed.inject(AuthService).isAuthenticated()).toBe(false);
  });

  it('register returns to saving the farm when registration was an optional map action', async () => {
    TestBed.overrideProvider(ActivatedRoute, {
      useValue: { snapshot: { queryParamMap: convertToParamMap({ volver: '/fincas' }) } },
    });
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    const fixture = TestBed.createComponent(Register);
    await fixture.whenStable();
    const element = fixture.nativeElement as HTMLElement;
    for (const [id, value] of [
      ['reg-name', 'Ana'],
      ['reg-email', 'ana@correo.co'],
      ['reg-password', 'clave-de-prueba-larga'],
      ['reg-confirm', 'clave-de-prueba-larga'],
    ]) {
      const input = element.querySelector<HTMLInputElement>('#' + id)!;
      input.value = value;
      input.dispatchEvent(new Event('input'));
    }
    element.querySelector<HTMLInputElement>('input[type="checkbox"]')!.click();
    element
      .querySelector<HTMLFormElement>('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith('/fincas'));
  });

  it('login opens Exploration by default instead of the former dashboard', async () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    const fixture = TestBed.createComponent(Login);
    await fixture.whenStable();
    const element = fixture.nativeElement as HTMLElement;
    for (const [id, value] of [
      ['login-email', 'ana@correo.co'],
      ['login-password', 'clave-de-prueba-larga'],
    ]) {
      const input = element.querySelector<HTMLInputElement>('#' + id)!;
      input.value = value;
      input.dispatchEvent(new Event('input'));
    }
    element
      .querySelector<HTMLFormElement>('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith('/explorar'));
  });
});
