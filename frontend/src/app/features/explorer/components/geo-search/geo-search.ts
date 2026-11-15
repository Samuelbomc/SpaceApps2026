import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';
import { GeoSearchEntry, STATUS_LABEL, searchGeo } from '../../utils/geo-search';

/**
 * Geographic search (departments, the pilot region, Antioquia's municipalities).
 * WAI-ARIA 1.2 combobox: type to filter, ↑/↓ to move, Enter to choose, Esc to close.
 * Results show their coverage status as text, so nothing relies on colour alone.
 */
@Component({
  selector: 'app-geo-search',
  templateUrl: './geo-search.html',
  styleUrl: './geo-search.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GeoSearch {
  readonly index = input.required<readonly GeoSearchEntry[]>();
  readonly picked = output<GeoSearchEntry>();

  protected readonly query = signal('');
  protected readonly open = signal(false);
  protected readonly active = signal(0);
  protected readonly statusLabel = STATUS_LABEL;
  protected readonly kindLabel = {
    region: 'Región',
    municipality: 'Municipio',
    department: 'Departamento',
  };

  protected readonly results = computed(() => searchGeo(this.index(), this.query()));
  protected readonly showList = computed(() => this.open() && this.query().trim().length >= 2);
  protected readonly activeId = computed(() =>
    this.showList() && this.results().length ? `geo-opt-${this.active()}` : null,
  );

  protected onInput(value: string): void {
    this.query.set(value);
    this.active.set(0);
    this.open.set(true);
  }

  protected onKeydown(event: KeyboardEvent): void {
    const n = this.results().length;
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        this.open.set(true);
        if (n) this.active.set((this.active() + 1) % n);
        break;
      case 'ArrowUp':
        event.preventDefault();
        if (n) this.active.set((this.active() - 1 + n) % n);
        break;
      case 'Enter':
        if (this.showList() && n) {
          event.preventDefault();
          this.choose(this.results()[this.active()]);
        }
        break;
      case 'Escape':
        if (this.open()) {
          event.preventDefault();
          this.open.set(false);
        } else {
          this.query.set('');
        }
        break;
    }
  }

  protected choose(entry: GeoSearchEntry): void {
    this.query.set(entry.name);
    this.open.set(false);
    this.picked.emit(entry);
  }

  /** Delay closing so a click on an option registers before blur hides the list. */
  protected onBlur(): void {
    setTimeout(() => this.open.set(false), 150);
  }

  protected clear(input: HTMLInputElement): void {
    this.query.set('');
    this.open.set(false);
    input.focus();
  }
}
