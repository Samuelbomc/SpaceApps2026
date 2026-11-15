import { TestBed } from '@angular/core/testing';
import { HomeSources } from './sources';
import { DATA_SOURCES } from '../../../../core/catalog/data-sources';

describe('HomeSources', () => {
  it('keeps all official sources available in a collapsed disclosure', async () => {
    const fixture = TestBed.createComponent(HomeSources);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('details')?.open).toBe(false);
    expect(el.textContent).toContain('UPRA');
    expect(el.textContent).toContain('EVA y calendarios agrícolas');
    expect(el.textContent).toContain('Aptitud de cultivos');
    expect(el.textContent).not.toMatch(/ECOSTRESS|IDEAM|FAO GAEZ/);
    expect(el.querySelectorAll('.source').length).toBe(DATA_SOURCES.length);
    expect([...el.querySelectorAll('.source a')].map((link) => link.getAttribute('href'))).toEqual(
      DATA_SOURCES.map((source) => source.url),
    );
  });
});
