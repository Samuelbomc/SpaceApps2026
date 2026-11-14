import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { StatusBadge } from '../status-badge/status-badge';

/**
 * Temporary page used by modules that are not built yet. Keeps routes working
 * and tells users honestly what is coming. Replace per module as it is implemented.
 */
@Component({
  selector: 'app-module-placeholder',
  imports: [RouterLink, StatusBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: `
    .head { max-width: 48rem; }
    h1 { font-size: var(--fs-3xl); margin-block: var(--sp-3) var(--sp-4); }
    .lead { font-size: var(--fs-md); color: var(--c-ink-muted); }
    .body {
      display: grid;
      gap: var(--sp-5);
      grid-template-columns: 1.4fr 1fr;
      margin-top: var(--sp-7);
      align-items: start;
    }
    @media (max-width: 800px) { .body { grid-template-columns: 1fr; } }
    h2 { font-size: var(--fs-md); margin-bottom: var(--sp-4); }
    .actions { margin-top: var(--sp-6); }
  `,
  template: `
    <section class="section">
      <div class="container">
        <div class="head">
          <span class="eyebrow">{{ eyebrow() }}</span>
          <h1>{{ title() }}</h1>
          <p class="lead">{{ description() }}</p>
        </div>
        <div class="body">
          <div class="card">
            <h2>Capacidades previstas</h2>
            <ul class="check-list">
              @for (item of capabilities(); track item) {
                <li>{{ item }}</li>
              }
            </ul>
          </div>
          <div class="notice notice--caution" role="status">
            <app-status-badge status="in-development" />
            <p>
              <strong>Módulo en construcción.</strong> Esta sección aún no muestra datos. Cuando se
              use información de demostración, se identificará claramente como tal.
            </p>
          </div>
        </div>
        <div class="actions">
          <a class="link-arrow" routerLink="/">Volver al inicio</a>
        </div>
      </div>
    </section>
  `,
})
export class ModulePlaceholder {
  readonly eyebrow = input.required<string>();
  readonly title = input.required<string>();
  readonly description = input.required<string>();
  readonly capabilities = input.required<readonly string[]>();
}
