import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { APP_IDENTITY } from '../../../core/config/app-identity';
import { PILOT_TERRITORY } from '../../../core/catalog/pilot-territory';

/**
 * Shared frame for login, registration and password recovery:
 * a brand panel (what the platform does) and the form card (projected content).
 */
@Component({
  selector: 'app-auth-layout',
  templateUrl: './auth-layout.html',
  styleUrl: './auth-layout.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AuthLayout {
  readonly heading = input.required<string>();
  readonly lead = input<string>('');

  protected readonly identity = APP_IDENTITY;
  protected readonly region = PILOT_TERRITORY.pilotRegion.name;
}
