import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DataNatureBadge } from '../../../../../shared/ui/data-nature-badge/data-nature-badge';
import { formatArea, formatLngLat } from '../../../../../shared/geo/geodesy';
import { PlotSummary } from '../../plot-summary';

/** Read-out of the drawn plot: area, perimeter, centre, vertices and checks. */
@Component({
  selector: 'app-plot-details',
  imports: [DataNatureBadge],
  templateUrl: './plot-details.html',
  styleUrl: './plot-details.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlotDetails {
  readonly summary = input<PlotSummary | null>(null);
  readonly municipalityName = input.required<string>();
  /** True while an outline is being drawn but not yet closed. */
  readonly drawing = input(false);

  protected readonly formatLngLat = formatLngLat;

  protected readonly area = computed(() => {
    const s = this.summary();
    return s ? formatArea(s.areaM2) : '';
  });

  protected readonly perimeter = computed(() => {
    const m = this.summary()?.perimeterM ?? 0;
    return m >= 1000
      ? `${(m / 1000).toLocaleString('es-CO', { maximumFractionDigits: 2 })} km`
      : `${Math.round(m).toLocaleString('es-CO')} m`;
  });

  protected readonly withinLabel = computed(() => {
    switch (this.summary()?.within) {
      case 'inside':
        return `Dentro de ${this.municipalityName()}`;
      case 'partial':
        return `Parcialmente fuera de ${this.municipalityName()}`;
      default:
        return `Fuera de ${this.municipalityName()}`;
    }
  });
}
