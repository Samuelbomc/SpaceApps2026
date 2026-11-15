import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Analysis } from './analysis';
import { Backend } from '../../../core/api/backend';
import { vi } from 'vitest';
import type { Observation } from '@agrogeo/api-client/observations';

describe('Analysis with connected XGBoost models', () => {
  const savedAnalysis = {
    analysis_id: 'archive-test-only',
    status: 'pending_recommendations',
    request: {
      region_id: 'test-only',
      reference_date: '2026-10-01',
      forecast_start_date: '2026-10-03',
      horizon_days: 15,
    },
    climate: {
      model_kind: 'climate',
      model_version: 'historical-test-only',
      validation_status: 'experimental',
      limitations: [],
      values: [
        { variable: 'temperature_mean', value: 17.75, unit: 'C', aggregation: 'media de 15 días' },
      ],
    },
    soil: null,
    recommendations: null,
    messages: [],
  };
  const button = (fixture: ComponentFixture<Analysis>, text: string) =>
    [...(fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>('button')].find(
      (item) => item.textContent?.includes(text),
    )!;
  const openArchive = async (fixture: ComponentFixture<Analysis>) => {
    fixture.componentRef.setInput('historyEnabled', true);
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(button(fixture, 'Análisis anteriores')).toBeDefined();
    });
    button(fixture, 'Análisis anteriores').click();
  };
  const catalog = {
    models: [
      {
        model_id: 'temperature_mean',
        model_kind: 'climate',
        horizon_days: 7,
        features: [],
        version: 'test-only',
        evaluation_mae: 0.5,
        baseline_mae: 0.6,
        unit: 'C',
        formula: 'XGBoost(features)',
        evaluation_note: 'Solo modelo de prueba',
        validation_status: 'experimental',
      },
    ],
    supported_horizons: [7],
    limitations: [],
  };
  const defaultRequest = async (path: string): Promise<unknown> => {
    if (path === 'regions')
      return [{ region_id: 'test-only', name: 'Solo test', latitude: 6, longitude: -75 }];
    if (path === 'crops/catalog') return { crops: [] };
    if (path === 'models') return catalog;
    return {
      status: 'insufficient_data',
      messages: ['Faltan variables de SMAP para esta fecha.'],
      climate: null,
      soil: null,
      recommendations: null,
    };
  };
  const request = vi.fn(defaultRequest);
  const observation = (
    variable: string,
    value: number | null,
    extra: Partial<Observation> = {},
  ): Observation => ({
    variable,
    value,
    date: '2026-10-03',
    source: 'NASA_POWER',
    unit: 'C',
    quality: 'provider_value_unvalidated',
    resolution: 'test-only',
    ...extra,
  });
  const setObservations = (items: Observation[]) => {
    TestBed.inject(Backend).client.loadObservationHistory = async () => ({
      region_id: 'test-only',
      items,
      total: items.length,
      first_date: '2026-10-01',
      last_date: '2026-10-05',
      last_updated_at: '2026-10-06T00:00:00Z',
    });
  };
  beforeEach(() => {
    request.mockReset();
    request.mockImplementation(defaultRequest);
    TestBed.configureTestingModule({
      providers: [
        {
          provide: Backend,
          useValue: {
            client: {
              request,
              loadObservationHistory: async () => ({ items: [], total: 0, last_updated_at: null }),
            },
          },
        },
      ],
    });
  });
  it('shows one clear pending state without requesting technical catalogs or inventing forecasts', async () => {
    const fixture = TestBed.createComponent(Analysis);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Faltan datos recientes');
    });
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Aún no hay predicciones para este periodo');
    expect(
      (fixture.nativeElement as HTMLElement).querySelector<HTMLDetailsElement>('.analysis-cause')
        ?.open,
    ).toBe(false);
    expect(text).toContain('Faltan variables de SMAP');
    expect(request.mock.calls.some(([path]) => path === 'models' || path === 'crops/catalog')).toBe(
      false,
    );
    expect(text).not.toContain('Temperatura media:');
    expect(text).not.toContain('MAE de evaluación');
  });
  it('technical detail exposes metadata and evaluation context', async () => {
    const fixture = TestBed.createComponent(Analysis);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const toggle = fixture.nativeElement.querySelector('select[aria-label="Nivel de detalle"]');
    toggle.value = 'technical';
    toggle.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('MAE de evaluación');
      expect(fixture.nativeElement.textContent).toContain('Solo modelo de prueba');
      expect(fixture.nativeElement.textContent).toContain('Faltan variables de SMAP');
    });
    toggle.value = 'simple';
    toggle.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).not.toContain('MAE de evaluación');
  });
  it('selecting 30 days requests that exact horizon and clears the earlier result', async () => {
    const fixture = TestBed.createComponent(Analysis);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const select = fixture.nativeElement.querySelector('select[aria-label="Plazo"]');
    select.value = '30';
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(request.mock.calls.some(([path]) => path.includes('horizon_days=30'))).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('próximos 30 días');
  });

  it('keeps experimental status visible in simple mode when forecasts exist', async () => {
    request.mockImplementation(async (path: string) => {
      if (!path.includes('latest-analysis')) return defaultRequest(path);
      return {
        status: 'pending_recommendations',
        climate: {
          model_kind: 'climate',
          model_version: 'test-only',
          validation_status: 'experimental',
          limitations: [],
          values: [{ variable: 'temperature_mean', value: 22, unit: 'C', aggregation: 'mean' }],
        },
      };
    });
    const fixture = TestBed.createComponent(Analysis);
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Experimental');
    });
    expect(fixture.nativeElement.textContent).toContain('Temperatura media');
    expect(fixture.nativeElement.textContent).not.toContain('MAE de evaluación');
    expect(fixture.nativeElement.textContent).not.toContain('Aún no hay predicciones');
  });

  it('preserves the primary analysis when optional technical metadata fails', async () => {
    request.mockImplementation(async (path: string) => {
      if (path === 'models') throw new Error('Catalog unavailable');
      return defaultRequest(path);
    });
    const fixture = TestBed.createComponent(Analysis);
    fixture.detectChanges();
    await fixture.whenStable();
    const toggle = fixture.nativeElement.querySelector('select[aria-label="Nivel de detalle"]');
    toggle.value = 'technical';
    toggle.dispatchEvent(new Event('change'));
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain(
        'No se pudieron cargar todos los detalles',
      );
    });
    expect(fixture.nativeElement.textContent).toContain('Faltan datos recientes');
    expect(fixture.nativeElement.textContent).toContain('Faltan variables de SMAP');
  });

  it('clears unrelated results when the selected area has no stored location', async () => {
    const fixture = TestBed.createComponent(Analysis);
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Faltan datos recientes');
    });
    const area = {
      type: 'Polygon',
      coordinates: [
        [
          [-74, 5],
          [-73, 5],
          [-73, 6],
          [-74, 6],
          [-74, 5],
        ],
      ],
    };
    fixture.componentRef.setInput('area', area);
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain(
        'Sin análisis almacenados para esta ubicación',
      );
      expect(fixture.nativeElement.textContent).toContain(
        'Análisis para un periodo de los próximos 7 días',
      );
      expect(fixture.nativeElement.textContent).not.toContain('Faltan datos recientes');
    });
    expect(fixture.nativeElement.textContent).not.toContain('Datos históricos de referencia');
    const button = [...fixture.nativeElement.querySelectorAll('button')].find((item: any) =>
      item.textContent.includes('Ver otras ubicaciones'),
    ) as HTMLButtonElement;
    button.click();
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain(
        'Datos de Solo test; están fuera del área seleccionada',
      );
      expect(fixture.nativeElement.textContent).toContain('Faltan datos recientes');
    });
    fixture.componentRef.setInput('area', { ...area });
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain(
        'Sin análisis almacenados para esta ubicación',
      );
    });
  });

  it('shows conditional stages and never presents later crops as forecasted', async () => {
    request.mockImplementation(async (path: string) => {
      if (!path.includes('latest-analysis')) return defaultRequest(path);
      return {
        status: 'pending_recommendations',
        messages: [],
        rotation_assessment: {
          status: 'pending_agronomic_requirements',
          engine_version: 'test-only',
          catalog_version: 'test-only',
          rules_version: 'test-only',
          input_snapshot_id: 'test-only',
          region_id: 'test-only',
          horizon_days: 7,
          climate_model_version: 'climate-test',
          soil_model_version: 'soil-test',
          forecast_values: { precipitation: 42 },
          limitations: [],
          candidates: [],
          scenarios: [
            {
              status: 'conditional',
              explanation: 'Solo prueba de interfaz',
              stages: [
                {
                  crop_id: 'one',
                  crop_name: 'Cultivo inicial de prueba',
                  family: 'A',
                  forecast_evaluated: true,
                },
                {
                  crop_id: 'two',
                  crop_name: 'Cultivo posterior de prueba',
                  family: 'B',
                  forecast_evaluated: false,
                },
              ],
            },
          ],
        },
      };
    });
    const fixture = TestBed.createComponent(Analysis);
    fixture.detectChanges();
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Escenario condicional');
    });
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Evaluación provisional');
    expect(text).toContain('Todavía no es una recomendación de siembra aprobada');
    expect(text).toContain('evaluación parcial del periodo');
    expect(text).toContain('requiere nuevas predicciones');
    expect(text).not.toContain('Qué sembrar este año');
  });
  it('does not render scenarios before forecasts exist', async () => {
    request.mockImplementation(async (path: string) => {
      if (!path.includes('latest-analysis')) return defaultRequest(path);
      return {
        status: 'insufficient_data',
        messages: [],
        rotation_assessment: {
          status: 'pending_forecasts',
          engine_version: 'test-only',
          catalog_version: 'test-only',
          rules_version: 'test-only',
          input_snapshot_id: 'test-only',
          limitations: [],
          candidates: [],
          scenarios: [],
        },
      };
    });
    const fixture = TestBed.createComponent(Analysis);
    fixture.detectChanges();
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain(
        'Aún no hay predicciones para este periodo',
      );
    });
    expect(fixture.nativeElement.textContent).not.toContain('Escenario condicional');
    expect(fixture.nativeElement.textContent).not.toContain('Cultivos y rotaciones');
  });
  it('loads stored analyses only on request and shows historical dates without presenting them as current forecasts', async () => {
    request.mockImplementation(async (path) =>
      path.includes('/analyses?') ? [savedAnalysis] : defaultRequest(path),
    );
    const fixture = TestBed.createComponent(Analysis);
    await openArchive(fixture);
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect((fixture.nativeElement as HTMLElement).querySelector('.archive-entry')).not.toBeNull();
    });
    expect(request.mock.calls.filter(([path]) => path.includes('/analyses?')).length).toBe(1);
    (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLButtonElement>('.archive-entry')!
      .click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Estás consultando un análisis guardado');
    expect(text).toContain('Análisis del');
    expect(text).toContain('Experimental');
    expect(text).not.toContain('próximos 7 días');
    expect(text).not.toContain('Datos observados');
    fixture.componentInstance.refreshAvailableData();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Estás consultando un análisis guardado');
    expect(
      (fixture.nativeElement as HTMLElement).querySelector<HTMLSelectElement>(
        'select[aria-label="Plazo"]',
      )!.disabled,
    ).toBe(true);
    button(fixture, 'Volver al análisis actual').click();
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('próximos 7 días');
    });
    expect(fixture.nativeElement.textContent).not.toContain(
      'Estás consultando un análisis guardado',
    );
  });

  it('has no archive controls or archive requests for the anonymous view', async () => {
    const fixture = TestBed.createComponent(Analysis);
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Faltan datos recientes');
    });
    expect(button(fixture, 'Análisis anteriores')).toBeUndefined();
    expect(request.mock.calls.some(([path]) => path.includes('/analyses?'))).toBe(false);
  });

  it('identifies provider, date and reference location for historical humidity and wind without calling them forecasts', async () => {
    TestBed.inject(Backend).client.loadObservationHistory = async () => ({
      region_id: 'test-only',
      total: 2,
      first_date: '2026-10-01',
      last_date: '2026-10-01',
      last_updated_at: '2026-10-02T00:00:00Z',
      items: [
        {
          source: 'NASA_POWER',
          date: '2026-10-01',
          variable: 'RH2M',
          value: 50,
          unit: '%',
          quality: 'provider_value_unvalidated',
          resolution: 'test-only',
        },
        {
          source: 'NASA_POWER',
          date: '2026-10-01',
          variable: 'WS10M',
          value: 1.2,
          unit: 'm/s',
          quality: 'provider_value_unvalidated',
          resolution: 'test-only',
        },
      ],
    });
    const fixture = TestBed.createComponent(Analysis);
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Humedad relativa del aire a 2 m');
    });
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Velocidad del viento a 10 m');
    expect(text).toContain('Últimos valores disponibles para Solo test');
    expect(text).toContain('No son pronósticos');
    const captions = [
      ...(fixture.nativeElement as HTMLElement).querySelectorAll('.metric__caption'),
    ];
    expect(captions).toHaveLength(2);
    for (const caption of captions) {
      expect(caption.textContent).toContain('NASA POWER');
      expect(caption.textContent).toContain('2026');
    }
    expect(text).toContain('Aún no hay predicciones para este periodo');
  });

  it('groups all latest usable values by topic, with temperatures together regardless of input order', async () => {
    setObservations([
      observation('T2M', -30, { date: '2026-10-01' }),
      observation('WS10M', 1.2, { unit: 'm/s' }),
      observation('T2M_MAX', 28),
      observation('RH2M', 50, { unit: '%' }),
      observation('T2M_MIN', 16),
      observation('ALLSKY_SFC_SW_DWN', 4.2, { unit: 'kWh/m²/day' }),
      observation('T2M', 22),
      observation('PRECTOTCORR', 0, { unit: 'mm/day' }),
      observation('T2M', null, { date: '2026-10-04', quality: 'missing' }),
      observation('T2M', 900, { date: '2026-10-05', quality: 'out_of_range' }),
      observation('surface_soil_moisture', null, { unit: 'm³/m³', quality: 'missing' }),
    ]);
    const fixture = TestBed.createComponent(Analysis);
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.querySelectorAll('.observations .metric')).toHaveLength(7);
    });
    const groups = [
      ...(fixture.nativeElement as HTMLElement).querySelectorAll('.observation-group'),
    ];
    expect(groups.map((group) => group.querySelector('h4')?.textContent)).toEqual([
      'Temperatura',
      'Lluvia y humedad',
      'Viento y radiación',
    ]);
    expect(
      [...groups[0].querySelectorAll('.metric > span:first-child')].map((el) => el.textContent),
    ).toEqual(['Temperatura mínima', 'Temperatura media', 'Temperatura máxima']);
    const mean = groups[0].querySelectorAll('.metric')[1];
    expect(mean.querySelector('strong')?.textContent).toContain('22');
    expect(mean.querySelector('time')?.getAttribute('datetime')).toBe('2026-10-03');
    expect(groups[1].querySelector('.metric strong')?.textContent).toContain('0');
    expect(fixture.nativeElement.querySelector('.observations').textContent).not.toContain('900');
    expect(fixture.nativeElement.querySelector('.observations').textContent).not.toContain(
      'Humedad superficial del suelo',
    );
  });

  it('keeps sources, units and resolutions separate and includes additional observed variables', async () => {
    setObservations([
      observation('T2M', 22),
      observation('T2M', 18, { source: 'OTHER_SOURCE', date: '2026-10-02' }),
      observation('T2M', 71.6, { unit: 'F' }),
      observation('T2M', 23, { resolution: 'other-resolution' }),
      observation('soil_ph', 6.2, { unit: 'pH' }),
    ]);
    const fixture = TestBed.createComponent(Analysis);
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.querySelectorAll('.observations .metric')).toHaveLength(5);
    });
    const groups = [
      ...(fixture.nativeElement as HTMLElement).querySelectorAll('.observation-group'),
    ];
    expect(groups[0].querySelectorAll('.metric')).toHaveLength(4);
    expect(groups[0].textContent).toContain('OTHER SOURCE');
    expect(groups[0].querySelectorAll('time')[1].getAttribute('datetime')).toBe('2026-10-02');
    expect(groups[1].querySelector('h4')?.textContent).toBe('Otros datos');
    expect(groups[1].textContent).toContain('6.2');
    const toggle = fixture.nativeElement.querySelector('select[aria-label="Nivel de detalle"]');
    toggle.value = 'technical';
    toggle.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(groups[0].textContent).toContain('other-resolution');
    expect(groups[0].textContent).toContain('T2M');
  });

  it('distinguishes an empty archive from an error and allows retry without losing the current result', async () => {
    let failed = true;
    request.mockImplementation(async (path) => {
      if (!path.includes('/analyses?')) return defaultRequest(path);
      if (failed) throw new Error('No se pudo leer el historial de prueba');
      return [];
    });
    const fixture = TestBed.createComponent(Analysis);
    await openArchive(fixture);
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(button(fixture, 'Reintentar historial')).toBeDefined();
    });
    expect(fixture.nativeElement.textContent).not.toContain('No hay análisis guardados');
    failed = false;
    button(fixture, 'Reintentar historial').click();
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain(
        'No hay análisis guardados para esta ubicación',
      );
      expect(fixture.nativeElement.textContent).toContain('Faltan datos recientes');
    });
  });

  it('ignores a late archive response after the selected area changes', async () => {
    let resolveArchive!: (value: unknown) => void;
    request.mockImplementation(async (path) =>
      path.includes('/analyses?')
        ? new Promise((resolve) => {
            resolveArchive = resolve;
          })
        : defaultRequest(path),
    );
    const fixture = TestBed.createComponent(Analysis);
    await openArchive(fixture);
    await vi.waitFor(() => expect(resolveArchive).toBeDefined());
    fixture.componentRef.setInput('area', {
      type: 'Polygon',
      coordinates: [
        [
          [-74, 5],
          [-73, 5],
          [-73, 6],
          [-74, 6],
          [-74, 5],
        ],
      ],
    });
    fixture.detectChanges();
    resolveArchive([savedAnalysis]);
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain(
        'Sin análisis almacenados para esta ubicación',
      );
    });
    expect((fixture.nativeElement as HTMLElement).querySelector('.archive-entry')).toBeNull();
  });
});
