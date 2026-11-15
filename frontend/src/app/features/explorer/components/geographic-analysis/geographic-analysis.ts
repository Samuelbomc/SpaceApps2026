import {
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe, DecimalPipe } from '@angular/common';
import type {
  GeographicAnalysis as GeographicState,
  GeographicAnalysisRequest,
} from '@agrogeo/api-client';
import { Backend, errorMessage } from '../../../../core/api/backend';
import { Analysis } from '../../../farm/analysis/analysis';

@Component({
  selector: 'app-geographic-analysis',
  imports: [FormsModule, DatePipe, DecimalPipe, Analysis],
  template: `
    <section class="card" aria-label="Analizar área seleccionada">
      <h2>
        {{
          selectionKind() === 'municipality' && selectionName()
            ? 'Análisis de ' + selectionName()
            : 'Análisis de tu terreno'
        }}
      </h2>
      @if (geometry()) {
        <label
          >Periodo
          <select
            class="input"
            aria-label="Periodo del terreno"
            [ngModel]="horizon()"
            (ngModelChange)="changeHorizon(+$event)"
          >
            @for (days of [7, 15, 30, 60]; track days) {
              <option [value]="days">{{ days }} días</option>
            }
          </select>
        </label>
        <button class="btn btn--primary" type="button" [disabled]="submitting()" (click)="submit()">
          {{
            submitting()
              ? 'Enviando…'
              : selectionKind() === 'municipality'
                ? 'Analizar municipio'
                : 'Analizar esta área'
          }}
        </button>
      } @else {
        <p>
          {{
            selectionKind() === 'plot'
              ? 'Completa el contorno del lote o elimina el dibujo para analizar el municipio.'
              : 'Selecciona un municipio para iniciar el análisis. Delimitar un lote es opcional.'
          }}
        </p>
      }
      @if (error()) {
        <p role="alert">{{ error() }}</p>
      }
      @if (state(); as item) {
        @if (!displayedState()?.result?.climate && !displayedState()?.result?.soil) {
          <p role="status">
            {{
              item.result?.spatial_match?.method === 'nearest'
                ? 'Todavía no hay predicciones del punto seleccionado.'
                : statusLabel(item.status)
            }}
          </p>
        }
      }
      @if (referenceResult(); as reference) {
        <button
          class="link-btn"
          type="button"
          [attr.aria-expanded]="usingReference()"
          (click)="referencePreference.set(usingReference() ? 'local' : 'regional')"
        >
          {{
            samePointReference()
              ? usingReference()
                ? 'Ocultar corte anterior'
                : 'Ver último corte completo de esta ubicación'
              : usingReference()
                ? 'Ocultar referencia regional'
                : 'Ver referencia regional'
          }}
        </button>
        @if (usingReference()) {
          <p role="status">
            {{
              samePointReference()
                ? 'Estimación con el último corte completo de esta ubicación'
                : 'Estimación con datos de referencia'
            }}
            @if (!samePointReference() && reference.spatial_match; as match) {
              · a {{ match.distance_km | number: '1.1-1' }} km de tu selección
            }
            .
          </p>
        }
      }
    </section>
    @if (latestObservations().length) {
      <section class="card" aria-label="Datos observados de la ubicación seleccionada">
        <h3>Datos observados en tu ubicación</h3>
        <div class="observations">
          @for (observation of latestObservations(); track observation.variable) {
            <article>
              <span>{{ observationLabel(observation.variable) }}</span>
              <strong
                >{{ observation.value | number: '1.1-2' }}
                {{ observation.unit === 'C' ? '°C' : observation.unit }}</strong
              >
              <small
                >{{ observation.source }} ·
                {{ observation.date | date: 'shortDate' : 'UTC' }}</small
              >
            </article>
          }
        </div>
      </section>
    }
    @if (displayedState(); as item) {
      @if (item.result?.climate || item.result?.soil) {
        <app-analysis
          [embedded]="true"
          [historyEnabled]="historyEnabled() && !usingReference()"
          [referenceMode]="usingReference()"
          [geographicMode]="true"
          [geographic]="item"
        />
      }
    }
  `,
  styles: [
    `
      .observations {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 1rem;
      }
      .observations article {
        display: grid;
        gap: 0.25rem;
      }
    `,
  ],
})
export class GeographicAnalysis {
  readonly geometry = input<GeographicAnalysisRequest['geometry'] | null>(null);
  readonly selectionKind = input<'municipality' | 'plot'>('plot');
  readonly selectionName = input('');
  readonly historyEnabled = input(false);
  private readonly backend = inject(Backend);
  private readonly destroy = inject(DestroyRef);
  protected readonly horizon = signal(7);
  protected readonly state = signal<GeographicState | null>(null);
  protected readonly referencePreference = signal<'auto' | 'local' | 'regional'>('auto');
  protected readonly latestObservations = computed(() => {
    const order = ['T2M_MIN', 'T2M', 'T2M_MAX', 'RH2M', 'QV2M', 'WS2M', 'ALLSKY_SFC_SW_DWN'];
    return [...(this.state()?.observations ?? [])].sort(
      (a, b) => order.indexOf(a.variable) - order.indexOf(b.variable),
    );
  });
  protected readonly referenceResult = computed(() => {
    const item = this.state();
    const result = item?.result;
    const nearby =
      result?.spatial_match?.method === 'nearest' && (result.climate || result.soil)
        ? result
        : null;
    if (nearby?.climate && nearby.soil) return nearby;
    if (result?.spatial_match?.method !== 'nearest' && result?.climate && result.soil) return null;
    return item?.reference?.result ?? nearby;
  });
  protected readonly usingReference = computed(() => {
    if (!this.referenceResult() || this.referencePreference() === 'local') return false;
    if (this.referencePreference() === 'regional') return true;
    const result = this.state()?.result;
    return result?.spatial_match?.method === 'nearest' || !(result?.climate || result?.soil);
  });
  protected readonly samePointReference = computed(
    () => this.referenceResult()?.spatial_match?.method === 'exact',
  );
  protected readonly displayedState = computed(() => {
    const item = this.state();
    if (!item) return null;
    if (this.usingReference()) return { ...item, result: this.referenceResult() };
    return item.result?.spatial_match?.method === 'nearest' ? { ...item, result: null } : item;
  });
  protected readonly error = signal('');
  protected readonly submitting = signal(false);
  private controller: AbortController | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    effect(() => {
      this.geometry();
      this.selectionKind();
      this.selectionName();
      untracked(() => this.clear());
    });
    this.destroy.onDestroy(() => this.clear());
  }

  private clear() {
    this.controller?.abort();
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
    this.state.set(null);
    this.referencePreference.set('auto');
    this.error.set('');
    this.submitting.set(false);
  }

  protected changeHorizon(days: number) {
    this.clear();
    this.horizon.set(days);
  }

  protected async submit() {
    if (this.submitting()) return;
    const geometry = this.geometry();
    if (!geometry) return;
    this.clear();
    const controller = new AbortController();
    this.controller = controller;
    this.submitting.set(true);
    const request: GeographicAnalysisRequest = {
      geometry,
      horizon_days: this.horizon() as 7 | 15 | 30 | 60,
    };
    try {
      const item = await this.backend.client.request<GeographicState>('geographic-analyses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      this.accept(item, controller);
    } catch (error) {
      if (!controller.signal.aborted) this.error.set(errorMessage(error));
    } finally {
      if (!controller.signal.aborted) this.submitting.set(false);
    }
  }

  private accept(item: GeographicState, controller: AbortController) {
    this.state.set(item);
    this.error.set('');
    if (['completed', 'failed'].includes(item.status)) return;
    this.timer = setTimeout(() => void this.poll(item.request_id, controller), 5000);
  }

  private async poll(id: string, controller: AbortController) {
    try {
      const item = await this.backend.client.request<GeographicState>(`geographic-analyses/${id}`, {
        signal: controller.signal,
      });
      if (!controller.signal.aborted) this.accept(item, controller);
    } catch (error) {
      if (!controller.signal.aborted) {
        this.error.set(errorMessage(error));
        this.timer = setTimeout(() => void this.poll(id, controller), 15000);
      }
    }
  }

  refreshAvailableData() {
    const item = this.state();
    if (!item || !this.controller) return;
    if (this.timer !== null) clearTimeout(this.timer);
    void this.poll(item.request_id, this.controller);
  }

  protected statusLabel(status: GeographicState['status']) {
    return {
      queued: 'Solicitud en cola.',
      running: 'Preparando datos de esta ubicación…',
      waiting_inputs: 'Todavía no hay predicciones disponibles para esta zona.',
      retry_scheduled: 'La consulta se reintentará automáticamente.',
      completed: 'Predicciones disponibles.',
      failed: 'La solicitud no pudo completarse. Puedes iniciar una nueva consulta.',
    }[status];
  }
  protected observationLabel(variable: string) {
    return (
      {
        T2M_MIN: 'Temperatura mínima',
        T2M: 'Temperatura media',
        T2M_MAX: 'Temperatura máxima',
        RH2M: 'Humedad del aire',
        QV2M: 'Humedad específica del aire',
        WS2M: 'Viento a 2 m',
        ALLSKY_SFC_SW_DWN: 'Radiación solar',
      }[variable] ?? variable
    );
  }
}
