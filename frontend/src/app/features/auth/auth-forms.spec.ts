import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { AuthGateway } from '../../core/auth/auth-gateway';
import { MockAuthGateway } from '../../core/auth/mock-auth-gateway';
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

  it('login: the demo account signs in and navigates to the panel', async () => {
    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    const fixture = TestBed.createComponent(Login);
    await fixture.whenStable();

    (fixture.nativeElement as HTMLElement)
      .querySelectorAll<HTMLButtonElement>('button[type="button"]')[1]
      .click();
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith('/panel'));
    expect(TestBed.inject(AuthService).isAuthenticated()).toBe(true);
  });

  it('register: requires matching passwords and the demo acknowledgement', async () => {
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
});
