import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { Backend } from '../../../../core/api/backend';
import { ManualRefresh } from './manual-refresh';
import type { ManualUpdate } from '@agrogeo/api-client';

const state = (status: ManualUpdate['status']): ManualUpdate => ({
  request_id: '00000000-0000-4000-8000-000000000001',
  status,
  created_at: '2026-11-15T00:00:00Z',
  updated_at: '2026-11-15T00:00:00Z',
  phase: 'ingestion',
  message:
    status === 'queued'
      ? 'Solicitud sintética en espera.'
      : 'Actualización parcial de prueba; no se publicaron modelos.',
  stages: [
    {
      phase: 'ingestion',
      status: status === 'queued' ? 'pending' : 'completed',
      message: 'Solo fixture de interfaz.',
      counts: {},
      limitations: status === 'queued' ? [] : ['Faltan entradas recientes de prueba.'],
    },
  ],
});
describe('Manual data/model update', () => {
  const request = vi.fn();
  const write = vi.fn();
  beforeEach(() => {
    request.mockReset().mockResolvedValue(null);
    write.mockReset().mockResolvedValue(state('queued'));
    TestBed.configureTestingModule({
      providers: [{ provide: Backend, useValue: { client: { request }, write } }],
    });
  });
  it('only queues once, polls the result and reports incomplete model inputs without claiming publication', async () => {
    const fixture = TestBed.createComponent(ManualRefresh);
    await fixture.whenStable();
    fixture.detectChanges();
    const completed = vi.fn();
    fixture.componentInstance.updated.subscribe(completed);
    request.mockResolvedValue(state('completed_with_limitations'));
    const button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      'button',
    )!;
    button.click();
    button.click();
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(button.disabled).toBe(true);
    });
    expect(write).toHaveBeenCalledExactlyOnceWith('automation/refresh', 'POST');
    await vi.waitFor(
      () => {
        fixture.detectChanges();
        expect(completed).toHaveBeenCalledOnce();
      },
      { timeout: 6500 },
    );
    expect(fixture.nativeElement.textContent).toContain('no se publicaron modelos');
    expect((fixture.nativeElement as HTMLElement).querySelector('details')?.open).toBe(true);
    expect(button.disabled).toBe(false);
    fixture.destroy();
  }, 10000);
  it('ignores an obsolete status response after the user queues an update', async () => {
    let resolve!: (update: ManualUpdate | null) => void;
    request.mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );
    const fixture = TestBed.createComponent(ManualRefresh);
    fixture.detectChanges();
    (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('button')!.click();
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Solicitud sintética en espera');
    });
    resolve(state('completed'));
    await Promise.resolve();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Solicitud sintética en espera');
    expect(fixture.nativeElement.textContent).not.toContain('no se publicaron modelos');
    fixture.destroy();
  });
  it('allows a status retry after a read failure without submitting another job', async () => {
    request.mockRejectedValueOnce(new Error('Estado temporalmente no disponible.'));
    const fixture = TestBed.createComponent(ManualRefresh);
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Estado temporalmente no disponible');
    });
    const retry = [
      ...(fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>('button'),
    ].find((button) => button.textContent?.includes('Consultar estado'))!;
    retry.click();
    await vi.waitFor(() => {
      fixture.detectChanges();
      expect(fixture.nativeElement.querySelector('[role="alert"]')).toBeNull();
    });
    expect(write).not.toHaveBeenCalled();
    expect(request).toHaveBeenCalledTimes(2);
    fixture.destroy();
  });
  it('cancels pending status reads on destruction', () => {
    request.mockImplementation(() => new Promise(() => {}));
    const fixture = TestBed.createComponent(ManualRefresh);
    const options = request.mock.calls[0][1] as RequestInit;
    fixture.destroy();
    expect(options.signal?.aborted).toBe(true);
  });
});
