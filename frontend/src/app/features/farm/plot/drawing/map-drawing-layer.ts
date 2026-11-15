import type { GeoJSONSource, Map as MapLibreMap, MapMouseEvent, MapTouchEvent, PointLike } from 'maplibre-gl';
import { LngLat, closeRing } from '../../../../shared/geo/geodesy';
import { PolygonEditor } from './polygon-editor';

const SOURCE = 'plot-drawing';
const L = {
  fill: 'plot-fill',
  line: 'plot-line',
  rubber: 'plot-rubber',
  mid: 'plot-midpoints',
  vertex: 'plot-vertices',
} as const;

const COLOR = { stroke: '#ffcf6b', fill: '#ffcf6b', vertex: '#ffffff', selected: '#ff8a3d' };
/** Clicking within this many pixels of the first vertex closes the outline. */
const CLOSE_TOLERANCE_PX = 12;

/**
 * Binds a PolygonEditor to a MapLibre map: renders its state as one GeoJSON
 * source (updated with setData — no layer rebuilds) and turns mouse/touch
 * gestures into editor commands.
 *
 * Gestures
 *  drawing: click/tap = add point · click first point or double-click = close
 *  editing: drag a point = move · drag a midpoint = insert · click a point = select
 */
export class MapDrawingLayer {
  private cursor: LngLat | null = null;
  private dragging: number | null = null;
  private readonly offs: (() => void)[] = [];

  constructor(
    private readonly map: MapLibreMap,
    private readonly editor: PolygonEditor,
  ) {}

