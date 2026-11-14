import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-not-found',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: `
    .wrap { max-width: 36rem; }
    h1 { font-size: var(--fs-2xl); margin-block: var(--sp-3); }
    p { color: var(--c-ink-muted); margin-bottom: var(--sp-5); }
  `,
  template: `
    <section class="section">
      <div class="container wrap">
        <span class="eyebrow">Error 404</span>
        <h1>No encontramos esta página</h1>
        <p>Es posible que la dirección haya cambiado o que la sección aún no exista.</p>
        <a class="btn btn--primary" routerLink="/">Ir al inicio</a>
      </div>
    </section>
  `,
})
export class NotFound {}
