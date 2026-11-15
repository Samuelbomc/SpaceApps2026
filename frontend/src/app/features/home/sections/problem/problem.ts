import { ChangeDetectionStrategy, Component } from '@angular/core';

/** States the problem the platform addresses, without unsupported statistics. */
@Component({
  selector: 'app-home-problem',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: `
    .grid {
      --grid-min: 15rem;
      list-style: none;
    }
    .num {
      display: inline-grid;
      place-items: center;
      width: 2rem;
      height: 2rem;
      margin-bottom: var(--sp-4);
      border-radius: var(--radius-sm);
      background: var(--c-sage-100);
      color: var(--c-forest-700);
      font-family: var(--font-mono);
      font-weight: 700;
      font-size: var(--fs-sm);
    }
    h3 {
      margin-bottom: var(--sp-2);
    }
  `,
  template: `
    <section class="section" aria-labelledby="problem-title">
      <div class="container">
        <header class="section-head">
          <span class="eyebrow">El reto</span>
          <h2 id="problem-title">Decidir qué sembrar es cada vez más difícil</h2>
          <p>
            Los cambios en lluvia, temperatura y disponibilidad de agua afectan la producción
            agrícola. La información para entenderlos existe, pero rara vez llega de forma útil a
            quien toma las decisiones en la finca.
          </p>
        </header>
        <ol class="grid" role="list">
          @for (item of challenges; track item.title; let i = $index) {
            <li class="card">
              <span class="num" aria-hidden="true">{{ i + 1 }}</span>
              <h3>{{ item.title }}</h3>
              <p>{{ item.text }}</p>
            </li>
          }
        </ol>
      </div>
    </section>
  `,
})
export class HomeProblem {
  protected readonly challenges = [
    {
      title: 'Clima y agua cambiantes',
      text: 'Las variaciones en la lluvia, la temperatura y la humedad del suelo influyen en qué, cuándo y cómo sembrar.',
    },
    {
      title: 'Datos dispersos y técnicos',
      text: 'La información satelital e institucional está repartida en distintos portales, formatos y escalas, y suele requerir conocimiento especializado.',
    },
    {
      title: 'Decisiones que dependen de cada finca',
      text: 'Una buena rotación depende del suelo, el historial y las prioridades de cada productor, no solo de promedios regionales.',
    },
  ] as const;
}
