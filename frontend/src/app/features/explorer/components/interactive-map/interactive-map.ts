import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  computed,
  effect,
  inject,
  model,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import type { Map as MapLibreMap, MapMouseEvent, PointLike } from 'maplibre-gl';
import { GeoBoundariesService } from '../../services/geo-boundaries.service';
import {
  BBox,
  BoundaryCollection,
  DepartmentProperties,
  MunicipalityProperties,
} from '../../models/geo.models';
import { displayName, featuresBBox, geometryBBox } from '../../utils/geo-utils';
import { PILOT_TERRITORY, isSupportedMunicipality } from '../../../../core/catalog/pilot-territory';
import {
  MAP_LOCALE,
  WebGLUnavailableError,
  loadMapLibre,
} from '../../../../shared/map/maplibre-loader';
import {
  ATTRIBUTION,
  LAYER,
  MAP_COLOR,
  MUNICIPAL_MIN_ZOOM,
  SOURCE,
  baseStyle,
  departmentLabelLayers,
  departmentLayers,
  municipalityLabelLayers,
  municipalityLayers,
  regionLabelLayer,
} from './map-style';

export type ViewLevel = 'globe' | 'country' | 'department' | 'region';
type LoadState = 'idle' | 'loading' | 'ready' | 'error';
type Tone = 'pilot' | 'explore' | 'outside' | 'reference';

interface HoverInfo {
  key: string;
  name: string;
  detail: string;
  tone: Tone;
}

interface FeatureRef {
  source: string;
  id: number;
}

/** Initial globe camera: the Americas facing the viewer. */
const GLOBE_VIEW = { center: [-72, 6] as [number, number], zoom: 1.6 };
/** San Andrés (88) is excluded from the "Colombia" camera so the mainland fills the view. */
const CAMERA_EXCLUDED_DEPARTMENTS = new Set(['88']);
const FIT_PADDING = 36;
const IMAGERY_TIMEOUT_MS = 12000;
/** Shorter on-map labels for very long official names (the official name stays in the data). */
const MAP_LABEL_OVERRIDES: Record<string, string> = { '88': 'San Andrés y Providencia' };

/**
 * Interactive globe → Colombia → Antioquia → Oriente Antioqueño map
 * (MapLibre GL JS, globe projection).
 *
 * - Hover/selection use MapLibre feature-state: only paint changes, no source rebuilds.
 * - Municipal boundaries are fetched lazily (municipal zoom, region focus or selection).
 * - MapLibre is imported lazily; the page stays usable if WebGL, the library or a
 *   remote imagery service fails (boundaries are bundled with the app).
 * - The selected municipality is a two-way `model` shared with the explorer page;
 *   departments and the pilot region are focused through public methods.
 */
