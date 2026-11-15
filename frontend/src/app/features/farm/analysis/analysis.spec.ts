import { TestBed } from '@angular/core/testing';
import { Analysis } from './analysis';
import { Backend } from '../../../core/api/backend';
import { vi } from 'vitest';

describe('Analysis with connected XGBoost models', () => {
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
    if (path === 'regions') return [{ region_id: 'test-only', name: 'Solo test' }];
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
  it('shows available models and missing inputs without inventing forecasts', async () => {
    const fixture = TestBed.createComponent(Analysis);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Faltan variables de SMAP');
    });
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('modelos XGBoost integrados');
    expect(text).toContain('Versión experimental');
    expect(text).toContain('Faltan variables de SMAP');
    expect(text).not.toContain('Temperatura media:');
    expect(text).not.toContain('MAE de evaluación');
  });
  it('technical detail exposes metadata and evaluation context', async () => {
    const fixture = TestBed.createComponent(Analysis);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const toggle = fixture.nativeElement.querySelector('input[type="checkbox"]');
    toggle.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('MAE de evaluación');
    expect(fixture.nativeElement.textContent).toContain('Solo modelo de prueba');
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
    expect(text).toContain('Evaluación provisional basada en XGBoost');
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
      expect(fixture.nativeElement.textContent).toContain('La evaluación de rotaciones necesita');
    });
    expect(fixture.nativeElement.textContent).not.toContain('Escenario condicional');
  });
});
