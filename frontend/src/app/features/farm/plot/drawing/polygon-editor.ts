import { computed, signal } from '@angular/core';
import { LngLat, openRing, selfIntersects } from '../../../../shared/geo/geodesy';

export type DrawMode = 'idle' | 'drawing' | 'editing';

export const MIN_VERTICES = 3;

/**
 * Pure state of a single polygon being drawn and edited (no map involved,
 * so it can be unit-tested and reused with any renderer).
 *
 * idle ──start()──▶ drawing ──finish()──▶ editing
 *   ▲                  │ add / undo           │ move / insert / remove / select
 *   └──── clear() ─────┴──────────────────────┘
 */
export class PolygonEditor {
  private readonly verticesState = signal<LngLat[]>([]);
  private readonly modeState = signal<DrawMode>('idle');
  private readonly selectedState = signal<number | null>(null);

  readonly vertices = this.verticesState.asReadonly();
  readonly mode = this.modeState.asReadonly();
  readonly selected = this.selectedState.asReadonly();

  readonly count = computed(() => this.vertices().length);
  readonly canFinish = computed(() => this.mode() === 'drawing' && this.count() >= MIN_VERTICES);
  readonly canRemoveSelected = computed(
    () => this.mode() === 'editing' && this.selected() !== null && this.count() > MIN_VERTICES,
  );
  readonly closed = computed(() => this.mode() === 'editing');
  readonly selfIntersecting = computed(() => this.closed() && selfIntersects(this.vertices()));

  start(): void {
    this.verticesState.set([]);
    this.selectedState.set(null);
    this.modeState.set('drawing');
  }

  add(point: LngLat): void {
    if (this.mode() !== 'drawing') return;
    this.verticesState.update((v) => [...v, point]);
  }

  undo(): void {
    if (this.mode() !== 'drawing') return;
    this.verticesState.update((v) => v.slice(0, -1));
  }

  /** Closes the outline. Returns false if there are not enough vertices. */
  finish(): boolean {
    if (!this.canFinish()) return false;
    this.modeState.set('editing');
    return true;
  }

  move(index: number, point: LngLat): void {
    if (this.mode() !== 'editing' || !this.has(index)) return;
    this.verticesState.update((v) => v.map((p, i) => (i === index ? point : p)));
  }

  /** Inserts a vertex after `index` (i.e. on the edge index → index+1). Returns the new index. */
  insertAfter(index: number, point: LngLat): number {
    if (this.mode() !== 'editing' || !this.has(index)) return -1;
    this.verticesState.update((v) => [...v.slice(0, index + 1), point, ...v.slice(index + 1)]);
    this.selectedState.set(index + 1);
    return index + 1;
  }

  remove(index: number): void {
    if (this.mode() !== 'editing' || !this.has(index) || this.count() <= MIN_VERTICES) return;
    this.verticesState.update((v) => v.filter((_, i) => i !== index));
    this.selectedState.set(null);
  }

  removeSelected(): void {
    const s = this.selected();
    if (s !== null) this.remove(s);
  }

  select(index: number | null): void {
    this.selectedState.set(index !== null && this.has(index) ? index : null);
  }

  clear(): void {
    this.verticesState.set([]);
    this.selectedState.set(null);
    this.modeState.set('idle');
  }

  /** Loads an existing closed polygon for editing. */
  load(ring: readonly LngLat[]): void {
    const v = openRing(ring);
    if (v.length < MIN_VERTICES) return this.clear();
    this.verticesState.set(v);
    this.selectedState.set(null);
    this.modeState.set('editing');
  }

  private has(index: number): boolean {
    return index >= 0 && index < this.count();
  }
}
