import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { NavDropdown } from './nav-dropdown';
import { HOME_GROUP } from '../navigation';

describe('NavDropdown', () => {
  async function render() {
    TestBed.configureTestingModule({ providers: [provideRouter([{ path: '**', children: [] }])] });
    const fixture = TestBed.createComponent(NavDropdown);
    fixture.componentRef.setInput('group', HOME_GROUP);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    document.body.appendChild(el);
    const trigger = el.querySelector<HTMLButtonElement>('.dropdown__trigger')!;
    const menu = el.querySelector<HTMLElement>('.dropdown__menu')!;
    return { fixture, el, trigger, menu };
  }

  it('opens on hover and closes when the pointer leaves, only with a mouse-like pointer', async () => {
    const original = globalThis.matchMedia;
    // Desktop: hover-capable fine pointer, wide viewport.
    globalThis.matchMedia = ((query: string) => ({ matches: !query.includes('max-width') })) as typeof matchMedia;
    try {
      const { fixture, el, trigger } = await render();
      el.dispatchEvent(new MouseEvent('mouseenter'));
      await fixture.whenStable();
      expect(trigger.getAttribute('aria-expanded')).toBe('true');

      // A click after hovering keeps it open (it does not toggle it shut).
      trigger.click();
      await fixture.whenStable();
      expect(trigger.getAttribute('aria-expanded')).toBe('true');
      trigger.click();
      await fixture.whenStable();
      expect(trigger.getAttribute('aria-expanded')).toBe('false');

      el.dispatchEvent(new MouseEvent('mouseenter'));
      el.dispatchEvent(new MouseEvent('mouseleave'));
      await new Promise((r) => setTimeout(r, 250));
      await fixture.whenStable();
      expect(trigger.getAttribute('aria-expanded')).toBe('false');
    } finally {
      globalThis.matchMedia = original;
    }
  });

  it('ignores hover on touch devices (no hover capability)', async () => {
    const original = globalThis.matchMedia;
    globalThis.matchMedia = (() => ({ matches: false })) as unknown as typeof matchMedia;
    try {
      const { fixture, el, trigger } = await render();
      el.dispatchEvent(new MouseEvent('mouseenter'));
      await fixture.whenStable();
      expect(trigger.getAttribute('aria-expanded')).toBe('false');
    } finally {
      globalThis.matchMedia = original;
    }
  });

  it('lists Inicio, Cómo funciona and Fuentes y métodos with correct targets', async () => {
    const { el } = await render();
    const links = [...el.querySelectorAll<HTMLAnchorElement>('.dropdown__link')];
    expect(links.map((a) => a.textContent?.trim())).toEqual(['Inicio', 'Cómo funciona', 'Fuentes y métodos']);
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/', '/#como-funciona', '/#fuentes']);
  });

  it('toggles with a click and exposes aria-expanded', async () => {
    const { fixture, trigger, menu } = await render();
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    trigger.click();
    await fixture.whenStable();
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(menu.classList).toContain('dropdown__menu--open');
    trigger.click();
    await fixture.whenStable();
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });

  it('opens with ArrowDown focusing the first link, and Escape closes returning focus', async () => {
    const { fixture, el, trigger } = await render();
    trigger.focus();
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    await fixture.whenStable();
    expect(document.activeElement?.classList).toContain('dropdown__link');
    expect(document.activeElement?.textContent?.trim()).toBe('Inicio');

    el.querySelector('.dropdown__menu')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    expect(document.activeElement?.textContent?.trim()).toBe('Cómo funciona');

    document.activeElement!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await fixture.whenStable();
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(trigger);
  });

  it('closes after choosing a link and after any navigation', async () => {
    const { fixture, el, trigger } = await render();
    let navigated = 0;
    fixture.componentInstance.navigated.subscribe(() => navigated++);

    trigger.click();
    await fixture.whenStable();
    el.querySelectorAll<HTMLAnchorElement>('.dropdown__link')[2].click();
    await fixture.whenStable();
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(navigated).toBe(1);

    trigger.click();
    await fixture.whenStable();
    await TestBed.inject(Router).navigateByUrl('/explorar');
    await fixture.whenStable();
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });
});
