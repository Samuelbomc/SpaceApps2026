import { Routes } from '@angular/router';
import { pageTitle } from './core/config/app-identity';

/**
 * Top-level routes. Each feature is lazy-loaded so the initial bundle stays small
 * as the data portal (maps, charts) and farmer workspace grow.
 */
export const routes: Routes = [
  {
    path: '',
    title: pageTitle('Inicio'),
    loadComponent: () => import('./features/home/home').then((m) => m.Home),
  },
  {
    path: 'datos',
    title: pageTitle('Portal de datos'),
    loadComponent: () =>
      import('./features/data-portal/data-portal').then((m) => m.DataPortal),
  },
  {
    path: 'agricultor',
    title: pageTitle('Espacio del agricultor'),
    loadComponent: () =>
      import('./features/farmer-workspace/farmer-workspace').then((m) => m.FarmerWorkspace),
  },
  {
    path: '**',
    title: pageTitle('Página no encontrada'),
    loadComponent: () => import('./features/not-found/not-found').then((m) => m.NotFound),
  },
];
