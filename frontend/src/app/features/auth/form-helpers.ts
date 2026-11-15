import { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';
import { APIError } from '@agrogeo/api-client';
import { AuthError } from '../../core/auth/auth.models';

export const MIN_PASSWORD_LENGTH = 15;

/** Show a field's error only after the user has interacted with it (or tried to submit). */
export function showError(control: AbstractControl): boolean {
  return control.invalid && (control.touched || control.dirty);
}

/** Moves keyboard focus to the first invalid input inside a form element. */
export function focusFirstInvalid(form: HTMLElement): void {
  form
    .querySelector<HTMLElement>('input.ng-invalid, select.ng-invalid, textarea.ng-invalid')
    ?.focus();
}

/** Group validator: `password` and `confirm` controls must match. */
export const passwordsMatch: ValidatorFn = (group: AbstractControl): ValidationErrors | null => {
  const password = group.get('password')?.value;
  const confirm = group.get('confirm')?.value;
  return password && confirm && password !== confirm ? { mismatch: true } : null;
};

export function messageFor(error: unknown): string {
  return error instanceof AuthError || error instanceof APIError
    ? error.message
    : 'No fue posible completar la solicitud. Inténtalo de nuevo.';
}
