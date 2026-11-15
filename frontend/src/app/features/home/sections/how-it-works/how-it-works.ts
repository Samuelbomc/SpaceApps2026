import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { JOURNEY } from '../../../../core/journey/journey';
import { AuthService } from '../../../../core/auth/auth.service';

/**
 * "Cómo funciona": the single user journey, generated from the same JOURNEY
 * definition that drives the stepper, so the home page never drifts from the app.
 */
@Component({
  selector: 'app-home-how-it-works',
  imports: [RouterLink],
  templateUrl: './how-it-works.html',
  styleUrl: './how-it-works.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomeHowItWorks {
  protected readonly steps = JOURNEY;
  protected readonly auth = inject(AuthService);
}
