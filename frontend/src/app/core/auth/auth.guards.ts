import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

/** Sends signed-out users to the login screen, remembering where they wanted to go. */
export const requireSession: CanActivateFn = async (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  await auth.ready;
  if (auth.isAuthenticated()) return true;
  return router.createUrlTree(['/acceso'], { queryParams: { volver: state.url } });
};

/** Keeps signed-in users away from login/registration screens. */
export const requireGuest: CanActivateFn = async () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  await auth.ready;
  return auth.isAuthenticated() ? router.createUrlTree(['/panel']) : true;
};

/** Only allows internal return URLs (prevents open redirects via ?volver=). */
export function safeReturnUrl(value: string | null | undefined, fallback = '/panel'): string {
  return value && value.startsWith('/') && !value.startsWith('//') ? value : fallback;
}
