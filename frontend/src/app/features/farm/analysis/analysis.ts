import { Component, DestroyRef, computed, effect, inject, signal } from '@angular/core';
import { DatePipe, JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Backend, errorMessage } from '../../../core/api/backend';
import type {
  Region,
  Analysis as AnalysisResult,
  ObservationHistory,
  AgronomicCatalog,
  Forecast,
} from '@field-shift/api-client';
import {
  summarizeObservations,
  dailySegments,
  isUsable,
  type Observation,
} from '@field-shift/api-client/observations';
const today = () =>
  new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Bogota',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
@Component({
  selector: 'app-analysis',
  imports: [FormsModule, DatePipe, JsonPipe],
  templateUrl: './analysis.html',
  styles: `
    .analysis-layout {
      display: grid;
      gap: 1.5rem;
    }
    .actions {
      display: flex;
      gap: 1rem;
      align-items: end;
      flex-wrap: wrap;
    }
    .actions label {
      display: grid;
      gap: 0.5rem;
    }
    svg {
      width: 100%;
      max-height: 160px;
    }
    pre {
      overflow: auto;
      font-size: 0.8rem;
    }
    .table-wrap {
      overflow: auto;
    }
    td,
    th {
      padding: 0.5rem;
      text-align: left;
    }
    article {
      margin: 1rem 0;
    }
  `,
})
export class Analysis {
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
  protected readonly page = signal(0);
  protected readonly addOne = (value: number) => value + 1;
  protected readonly previousPage = (value: number) => Math.max(0, value - 1);
  protected readonly summary = computed(() => summarizeObservations(this.history()?.items || []));
  protected readonly visibleRows = computed(() =>
    (this.history()?.items || []).slice(this.page() * 100, this.page() * 100 + 100),
  );
  protected readonly forecasts = computed(() =>
    [this.analysis()?.climate, this.analysis()?.soil].filter((item): item is Forecast => !!item),
  );
  protected readonly latest = computed(() => {
    const rows = new Map<string, Observation>();
    for (const row of this.history()?.items || [])
      if (isUsable(row) && !rows.has(row.variable)) rows.set(row.variable, row);
    return [...rows.values()];
  });
  protected readonly segments = dailySegments;
  private readonly destroyed = inject(DestroyRef);
  constructor() {
    const controller = new AbortController();
    this.destroyed.onDestroy(() => controller.abort());
    void Promise.all([
      this.backend.client.request<Region[]>('regions', { signal: controller.signal }),
      this.backend.client.request<AgronomicCatalog>('crops/catalog', { signal: controller.signal }),
    ])
      .then(([regions, catalog]) => {
        if (controller.signal.aborted) return;
        this.regions.set(regions);
        this.crops.set(catalog.crops);
        this.region.set(regions[0]?.region_id || '');
      })
      .catch((error) => {
        if (!controller.signal.aborted) this.error.set(errorMessage(error));
      });
    effect((onCleanup) => {
      const region = this.region(),
        horizon = this.horizon();
      this.refresh();
      if (!region) return;
      const request = new AbortController();
      onCleanup(() => request.abort());
      this.loading.set(true);
      this.error.set('');
      this.history.set(null);
      this.analysis.set(null);
      this.page.set(0);
      void this.load(region, horizon, request.signal);
    });
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
    const status = this.analysis()?.status;
    return status
      ? {
          pending_model: 'Los modelos aún no están conectados.',
          pending_run: 'El análisis todavía no se ha generado.',
          insufficient_data: 'No hay suficientes datos.',
          pending_recommendations: 'Predicciones disponibles; recomendaciones pendientes.',
          ready: 'Análisis disponible.',
        }[status]
      : 'No hay un análisis almacenado disponible.';
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
