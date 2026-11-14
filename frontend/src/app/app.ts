import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { SiteHeader } from './core/layout/site-header/site-header';
import { SiteFooter } from './core/layout/site-footer/site-footer';

/** Application shell: skip link, header, routed page, footer. */
@Component({
  selector: 'app-root',
  imports: [RouterOutlet, SiteHeader, SiteFooter],
  templateUrl: './app.html',
  styleUrl: './app.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {
  /**
   * A plain href="#main" would be resolved against <base href="/"> and navigate
   * to the home page, so the skip link moves focus programmatically instead.
   */
  protected skipToMain(event: Event, main: HTMLElement): void {
    event.preventDefault();
    main.focus();
    main.scrollIntoView();
  }
}
