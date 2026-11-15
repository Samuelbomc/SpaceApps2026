import type { components } from '../../../../packages/contracts/api.generated';

export type AuthSession = components['schemas']['FarmerSession'];
export type Farm = components['schemas']['Farm'];
export type FarmWrite = components['schemas']['FarmWrite'];
export type FarmCatalog = components['schemas']['FarmCatalog'];
export type FarmDataset = components['schemas']['FarmDataset'];
export type DatasetUploadResult = components['schemas']['DatasetUploadResult'];
export type FarmModelContext = components['schemas']['FarmModelContext'];

export class APIError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.name = 'APIError'; this.status = status; }
}

export type Region = components['schemas']['Region'];
export type MapPlace = components['schemas']['MapPlace'];
export type ObservationPage = components['schemas']['ObservationPage'];
export type Status = components['schemas']['StatusResponse'];
export type Analysis = components['schemas']['AnalysisResult'];

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/backend/${path}`, { ...options, cache: 'no-store' });
  if (!response.ok) {
    let detail = 'No pudimos completar la consulta.';
    try {
      const error = await response.json();
      if (typeof error.detail === 'string') detail = error.detail;
      else if (Array.isArray(error.detail)) detail = error.detail.map((item: { msg?: string }) => item.msg || 'Revisa los campos.').join(' ');
    } catch { /* El proxy puede responder texto cuando la API está desconectada. */ }
    throw new APIError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export type ObservationHistory = Pick<ObservationPage, 'region_id' | 'items' | 'first_date' | 'last_date' | 'last_updated_at'> & { total: number };

export async function loadObservationHistory(region: string, signal?: AbortSignal): Promise<ObservationHistory> {
  // Cargar todas las páginas; si la ingesta cambia durante la lectura, repetir una vez.
  for (let attempt = 0; attempt < 2; attempt++) {
    const items: ObservationPage['items'] = [];
    let first: ObservationPage | undefined;
    let changed = false;
    do {
      const page = await api<ObservationPage>(`regions/${encodeURIComponent(region)}/observations?limit=1000&offset=${items.length}`, { signal });
      if (page.region_id !== region || !Number.isInteger(page.total) || page.total! < 0 || page.offset !== items.length) {
        throw new Error('La respuesta no permite comprobar el histórico completo.');
      }
      first ??= page;
      if (page.total !== first.total || page.last_updated_at !== first.last_updated_at ||
          page.first_date !== first.first_date || page.last_date !== first.last_date ||
          (page.items.length === 0 && items.length < page.total!) || items.length + page.items.length > page.total!) {
        changed = true;
        break;
      }
      items.push(...page.items);
    } while (items.length < first.total!);
    if (!changed && first) return { region_id: region, items, total: first.total!, first_date: first.first_date,
      last_date: first.last_date, last_updated_at: first.last_updated_at };
  }
  throw new Error('Los datos cambiaron durante la carga. Actualiza la vista para consultar el histórico completo.');
}
