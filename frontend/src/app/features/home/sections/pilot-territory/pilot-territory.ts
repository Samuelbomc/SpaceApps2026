import { ChangeDetectionStrategy, Component } from '@angular/core';
import { GEOGRAPHIC_LEVELS, PILOT_TERRITORY } from '../../../../core/catalog/pilot-territory';

/**
 * Pilot geography. Shows Antioquia's subregions and the three spatial levels.
 * No map is drawn here on purpose: an approximate hand-drawn outline would be
 * misleading. The real map arrives with the data portal and official boundaries.
 */
@Component({
  selector: 'app-home-pilot-territory',
  templateUrl: './pilot-territory.html',
  styleUrl: './pilot-territory.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomePilotTerritory {
  protected readonly territory = PILOT_TERRITORY;
  protected readonly levels = GEOGRAPHIC_LEVELS;
}
