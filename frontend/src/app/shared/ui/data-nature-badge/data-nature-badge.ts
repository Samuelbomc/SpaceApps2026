import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DATA_NATURE, DataNature } from '../../../core/catalog/data-nature';

/**
 * Labels a dataset or result by its origin (satellite, modeled, institutional…).
 * Use it next to EVERY value shown to users. The 'demo' variant is intentionally loud.
 */
@Component({
  selector: 'app-data-nature-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class]': '"nature-badge nature-badge--" + nature()',
    '[attr.title]': 'info().description',
  },
  styles: `
    :host {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.15rem 0.6rem;
      border-radius: var(--radius-pill);
      font-size: var(--fs-xs);
      font-weight: 600;
      line-height: 1.5;
      white-space: nowrap;
      background: var(--badge-bg);
      color: var(--badge-ink);
      border: 1px solid var(--badge-border, transparent);
    }
    .dot {
      width: 0.5rem;
      height: 0.5rem;
      border-radius: 50%;
      background: currentColor;
    }
    :host(.nature-badge--satellite) {
      --badge-bg: var(--c-water-100);
      --badge-ink: var(--c-water-600);
    }
    :host(.nature-badge--modeled) {
      --badge-bg: var(--c-slate-100);
      --badge-ink: var(--c-slate-600);
    }
    :host(.nature-badge--ground) {
      --badge-bg: var(--c-sage-100);
      --badge-ink: var(--c-forest-700);
    }
    :host(.nature-badge--institutional) {
      --badge-bg: var(--c-earth-100);
      --badge-ink: var(--c-earth-600);
    }
    :host(.nature-badge--literature) {
      --badge-bg: var(--c-ochre-100);
      --badge-ink: var(--c-ochre-600);
    }
    :host(.nature-badge--farmer) {
      --badge-bg: var(--c-forest-700);
      --badge-ink: var(--c-ink-inverse);
    }
    :host(.nature-badge--demo) {
      --badge-bg: var(--c-demo-bg);
      --badge-ink: var(--c-demo-ink);
      --badge-border: var(--c-demo-border);
      border-style: dashed;
    }
  `,
  template: `<span class="dot" aria-hidden="true"></span>{{ info().label }}`,
})
export class DataNatureBadge {
  readonly nature = input.required<DataNature>();
  protected readonly info = computed(() => DATA_NATURE[this.nature()]);
}