  attach(): void {
    const map = this.map;
    map.addSource(SOURCE, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } as never });
    map.addLayer({ id: L.fill, type: 'fill', source: SOURCE, filter: ['==', ['get', 'role'], 'polygon'], paint: { 'fill-color': COLOR.fill, 'fill-opacity': 0.25 } });
    map.addLayer({ id: L.line, type: 'line', source: SOURCE, filter: ['in', ['get', 'role'], ['literal', ['polygon', 'path']]], paint: { 'line-color': COLOR.stroke, 'line-width': 3 } });
    map.addLayer({ id: L.rubber, type: 'line', source: SOURCE, filter: ['==', ['get', 'role'], 'rubber'], paint: { 'line-color': COLOR.stroke, 'line-width': 2, 'line-dasharray': [2, 2] } });
    map.addLayer({ id: L.mid, type: 'circle', source: SOURCE, filter: ['==', ['get', 'role'], 'mid'], paint: { 'circle-radius': 5, 'circle-color': COLOR.stroke, 'circle-opacity': 0.85, 'circle-stroke-color': '#1b231f', 'circle-stroke-width': 1 } });
    map.addLayer({
      id: L.vertex,
      type: 'circle',
      source: SOURCE,
      filter: ['==', ['get', 'role'], 'vertex'],
      paint: {
        'circle-radius': ['case', ['get', 'selected'], 9, ['get', 'first'], 8, 7],
        'circle-color': ['case', ['get', 'selected'], COLOR.selected, COLOR.vertex],
        'circle-stroke-color': '#1b231f',
        'circle-stroke-width': 2,
      },
    });

    this.on('click', (e) => this.onClick(e as MapMouseEvent));
    this.on('dblclick', (e) => this.onDblClick(e as MapMouseEvent));
    this.on('mousemove', (e) => this.onMove(e as MapMouseEvent));
    this.on('mousedown', (e) => this.onPress(e as MapMouseEvent));
    this.on('touchstart', (e) => this.onPress(e as MapTouchEvent));
    this.on('mouseup', () => this.endDrag());
    this.on('touchend', () => this.endDrag());
    this.render();
  }

  /** Re-draws the editor state (call whenever it changes). */
  render(): void {
    const src = this.map.getSource(SOURCE) as GeoJSONSource | undefined;
    if (!src) return;
    const v = this.editor.vertices();
    const mode = this.editor.mode();
    const selected = this.editor.selected();
    const features: DrawFeature[] = [];

    if (mode === 'editing' && v.length >= 3) {
      features.push(feature('polygon', { type: 'Polygon', coordinates: [closeRing(v)] }));
      v.forEach((p, i) => {
        const q = v[(i + 1) % v.length];
        features.push(feature('mid', { type: 'Point', coordinates: [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2] }, { edge: i }));
      });
    } else if (mode === 'drawing' && v.length >= 2) {
      features.push(feature('path', { type: 'LineString', coordinates: v }));
    }
    if (mode === 'drawing' && v.length && this.cursor) {
      features.push(feature('rubber', { type: 'LineString', coordinates: [v[v.length - 1], this.cursor] }));
    }
    v.forEach((p, i) =>
      features.push(feature('vertex', { type: 'Point', coordinates: p }, { index: i, selected: i === selected, first: mode === 'drawing' && i === 0 })),
    );
    src.setData({ type: 'FeatureCollection', features } as never);
  }

  /** Disables map double-click zoom while drawing (double-click closes the outline). */
  syncInteractions(): void {
    if (this.editor.mode() === 'drawing') this.map.doubleClickZoom.disable();
    else this.map.doubleClickZoom.enable();
    this.map.getCanvas().style.cursor = this.editor.mode() === 'drawing' ? 'crosshair' : '';
    if (this.editor.mode() !== 'drawing') this.cursor = null;
  }

  detach(): void {
    this.offs.splice(0).forEach((off) => off());
  }

  // ------------------------------------------------------------------ events
  private onClick(e: MapMouseEvent): void {
    const mode = this.editor.mode();
    if (mode === 'drawing') {
      if (this.isNearFirstVertex(e.point) && this.editor.finish()) return;
      this.editor.add(toLngLat(e.lngLat));
    } else if (mode === 'editing') {
      const vertex = this.hit(e.point, L.vertex);
      this.editor.select(vertex ? (vertex.properties['index'] as number) : null);
    }
  }

  private onDblClick(e: MapMouseEvent): void {
    if (this.editor.mode() !== 'drawing') return;
    e.preventDefault();
    // The two clicks of a double-click already added a duplicate final point.
    this.editor.undo();
    this.editor.finish();
  }

  private onMove(e: MapMouseEvent): void {
    const mode = this.editor.mode();
    if (this.dragging !== null) {
      this.editor.move(this.dragging, toLngLat(e.lngLat));
      return;
    }
    if (mode === 'drawing') {
      this.cursor = toLngLat(e.lngLat);
      this.render();
    } else if (mode === 'editing') {
      const over = this.hit(e.point, L.vertex) ?? this.hit(e.point, L.mid);
      this.map.getCanvas().style.cursor = over ? 'move' : '';
    }
  }

  /** Mouse down / touch start: begins dragging a vertex, or a midpoint (which inserts one). */
  private onPress(e: MapMouseEvent | MapTouchEvent): void {
    if (this.editor.mode() !== 'editing') return;
    const vertex = this.hit(e.point, L.vertex);
    const mid = vertex ? null : this.hit(e.point, L.mid);
    if (!vertex && !mid) return;
    e.preventDefault(); // stops the map from panning
    this.map.dragPan.disable();
    this.dragging = vertex
      ? (vertex.properties['index'] as number)
      : this.editor.insertAfter(mid!.properties['edge'] as number, toLngLat(e.lngLat));
    if (vertex) this.editor.select(this.dragging);
    if (e.type === 'touchstart') {
      const move = (ev: MapTouchEvent) => {
        if (this.dragging !== null) this.editor.move(this.dragging, toLngLat(ev.lngLat));
      };
      this.map.on('touchmove', move);
      this.map.once('touchend', () => this.map.off('touchmove', move));
    }
  }

  private endDrag(): void {
    if (this.dragging === null) return;
    this.dragging = null;
    this.map.dragPan.enable();
  }

  // ----------------------------------------------------------------- helpers
  private hit(point: PointLike, layer: string) {
    if (!this.map.getLayer(layer)) return undefined;
    const [x, y] = Array.isArray(point) ? point : [point.x, point.y];
    const pad = 6;
    return this.map.queryRenderedFeatures([[x - pad, y - pad], [x + pad, y + pad]], { layers: [layer] })[0];
  }

  private isNearFirstVertex(point: { x: number; y: number }): boolean {
    const v = this.editor.vertices();
    if (v.length < 3) return false;
    const p = this.map.project(v[0]);
    return Math.hypot(p.x - point.x, p.y - point.y) <= CLOSE_TOLERANCE_PX;
  }

  private on(type: string, handler: (e: unknown) => void): void {
    this.map.on(type as never, handler as never);
    this.offs.push(() => this.map.off(type as never, handler as never));
  }
}

function toLngLat(ll: { lng: number; lat: number }): LngLat {
  return [round(ll.lng), round(ll.lat)];
}

/** 7 decimals ≈ 1 cm: more than enough, keeps the GeoJSON compact. */
function round(v: number): number {
  return Math.round(v * 1e7) / 1e7;
}

/** Minimal GeoJSON shapes used by the drawing source. */
type DrawGeometry =
  | { type: 'Point'; coordinates: LngLat }
  | { type: 'LineString'; coordinates: LngLat[] }
  | { type: 'Polygon'; coordinates: LngLat[][] };

interface DrawFeature {
  type: 'Feature';
  properties: Record<string, unknown>;
  geometry: DrawGeometry;
}

function feature(role: string, geometry: DrawGeometry, props: Record<string, unknown> = {}): DrawFeature {
  return { type: 'Feature', properties: { role, ...props }, geometry };
}
