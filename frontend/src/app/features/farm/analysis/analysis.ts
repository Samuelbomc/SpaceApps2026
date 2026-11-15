import { Component, DestroyRef, computed, effect, inject, input, signal } from '@angular/core';
import { DatePipe, DecimalPipe, JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { BoundaryGeometry } from '../../explorer/models/geo.models';
import { pointInPolygons, LngLat } from '../../../shared/geo/geodesy';
import { Backend, errorMessage } from '../../../core/api/backend';
import type {
  Region,
  Analysis as AnalysisResult,
  ObservationHistory,
  AgronomicCatalog,
  Forecast,
  ModelCatalog,
} from '@agrogeo/api-client';
import {
  summarizeObservations,
  dailySegments,
  isUsable,
  type Observation,
} from '@agrogeo/api-client/observations';
const today = () =>
  new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Bogota',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
@Component({
  selector: 'app-analysis',
  imports: [FormsModule, DatePipe, DecimalPipe, JsonPipe],
  templateUrl: './analysis.html',
  styleUrl: './analysis.scss',
})
export class Analysis {
  readonly embedded = input(false);
  readonly historyEnabled = input(false);
  readonly locationState = input<'ready' | 'loading' | 'error'>('ready');
  protected readonly historyOpen = signal(false);
  protected readonly pastAnalyses = signal<AnalysisResult[]>([]);
  protected readonly archiveLoading = signal(false);
  protected readonly archiveError = signal('');
  protected readonly archiveRefresh = signal(0);
  protected readonly selectedPast = signal<AnalysisResult | null>(null);
  protected readonly displayedAnalysis = computed(() => this.selectedPast() ?? this.analysis());
  protected readonly displayedHorizon = computed(
    () => this.selectedPast()?.request.horizon_days ?? this.horizon(),
  );
  readonly area = input<BoundaryGeometry | null>(null);
  protected readonly showOtherLocations = signal(false);
  protected readonly regionsLoading = signal(true);
  protected readonly matchingRegions = computed(() => {
    if (this.locationState() !== 'ready') return [];
    const area = this.area();
    if (!area) return this.regions();
    const polygons = (
      area.type === 'Polygon' ? [area.coordinates] : area.coordinates
    ) as LngLat[][][];
    return this.regions().filter((region) =>
      pointInPolygons([region.longitude, region.latitude], polygons),
    );
  });
  protected readonly availableRegions = computed(() =>
    this.locationState() !== 'ready'
      ? []
      : this.showOtherLocations()
        ? this.regions()
        : this.matchingRegions(),
  );
  protected readonly selectedRegion = computed(() =>
    this.regions().find((region) => region.region_id === this.region()),
  );
  protected readonly outsideSelection = computed(
    () =>
      !!this.area() && !this.matchingRegions().some((region) => region.region_id === this.region()),
  );
  private readonly backend = inject(Backend);
  protected readonly regions = signal<Region[]>([]);
  protected readonly region = signal('');
  protected readonly horizon = signal(7);
  protected readonly horizons = [7, 15, 30, 60];
  protected readonly refresh = signal(0);
  protected readonly technical = signal(false);
  protected readonly loading = signal(false);
  protected readonly error = signal('');
  protected readonly history = signal<ObservationHistory | null>(null);
  protected readonly analysis = signal<AnalysisResult | null>(null);
  protected readonly crops = signal<AgronomicCatalog['crops']>([]);
  protected readonly models = signal<ModelCatalog | null>(null);
  protected readonly currentModels = computed(
    () =>
      this.models()?.models.filter((model) => (model.supported_leads?.includes(this.displayedHorizon()) || model.horizon_days === this.displayedHorizon())) || [],
  );
  protected readonly modelError = signal('');
  protected readonly page = signal(0);
  protected readonly addOne = (value: number) => value + 1;
  protected readonly previousPage = (value: number) => Math.max(0, value - 1);
  protected readonly summary = computed(() => summarizeObservations(this.history()?.items || []));
  protected readonly visibleRows = computed(() =>
    (this.history()?.items || []).slice(this.page() * 100, this.page() * 100 + 100),
  );
  protected readonly forecasts = computed(() =>
    [this.displayedAnalysis()?.climate, this.displayedAnalysis()?.soil].filter(
      (item): item is Forecast => !!item,
    ),
  );
  protected readonly latest = computed(() => {
    return this.summary().series.flatMap((series) => {
      const row = series.rows.reduce<Observation | null>(
        (last, candidate) => (isUsable(candidate) ? candidate : last),
        null,
      );
      return row ? [{ ...row, key: series.key }] : [];
    });
  });
  protected readonly segments = dailySegments;
  private referenceRequested = false;
  protected readonly metadataLoading = signal(false);
  protected readonly observationGroups = computed(() => {
    const definitions = [
      { label: 'Temperatura', variables: ['T2M_MIN', 'T2M', 'T2M_MAX'] },
      {
        label: 'Lluvia y humedad',
        variables: ['PRECTOTCORR', 'RH2M', 'surface_soil_moisture'],
      },
      {
        label: 'Viento y radiación',
        variables: ['WS2M', 'WS10M', 'ALLSKY_SFC_SW_DWN'],
      },
    ];
    const rows = this.latest();
    const knownVariables = new Set(definitions.flatMap((group) => group.variables));
    return [
      ...definitions.map((group) => ({
        label: group.label,
        rows: group.variables.flatMap((variable) =>
          rows.filter((row) => row.variable === variable),
        ),
      })),
      { label: 'Otros datos', rows: rows.filter((row) => !knownVariables.has(row.variable)) },
    ].filter((group) => group.rows.length);
  });
  protected readonly hasExperimentalForecasts = computed(() =>
    this.forecasts().some((forecast) => forecast.validation_status === 'experimental'),
  );
  private readonly destroyed = inject(DestroyRef);
  constructor() {
    const controller = new AbortController();
    this.destroyed.onDestroy(() => controller.abort());
    void this.backend.client
      .request<Region[]>('regions', { signal: controller.signal })
      .then((regions) => {
        if (controller.signal.aborted) return;
        this.regions.set(regions);
      })
      .catch((error) => {
        if (!controller.signal.aborted) this.error.set(errorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) this.regionsLoading.set(false);
      });
    effect(() => {
      this.area();
      this.showOtherLocations.set(false);
    });
    effect(() => {
      const regions = this.availableRegions();
      const selected = this.region();
      if (!regions.some((region) => region.region_id === selected))
        this.region.set(regions[0]?.region_id || '');
    });
    effect(() => {
      if (!this.technical() || this.referenceRequested) return;
      this.referenceRequested = true;
      void this.loadReference(controller.signal);
    });
    effect(() => {
      this.region();
      const enabled = this.historyEnabled();
      this.selectedPast.set(null);
      this.pastAnalyses.set([]);
      this.archiveError.set('');
      if (!enabled) this.historyOpen.set(false);
    });
    effect((onCleanup) => {
      const region = this.region(),
        enabled = this.historyEnabled(),
        open = this.historyOpen();
      this.archiveRefresh();
      if (!enabled || !region || !open) {
        this.archiveLoading.set(false);
        return;
      }
      const request = new AbortController();
      onCleanup(() => request.abort());
      this.archiveLoading.set(true);
      this.archiveError.set('');
      void this.loadArchive(region, request.signal);
    });
    effect((onCleanup) => {
      const region = this.region(),
        horizon = this.horizon();
      this.refresh();
      this.selectedPast.set(null);
      this.history.set(null);
      this.analysis.set(null);
      this.page.set(0);
      if (!region) {
        this.loading.set(false);
        return;
      }
      const request = new AbortController();
      onCleanup(() => request.abort());
      this.loading.set(true);
      this.error.set('');
      void this.load(region, horizon, request.signal);
    });
  }
  private async loadArchive(region: string, signal: AbortSignal) {
    try {
      const rows = await this.backend.client.request<AnalysisResult[]>(
        `regions/${encodeURIComponent(region)}/analyses?limit=20`,
        { signal },
      );
      if (signal.aborted) return;
      this.pastAnalyses.set(rows.filter((row) => row.request.region_id === region));
    } catch (error) {
      if (!signal.aborted) this.archiveError.set(errorMessage(error));
    } finally {
      if (!signal.aborted) this.archiveLoading.set(false);
    }
  }
  protected openPast(result: AnalysisResult) {
    if (!this.historyEnabled() || result.request.region_id !== this.region()) return;
    this.selectedPast.set(result);
    this.historyOpen.set(false);
  }
  refreshAvailableData() {
    if (!this.selectedPast()) this.refresh.update((value) => value + 1);
    if (this.historyOpen()) this.archiveRefresh.update((value) => value + 1);
  }
  protected returnToCurrent() {
    this.selectedPast.set(null);
    this.refresh.update((value) => value + 1);
  }
  protected forecastStart(result: AnalysisResult): string {
    if (result.request.forecast_start_date) return result.request.forecast_start_date;
    const date = new Date(result.request.reference_date + 'T00:00:00Z');
    date.setUTCDate(date.getUTCDate() + 1);
    return date.toISOString().slice(0, 10);
  }
  protected statusLabel(status: AnalysisResult['status']) {
    return {
      ready: 'Disponible',
      pending_model: 'Modelo pendiente',
      pending_run: 'Pendiente',
      insufficient_data: 'Datos insuficientes',
      pending_recommendations: 'Recomendaciones pendientes',
    }[status];
  }
  private async loadReference(signal: AbortSignal) {
    this.metadataLoading.set(true);
    const [models, crops] = await Promise.allSettled([
      this.backend.client.request<ModelCatalog>('models', { signal }),
      this.backend.client.request<AgronomicCatalog>('crops/catalog', { signal }),
    ]);
    if (signal.aborted) return;
    if (models.status === 'fulfilled') this.models.set(models.value);
    if (crops.status === 'fulfilled') this.crops.set(crops.value.crops);
    if (models.status === 'rejected' || crops.status === 'rejected')
      this.modelError.set('No se pudieron cargar todos los detalles de referencia.');
    this.metadataLoading.set(false);
  }
  private async load(region: string, horizon: number, signal: AbortSignal) {
    const outcomes = await Promise.allSettled([
      this.backend.client.loadObservationHistory(region, signal),
      this.backend.client.request<AnalysisResult | null>(
        `regions/${encodeURIComponent(region)}/latest-analysis?horizon_days=${horizon}&as_of=${today()}`,
        { signal },
      ),
    ]);
    if (signal.aborted) return;
    if (outcomes[0].status === 'fulfilled') this.history.set(outcomes[0].value);
    else this.error.set(errorMessage(outcomes[0].reason));
    if (outcomes[1].status === 'fulfilled') this.analysis.set(outcomes[1].value);
    else this.error.set(errorMessage(outcomes[1].reason));
    this.loading.set(false);
  }
  protected analysisMessage() {
    const status = this.displayedAnalysis()?.status;
    if (status && this.selectedPast())
      return status === 'insufficient_data'
        ? 'No había datos suficientes al generar este análisis.'
        : this.statusLabel(status) + '.';
    return status
      ? {
          pending_model: 'Este plazo todavía no tiene predicciones disponibles.',
          pending_run: 'El análisis de este periodo todavía está pendiente.',
          insufficient_data:
            'Faltan datos recientes procesados para completar las predicciones de clima y suelo.',
          pending_recommendations: 'Predicciones disponibles; recomendaciones pendientes.',
          ready: 'Análisis disponible.',
        }[status]
      : 'Todavía no hay un análisis disponible para este periodo.';
  }
  protected sourceLabel(source: string) {
    return source.replaceAll('_', ' ');
  }
  protected variableLabel(variable: string) {
    return (
      (
        {
          T2M: 'Temperatura media',
          T2M_MIN: 'Temperatura mínima',
          T2M_MAX: 'Temperatura máxima',
          RH2M: 'Humedad relativa del aire a 2 m',
          WS2M: 'Viento a 2 m',
          WS10M: 'Velocidad del viento a 10 m',
          PRECTOTCORR: 'Lluvia',
          ALLSKY_SFC_SW_DWN: 'Radiación solar',
          temperature_mean: 'Temperatura media',
          temperature_min: 'Media de temperaturas mínimas',
          temperature_max: 'Media de temperaturas máximas',
          precipitation: 'Lluvia acumulada',
          surface_soil_moisture: 'Humedad superficial del suelo',
        } as Record<string, string>
      )[variable] || variable
    );
  }
  protected points(segment: Observation[], all: Observation[]) {
    const valid = all.filter(isUsable);
    if (!valid.length) return '';
    const start = Date.parse(all[0].date),
      end = Date.parse(all[all.length - 1].date),
      min = Math.min(...valid.map((row) => row.value)),
      max = Math.max(...valid.map((row) => row.value));
    return segment
      .map(
        (row) =>
          `${10 + (580 * (Date.parse(row.date) - start)) / Math.max(1, end - start)},${110 - (100 * ((row.value as number) - min)) / Math.max(1, max - min)}`,
      )
      .join(' ');
  }
}
