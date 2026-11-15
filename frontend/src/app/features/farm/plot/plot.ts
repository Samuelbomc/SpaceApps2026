import { ChangeDetectionStrategy, Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AnalysisJourneyStore } from '../../../core/journey/analysis-journey.store';
import { PILOT_TERRITORY, isSupportedMunicipality } from '../../../core/catalog/pilot-territory';
import { GeoBoundariesService } from '../../explorer/services/geo-boundaries.service';
import { MunicipalitySummary } from '../../explorer/models/geo.models';
import { displayName } from '../../explorer/utils/geo-utils';
import { JourneySteps } from '../../../shared/ui/journey-steps/journey-steps';
import { SENTINEL2_CLOUDLESS } from '../../../shared/map/imagery';
import { LngLat, openRing } from '../../../shared/geo/geodesy';
import { PlotMap, PlotMunicipality, PlotShape } from './components/plot-map/plot-map';
import { PlotDetails } from './components/plot-details/plot-details';
import { summarizePlot, toPlotSelection } from './plot-summary';

type PageState = 'loading' | 'choose' | 'unsupported' | 'ready' | 'error';

/**
 * Journey step 3 — "Municipio y lote" (one step).
 *
 * Arrives from the explorer with ?municipio=<DANE code> (or uses the municipality
 * already in the journey). Only verified pilot municipalities open the satellite
 * map; the farmer draws, edits and confirms the plot, which is stored in memory
 * and unlocks the characterization step. Requires a session (route guard).
 */
@Component({
  selector: 'app-plot',
  imports: [RouterLink, JourneySteps, PlotMap, PlotDetails],
  templateUrl: './plot.html',
  styleUrl: './plot.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Plot {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly geo = inject(GeoBoundariesService);
  protected readonly journey = inject(AnalysisJourneyStore);

  protected readonly region = PILOT_TERRITORY.pilotRegion;
  protected readonly imagery = SENTINEL2_CLOUDLESS;

  private readonly params = toSignal(this.route.queryParamMap, { initialValue: this.route.snapshot.queryParamMap });
  private readonly requestedCode = computed(
    () => this.params().get('municipio') ?? untracked(() => this.journey.municipality()?.code) ?? null,
  );

  protected readonly state = signal<PageState>('loading');
  protected readonly municipality = signal<PlotMunicipality | null>(null);
  protected readonly unsupportedName = signal('');
  protected readonly pilotOptions = signal<MunicipalitySummary[]>([]);
  protected readonly shape = signal<PlotShape | null>(null);
  protected readonly pendingSwitch = signal<string | null>(null);
  /** False until the map reports its first drawing state (so "nothing yet" ≠ "deleted"). */
  private shapeReported = false;

  /** Restores a plot already drawn for this municipality (e.g. coming back from step 4). */
  protected readonly initialRing = computed<LngLat[] | null>(() => {
    const plot = untracked(() => this.journey.plot());
    const m = this.municipality();
    return plot && m && plot.municipalityCode === m.code ? openRing(plot.geometry.coordinates[0]) : null;
  });

  protected readonly summary = computed(() => {
    const s = this.shape();
    const m = this.municipality();
    return s?.closed && s.ring.length >= 3 && m ? summarizePlot(s.ring, m) : null;
  });

  protected readonly canConfirm = computed(() => !!this.summary()?.valid && this.journey.municipalitySupported());

  constructor() {
    this.geo
      .municipalitySummaries()
      .then((all) => this.pilotOptions.set(all.filter((m) => isSupportedMunicipality(m.code))))
      .catch(() => undefined);

    effect(() => {
      const code = this.requestedCode();
      untracked(() => void this.resolve(code));
    });

    // Keep the journey's plot in step with what is drawn (geometry only).
    effect(() => {
      const summary = this.summary();
      const m = this.municipality();
      untracked(() => {
        if (!m || this.state() !== 'ready') return;
        const stored = this.journey.plot();
        if (summary?.valid) {
          const next = toPlotSelection(summary, m.code);
          if (JSON.stringify(stored?.geometry) !== JSON.stringify(next.geometry)) this.journey.setPlot(next);
        } else if (stored && this.shapeReported) {
          // Deleted, being redrawn or invalid: nothing confirmed may remain.
          this.journey.setPlot(null);
        }
      });
    });
  }

  private async resolve(code: string | null): Promise<void> {
    if (!code) {
      this.state.set('choose');
      return;
    }
    if (this.municipality()?.code === code && this.state() === 'ready') return;
    if (!isSupportedMunicipality(code)) {
      // Never open the plot map outside the verified pilot region (URL tampering included).
      const known = await this.geo.municipality(code).catch(() => null);
      this.unsupportedName.set(known ? displayName(known.properties.name) : `el código ${code}`);
      this.state.set('unsupported');
      return;
    }
    this.state.set('loading');
    try {
      const feature = await this.geo.municipality(code);
      if (!feature) {
        this.unsupportedName.set(`el código ${code}`);
        this.state.set('unsupported');
        return;
      }
      const name = displayName(feature.properties.name);
      this.journey.selectMunicipality({ code, name });
      this.shapeReported = false;
      this.shape.set(null);
      this.municipality.set({ code, name, geometry: feature.geometry });
      this.state.set('ready');
    } catch {
      this.state.set('error');
    }
  }

  protected onShape(shape: PlotShape | null): void {
    this.shapeReported = true;
    this.shape.set(shape);
  }

  /** Municipality switcher: warns before discarding a drawn plot. */
  protected requestSwitch(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const code = select.value;
    if (!code || code === this.municipality()?.code) return;
    if (this.shape()?.ring.length) {
      this.pendingSwitch.set(code);
      select.value = this.municipality()?.code ?? '';
      return;
    }
    this.goTo(code);
  }

  protected confirmSwitch(): void {
    const code = this.pendingSwitch();
    this.pendingSwitch.set(null);
    if (code) this.goTo(code);
  }

  protected chooseFromList(event: Event): void {
    const code = (event.target as HTMLSelectElement).value;
    if (code) this.goTo(code);
  }

  private goTo(code: string): void {
    void this.router.navigate([], { relativeTo: this.route, queryParams: { municipio: code } });
  }

  protected pendingName(): string {
    return this.pilotOptions().find((m) => m.code === this.pendingSwitch())?.name ?? '';
  }

  protected confirmPlot(): void {
    if (this.journey.confirmPlot()) void this.router.navigateByUrl('/finca/caracterizacion');
  }
}
