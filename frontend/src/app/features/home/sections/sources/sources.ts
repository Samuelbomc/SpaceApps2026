import { ChangeDetectionStrategy, Component } from '@angular/core';
import { DATA_SOURCES } from '../../../../core/catalog/data-sources';
@Component({
  selector: 'app-home-sources',
  templateUrl: './sources.html',
  styleUrl: './sources.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomeSources {
  protected readonly sources = DATA_SOURCES;
}
