import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { JOURNEY, JourneyStepId } from '../../../core/journey/journey';
import { JourneySteps } from '../journey-steps/journey-steps';
import { StatusBadge } from '../status-badge/status-badge';

export interface StepLink {
  path: string;
  label: string;
}

export interface StepPrerequisite {
  message: string;
  link: StepLink;
}

/**
 * Temporary screen for journey steps whose interface is built in a later increment.
 * Keeps the journey navigable, states what the step will do, and shows honestly
 * what the user still needs to complete before it.
 */
@Component({
  selector: 'app-step-placeholder',
  imports: [RouterLink, JourneySteps, StatusBadge],
  templateUrl: './step-placeholder.html',
  styleUrl: './step-placeholder.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StepPlaceholder {
  readonly step = input.required<JourneyStepId>();
  readonly title = input.required<string>();
  readonly description = input.required<string>();
  readonly capabilities = input.required<readonly string[]>();
  readonly prerequisite = input<StepPrerequisite | null>(null);
  readonly back = input<StepLink | null>(null);
  readonly next = input<StepLink | null>(null);
  /** Extra scientific/legal caveat specific to the step. */
  readonly caveat = input<string>('');

  protected readonly position = computed(() => JOURNEY.findIndex((s) => s.id === this.step()) + 1);
  protected readonly total = JOURNEY.length;
}
