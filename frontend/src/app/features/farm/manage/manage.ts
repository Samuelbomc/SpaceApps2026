import { Component, DestroyRef, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Backend, errorMessage } from '../../../core/api/backend';
import { AuthService } from '../../../core/auth/auth.service';
import { AnalysisJourneyStore } from '../../../core/journey/analysis-journey.store';
import type {
  Farm,
  FarmWrite,
  FarmCatalog,
  FarmDataset,
  DatasetUploadResult,
  FarmModelContext,
} from '@agrogeo/api-client';

@Component({
  selector: 'app-farm-manage',
  imports: [FormsModule, RouterLink],
  templateUrl: './manage.html',
  styles: `
    .farm-layout {
      display: grid;
      gap: 1.5rem;
    }
    .farm-list {
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
    }
    .farm-form {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1rem;
    }
    .farm-form .field input,
    .farm-form select,
    .farm-form textarea {
      width: 100%;
    }
    .full {
      grid-column: 1/-1;
    }
    .actions {
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
    }
    .dataset {
      padding: 1rem 0;
      border-bottom: 1px solid #ccc;
    }
    .dataset p {
      overflow-wrap: anywhere;
    }
    .farm-message {
      padding: 1rem;
    }
    summary {
      cursor: pointer;
      font-weight: 600;
    }
    .extra-fields {
      margin-top: var(--sp-4);
    }
    fieldset {
      border: 0;
      padding: 0;
      margin: 0;
      min-width: 0;
    }
    @media (max-width: 650px) {
      .farm-form {
        grid-template-columns: 1fr;
      }
    }
  `,
})
export class FarmManage {
  private readonly backend = inject(Backend);
  protected readonly auth = inject(AuthService);
  private readonly journey = inject(AnalysisJourneyStore);
  protected readonly farms = signal<Farm[]>([]);
  protected readonly catalog = signal<FarmCatalog | null>(null);
  protected readonly selected = signal<Farm | null>(null);
  protected readonly datasets = signal<FarmDataset[]>([]);
  protected readonly context = signal<FarmModelContext | null>(null);
  protected readonly loading = signal(true);
  protected readonly busy = signal(false);
  protected readonly error = signal('');
  protected readonly notice = signal('');
  protected draft: FarmWrite = this.empty();
  private epoch = 0;
  private readonly destroyed = inject(DestroyRef);
  constructor() {
    this.destroyed.onDestroy(() => {
      this.epoch++;
    });
    effect((onCleanup) => {
      const owner = this.auth.user()?.id;
      const controller = new AbortController();
      onCleanup(() => {
        controller.abort();
        this.epoch++;
      });
      this.farms.set([]);
      this.catalog.set(null);
      this.selected.set(null);
      this.datasets.set([]);
      this.context.set(null);
      this.draft = this.empty();
      if (owner) void this.load(controller.signal);
    });
  }
  private empty(): FarmWrite {
    return {
      name: '',
      municipality: '',
      latitude: null as unknown as number,
      longitude: null as unknown as number,
      area_ha: null as unknown as number,
      soil_texture: 'unknown',
      irrigation: 'unknown',
      soil_ph: null,
      altitude_m: null,
      current_crops: [],
      notes: '',
      boundary: null,
      geometry: null,
    };
  }
  private async load(signal: AbortSignal) {
    this.loading.set(true);
    this.error.set('');
    try {
      const [farms, catalog] = await Promise.all([
        this.backend.client.request<Farm[]>('farms', { signal }),
        this.backend.client.request<FarmCatalog>('farms/catalog', { signal }),
      ]);
      if (signal.aborted) return;
      this.farms.set(farms);
      this.catalog.set(catalog);
      this.newFarm();
    } catch (error) {
      if (!signal.aborted) this.error.set(errorMessage(error));
    } finally {
      if (!signal.aborted) this.loading.set(false);
    }
  }
  protected newFarm() {
    this.epoch++;
    this.selected.set(null);
    this.datasets.set([]);
    this.context.set(null);
    this.draft = this.empty();
    this.notice.set('');
    const plot = this.journey.plot();
    if (plot) {
      this.draft = {
        ...this.draft,
        latitude: plot.centroid[1],
        longitude: plot.centroid[0],
        area_ha: plot.areaM2 / 10000,
        municipality: this.journey.municipality()?.name || '',
        geometry: plot.geometry,
      };
    }
  }
  protected async choose(farm: Farm) {
    this.epoch++;
    this.selected.set(farm);
    const { farm_id, revision, created_at, updated_at, ...draft } = farm;
    this.draft = { ...draft, current_crops: [...(draft.current_crops || [])] };
    this.datasets.set([]);
    this.context.set(null);
    this.error.set('');
    this.notice.set('');
    await this.details(farm.farm_id);
  }
  private async details(id: string) {
    const epoch = ++this.epoch;
    try {
      const [files, context] = await Promise.all([
        this.backend.client.request<FarmDataset[]>(`farms/${id}/datasets`),
        this.backend.client.request<FarmModelContext>(`farms/${id}/model-context`),
      ]);
      if (epoch !== this.epoch || this.selected()?.farm_id !== id) return;
      this.datasets.set(files);
      this.context.set(context);
    } catch (error) {
      if (epoch === this.epoch) this.error.set(errorMessage(error));
    }
  }
  protected clearBoundary() {
    this.draft.geometry = null;
    this.draft.boundary = null;
  }
  protected crops(value: string) {
    this.draft.current_crops = value
      .split(',')
      .map((v) => v.trim())
      .filter(Boolean);
  }
  protected async save() {
    this.busy.set(true);
    this.error.set('');
    this.notice.set('');
    const current = this.selected(),
      owner = this.auth.user()?.id;
    try {
      const saved = await this.backend.write<Farm>(
        current ? `farms/${current.farm_id}?revision=${current.revision}` : 'farms',
        current ? 'PUT' : 'POST',
        this.draft,
      );
      if (this.destroyed.destroyed || owner !== this.auth.user()?.id) return;
      this.farms.update((rows) => [saved, ...rows.filter((row) => row.farm_id !== saved.farm_id)]);
      await this.choose(saved);
      this.notice.set('Finca guardada.');
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
  protected async upload(input: HTMLInputElement) {
    const farm = this.selected(),
      file = input.files?.[0],
      owner = this.auth.user()?.id;
    if (!farm || !file) return;
    if (file.size > (this.catalog()?.max_file_bytes || 5 * 1024 * 1024)) {
      this.error.set('El archivo supera el límite de 5 MiB.');
      return;
    }
    this.busy.set(true);
    this.error.set('');
    this.notice.set('');
    try {
      const body = new FormData();
      body.append('file', file);
      const result = await this.backend.write<DatasetUploadResult>(
        `farms/${farm.farm_id}/datasets`,
        'POST',
        body,
      );
      if (this.destroyed.destroyed || owner !== this.auth.user()?.id) return;
      await this.details(farm.farm_id);
      this.notice.set(
        result.duplicate
          ? 'El archivo ya estaba cargado.'
          : 'Archivo cargado y validado en formato.',
      );
      input.value = '';
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
  private saveBlob(blob: Blob, name: string) {
    const url = URL.createObjectURL(blob),
      a = document.createElement('a');
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  protected template() {
    const catalog = this.catalog();
    if (catalog)
      this.saveBlob(
        new Blob([[...catalog.required_columns, ...catalog.optional_columns].join(',') + '\n'], {
          type: 'text/csv',
        }),
        'plantilla-finca.csv',
      );
  }
  protected async download(file: FarmDataset) {
    try {
      this.saveBlob(
        await this.backend.client.download(
          `farms/${file.farm_id}/datasets/${file.dataset_id}/download`,
        ),
        file.original_filename,
      );
    } catch (error) {
      this.error.set(errorMessage(error));
    }
  }
  protected async remove(file: FarmDataset) {
    if (!confirm(`¿Eliminar ${file.original_filename}?`)) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await this.backend.write(`farms/${file.farm_id}/datasets/${file.dataset_id}`, 'DELETE');
      await this.details(file.farm_id);
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
}
