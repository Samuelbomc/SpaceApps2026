import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';
import { DATA_SOURCES } from '../../../../core/catalog/data-sources';
import { DATA_NATURE, DataNature } from '../../../../core/catalog/data-nature';
import { DataNatureBadge } from '../../../../shared/ui/data-nature-badge/data-nature-badge';
import { StatusBadge } from '../../../../shared/ui/status-badge/status-badge';

type SourceFilter = 'all' | 'nasa' | 'other';

/**
 * Planned data sources, evidence-support levels and the labelling legend.
 * Anchored at #fuentes so the header can link to it.
 */
@Component({
  selector: 'app-home-sources',
  imports: [DataNatureBadge, StatusBadge],
  templateUrl: './sources.html',
  styleUrl: './sources.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomeSources {
  protected readonly filter = signal<SourceFilter>('all');

  protected readonly filters: { id: SourceFilter; label: string }[] = [
    { id: 'all', label: 'Todas' },
    { id: 'nasa', label: 'NASA' },
    { id: 'other', label: 'Complementarias' },
  ];

  protected readonly visibleSources = computed(() => {
    const f = this.filter();
    if (f === 'all') return DATA_SOURCES;
    return DATA_SOURCES.filter((s) => (f === 'nasa' ? s.isNasa : !s.isNasa));
  });

  protected readonly natures = Object.entries(DATA_NATURE).map(([id, info]) => ({
    id: id as DataNature,
    ...info,
  }));

  /** Definitions from CLAUDE.md §5.D. Explicit scoring rules are still being documented. */
  protected readonly evidenceLevels = [
    {
      id: 'high',
      label: 'Respaldo alto',
      text: 'Evidencia pertinente y suficientemente completa, a una escala apropiada.',
    },
    {
      id: 'moderate',
      label: 'Respaldo moderado',
      text: 'Evidencia útil, pero con vacíos locales importantes.',
    },
    {
      id: 'limited',
      label: 'Respaldo limitado',
      text: 'Evidencia indirecta o incompleta que requiere validación local.',
    },
  ] as const;

  protected setFilter(f: SourceFilter): void {
    this.filter.set(f);
  }
}
