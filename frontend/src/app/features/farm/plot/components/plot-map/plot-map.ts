import { FormsModule } from '@angular/forms';
import {
  squareArea,
  squareSideMetres,
  convertSquareSize,
  type AreaSizeUnit,
} from '@agrogeo/api-client/area';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import type { Map as MapLibreMap, GeoJSONSource } from 'maplibre-gl';
import {
  MAP_LOCALE,
  WebGLUnavailableError,
  loadMapLibre,
} from '../../../../../shared/map/maplibre-loader';
import { LOCAL_MAP_MAX_ZOOM, SENTINEL2_CLOUDLESS } from '../../../../../shared/map/imagery';
import { LngLat } from '../../../../../shared/geo/geodesy';
import { BBox, BoundaryGeometry } from '../../../../explorer/models/geo.models';
import { geometryBBox } from '../../../../explorer/utils/geo-utils';
import { PolygonEditor } from '../../drawing/polygon-editor';
import { MapDrawingLayer } from '../../drawing/map-drawing-layer';

export interface PlotMunicipality {
  code: string;
  name: string;
  geometry: BoundaryGeometry;
}

/** What the map reports to the page whenever the drawing changes. */
export interface PlotShape {
  /** Open ring (no repeated closing vertex), WGS84 [lon, lat]. */
  ring: LngLat[];
  closed: boolean;
}

const SRC = { imagery: SENTINEL2_CLOUDLESS.id, boundary: 'municipality-boundary' } as const;
const IMAGERY_TIMEOUT_MS = 12000;

/**
 * Satellite map of one municipality where the farmer draws their plot.
 *
 * Imagery: Sentinel-2 cloudless 2025 (EOX, 10 m). Beyond zoom 14 the image is only
 * magnified, which the UI states. The DANE municipal boundary is drawn for reference.
 * If imagery fails, the boundary and drawing tools keep working.
 */
