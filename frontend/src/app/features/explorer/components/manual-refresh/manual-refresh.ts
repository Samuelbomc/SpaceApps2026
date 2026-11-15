import { Component, DestroyRef, computed, inject, output, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Backend, errorMessage } from '../../../../core/api/backend';
import type { ManualUpdate } from '@agrogeo/api-client';

const active = (update: ManualUpdate | null) =>
  !!update && ['queued', 'running', 'retry_scheduled'].includes(update.status);

@Component({
  selector: 'app-manual-refresh',
  imports: [DatePipe],
  templateUrl: './manual-refresh.html',
  styleUrl: './manual-refresh.scss',
})
export class ManualRefresh {
  private readonly backend = inject(Backend);
  private readonly destroyed = inject(DestroyRef);
  readonly updated = output<void>();
  protected readonly update = signal<ManualUpdate | null>(null);
  protected readonly sending = signal(false);
  protected readonly error = signal('');
  protected readonly running = computed(() => active(this.update()));
  protected readonly phases = {
    ingestion: 'Datos NASA',
    training: 'Modelos XGBoost',
    recommendations: 'Análisis y recomendaciones',
  };
  protected readonly statuses = {
    pending: 'Pendiente',
    running: 'En curso',
    completed: 'Finalizada',
    retry_scheduled: 'Reintento programado',
    failed: 'No completada',
  };
  private timer?: ReturnType<typeof setTimeout>;
  private controller?: AbortController;
  private observedActive = false;
  private lastProgress = '';
  constructor() {
    this.destroyed.onDestroy(() => {
      clearTimeout(this.timer);
      this.controller?.abort();
    });
    void this.read();
  }
  protected async requestUpdate() {
    if (this.sending() || this.running()) return;
    clearTimeout(this.timer);
    this.controller?.abort();
    this.sending.set(true);
    this.error.set('');
    try {
      const update = await this.backend.write<ManualUpdate>('automation/refresh', 'POST');
      if (this.destroyed.destroyed) return;
      this.accept(update);
    } catch (error) {
      if (!this.destroyed.destroyed) this.error.set(errorMessage(error));
    } finally {
      if (!this.destroyed.destroyed) this.sending.set(false);
    }
  }
  protected checkStatus() {
    clearTimeout(this.timer);
    void this.read();
  }
  private accept(update: ManualUpdate | null) {
    const progress = JSON.stringify([update?.updated_at, update?.status, update?.stages]);
    const dataMayHaveChanged = update?.stages.some(
      (stage) =>
        stage.phase === 'ingestion' &&
        ['completed', 'retry_scheduled', 'failed'].includes(stage.status),
    );
    this.update.set(update);
    if (this.observedActive && dataMayHaveChanged && progress !== this.lastProgress)
      this.updated.emit();
    this.lastProgress = progress;
    this.observedActive = active(update);
    if (this.observedActive) this.timer = setTimeout(() => void this.read(), 5000);
  }
  private async read() {
    this.controller?.abort();
    const controller = (this.controller = new AbortController());
    try {
      const update = await this.backend.client.request<ManualUpdate | null>('automation/refresh', {
        signal: controller.signal,
      });
      if (controller.signal.aborted || this.destroyed.destroyed) return;
      this.error.set('');
      this.accept(update);
    } catch (error) {
      if (controller.signal.aborted || this.destroyed.destroyed) return;
      this.error.set(errorMessage(error));
      if (this.running()) this.timer = setTimeout(() => void this.read(), 10000);
    }
  }
}
