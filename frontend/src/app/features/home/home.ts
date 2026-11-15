import { ChangeDetectionStrategy, Component } from '@angular/core';
import { HomeHero } from './sections/hero/hero';
import { HomeHowItWorks } from './sections/how-it-works/how-it-works';
import { HomeSources } from './sections/sources/sources';

@Component({
  selector: 'app-home',
  imports: [HomeHero, HomeHowItWorks, HomeSources],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-home-hero />
    <app-home-how-it-works />
    <app-home-sources />
  `,
})
export class Home {}
