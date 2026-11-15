import { Routes } from '@angular/router';
import { pageTitle } from './core/config/app-identity';
import { requireGuest, requireSession } from './core/auth/auth.guards';

/**
 * One integrated platform, organised around the user journey:
 *   cuenta → explorar/municipio → lote → caracterización → análisis, plus panel and perfil.
 * Every screen is lazy-loaded. Guards here only shape the UX; real authorization
 * must be enforced by the backend when it exists.
 */
export const routes: Routes = [
  {
    path: '',
    title: pageTitle('Inicio'),
    loadComponent: () => import('./features/home/home').then((m) => m.Home),
  },

  // Account
  {
    path: 'acceso',
    title: pageTitle('Iniciar sesión'),
    canActivate: [requireGuest],
    loadComponent: () => import('./features/auth/login/login').then((m) => m.Login),
  },
  {
    path: 'registro',
    title: pageTitle('Crear cuenta'),
    canActivate: [requireGuest],
    loadComponent: () => import('./features/auth/register/register').then((m) => m.Register),
  },
  {
    path: 'recuperar-contrasena',
    title: pageTitle('Recuperar contraseña'),
    loadComponent: () =>
      import('./features/auth/password-recovery/password-recovery').then((m) => m.PasswordRecovery),
  },

  // Geographic exploration and municipality selection (public)
  {
    path: 'explorar',
    title: pageTitle('Explorar el territorio'),
    loadComponent: () => import('./features/explorer/explorer').then((m) => m.Explorer),
  },

  // Farm journey (requires a session)
  {
    path: 'finca',
    canActivate: [requireSession],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'lote' },
      {
        path: 'lote',
        title: pageTitle('Municipio y lote'),
        loadComponent: () => import('./features/farm/plot/plot').then((m) => m.Plot),
      },
      {
        path: 'caracterizacion',
        title: pageTitle('Caracterización del lote'),
        loadComponent: () =>
          import('./features/farm/characterization/characterization').then((m) => m.Characterization),
      },
      {
        path: 'analisis',
        title: pageTitle('Análisis y recomendaciones'),
        loadComponent: () => import('./features/farm/analysis/analysis').then((m) => m.Analysis),
      },
    ],
  },

  // Personal area (requires a session)
  {
    path: 'panel',
    title: pageTitle('Mi panel'),
    canActivate: [requireSession],
    loadComponent: () => import('./features/dashboard/dashboard').then((m) => m.Dashboard),
  },
  {
    path: 'perfil',
    title: pageTitle('Mi perfil'),
    canActivate: [requireSession],
    loadComponent: () => import('./features/profile/profile').then((m) => m.Profile),
  },

  // Addresses from the previous two-module structure
  { path: 'datos', redirectTo: 'explorar' },
  { path: 'agricultor', redirectTo: 'panel' },

  {
    path: '**',
    title: pageTitle('Página no encontrada'),
    loadComponent: () => import('./features/not-found/not-found').then((m) => m.NotFound),
  },
];
