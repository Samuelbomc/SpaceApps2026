import { ChangeDetectionStrategy, Component } from '@angular/core';
import { HomeHero } from './sections/hero/hero';
import { HomeProblem } from './sections/problem/problem';
import { HomeHowItWorks } from './sections/how-it-works/how-it-works';
import { HomeEarthObservation } from './sections/earth-observation/earth-observation';
import { HomePilotTerritory } from './sections/pilot-territory/pilot-territory';
import { HomeSources } from './sections/sources/sources';
import { HomeRoadmap } from './sections/roadmap/roadmap';

/**
 * Landing page of the integrated platform. Composes self-contained section
 * components so each one can be edited (and styled) independently.
 */
@Component({
  selector: 'app-home',
  imports: [
    HomeHero,
    HomeProblem,
    HomeHowItWorks,
    HomeEarthObservation,
    HomePilotTerritory,
    HomeSources,
    HomeRoadmap,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-home-hero />
    <app-home-problem />
    <app-home-how-it-works />
    <app-home-earth-observation />
    <app-home-pilot-territory />
    <app-home-sources />
    <app-home-roadmap />
  `,
})
export class Home {}
