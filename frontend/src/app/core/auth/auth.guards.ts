import { inject } from '@angular/core';
import { CanActivateFn, PRIMARY_OUTLET, Router } from '@angular/router';
import { AuthService } from './auth.service';

/** Sends signed-out users to the login screen, remembering where they wanted to go. */
export const requireSession: CanActivateFn = async (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  await auth.ready;
  if (auth.isAuthenticated()) return true;
  return router.createUrlTree(['/acceso'], { queryParams: { volver: state.url } });
};

/** Skips the obsolete login step for plot links; otherwise keeps signed-in users out. */
export const requireGuest: CanActivateFn = async (route) => {
  const router = inject(Router);
  const returnUrl = route.queryParamMap.get('volver');
  if (returnUrl?.startsWith('/') && !returnUrl.startsWith('//')) {
    const target = router.parseUrl(returnUrl);
    const segments = target.root.children[PRIMARY_OUTLET]?.segments;
    if (segments?.length === 2 && segments[0].path === 'finca' && segments[1].path === 'lote') {
      const municipality = target.queryParams['municipio'];
      return router.createUrlTree(['/explorar'], {
        queryParams:
          typeof municipality === 'string' && /^\d{5}$/.test(municipality)
            ? { municipio: municipality }
            : {},
        fragment: 'lote',
      });
    }
  }
  const auth = inject(AuthService);
  await auth.ready;
  return auth.isAuthenticated() ? router.createUrlTree(['/explorar']) : true;
};

/** Only allows internal return URLs (prevents open redirects via ?volver=). */
export function safeReturnUrl(value: string | null | undefined, fallback = '/explorar'): string {
  return value && value.startsWith('/') && !value.startsWith('//') ? value : fallback;
}
