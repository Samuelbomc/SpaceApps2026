import { ChangeDetectionStrategy, Component } from '@angular/core';
import { IntegrationStatus } from '../../../../core/catalog/data-nature';
import { StatusBadge } from '../../../../shared/ui/status-badge/status-badge';

/**
 * Honest development status. Update these lists as work lands —
 * never move an item to 'available' before it works end to end.
 */
@Component({
  selector: 'app-home-roadmap',
  imports: [StatusBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: `
    .columns {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: var(--sp-5);
    }
    @media (max-width: 860px) { .columns { grid-template-columns: 1fr; } }
    .card { display: grid; gap: var(--sp-4); align-content: start; }
  `,
  template: `
    <section class="section" aria-labelledby="roadmap-title">
      <div class="container">
        <header class="section-head">
          <span class="eyebrow">Estado del desarrollo</span>
          <h2 id="roadmap-title">Qué funciona hoy y qué viene</h2>
          <p>
            Este es un prototipo en construcción para el hackatón. Preferimos mostrar con claridad
            lo que falta antes que aparentar funciones que aún no existen.
          </p>
        </header>
        <div class="columns">
          @for (col of columns; track col.status) {
            <div class="card">
              <app-status-badge [status]="col.status" />
              <ul class="check-list">
                @for (item of col.items; track item) {
                  <li>{{ item }}</li>
                }
              </ul>
            </div>
          }
        </div>
      </div>
    </section>
  `,
})
export class HomeRoadmap {
  protected readonly columns: { status: IntegrationStatus; items: string[] }[] = [
    {
      status: 'available',
      items: [
        'Estructura de la aplicación y navegación',
        'Página de inicio y descripción del proyecto',
        'Catálogo descriptivo de fuentes previstas',
      ],
    },
    {
      status: 'in-development',
      items: [
        'Portal de datos con selección municipal y gráficos',
        'Espacio del agricultor: perfil, historial y prioridades',
        'Comparador de tres estrategias de rotación',
      ],
    },
    {
      status: 'planned',
      items: [
        'Integración real de datos NASA y fuentes colombianas',
        'API y base de datos geoespacial',
        'Cuentas de usuario y almacenamiento seguro de fincas',
        'Descargas de datos con metadatos',
      ],
    },
  ];
}
