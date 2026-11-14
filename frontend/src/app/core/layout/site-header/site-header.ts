import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { IsActiveMatchOptions, RouterLink, RouterLinkActive } from '@angular/router';
import { APP_IDENTITY } from '../../config/app-identity';
import { PRIMARY_NAV } from '../navigation';
import { BrandMark } from '../../../shared/ui/brand-mark/brand-mark';

/**
 * Sticky site header with responsive navigation.
 * Desktop: inline links. Below 900px: a disclosure menu toggled by a button
 * (aria-expanded/aria-controls), closed by Escape or by choosing a link.
 */
@Component({
  selector: 'app-site-header',
  imports: [RouterLink, RouterLinkActive, BrandMark],
  templateUrl: './site-header.html',
  styleUrl: './site-header.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(document:keydown.escape)': 'closeMenu()' },
})
export class SiteHeader {
  protected readonly identity = APP_IDENTITY;
  protected readonly navItems = PRIMARY_NAV;
  protected readonly menuOpen = signal(false);

  /** Fragment-aware matching so "Inicio" and "Fuentes y método" are not both active. */
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
}
