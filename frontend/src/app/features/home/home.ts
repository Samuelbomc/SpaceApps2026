import { ChangeDetectionStrategy, Component } from '@angular/core';
import { HomeHero } from './sections/hero/hero';
import { HomeProblem } from './sections/problem/problem';
import { HomeModules } from './sections/modules/modules';
import { HomeEarthObservation } from './sections/earth-observation/earth-observation';
import { HomePilotTerritory } from './sections/pilot-territory/pilot-territory';
import { HomeSources } from './sections/sources/sources';
import { HomeRoadmap } from './sections/roadmap/roadmap';

/**
 * Landing page. Composes self-contained section components so each one can be
 * edited (and styled) independently.
 */
@Component({
  selector: 'app-home',
  imports: [
    HomeHero,
    HomeProblem,
    HomeModules,
    HomeEarthObservation,
    HomePilotTerritory,
    HomeSources,
    HomeRoadmap,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-home-hero />
    <app-home-problem />
    <app-home-modules />
    <app-home-earth-observation />
    <app-home-pilot-territory />
    <app-home-sources />
    <app-home-roadmap />
  `,
})
export class Home {}
