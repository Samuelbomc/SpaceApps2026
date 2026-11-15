import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { AuthLayout } from '../auth-layout/auth-layout';
import {
  MIN_PASSWORD_LENGTH,
  focusFirstInvalid,
  messageFor,
  passwordsMatch,
  showError,
} from '../form-helpers';

/** Account registration screen backed by FastAPI. */
@Component({
  selector: 'app-register',
  imports: [ReactiveFormsModule, RouterLink, AuthLayout],
  templateUrl: './register.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Register {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly formEl = viewChild.required<ElementRef<HTMLFormElement>>('formEl');

  protected readonly form = inject(NonNullableFormBuilder).group(
    {
      name: ['', [Validators.required, Validators.maxLength(80)]],
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(MIN_PASSWORD_LENGTH)]],
      confirm: ['', [Validators.required]],
      acknowledge: [false, [Validators.requiredTrue]],
    },
    { validators: passwordsMatch },
  );
  protected readonly submitting = signal(false);
  protected readonly error = signal('');
  protected readonly showPassword = signal(false);
  protected readonly showError = showError;
  protected readonly minLength = MIN_PASSWORD_LENGTH;

  protected mismatch(): boolean {
    const confirm = this.form.controls.confirm;
    return this.form.hasError('mismatch') && (confirm.touched || confirm.dirty);
  }

  protected async submit(): Promise<void> {
    this.error.set('');
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      focusFirstInvalid(this.formEl().nativeElement);
      return;
    }
    this.submitting.set(true);
    try {
      const { name, email, password } = this.form.getRawValue();
      await this.auth.register({ name, email, password });
      this.form.reset();
      await this.router.navigateByUrl('/panel');
    } catch (err) {
      this.error.set(messageFor(err));
    } finally {
      this.submitting.set(false);
    }
  }
}
