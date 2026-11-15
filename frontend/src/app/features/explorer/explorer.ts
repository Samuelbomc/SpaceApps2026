import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { InteractiveMap } from './components/interactive-map/interactive-map';
import { MunicipalityPanel } from './components/municipality-panel/municipality-panel';
import { MapProvenance } from './components/map-provenance/map-provenance';
import { GeoSearch } from './components/geo-search/geo-search';
import { GeoBoundariesService } from './services/geo-boundaries.service';
import { MunicipalitySummary } from './models/geo.models';
import { GeoSearchEntry, buildSearchIndex } from './utils/geo-search';
import { PILOT_TERRITORY, isSupportedMunicipality } from '../../core/catalog/pilot-territory';
import { AnalysisJourneyStore } from '../../core/journey/analysis-journey.store';
import { PLOT_STEP_PATH } from '../../core/journey/journey';
import { AuthService } from '../../core/auth/auth.service';
import { JourneySteps } from '../../shared/ui/journey-steps/journey-steps';

/** A department or region focused from the search (municipalities use selectedCode). */
interface FocusedArea {
  kind: 'department' | 'region';
  name: string;
  status: GeoSearchEntry['status'];
}

/**
 * Journey step 2 — public geographic exploration.
 *
 * Globe → Colombia → Antioquia → Oriente Antioqueño, with search, a keyboard/touch
 * municipality list and the selection panel. Choosing a verified pilot municipality
 * offers one action that opens the satellite plot map (step 3) for that municipality;
 * signed-out visitors are sent through login and returned there.
 */
@Component({
  selector: 'app-explorer',
  imports: [RouterLink, InteractiveMap, MunicipalityPanel, MapProvenance, GeoSearch, JourneySteps],
  templateUrl: './explorer.html',
  styleUrl: './explorer.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Explorer {
  private readonly geo = inject(GeoBoundariesService);
  private readonly journey = inject(AnalysisJourneyStore);
  protected readonly auth = inject(AuthService);
  private readonly map = viewChild(InteractiveMap);

  protected readonly territory = PILOT_TERRITORY;
  protected readonly region = PILOT_TERRITORY.pilotRegion;
  protected readonly plotPath = PLOT_STEP_PATH;

  protected readonly selectedCode = signal<string | null>(
    this.journey.municipality()?.code ?? null,
  );
  protected readonly municipalities = signal<MunicipalitySummary[]>([]);
  protected readonly searchIndex = signal<GeoSearchEntry[]>([]);
  protected readonly listState = signal<'loading' | 'ready' | 'error'>('loading');
  protected readonly focused = signal<FocusedArea | null>(null);

  protected readonly selectedMunicipality = computed(
    () => this.municipalities().find((m) => m.code === this.selectedCode()) ?? null,
  );
  protected readonly canContinue = computed(() => isSupportedMunicipality(this.selectedCode()));
  protected readonly pilotMunicipalities = computed(() =>
    this.municipalities().filter((m) => isSupportedMunicipality(m.code)),
  );
  protected readonly otherMunicipalities = computed(() =>
    this.municipalities().filter((m) => !isSupportedMunicipality(m.code)),
  );

  constructor() {
    this.loadLists();

    // Keep the journey in sync with what the user selects (map, search or list).
    effect(() => {
      if (this.listState() !== 'ready') return;
      const m = this.selectedMunicipality();
      if (m) this.focused.set(null);
      this.journey.selectMunicipality(m ? { code: m.code, name: m.name } : null);
    });
  }

  protected loadLists(): void {
    this.listState.set('loading');
    Promise.all([this.geo.municipalitySummaries(), this.geo.departmentSummaries()])
      .then(([munis, deps]) => {
        this.municipalities.set(munis);
        this.searchIndex.set(buildSearchIndex(deps, munis));
        this.listState.set('ready');
      })
      .catch(() => this.listState.set('error'));
  }

  protected onPicked(entry: GeoSearchEntry): void {
    if (entry.kind === 'municipality') {
      this.selectedCode.set(entry.id);
      return;
    }
    this.selectedCode.set(null);
    this.focused.set({ kind: entry.kind, name: entry.name, status: entry.status });
    if (entry.kind === 'department') this.map()?.focusDepartment(entry.id);
    else this.map()?.focusRegion();
  }

  protected onSelect(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.selectedCode.set(value || null);
  }

  protected showRegion(): void {
    this.selectedCode.set(null);
    this.focused.set({ kind: 'region', name: this.region.name, status: 'pilot' });
    this.map()?.focusRegion();
  }
}
