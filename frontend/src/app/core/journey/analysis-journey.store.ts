import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { AuthService } from '../auth/auth.service';
import {
  PILOT_DEPARTMENT,
  PILOT_TERRITORY,
  isSupportedMunicipality,
} from '../catalog/pilot-territory';
import { JourneyStepId } from './journey';
import {
  PlotSelection,
  SelectedDepartment,
  SelectedMunicipality,
  SelectedRegion,
} from './journey.models';

/**
 * Progress of the current farm-analysis journey (in memory only).
 *
 * Holds the geographic selection (department → region → municipality) and the
 * farmer-drawn plot. Nothing is persisted, sent anywhere or analysed; a page
 * reload starts over (persistent storage arrives with the backend).
 */
@Injectable({ providedIn: 'root' })
export class AnalysisJourneyStore {
  private readonly auth = inject(AuthService);

  private readonly municipalityState = signal<SelectedMunicipality | null>(null);
  private readonly plotState = signal<PlotSelection | null>(null);
  private readonly plotConfirmedState = signal(false);
  private readonly questionnaireCompleteState = signal(false);

  constructor() {
    let previous: string | null = this.auth.user()?.id || null;
    effect(() => {
      const owner = this.auth.user()?.id || null;
      if (previous !== null && owner !== previous) this.reset();
      previous = owner;
    });
  }

  readonly municipality = this.municipalityState.asReadonly();
  readonly plot = this.plotState.asReadonly();
  readonly plotConfirmed = this.plotConfirmedState.asReadonly();
  readonly questionnaireComplete = this.questionnaireCompleteState.asReadonly();

  readonly department = computed<SelectedDepartment | null>(() =>
    this.municipality() ? { ...PILOT_DEPARTMENT } : null,
  );
  readonly region = computed<SelectedRegion | null>(() => {
    const m = this.municipality();
    const r = PILOT_TERRITORY.pilotRegion;
    return m?.supported ? { id: r.id, name: r.name } : null;
  });
  readonly municipalitySupported = computed(() => this.municipality()?.supported ?? false);

  /** Which steps the user has completed. */
  readonly completed = computed<Record<JourneyStepId, boolean>>(() => ({
    cuenta: this.auth.isAuthenticated(),
    explorar: this.municipality() !== null,
    lote: this.plotConfirmed(),
    caracterizacion: this.questionnaireComplete(),
    analisis: false,
  }));

  /** First step not yet completed — where "Continuar" should take the user. */
  readonly nextStep = computed<JourneyStepId>(() => {
    const done = this.completed();
    const order: JourneyStepId[] = ['cuenta', 'explorar', 'lote', 'caracterizacion', 'analisis'];
    return order.find((id) => !done[id]) ?? 'analisis';
  });

  /**
   * Selects (or clears) the municipality. Support is always derived from the
   * verified pilot list, never trusted from the caller. A different municipality
   * discards the plot and everything downstream.
   */
  selectMunicipality(municipality: { code: string; name: string } | null): void {
    if (municipality?.code === this.municipality()?.code) return;
    this.municipalityState.set(
      municipality
        ? {
            code: municipality.code,
            name: municipality.name,
            supported: isSupportedMunicipality(municipality.code),
          }
        : null,
    );
    this.plotState.set(null);
    this.plotConfirmedState.set(false);
    this.questionnaireCompleteState.set(false);
  }

  /** Stores the plot currently drawn (or null when deleted). Any change un-confirms it. */
  setPlot(plot: PlotSelection | null): void {
    this.plotState.set(plot);
    this.plotConfirmedState.set(false);
    this.questionnaireCompleteState.set(false);
  }

  /**
   * Confirms the plot. Refused (returns false) when there is no plot, the
   * municipality is not a verified pilot municipality, or the plot belongs to
   * another municipality.
   */
  confirmPlot(): boolean {
    const m = this.municipality();
    const plot = this.plot();
    if (!m?.supported || !plot || plot.municipalityCode !== m.code) return false;
    this.plotConfirmedState.set(true);
    return true;
  }

  reset(): void {
    this.selectMunicipality(null);
  }
}
