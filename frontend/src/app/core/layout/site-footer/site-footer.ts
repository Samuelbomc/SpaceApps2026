import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { APP_IDENTITY } from '../../config/app-identity';
import { PRIMARY_NAV } from '../navigation';
import { BrandMark } from '../../../shared/ui/brand-mark/brand-mark';

/** Site footer: navigation, project context, and the non-endorsement / decision-support disclaimer. */
@Component({
  selector: 'app-site-footer',
  imports: [RouterLink, BrandMark],
  templateUrl: './site-footer.html',
  styleUrl: './site-footer.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SiteFooter {
  protected readonly identity = APP_IDENTITY;
  protected readonly navItems = PRIMARY_NAV;
}
