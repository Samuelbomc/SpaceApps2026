import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { AnalysisJourneyStore } from '../../core/journey/analysis-journey.store';
import { JOURNEY } from '../../core/journey/journey';

/**
 * Personal dashboard: entry point after signing in.
 * Restores the current journey and links to private farms and stored analyses.
 */
@Component({
  selector: 'app-dashboard',
  imports: [RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Dashboard {
  protected readonly auth = inject(AuthService);
  protected readonly journey = inject(AnalysisJourneyStore);

  protected readonly firstName = computed(() => this.auth.user()?.name.split(' ')[0] ?? '');

  /** "Continue where you left off" — only when a journey is in progress. */
  protected readonly resume = computed(() => {
    const municipality = this.journey.municipality();
    if (!municipality) return null;
    const step = JOURNEY.find((s) => s.id === this.journey.nextStep())!;
    return { municipality: municipality.name, step };
  });
}
