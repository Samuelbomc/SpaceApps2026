import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { JOURNEY, JourneyStepId } from '../../../core/journey/journey';
import { AnalysisJourneyStore } from '../../../core/journey/analysis-journey.store';

/**
 * Optional progress indicator for the public workspace stages.
 * Completed steps get a check; the current one is marked with aria-current="step".
 */
@Component({
  selector: 'app-journey-steps',
  imports: [RouterLink],
  templateUrl: './journey-steps.html',
  styleUrl: './journey-steps.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JourneySteps {
  readonly current = input.required<JourneyStepId>();

  private readonly journey = inject(AnalysisJourneyStore);

  protected readonly steps = computed(() => {
    const done = this.journey.completed();
    return JOURNEY.map((step, index) => ({
      ...step,
      index: index + 1,
      status: step.id === this.current() ? 'current' : done[step.id] ? 'done' : 'upcoming',
    }));
  });
}