@Component({
  selector: 'app-plot-map',
  imports: [FormsModule],
  templateUrl: './plot-map.html',
  styleUrl: './plot-map.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlotMap {
  readonly municipality = input.required<PlotMunicipality>();
  /** Previously drawn plot to restore for editing (open or closed ring). */
  readonly initialRing = input<readonly LngLat[] | null>(null);
  readonly shapeChange = output<PlotShape | null>();

  private readonly container = viewChild.required<ElementRef<HTMLDivElement>>('mapContainer');

  protected readonly editor = new PolygonEditor();
  protected readonly state = signal<'loading' | 'ready' | 'error'>('loading');
  protected readonly errorMessage = signal('');
  protected readonly imageryFailed = signal(false);
  protected readonly overzoomed = signal(false);
  protected readonly imagery = SENTINEL2_CLOUDLESS;
  protected readonly ready = computed(() => this.state() === 'ready');

  protected readonly instructions = computed(() => {
    switch (this.editor.mode()) {
      case 'idle':
        return 'Acerca el mapa hasta tu finca y pulsa «Dibujar lote».';
      case 'drawing':
        return this.editor.count() < 3
          ? `Marca cada esquina del lote con un clic o toque (${this.editor.count()} de al menos 3). También puedes centrar el mapa en la esquina y usar «Añadir punto en la mira».`
          : 'Sigue marcando esquinas. Para cerrar el contorno, haz clic en el primer punto, doble clic, o pulsa «Terminar contorno».';
      case 'editing':
        return 'Arrastra un punto para moverlo; arrastra un punto intermedio para añadir otro; toca un punto para seleccionarlo y eliminarlo.';
    }
  });

  protected squareValue = 1000;
  protected squareUnit: AreaSizeUnit = 'm2';
  protected readonly squareError = signal('');
  protected changeSquareUnit(unit: AreaSizeUnit) {
    try {
      this.squareValue = convertSquareSize(this.squareValue, this.squareUnit, unit);
      this.squareUnit = unit;
      this.squareError.set('');
    } catch (error) {
      this.squareError.set(error instanceof Error ? error.message : 'Superficie inválida.');
    }
  }
  protected placeSquare() {
    const center = this.map?.getCenter();
    if (!center) return;
    try {
      const area = squareArea(
        { latitude: center.lat, longitude: center.lng },
        squareSideMetres(this.squareValue, this.squareUnit),
      );
      const first = this.editor.mode() === 'idle';
      this.editor.load([
        [area.west, area.south],
        [area.east, area.south],
        [area.east, area.north],
        [area.west, area.north],
      ]);
      this.squareError.set('');
      if (first)
        this.map?.fitBounds(
          [
            [area.west, area.south],
            [area.east, area.north],
          ],
          { maxZoom: LOCAL_MAP_MAX_ZOOM, padding: 40, duration: 0 },
        );
    } catch (error) {
      this.squareError.set(error instanceof Error ? error.message : 'Superficie inválida.');
    }
  }

  private map?: MapLibreMap;
  private drawing?: MapDrawingLayer;
  private destroyed = false;
  private imageryTimer?: ReturnType<typeof setTimeout>;
  private currentCode?: string;

  constructor() {
    afterNextRender(() => void this.init());

    // Redraw + report whenever the drawing state changes.
    effect(() => {
      const ring = this.editor.vertices();
      const mode = this.editor.mode();
      this.editor.selected();
      untracked(() => {
        // Before the map is ready nothing has been drawn: don't report an empty shape
        // (it would discard a stored plot that is about to be restored).
        if (this.state() !== 'ready' && !ring.length) return;
        this.drawing?.render();
        this.drawing?.syncInteractions();
        this.shapeChange.emit(
          mode === 'idle' && !ring.length ? null : { ring, closed: mode === 'editing' },
        );
      });
    });

    // A different municipality: move the map, update the boundary, discard the drawing.
    effect(() => {
      const m = this.municipality();
      untracked(() => {
        if (!this.map || this.state() !== 'ready' || m.code === this.currentCode) return;
        this.currentCode = m.code;
        (this.map.getSource(SRC.boundary) as GeoJSONSource | undefined)?.setData(
          boundaryFeature(m) as never,
        );
        this.editor.clear();
        this.fit(geometryBBox(m.geometry));
      });
    });

    inject(DestroyRef).onDestroy(() => {
      this.destroyed = true;
      clearTimeout(this.imageryTimer);
      this.drawing?.detach();
      this.map?.remove();
      this.map = undefined;
    });
  }

  protected async init(): Promise<void> {
    this.state.set('loading');
    try {
      const maplibre = await loadMapLibre();
      if (this.destroyed) return;
      const m = this.municipality();
      this.currentCode = m.code;
      const bbox = geometryBBox(m.geometry);

      const map = new maplibre.Map({
        container: this.container().nativeElement,
        bounds: [
          [bbox[0], bbox[1]],
          [bbox[2], bbox[3]],
        ],
        fitBoundsOptions: { padding: 24 },
        maxZoom: LOCAL_MAP_MAX_ZOOM,
        minZoom: 7,
        locale: MAP_LOCALE,
        attributionControl: {
          compact: true,
          customAttribution: [
            'Límite municipal: <a href="https://geoportal.dane.gov.co/" target="_blank" rel="noopener">DANE – MGN 2025</a>',
          ],
        },
        style: {
          version: 8,
          sources: {
            [SRC.imagery]: {
              type: 'raster',
              tiles: SENTINEL2_CLOUDLESS.tiles,
              tileSize: SENTINEL2_CLOUDLESS.tileSize,
              maxzoom: SENTINEL2_CLOUDLESS.maxzoom,
              attribution: SENTINEL2_CLOUDLESS.attribution,
            },
            [SRC.boundary]: { type: 'geojson', data: boundaryFeature(m) as never },
          },
          layers: [
            { id: 'background', type: 'background', paint: { 'background-color': '#1e3a2f' } },
            {
              id: 'imagery',
              type: 'raster',
              source: SRC.imagery,
              paint: { 'raster-fade-duration': 150 },
            },
            {
              id: 'boundary-casing',
              type: 'line',
              source: SRC.boundary,
              paint: { 'line-color': '#0b1d17', 'line-width': 6, 'line-opacity': 0.9 },
            },
            {
              id: 'boundary',
              type: 'line',
              source: SRC.boundary,
              paint: { 'line-color': '#ffffff', 'line-width': 3, 'line-dasharray': [3, 2] },
            },
          ],
        },
      });
      this.map = map;
      map.addControl(new maplibre.NavigationControl({ showCompass: true }), 'top-right');
      map.addControl(new maplibre.ScaleControl({ unit: 'metric' }), 'bottom-right');
      map
        .getCanvas()
        .setAttribute(
          'aria-label',
          `Imagen satelital de ${m.name}. Usa las flechas para desplazarte y más o menos para acercar.`,
        );

      map.on('error', (e) => {
        if ((e as unknown as { sourceId?: string }).sourceId === SRC.imagery)
          this.imageryFailed.set(true);
      });
      map.on('zoomend', () =>
        this.overzoomed.set(map.getZoom() > SENTINEL2_CLOUDLESS.maxzoom + 0.5),
      );

      // style.load: drawing works without waiting for imagery tiles.
      map.once('style.load', () => {
        this.drawing = new MapDrawingLayer(map, this.editor);
        this.drawing.attach();
        const ring = this.initialRing();
        if (ring && ring.length >= 3) {
          this.editor.load(ring);
          const xs = ring.map((p) => p[0]);
          const ys = ring.map((p) => p[1]);
          this.fit([Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)], 16);
        }
        this.watchImagery(map);
        this.state.set('ready');
      });
    } catch (err) {
      this.map?.remove();
      this.map = undefined;
      this.state.set('error');
      this.errorMessage.set(
        err instanceof WebGLUnavailableError
          ? 'Este navegador o dispositivo no permite mostrar el mapa (WebGL), así que no es posible dibujar el lote aquí.'
          : 'No fue posible cargar el mapa. Revisa tu conexión e inténtalo de nuevo.',
      );
    }
  }

  private watchImagery(map: MapLibreMap): void {
    this.imageryTimer = setTimeout(() => {
      if (!this.destroyed && !map.isSourceLoaded(SRC.imagery)) this.imageryFailed.set(true);
    }, IMAGERY_TIMEOUT_MS);
    map.on('sourcedata', (e) => {
      if (e.sourceId === SRC.imagery && e.isSourceLoaded && e.tile) {
        clearTimeout(this.imageryTimer);
        this.imageryFailed.set(false);
      }
    });
  }

  // ------------------------------------------------------------ toolbar actions
  protected startDrawing(): void {
    this.editor.start();
  }

  /** Keyboard/touch alternative: adds a vertex at the crosshair (map centre). */
  protected addAtCenter(): void {
    const c = this.map?.getCenter();
    if (c) this.editor.add([Math.round(c.lng * 1e7) / 1e7, Math.round(c.lat * 1e7) / 1e7]);
  }

  protected undo(): void {
    this.editor.undo();
  }

  protected finish(): void {
    this.editor.finish();
  }

  protected removeSelected(): void {
    this.editor.removeSelected();
  }

  protected deletePlot(): void {
    this.editor.clear();
  }

  protected redraw(): void {
    this.editor.start();
  }

  private fit(bbox: BBox, maxZoom = 15): void {
    this.map?.fitBounds(
      [
        [bbox[0], bbox[1]],
        [bbox[2], bbox[3]],
      ],
      { padding: 40, maxZoom, duration: 900 },
    );
  }
}

function boundaryFeature(m: PlotMunicipality) {
  return { type: 'Feature', properties: { code: m.code, name: m.name }, geometry: m.geometry };
}
