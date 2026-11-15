import { ChangeDetectionStrategy, Component, ElementRef, inject, signal, viewChild } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { safeReturnUrl } from '../../../core/auth/auth.guards';
import { AuthLayout } from '../auth-layout/auth-layout';
import { MIN_PASSWORD_LENGTH, focusFirstInvalid, messageFor, showError } from '../form-helpers';

/** Login screen (demonstration authentication). */
@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, RouterLink, AuthLayout],
  templateUrl: './login.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Login {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly formEl = viewChild.required<ElementRef<HTMLFormElement>>('formEl');

  protected readonly form = inject(NonNullableFormBuilder).group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(MIN_PASSWORD_LENGTH)]],
  });
  protected readonly submitting = signal(false);
  protected readonly error = signal('');
  protected readonly showPassword = signal(false);
  protected readonly showError = showError;
  protected readonly minLength = MIN_PASSWORD_LENGTH;

  /** Shown when a guard redirected here. */
  protected readonly redirected = !!this.route.snapshot.queryParamMap.get('volver');

  protected async submit(): Promise<void> {
    this.error.set('');
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      focusFirstInvalid(this.formEl().nativeElement);
      return;
    }
    this.submitting.set(true);
    try {
      await this.auth.login(this.form.getRawValue());
      // The password is not kept anywhere after this point.
      this.form.controls.password.reset();
      await this.router.navigateByUrl(safeReturnUrl(this.route.snapshot.queryParamMap.get('volver')));
    } catch (err) {
      this.error.set(messageFor(err));
    } finally {
      this.submitting.set(false);
    }
  }

  /** One-click access for demonstrations. */
  protected useDemoAccount(): void {
    this.form.setValue({ email: 'demo@ejemplo.co', password: 'demostracion' });
    void this.submit();
  }
}
