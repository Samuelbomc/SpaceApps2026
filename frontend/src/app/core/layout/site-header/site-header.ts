import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { IsActiveMatchOptions, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { APP_IDENTITY } from '../../config/app-identity';
import { APP_NAV, PUBLIC_NAV } from '../navigation';
import { AuthService } from '../../auth/auth.service';
import { AnalysisJourneyStore } from '../../journey/analysis-journey.store';
import { NavDropdown } from '../nav-dropdown/nav-dropdown';

/**
 * Sticky site header. Navigation adapts to the session:
 * visitors see public links + "Iniciar sesión / Crear cuenta";
 * signed-in users keep Home, Exploration, private farms and their account area.
 * Below 900px the links collapse into a disclosure menu (Escape closes it).
 */
@Component({
  selector: 'app-site-header',
  imports: [RouterLink, RouterLinkActive, NavDropdown],
  templateUrl: './site-header.html',
  styleUrl: './site-header.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(document:keydown.escape)': 'closeMenu()' },
})
export class SiteHeader {
  protected readonly identity = APP_IDENTITY;
  protected readonly auth = inject(AuthService);
  private readonly journey = inject(AnalysisJourneyStore);
  private readonly router = inject(Router);

  protected readonly navItems = computed(() =>
    this.auth.isAuthenticated() ? APP_NAV : PUBLIC_NAV,
  );
  protected readonly menuOpen = signal(false);
  protected readonly initials = computed(() =>
    (this.auth.user()?.name ?? '')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join(''),
  );

  protected readonly activeOptions: IsActiveMatchOptions = {
    paths: 'exact',
    fragment: 'exact',
    queryParams: 'ignored',
    matrixParams: 'ignored',
  };

  toggleMenu(): void {
    this.menuOpen.update((open) => !open);
  }

  closeMenu(): void {
    this.menuOpen.set(false);
  }

  protected async logout(): Promise<void> {
    this.closeMenu();
    await this.auth.logout();
    this.journey.reset();
    await this.router.navigateByUrl('/');
  }
}
