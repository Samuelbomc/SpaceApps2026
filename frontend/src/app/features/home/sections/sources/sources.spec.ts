import { TestBed } from '@angular/core/testing';
import { HomeSources } from './sources';
import { DATA_SOURCES } from '../../../../core/catalog/data-sources';

describe('HomeSources', () => {
  it('filters sources between NASA and complementary providers', async () => {
    const fixture = TestBed.createComponent(HomeSources);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const count = () => el.querySelectorAll('.source').length;
    const buttons = el.querySelectorAll<HTMLButtonElement>('.segmented__btn');

    expect(count()).toBe(DATA_SOURCES.length);

    buttons[1].click(); // NASA
    await fixture.whenStable();
    expect(count()).toBe(DATA_SOURCES.filter((s) => s.isNasa).length);
    expect(buttons[1].getAttribute('aria-pressed')).toBe('true');

    buttons[2].click(); // Complementary
    await fixture.whenStable();
    expect(count()).toBe(DATA_SOURCES.filter((s) => !s.isNasa).length);
  });
});
