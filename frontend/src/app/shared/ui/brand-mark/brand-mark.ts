import { ChangeDetectionStrategy, Component } from '@angular/core';

/**
 * Neutral placeholder logo: stacked data layers over a field.
 * Deliberately generic — no NASA insignia or lookalike shapes.
 */
@Component({
  selector: 'app-brand-mark',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { 'aria-hidden': 'true' },
  styles: `
    :host {
      display: inline-block;
      width: 2.25rem;
      height: 2.25rem;
      flex: none;
    }
  `,
  template: `
    <svg viewBox="0 0 36 36" width="100%" height="100%" focusable="false">
      <rect width="36" height="36" rx="9" fill="#1e4233" />
      <path d="M18 7 29 12.5 18 18 7 12.5Z" fill="#7fb0c4" />
      <path
        d="M7 17.5 18 23l11-5.5"
        fill="none"
        stroke="#a9c2ab"
        stroke-width="2"
        stroke-linejoin="round"
      />
      <path
        d="M7 22.5 18 28l11-5.5"
        fill="none"
        stroke="#d6a77f"
        stroke-width="2"
        stroke-linejoin="round"
      />
    </svg>
  `,
})
export class BrandMark {}
