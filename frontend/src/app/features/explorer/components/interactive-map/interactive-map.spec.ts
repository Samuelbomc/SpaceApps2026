import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { InteractiveMap } from './interactive-map';

/**
 * jsdom has no WebGL, which exercises the graceful-failure path: the map must
 * show an explanatory message instead of breaking the page.
 */
describe('InteractiveMap without WebGL', () => {
  it('shows an accessible fallback message and keeps camera buttons disabled', async () => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    const fixture = TestBed.createComponent(InteractiveMap);
    await fixture.whenStable();
    await new Promise((r) => setTimeout(r));
    await fixture.whenStable();

    const el = fixture.nativeElement as HTMLElement;
    const alert = el.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain('WebGL');
    expect(alert?.textContent).toContain('lista');
    el.querySelectorAll<HTMLButtonElement>('.views button').forEach((b) =>
      expect(b.disabled).toBe(true),
    );
  });
});
