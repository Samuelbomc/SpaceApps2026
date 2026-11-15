import { TestBed } from '@angular/core/testing';
import { MunicipalityPanel } from './municipality-panel';
import { MunicipalitySummary } from '../../models/geo.models';

const laUnion: MunicipalitySummary = {
  id: 5400,
  code: '05400',
  name: 'La Unión',
  areaKm2: 167.7,
  bbox: [-75.4, 5.9, -75.3, 6.0],
};
const briceno: MunicipalitySummary = {
  id: 5107,
  code: '05107',
  name: 'Briceño',
  areaKm2: 376.2,
  bbox: [-75.6, 7.0, -75.4, 7.2],
};

describe('MunicipalityPanel', () => {
  async function render(municipality: MunicipalitySummary | null) {
    const fixture = TestBed.createComponent(MunicipalityPanel);
    fixture.componentRef.setInput('departmentName', 'Antioquia');
    fixture.componentRef.setInput('all', [laUnion, briceno]);
    fixture.componentRef.setInput('municipality', municipality);
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  it('shows the department overview with honest coverage counts', async () => {
    const el = await render(null);
    expect(el.querySelector('h2')?.textContent).toContain('Antioquia');
    expect(el.querySelector('.tally')?.textContent).toMatch(/0\s*Datos integrados/);
    expect(el.querySelector('.tally')?.textContent).toMatch(/1\s*Datos procesados/);
  });

  it('marks La Unión as processed but not yet connected, with its sources', async () => {
    const el = await render(laUnion);
    expect(el.querySelector('h2')?.textContent).toContain('La Unión');
    expect(el.querySelector('.coverage strong')?.textContent).toContain('pendientes de conexión');
    expect(el.textContent).toContain('NASA POWER');
    expect(el.textContent).toContain('no una finca');
  });

  it('never invents data for municipalities without coverage', async () => {
    const el = await render(briceno);
    expect(el.querySelector('.coverage strong')?.textContent).toContain('Sin datos integrados');
    expect(el.querySelector('.coverage__sources')).toBeNull();
  });
});
