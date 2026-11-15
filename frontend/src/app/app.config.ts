import { ApplicationConfig, LOCALE_ID, provideBrowserGlobalErrorListeners } from '@angular/core';
import { registerLocaleData } from '@angular/common';
import { provideHttpClient, withFetch } from '@angular/common/http';
import localeEsCo from '@angular/common/locales/es-CO';
import { provideRouter, withInMemoryScrolling, withRouterConfig } from '@angular/router';
import { routes } from './app.routes';
import { AuthGateway } from './core/auth/auth-gateway';
import { MockAuthGateway } from './core/auth/mock-auth-gateway';

// Spanish (Colombia) number and date formatting for the whole UI.
registerLocaleData(localeEsCo);

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    { provide: LOCALE_ID, useValue: 'es-CO' },
    // Static data files today (geo boundaries); the future FastAPI backend later.
    provideHttpClient(withFetch()),
    // DEMONSTRATION authentication. Replace with a real HttpAuthGateway when the backend exists.
    { provide: AuthGateway, useClass: MockAuthGateway },
    provideRouter(
      routes,
      // Scroll to top on navigation and support in-page anchors such as /#fuentes.
      withInMemoryScrolling({ scrollPositionRestoration: 'top', anchorScrolling: 'enabled' }),
      // Re-clicking an in-page link (e.g. /#fuentes) scrolls to it again.
      withRouterConfig({ onSameUrlNavigation: 'reload' }),
    ),
  ],
};
