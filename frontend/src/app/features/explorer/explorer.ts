import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  viewChild,
  untracked,
  DestroyRef,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { InteractiveMap } from './components/interactive-map/interactive-map';
import { MunicipalityPanel } from './components/municipality-panel/municipality-panel';
import { MapProvenance } from './components/map-provenance/map-provenance';
import { GeoSearch } from './components/geo-search/geo-search';
import { GeoBoundariesService } from './services/geo-boundaries.service';
import { MunicipalitySummary } from './models/geo.models';
import { GeoSearchEntry, buildSearchIndex } from './utils/geo-search';
import { PILOT_TERRITORY, isSupportedMunicipality } from '../../core/catalog/pilot-territory';
import { AnalysisJourneyStore } from '../../core/journey/analysis-journey.store';
import { PlotMap, PlotMunicipality, PlotShape } from '../farm/plot/components/plot-map/plot-map';
import { summarizePlot, toPlotSelection } from '../farm/plot/plot-summary';
import { Analysis } from '../farm/analysis/analysis';
import { openRing, formatArea } from '../../shared/geo/geodesy';
import { displayName } from './utils/geo-utils';
import { ManualRefresh } from './components/manual-refresh/manual-refresh';
import { AuthService } from '../../core/auth/auth.service';

/** Public workspace: geographic selection, optional plot and stored analysis on one page. */
@Component({
  selector: 'app-explorer',
  imports: [
    RouterLink,
    InteractiveMap,
    MunicipalityPanel,
    MapProvenance,
    GeoSearch,
    PlotMap,
    Analysis,
    ManualRefresh,
  ],
  templateUrl: './explorer.html',
  styleUrl: './explorer.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Explorer {
  private readonly geo = inject(GeoBoundariesService);
  private readonly journey = inject(AnalysisJourneyStore);
  private readonly analysisView = viewChild(Analysis);
  protected readonly auth = inject(AuthService);
  protected readonly focusTarget = signal<{ kind: 'department' | 'region'; id: string } | null>(
    null,
  );

  protected readonly territory = PILOT_TERRITORY;
  protected readonly region = PILOT_TERRITORY.pilotRegion;
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  protected readonly analysisSession = signal(0);
  private readonly destroyed = inject(DestroyRef);
  protected readonly formatArea = formatArea;
  protected readonly boundary = signal<PlotMunicipality | null>(null);
  protected readonly boundaryState = signal<'idle' | 'loading' | 'ready' | 'error'>('idle');
  protected readonly shape = signal<PlotShape | null>(null);
  private boundaryRequest = 0;
  protected readonly plotSummary = computed(() => {
    const shape = this.shape(),
      municipality = this.boundary();
    return shape?.closed && shape.ring.length >= 3 && municipality
      ? summarizePlot(shape.ring, municipality)
      : null;
  });
  protected readonly initialRing = computed(() => {
    const plot = untracked(() => this.journey.plot());
    return plot && plot.municipalityCode === this.boundary()?.code
      ? openRing(plot.geometry.coordinates[0])
      : null;
  });
  protected readonly analysisArea = computed(() => {
    const summary = this.plotSummary();
    const municipality = this.boundary();
    return summary?.valid && municipality
      ? toPlotSelection(summary, municipality.code).geometry
      : (municipality?.geometry ?? null);
  });

  protected readonly selectedCode = signal<string | null>(
    this.route.snapshot.queryParamMap.get('municipio') ?? this.journey.municipality()?.code ?? null,
  );
  protected readonly municipalities = signal<MunicipalitySummary[]>([]);
  protected readonly searchIndex = signal<GeoSearchEntry[]>([]);
  protected readonly listState = signal<'loading' | 'ready' | 'error'>('loading');

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
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyed)).subscribe((params) => {
      const code = params.get('municipio');
      if (code) this.selectedCode.set(code);
    });

    // Keep the journey in sync with what the user selects (map, search or list).
    effect(() => {
      if (this.listState() !== 'ready') return;
      const m = this.selectedMunicipality();
      untracked(() => this.journey.selectMunicipality(m ? { code: m.code, name: m.name } : null));
    });
    effect(() => {
      const code = this.selectedCode();
      untracked(() => void this.loadBoundary(code));
    });
    effect(() => {
      const summary = this.plotSummary();
      const municipality = this.boundary();
      untracked(() => {
        if (summary?.valid && municipality && isSupportedMunicipality(municipality.code)) {
          this.journey.setPlot(toPlotSelection(summary, municipality.code));
          this.journey.confirmPlot();
        } else if (this.journey.plot() && this.shape() !== null) {
          this.journey.setPlot(null);
        }
      });
    });
    this.destroyed.onDestroy(() => this.boundaryRequest++);
  }

  private async loadBoundary(code: string | null) {
    const request = ++this.boundaryRequest;
    this.boundary.set(null);
    this.shape.set(null);
    this.boundaryState.set(code ? 'loading' : 'idle');
    if (!code) return;
    try {
      const feature = await this.geo.municipality(code);
      if (request !== this.boundaryRequest) return;
      if (!feature) {
        this.boundaryState.set('error');
        return;
      }
      this.boundary.set({
        code,
        name: displayName(feature.properties.name),
        geometry: feature.geometry,
      });
      this.boundaryState.set('ready');
    } catch {
      if (request === this.boundaryRequest) this.boundaryState.set('error');
    }
  }

  protected onDataUpdated() {
    this.analysisView()?.refreshAvailableData();
  }

  protected newAnalysis() {
    this.journey.reset();
    this.selectedCode.set(null);
    this.shape.set(null);
    this.focusTarget.set(null);
    this.analysisSession.update((value) => value + 1);
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: {},
      fragment: undefined,
      replaceUrl: true,
    });
  }

  protected retryBoundary() {
    void this.loadBoundary(this.selectedCode());
  }
  protected onShape(shape: PlotShape | null) {
    this.shape.set(shape);
    if (!shape) this.journey.setPlot(null);
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
    this.focusTarget.set({ kind: entry.kind, id: entry.id });
  }

  protected onSelect(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.selectedCode.set(value || null);
  }
}
