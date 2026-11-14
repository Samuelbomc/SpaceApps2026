import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { INTEGRATION_STATUS_LABEL, IntegrationStatus } from '../../../core/catalog/data-nature';

/** Shows whether a capability or data source is available, in development, or planned. */
@Component({
  selector: 'app-status-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[class]': '"status status--" + status()' },
  styles: `
    :host {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.1rem 0.55rem;
      border-radius: var(--radius-sm);
      font-size: var(--fs-xs);
      font-weight: 700;
      letter-spacing: 0.02em;
      white-space: nowrap;
      background: var(--st-bg);
      color: var(--st-ink);
    }
    :host::before {
      content: '';
      width: 0.45rem;
      height: 0.45rem;
      border-radius: 50%;
      border: 2px solid currentColor;
      background: var(--st-fill, transparent);
    }
    :host(.status--available) { --st-bg: var(--c-sage-100); --st-ink: var(--c-forest-700); --st-fill: currentColor; }
    :host(.status--in-development) { --st-bg: var(--c-ochre-100); --st-ink: var(--c-ochre-600); }
    :host(.status--planned) { --st-bg: var(--c-slate-100); --st-ink: var(--c-slate-600); }
  `,
  template: `{{ label() }}`,
})
export class StatusBadge {
  readonly status = input.required<IntegrationStatus>();
  protected readonly label = computed(() => INTEGRATION_STATUS_LABEL[this.status()]);
}
