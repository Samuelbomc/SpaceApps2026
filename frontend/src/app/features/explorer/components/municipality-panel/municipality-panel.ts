import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { MunicipalitySummary } from '../../models/geo.models';
import {
  COVERAGE_LABEL,
  CoverageStatus,
  MUNICIPAL_COVERAGE,
  coverageOf,
} from '../../../../core/catalog/data-coverage';
import { DATA_SOURCES } from '../../../../core/catalog/data-sources';
import { PILOT_TERRITORY, isSupportedMunicipality } from '../../../../core/catalog/pilot-territory';
import { DataNatureBadge } from '../../../../shared/ui/data-nature-badge/data-nature-badge';

/**
 * Context panel for the current selection: either the pilot department overview
 * or one municipality with its DANE identity and honest data-coverage state.
 * Increment 3 will add variables, periods and charts here.
 */
@Component({
  selector: 'app-municipality-panel',
  imports: [DecimalPipe, DataNatureBadge],
  templateUrl: './municipality-panel.html',
  styleUrl: './municipality-panel.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MunicipalityPanel {
  readonly municipality = input<MunicipalitySummary | null>(null);
  readonly all = input<readonly MunicipalitySummary[]>([]);
  readonly departmentName = input.required<string>();
  readonly cleared = output<void>();

  protected readonly coverageLabel = COVERAGE_LABEL;
  protected readonly regionName = PILOT_TERRITORY.pilotRegion.name;

  protected readonly inPilot = computed(() => isSupportedMunicipality(this.municipality()?.code));
  protected readonly pilotCount = computed(() => this.all().filter((m) => isSupportedMunicipality(m.code)).length);

  protected readonly status = computed<CoverageStatus>(() => {
    const m = this.municipality();
    return m ? coverageOf(m.code) : 'none';
  });

  protected readonly coverage = computed(() => {
    const m = this.municipality();
    return m ? MUNICIPAL_COVERAGE[m.code] : undefined;
  });

  protected readonly sources = computed(() => {
    const ids = this.coverage()?.sourceIds ?? [];
    return DATA_SOURCES.filter((s) => ids.includes(s.id));
  });

  protected readonly counts = computed(() => {
    const totals: Record<CoverageStatus, number> = { integrated: 0, 'processed-pending': 0, none: 0 };
    for (const m of this.all()) totals[coverageOf(m.code)]++;
    return totals;
  });
}