@Component({
  selector: 'app-interactive-map',
  templateUrl: './interactive-map.html',
  styleUrl: './interactive-map.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InteractiveMap {
  /** DIVIPOLA code of the selected municipality (two-way bindable). */
  readonly selectedCode = model<string | null>(null);

  private readonly geo = inject(GeoBoundariesService);
  private readonly container = viewChild.required<ElementRef<HTMLDivElement>>('mapContainer');
  private readonly tooltip = viewChild.required<ElementRef<HTMLDivElement>>('tooltip');

  protected readonly state = signal<LoadState>('loading');
  protected readonly errorMessage = signal('');
  protected readonly municipalState = signal<LoadState>('idle');
  protected readonly imageryFailed = signal(false);
  protected readonly hover = signal<HoverInfo | null>(null);
  protected readonly level = signal<ViewLevel>('globe');
  protected readonly color = MAP_COLOR;
  protected readonly regionName = PILOT_TERRITORY.pilotRegion.name;
  protected readonly ready = computed(() => this.state() === 'ready');

  private map?: MapLibreMap;
  private destroyed = false;
  private imageryTimer?: ReturnType<typeof setTimeout>;
  private hovered: FeatureRef | null = null;
  private selected: FeatureRef | null = null;
  private selectedDepartment: FeatureRef | null = null;
  private colombiaBBox?: BBox;
  private regionBBox?: BBox;
  private readonly departmentIndex = new Map<string, { id: number; bbox: BBox }>();
  private readonly municipalIndex = new Map<string, { id: number; bbox: BBox }>();
  private municipalLoad?: Promise<void>;

  constructor() {
    afterNextRender(() => void this.init());

    // React to selection changes coming from outside (search, list, other pages).
    effect(() => {
      const code = this.selectedCode();
      untracked(() => void this.applySelection(code).catch(() => undefined));
    });

    inject(DestroyRef).onDestroy(() => {
      this.destroyed = true;
      clearTimeout(this.imageryTimer);
      this.map?.remove(); // also removes every listener registered with map.on()
      this.map = undefined;
    });
  }

  // ------------------------------------------------------------------ lifecycle
  protected async init(): Promise<void> {
    this.state.set('loading');
    this.errorMessage.set('');
    try {
      const [maplibre, departments] = await Promise.all([loadMapLibre(), this.geo.departments()]);
      if (this.destroyed) return;

      const map = new maplibre.Map({
        container: this.container().nativeElement,
        style: baseStyle(),
        center: GLOBE_VIEW.center,
        zoom: GLOBE_VIEW.zoom,
        minZoom: 0.8,
        maxZoom: 12,
        maxPitch: 60,
        locale: MAP_LOCALE,
        attributionControl: {
          compact: true,
          customAttribution: [ATTRIBUTION.boundaries, ATTRIBUTION.glyphs],
        },
      });
      this.map = map;
      map.addControl(new maplibre.NavigationControl({ visualizePitch: true }), 'top-right');
      map.addControl(new maplibre.ScaleControl({ unit: 'metric' }), 'bottom-right');
      map
        .getCanvas()
        .setAttribute(
          'aria-label',
          'Mapa interactivo de Colombia. Usa las flechas para desplazarte y las teclas más y menos para acercar o alejar.',
        );

      map.on('error', (event) => {
        // Imagery failures must never break the map: boundaries keep working.
        const id = (event as unknown as { sourceId?: string }).sourceId;
        if (id === SOURCE.imagery || id === SOURCE.sentinel) this.imageryFailed.set(true);
      });

      // 'style.load' (not 'load'): 'load' waits for every initial imagery tile, so slow
      // or unavailable imagery would keep the bundled DANE boundaries unusable.
      map.once('style.load', () => {
        this.addDepartments(departments);
        this.watchImagery(map);
        map.on('mousemove', (e) => this.onPointerMove(e));
        map.on('mouseout', () => this.clearHover());
        map.on('click', (e) => this.onClick(e));
        // A camera animation moves features under a still pointer: drop the stale tooltip.
        map.on('movestart', (e) => {
          if (!(e as { originalEvent?: Event }).originalEvent) this.clearHover();
        });
        map.on('moveend', () => this.onMoveEnd());
        this.state.set('ready');
        void this.applySelection(this.selectedCode(), false).catch(() => undefined);
      });
    } catch (err) {
      this.map?.remove();
      this.map = undefined;
      this.state.set('error');
      this.errorMessage.set(
        err instanceof WebGLUnavailableError
          ? 'Este navegador o dispositivo no permite mostrar el mapa 3D (WebGL). Puedes buscar y elegir tu municipio con el buscador o la lista.'
          : 'No fue posible cargar el mapa. Revisa tu conexión e inténtalo de nuevo.',
      );
    }
  }

  /** Warns when the global imagery has not produced any tile after a while. */
  private watchImagery(map: MapLibreMap): void {
    this.imageryTimer = setTimeout(() => {
      if (!this.destroyed && !map.isSourceLoaded(SOURCE.imagery)) this.imageryFailed.set(true);
    }, IMAGERY_TIMEOUT_MS);
    map.on('sourcedata', (e) => {
      if (e.sourceId === SOURCE.imagery && e.isSourceLoaded) {
        clearTimeout(this.imageryTimer);
        this.imageryFailed.set(false);
      }
    });
  }

  // ------------------------------------------------------------- data layers
  private addDepartments(fc: BoundaryCollection<DepartmentProperties>): void {
    const map = this.map!;
    const features = fc.features.map((f) => {
      this.departmentIndex.set(f.properties.code, { id: f.id, bbox: geometryBBox(f.geometry) });
      return {
        ...f,
        properties: {
          ...f.properties,
          labelName: MAP_LABEL_OVERRIDES[f.properties.code] ?? displayName(f.properties.name),
        },
      };
    });
    this.colombiaBBox = featuresBBox(
      features.filter((f) => !CAMERA_EXCLUDED_DEPARTMENTS.has(f.properties.code)),
    );

    map.addSource(SOURCE.departments, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features } as never,
    });
    map.addSource(SOURCE.departmentLabels, {
      type: 'geojson',
      data: labelPoints(features) as never,
    });
    departmentLayers().forEach((l) => map.addLayer(l));
    departmentLabelLayers().forEach((l) => map.addLayer(l));
  }

  /** Fetches municipal boundaries once; concurrent callers share the same promise. */
  private ensureMunicipalities(): Promise<void> {
    return (this.municipalLoad ??= this.loadMunicipalities().catch((err) => {
      this.municipalLoad = undefined;
      this.municipalState.set('error');
      throw err;
    }));
  }

  private async loadMunicipalities(): Promise<void> {
    this.municipalState.set('loading');
    const fc: BoundaryCollection<MunicipalityProperties> = await this.geo.municipalities();
    const map = this.map;
    if (!map || this.destroyed) return;

    const features = fc.features.map((f) => {
      this.municipalIndex.set(f.properties.code, { id: f.id, bbox: geometryBBox(f.geometry) });
      return {
        ...f,
        properties: {
          ...f.properties,
          labelName: displayName(f.properties.name),
          pilot: isSupportedMunicipality(f.properties.code),
        },
      };
    });
    const pilot = features.filter((f) => f.properties.pilot);
    this.regionBBox = pilot.length ? featuresBBox(pilot) : undefined;

    map.addSource(SOURCE.municipalities, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features } as never,
    });
    map.addSource(SOURCE.municipalityLabels, {
      type: 'geojson',
      data: labelPoints(features) as never,
    });
    // Insert below department labels so country-scale labels stay on top.
    municipalityLayers().forEach((l) => map.addLayer(l, LAYER.departmentLabel));
    municipalityLabelLayers().forEach((l) => map.addLayer(l));

    if (pilot.length) {
      map.addSource(SOURCE.regionLabel, {
        type: 'geojson',
        data: regionLabelPoint(pilot, this.regionName) as never,
      });
      map.addLayer(regionLabelLayer());
    }
    this.municipalState.set('ready');
  }

  // ------------------------------------------------------------- interaction
  private featureAt(point: PointLike) {
    const map = this.map!;
    const layers = [LAYER.municipalityFill, LAYER.departmentFill].filter((id) => map.getLayer(id));
    return map.queryRenderedFeatures(point, { layers })[0];
  }

  private onPointerMove(e: MapMouseEvent): void {
    const feature = this.featureAt(e.point);
    const canvas = this.map!.getCanvas();
    if (!feature || typeof feature.id !== 'number') {
      this.clearHover();
      return;
    }
    this.setHoverState({ source: feature.source, id: feature.id });
    const info = this.describe(feature.source, feature.properties as Record<string, unknown>);
    canvas.style.cursor = info.tone === 'reference' ? '' : 'pointer';
    if (this.hover()?.key !== info.key) this.hover.set(info);
    this.positionTooltip(e.point.x, e.point.y);
  }

  private onClick(e: MapMouseEvent): void {
    const feature = this.featureAt(e.point);
    if (!feature) {
      this.clearHover();
      return;
    }
    const props = feature.properties as Record<string, unknown>;
    if (feature.source === SOURCE.municipalities) {
      this.selectedCode.set(props['code'] as string);
    } else if (props['isPilot']) {
      this.flyToRegion();
    } else {
      // Other departments: show the tooltip (also serves touch devices without hover).
      this.hover.set(this.describe(feature.source, props));
      this.positionTooltip(e.point.x, e.point.y);
    }
  }

  private onMoveEnd(): void {
    const zoom = this.map!.getZoom();
    this.level.set(
      zoom < 3.2
        ? 'globe'
        : zoom < MUNICIPAL_MIN_ZOOM
          ? 'country'
          : zoom < 7.4
            ? 'department'
            : 'region',
    );
    if (zoom >= MUNICIPAL_MIN_ZOOM - 0.4) void this.ensureMunicipalities().catch(() => undefined);
  }

  private describe(source: string, p: Record<string, unknown>): HoverInfo {
    const name = p['labelName'] as string;
    if (source === SOURCE.municipalities) {
      return p['pilot']
        ? {
            key: `m${p['code']}`,
            name,
            detail: `${this.regionName} · puedes delimitar tu lote aquí`,
            tone: 'pilot',
          }
        : {
            key: `m${p['code']}`,
            name,
            detail: 'Fuera de la región piloto · solo exploración',
            tone: 'outside',
          };
    }
    return p['isPilot']
      ? {
          key: `d${p['code']}`,
          name,
          detail: `Contiene la región piloto ${this.regionName} · clic para acercar`,
          tone: 'explore',
        }
      : {
          key: `d${p['code']}`,
          name,
          detail: 'Referencia geográfica · fuera de la cobertura',
          tone: 'reference',
        };
  }

  private setHoverState(next: FeatureRef | null): void {
    const map = this.map;
    if (!map) return;
    if (this.hovered?.source === next?.source && this.hovered?.id === next?.id) return;
    if (this.hovered) map.setFeatureState(this.hovered, { hover: false });
    if (next) map.setFeatureState(next, { hover: true });
    this.hovered = next;
  }

  private clearHover(): void {
    this.setHoverState(null);
    if (this.map) this.map.getCanvas().style.cursor = '';
    if (this.hover()) this.hover.set(null);
  }

  /** Moves the tooltip with direct style writes: no change detection per mouse move. */
  private positionTooltip(x: number, y: number): void {
    this.tooltip().nativeElement.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
  }

  // --------------------------------------------------------------- selection
  private async applySelection(code: string | null, fly = true): Promise<void> {
    const map = this.map;
    if (!map || this.state() !== 'ready') return;
    if (this.selected) {
      map.setFeatureState(this.selected, { selected: false });
      this.selected = null;
    }
    if (!code) return;
    this.setSelectedDepartment(null);

    await this.ensureMunicipalities();
    const entry = this.municipalIndex.get(code);
    if (!entry || !this.map || this.selectedCode() !== code) return;
    this.selected = { source: SOURCE.municipalities, id: entry.id };
    this.map.setFeatureState(this.selected, { selected: true });
    if (fly) this.fit(entry.bbox, 10.5);
  }

  private setSelectedDepartment(next: FeatureRef | null): void {
    const map = this.map;
    if (!map) return;
    if (this.selectedDepartment) map.setFeatureState(this.selectedDepartment, { selected: false });
    if (next) map.setFeatureState(next, { selected: true });
    this.selectedDepartment = next;
  }

  /** Highlights and frames a department (from search). Clears any municipality selection. */
  focusDepartment(code: string): void {
    const entry = this.departmentIndex.get(code);
    if (!entry || !this.map) return;
    this.selectedCode.set(null);
    this.setSelectedDepartment({ source: SOURCE.departments, id: entry.id });
    this.fit(entry.bbox, 8);
  }

  /** Frames the pilot region (from search or the camera preset). */
  focusRegion(): void {
    this.flyToRegion();
  }

  // ----------------------------------------------------------------- cameras
  protected flyToGlobe(): void {
    this.setSelectedDepartment(null);
    this.map?.flyTo({
      center: GLOBE_VIEW.center,
      zoom: GLOBE_VIEW.zoom,
      bearing: 0,
      pitch: 0,
      duration: 1800,
    });
  }

  protected flyToColombia(): void {
    this.setSelectedDepartment(null);
    if (this.colombiaBBox) this.fit(this.colombiaBBox);
  }

  protected flyToDepartment(): void {
    const entry = this.departmentIndex.get(PILOT_TERRITORY.departmentCode);
    this.setSelectedDepartment(null);
    if (entry) this.fit(entry.bbox);
    void this.ensureMunicipalities().catch(() => undefined);
  }

  protected flyToRegion(): void {
    this.setSelectedDepartment(null);
    void this.ensureMunicipalities()
      .then(() => {
        if (this.regionBBox) this.fit(this.regionBBox, 10);
      })
      .catch(() => undefined);
  }

  protected retryMunicipalities(): void {
    void this.ensureMunicipalities().catch(() => undefined);
  }

  private fit(bbox: BBox, maxZoom = 9): void {
    this.map?.fitBounds(
      [
        [bbox[0], bbox[1]],
        [bbox[2], bbox[3]],
      ],
      { padding: FIT_PADDING, maxZoom, bearing: 0, pitch: 0, duration: 1800 },
    );
  }
}

// ---------------------------------------------------------------- helpers
function labelPoints(
  features: {
    id: number;
    properties: { labelLon: number; labelLat: number } & Record<string, unknown>;
  }[],
) {
  return {
    type: 'FeatureCollection',
    features: features.map((f) => ({
      type: 'Feature',
      id: f.id,
      properties: f.properties,
      geometry: { type: 'Point', coordinates: [f.properties.labelLon, f.properties.labelLat] },
    })),
  };
}

/** One label for the region, at the mean of its municipalities' label points. */
function regionLabelPoint(
  features: { properties: { labelLon: number; labelLat: number } }[],
  name: string,
) {
  const lon = features.reduce((s, f) => s + f.properties.labelLon, 0) / features.length;
  const lat = features.reduce((s, f) => s + f.properties.labelLat, 0) / features.length;
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { name },
        geometry: { type: 'Point', coordinates: [lon, lat] },
      },
    ],
  };
}
