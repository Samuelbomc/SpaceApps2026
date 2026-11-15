import { Component, computed, input } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import type { Analysis, ProbabilityEstimate } from '@agrogeo/api-client';
import { CropCondition } from './crop-condition';

@Component({
  selector: 'app-analysis-summary',
  imports: [DatePipe, DecimalPipe, CropCondition],
  template: `
    <div class="summary">
      <section class="card" aria-labelledby="forecast-summary-title">
        <div class="title-row">
          <h3 id="forecast-summary-title">Predicciones</h3>
          <small
            >{{
              reference()
                ? result().spatial_match?.method === 'exact'
                  ? 'Último corte completo de esta ubicación'
                  : 'Referencia regional'
                : 'Zona seleccionada'
            }}
            · {{ start() | date: 'mediumDate' : 'UTC' }}–{{
              end() | date: 'mediumDate' : 'UTC'
            }}</small
          >
        </div>
        <div class="prediction-grid">
          @for (column of columns(); track column.key) {
            <div class="prediction">
              <span>{{ label(column.value.variable) }}</span>
              <strong
                >{{
                  column.value.value | number: (column.value.unit === 'm3/m3' ? '1.1-3' : '1.1-2')
                }}
                <small>{{ unit(column.value.unit) }}</small></strong
              >
            </div>
          }
        </div>
        @if (dailyRows().length) {
          <details>
            <summary>Ver predicciones por día</summary>
            <div class="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Día</th>
                    @for (column of columns(); track column.key) {
                      <th>
                        {{ dailyLabel(column.value.variable) }} ({{ unit(column.value.unit) }})
                      </th>
                    }
                  </tr>
                </thead>
                <tbody>
                  @for (row of dailyRows(); track row.date) {
                    <tr>
                      <td>{{ row.date | date: 'shortDate' : 'UTC' }}</td>
                      @for (column of columns(); track column.key) {
                        <td>
                          {{
                            row.values[column.key] === undefined
                              ? '—'
                              : (row.values[column.key] | number: '1.1-2')
                          }}
                        </td>
                      }
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          </details>
        }
      </section>

      <section class="card" aria-labelledby="crop-summary-title">
        <div class="title-row">
          <h3 id="crop-summary-title">Cultivos compatibles</h3>
          <small>Condiciones previstas · evaluación provisional</small>
        </div>
        @if (crops().length) {
          <div class="table-scroll">
            <table class="crop-list">
              <thead>
                <tr>
                  <th>Cultivo</th>
                  <th>Temperatura</th>
                  <th>Lluvia del periodo</th>
                  <th>Humedad del suelo</th>
                  <th
                    title="Los modelos actuales no calculan una probabilidad de éxito del cultivo."
                  >
                    Probabilidad
                  </th>
                </tr>
              </thead>
              <tbody>
                @for (crop of crops(); track crop.crop_id) {
                  <tr>
                    <td>{{ crop.crop_name }}</td>
                    <td>
                      {{
                        crop.temperature_fit === 'optimal'
                          ? 'Óptima'
                          : crop.temperature_fit === 'tolerated'
                            ? 'Tolerada'
                            : 'Por evaluar'
                      }}
                      @if (
                        crop.temperature_optimal_min_c !== null &&
                        crop.temperature_optimal_min_c !== undefined
                      ) {
                        <small class="range"
                          >Óptimo: {{ crop.temperature_optimal_min_c }}–{{
                            crop.temperature_optimal_max_c
                          }}
                          °C</small
                        >
                      }
                    </td>
                    <td><app-crop-condition [check]="condition(crop, 'precipitation')" /></td>
                    <td>
                      <app-crop-condition [check]="condition(crop, 'surface_soil_moisture')" />
                    </td>
                    <td>{{ probability(crop.probability) }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
          @if (uncalibrated()) {
            <small class="muted">Probabilidad no calculada por los modelos actuales.</small>
          }
        } @else {
          <p>No hay cultivos compatibles con la evaluación disponible.</p>
        }
      </section>

      <section class="card" aria-labelledby="rotation-summary-title">
        <h3 id="rotation-summary-title">Rotaciones orientativas</h3>
        @if (rotations().length) {
          <table>
            <thead>
              <tr>
                <th>Secuencia</th>
                <th>Probabilidad</th>
              </tr>
            </thead>
            <tbody>
              @for (rotation of rotations(); track $index) {
                <tr>
                  <td>{{ rotation.names.join(' → ') }}</td>
                  <td>{{ probability(rotation.probability) }}</td>
                </tr>
              }
            </tbody>
          </table>
        } @else {
          <p>No hay secuencias disponibles.</p>
        }
      </section>
    </div>
  `,
  styles: `
    :host {
      display: block;
      min-width: 0;
    }
    .summary {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: var(--sp-4);
    }
    .title-row {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: var(--sp-3);
      flex-wrap: wrap;
    }
    .title-row small,
    .muted {
      color: var(--c-ink-muted);
    }
    .prediction-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 150px), 1fr));
      gap: var(--sp-3);
      margin-top: var(--sp-3);
    }
    .prediction {
      display: grid;
      gap: var(--sp-2);
      padding: var(--sp-3);
      border-radius: var(--radius-sm);
      background: var(--c-sage-50);
    }
    .prediction span {
      font-size: var(--fs-sm);
    }
    .prediction strong {
      font-size: var(--fs-xl);
      font-variant-numeric: tabular-nums;
    }
    .prediction strong small {
      font-size: var(--fs-sm);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: var(--sp-3);
      font-size: var(--fs-sm);
    }
    th,
    td {
      padding: var(--sp-2);
      text-align: left;
      border-bottom: 1px solid var(--c-border);
    }
    td:last-child {
      font-variant-numeric: tabular-nums;
    }
    .range {
      display: block;
      color: var(--c-ink-muted);
    }
    details {
      margin-top: var(--sp-3);
    }
    .table-scroll {
      overflow-x: auto;
    }
    .table-scroll th {
      white-space: nowrap;
    }
  `,
})
export class AnalysisSummary {
  readonly result = input.required<Analysis>();
  readonly reference = input(false);
  protected readonly forecasts = computed(() =>
    [this.result().climate, this.result().soil].filter((item) => item != null),
  );
  protected readonly columns = computed(() =>
    this.forecasts().flatMap((forecast) =>
      forecast.values.map((value) => ({ key: forecast.model_kind + ':' + value.variable, value })),
    ),
  );
  protected readonly crops = computed(() =>
    [...(this.result().rotation_assessment?.candidates ?? [])]
      .filter((crop) => crop.status !== 'excluded')
      .sort(
        (a, b) => Number(b.temperature_fit === 'optimal') - Number(a.temperature_fit === 'optimal'),
      ),
  );
  protected readonly rotations = computed(() => {
    const result = this.result();
    if (result.recommendations)
      return result.recommendations.alternatives.map((rotation) => ({
        names: rotation.crops,
        probability: rotation.probability,
      }));
    return (result.rotation_assessment?.scenarios ?? []).map((rotation) => ({
      names: rotation.stages.map((stage) => stage.crop_name),
      probability: rotation.probability,
    }));
  });
  protected readonly uncalibrated = computed(() =>
    this.crops().some((crop) => crop.probability?.status !== 'calibrated'),
  );
  protected readonly start = computed(() => {
    const explicit =
      this.forecasts()[0]?.forecast_start_date ?? this.result().request.forecast_start_date;
    if (explicit) return explicit;
    const date = new Date(this.result().request.reference_date + 'T00:00:00Z');
    date.setUTCDate(date.getUTCDate() + 1);
    return date.toISOString().slice(0, 10);
  });
  protected readonly end = computed(() => {
    const date = new Date(this.start() + 'T00:00:00Z');
    date.setUTCDate(date.getUTCDate() + (this.result().request.horizon_days ?? 7) - 1);
    return date.toISOString().slice(0, 10);
  });
  protected readonly dailyRows = computed(() => {
    const rows = new Map<string, Record<string, number>>();
    for (const forecast of this.forecasts())
      for (const day of forecast.daily ?? []) {
        const values = rows.get(day.date) ?? {};
        for (const value of day.values)
          values[forecast.model_kind + ':' + value.variable] = value.value;
        rows.set(day.date, values);
      }
    return [...rows]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, values]) => ({ date, values }));
  });
  protected label(variable: string) {
    return (
      (
        {
          temperature_mean: 'Temperatura media',
          temperature_min: 'Temperatura mínima media',
          temperature_max: 'Temperatura máxima media',
          precipitation: 'Lluvia acumulada',
          surface_soil_moisture: 'Humedad superficial del suelo',
        } as Record<string, string>
      )[variable] ?? variable
    );
  }
  protected unit(unit: string) {
    return unit === 'C' ? '°C' : unit === 'm3/m3' ? 'm³/m³' : unit;
  }
  protected dailyLabel(variable: string) {
    return (
      (
        {
          temperature_min: 'Temperatura mínima',
          temperature_max: 'Temperatura máxima',
          precipitation: 'Lluvia diaria',
        } as Record<string, string>
      )[variable] ?? this.label(variable)
    );
  }
  protected probability(estimate?: ProbabilityEstimate) {
    return estimate?.status === 'calibrated' && estimate.value != null
      ? (estimate.value * 100).toLocaleString('es-CO', { maximumFractionDigits: 1 }) + ' %'
      : 'No disponible';
  }

  protected condition(
    crop: NonNullable<NonNullable<Analysis['rotation_assessment']>['candidates']>[number],
    variable: 'precipitation' | 'surface_soil_moisture',
  ) {
    return crop.checks.find((check) => check.variable === variable) ?? null;
  }
}
