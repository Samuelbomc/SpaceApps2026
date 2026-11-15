import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { AnalysisJourneyStore } from '../../core/journey/analysis-journey.store';
import { showError } from '../auth/form-helpers';

/** User profile: view and edit public profile data, see session info, sign out. */
@Component({
  selector: 'app-profile',
  imports: [ReactiveFormsModule, DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: `
    .profile { max-width: 44rem; padding-top: var(--sp-6); }
    h1 { font-size: var(--fs-2xl); margin-block: var(--sp-2) var(--sp-5); }
    .card { display: grid; gap: var(--sp-5); margin-bottom: var(--sp-5); }
    h2 { font-size: var(--fs-lg); }
    .actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-3); }
    .saved { font-size: var(--fs-sm); color: var(--c-forest-700); font-weight: 600; }
  `,
  template: `
    <section class="section">
      <div class="container profile">
        <span class="eyebrow">Cuenta</span>
        <h1>Mi perfil</h1>

        @if (auth.user(); as user) {
          <form class="card form" [formGroup]="form" (ngSubmit)="save()" novalidate>
            <h2>Datos personales</h2>
            <div class="field">
              <label for="profile-name">Nombre</label>
              <input id="profile-name" class="input" formControlName="name" autocomplete="name"
                [attr.aria-invalid]="showError(form.controls.name)" aria-describedby="profile-name-error" />
              @if (showError(form.controls.name)) {
                <p id="profile-name-error" class="field-error">Escribe tu nombre.</p>
              }
            </div>
            <div class="field">
              <label for="profile-email">Correo electrónico</label>
              <input id="profile-email" class="input" [value]="user.email" readonly aria-describedby="profile-email-hint" />
              <p id="profile-email-hint" class="field-hint">El cambio de correo estará disponible con las cuentas reales.</p>
            </div>
            <div class="actions">
              <button type="submit" class="btn btn--primary" [disabled]="saving()">
                {{ saving() ? 'Guardando…' : 'Guardar cambios' }}
              </button>
              @if (saved()) {
                <span class="saved" role="status">Cambios guardados en esta sesión.</span>
              }
            </div>
          </form>

          <div class="card">
            <h2>Sesión</h2>
            <dl class="spec-list">
              <dt>Tipo</dt>
              <dd>{{ auth.isDemo() ? 'Demostración (sin cuenta real)' : 'Cuenta' }}</dd>
              <dt>Iniciada</dt>
              <dd>{{ auth.session()?.startedAt | date: 'medium' }}</dd>
            </dl>
            @if (auth.isDemo()) {
              <p class="notice notice--demo" role="note">
                <span>Esta sesión y sus datos se borran al cerrar la pestaña o al cerrar sesión.</span>
              </p>
            }
            <div class="actions">
              <button type="button" class="btn btn--secondary" (click)="logout()">Cerrar sesión</button>
            </div>
          </div>
        }
      </div>
    </section>
  `,
})
export class Profile {
  protected readonly auth = inject(AuthService);
  private readonly journey = inject(AnalysisJourneyStore);
  private readonly router = inject(Router);

  protected readonly form = inject(NonNullableFormBuilder).group({
    name: [this.auth.user()?.name ?? '', [Validators.required, Validators.maxLength(80)]],
  });
  protected readonly saving = signal(false);
  protected readonly saved = signal(false);
  protected readonly showError = showError;

  protected async save(): Promise<void> {
    this.saved.set(false);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    try {
      await this.auth.updateName(this.form.getRawValue().name);
      this.saved.set(true);
    } finally {
      this.saving.set(false);
    }
  }

  protected async logout(): Promise<void> {
    await this.auth.logout();
    this.journey.reset();
    await this.router.navigateByUrl('/');
  }
}
