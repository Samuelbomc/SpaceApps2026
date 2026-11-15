import type { components } from '../../contracts/api.generated';

export type AuthSession = components['schemas']['FarmerSession'];
export type Farm = components['schemas']['Farm'];
export type FarmWrite = components['schemas']['FarmWrite'];
export type FarmCatalog = components['schemas']['FarmCatalog'];
export type FarmDataset = components['schemas']['FarmDataset'];
export type DatasetUploadResult = components['schemas']['DatasetUploadResult'];
export type FarmModelContext = components['schemas']['FarmModelContext'];

export class APIError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'APIError';
    this.status = status;
  }
}

export type AgronomicCatalog = components['schemas']['CropCatalog'];
export type Region = components['schemas']['Region'];
export type MapPlace = components['schemas']['MapPlace'];
export type ObservationPage = components['schemas']['ObservationPage'];
export type Status = components['schemas']['StatusResponse'];
export type Forecast = components['schemas']['Forecast'];
export type Analysis = components['schemas']['AnalysisResult'];
export type ModelCatalog = components['schemas']['ModelCatalog'];
export type ModelInputContract = components['schemas']['ModelInputContract'];
export type ManualUpdate = components['schemas']['ManualUpdate'];

export type ObservationHistory = Pick<
  ObservationPage,
  'region_id' | 'items' | 'first_date' | 'last_date' | 'last_updated_at'
> & { total: number };

export type APIClientOptions = { baseURL?: string; fetcher?: typeof fetch };

export function createAPIClient({
  baseURL = '/backend/',
  fetcher = (input, init) => globalThis.fetch(input, init),
}: APIClientOptions = {}) {
  if (!(baseURL.startsWith('/') && !baseURL.startsWith('//')) && !/^https?:\/\//.test(baseURL))
    throw new Error('URL base de API inválida.');
  baseURL = baseURL.replace(/\/+$/, '') + '/';
  async function requestResponse(path: string, options?: RequestInit): Promise<Response> {
    if (
      !path ||
      path.startsWith('/') ||
      /^[a-z][a-z0-9+.-]*:/i.test(path) ||
      path
        .split('?')[0]
        .split('/')
        .some((part) => ['.', '..'].includes(decodeURIComponent(part)))
    ) {
      throw new Error('La ruta de API debe ser relativa a la URL base.');
    }
    const response = await fetcher(`${baseURL}${path}`, {
      ...options,
      credentials: 'include',
      cache: 'no-store',
    });
    if (!response.ok) {
      let detail = 'No pudimos completar la consulta.';
      try {
        const error = await response.json();
        if (typeof error.detail === 'string') detail = error.detail;
        else if (Array.isArray(error.detail))
          detail = error.detail
            .map((item: { msg?: string }) => item.msg || 'Revisa los campos.')
            .join(' ');
      } catch {
        /* El proxy puede responder texto cuando la API está desconectada. */
      }
      throw new APIError(detail, response.status);
    }
    return response;
  }

  async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await requestResponse(path, options);
    return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>);
  }

  async function download(path: string, options?: RequestInit): Promise<Blob> {
    return (await requestResponse(path, options)).blob();
  }

  async function loadObservationHistory(
    region: string,
    signal?: AbortSignal,
  ): Promise<ObservationHistory> {
    // Cargar todas las páginas; si la ingesta cambia durante la lectura, repetir una vez.
    for (let attempt = 0; attempt < 2; attempt++) {
      const items: ObservationPage['items'] = [];
      let first: ObservationPage | undefined;
      let changed = false;
      do {
        const page = await request<ObservationPage>(
          `regions/${encodeURIComponent(region)}/observations?limit=1000&offset=${items.length}`,
          { signal },
        );
        if (
          page.region_id !== region ||
          !Number.isInteger(page.total) ||
          page.total! < 0 ||
          page.offset !== items.length
        ) {
          throw new Error('La respuesta no permite comprobar el histórico completo.');
        }
        first ??= page;
        if (
          page.total !== first.total ||
          page.last_updated_at !== first.last_updated_at ||
          page.first_date !== first.first_date ||
          page.last_date !== first.last_date ||
          (page.items.length === 0 && items.length < page.total!) ||
          items.length + page.items.length > page.total!
        ) {
          changed = true;
          break;
        }
        items.push(...page.items);
      } while (items.length < first.total!);
      if (!changed && first)
        return {
          region_id: region,
          items,
          total: first.total!,
          first_date: first.first_date,
          last_date: first.last_date,
          last_updated_at: first.last_updated_at,
        };
    }
    throw new Error(
      'Los datos cambiaron durante la carga. Actualiza la vista para consultar el histórico completo.',
    );
  }

  return { request, download, loadObservationHistory };
}
