import { inject } from '@angular/core';
import { Router, Routes, RedirectFunction } from '@angular/router';
import { pageTitle } from './core/config/app-identity';
import { requireGuest, requireSession } from './core/auth/auth.guards';

/**
 * One integrated platform, organised around the user journey:
 *   exploración, lote y resultados públicos en /explorar; cuenta opcional para guardar.
 * Every screen is lazy-loaded. Guards here only shape the UX; real authorization
 * is enforced by FastAPI.
 */
const workspaceRedirect: RedirectFunction = ({ queryParams, fragment }) =>
  inject(Router).createUrlTree(['/explorar'], { queryParams, fragment: fragment ?? undefined });
const analysisRedirect: RedirectFunction = ({ queryParams }) =>
  inject(Router).createUrlTree(['/explorar'], { queryParams, fragment: 'resultados' });

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
    title: pageTitle('Exploración'),
    loadComponent: () => import('./features/explorer/explorer').then((m) => m.Explorer),
  },

  // Compatibility addresses: map and results are public; editing private farms requires a session.
  {
    path: 'finca',
    children: [
      { path: '', pathMatch: 'full', redirectTo: workspaceRedirect },
      {
        path: 'lote',
        pathMatch: 'full',
        redirectTo: workspaceRedirect,
      },
      {
        path: 'caracterizacion',
        canActivate: [requireSession],
        title: pageTitle('Caracterización del lote'),
        loadComponent: () =>
          import('./features/farm/characterization/characterization').then(
            (m) => m.Characterization,
          ),
      },
      {
        path: 'analisis',
        pathMatch: 'full',
        redirectTo: workspaceRedirect,
      },
    ],
  },

  {
    path: 'fincas',
    canActivate: [requireSession],
    loadComponent: () => import('./features/farm/manage/manage').then((m) => m.FarmManage),
  },
  {
    path: 'analisis',
    pathMatch: 'full',
    redirectTo: analysisRedirect,
  },
  { path: 'login', redirectTo: 'acceso', pathMatch: 'full' },
  // Personal area (requires a session)
  {
    path: 'panel',
    pathMatch: 'full',
    redirectTo: workspaceRedirect,
  },
  {
    path: 'perfil',
    title: pageTitle('Mi perfil'),
    canActivate: [requireSession],
    loadComponent: () => import('./features/profile/profile').then((m) => m.Profile),
  },

  // Addresses from the previous two-module structure
  { path: 'datos', redirectTo: 'explorar' },
  { path: 'agricultor', redirectTo: 'explorar' },

  {
    path: '**',
    title: pageTitle('Página no encontrada'),
    loadComponent: () => import('./features/not-found/not-found').then((m) => m.NotFound),
  },
];
