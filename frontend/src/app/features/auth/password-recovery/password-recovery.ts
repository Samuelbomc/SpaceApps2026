import { ChangeDetectionStrategy, Component, ElementRef, inject, signal, viewChild } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { AuthLayout } from '../auth-layout/auth-layout';
import { focusFirstInvalid, messageFor, showError } from '../form-helpers';

/**
 * Password recovery screen. The confirmation message is deliberately neutral
 * ("if an account exists…") — the pattern a real backend should keep, so the
 * screen never reveals whether an e-mail is registered.
 */
@Component({
  selector: 'app-password-recovery',
  imports: [ReactiveFormsModule, RouterLink, AuthLayout],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-auth-layout
      heading="Recuperar contraseña"
      lead="Escribe el correo de tu cuenta y te enviaremos instrucciones."
    >
      @if (sent()) {
        <div class="notice notice--info" role="status">
          <span>
            <strong>Solicitud recibida.</strong> Si existe una cuenta con ese correo, recibirás las
            instrucciones. En esta demostración no se envía ningún correo.
          </span>
        </div>
        <a class="btn btn--primary btn--block" routerLink="/acceso">Volver a iniciar sesión</a>
      } @else {
        <form #formEl class="form" [formGroup]="form" (ngSubmit)="submit()" novalidate>
          @if (error()) {
            <p class="form-alert" role="alert">{{ error() }}</p>
          }
          <div class="field">
            <label for="rec-email">Correo electrónico</label>
            <input
              id="rec-email"
              class="input"
              type="email"
              formControlName="email"
              autocomplete="email"
              inputmode="email"
              [attr.aria-invalid]="showError(form.controls.email)"
              aria-describedby="rec-email-error"
            />
            @if (showError(form.controls.email)) {
              <p id="rec-email-error" class="field-error">Escribe un correo válido.</p>
            }
          </div>
          <button type="submit" class="btn btn--primary btn--block" [disabled]="submitting()">
            {{ submitting() ? 'Enviando…' : 'Enviar instrucciones' }}
          </button>
        </form>
        <p><a routerLink="/acceso">Volver a iniciar sesión</a></p>
      }
    </app-auth-layout>
  `,
})
export class PasswordRecovery {
  private readonly auth = inject(AuthService);
  private readonly formEl = viewChild<ElementRef<HTMLFormElement>>('formEl');

  protected readonly form = inject(NonNullableFormBuilder).group({
    email: ['', [Validators.required, Validators.email]],
  });
  protected readonly submitting = signal(false);
  protected readonly sent = signal(false);
  protected readonly error = signal('');
  protected readonly showError = showError;

  protected async submit(): Promise<void> {
    this.error.set('');
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      const el = this.formEl();
      if (el) focusFirstInvalid(el.nativeElement);
      return;
    }
    this.submitting.set(true);
    try {
      await this.auth.requestPasswordReset(this.form.getRawValue().email);
      this.sent.set(true);
    } catch (err) {
      this.error.set(messageFor(err));
    } finally {
      this.submitting.set(false);
    }
  }
}
