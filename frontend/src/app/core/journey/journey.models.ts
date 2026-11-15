import { LngLat } from '../../shared/geo/geodesy';

export interface SelectedDepartment {
  code: string;
  name: string;
}

export interface SelectedRegion {
  id: string;
  name: string;
}

export interface SelectedMunicipality {
  /** DANE DIVIPOLA code (verified against MGN 2025). */
  code: string;
  name: string;
  /** True only when membership in the pilot region is officially verified. */
  supported: boolean;
}

/** GeoJSON Polygon in WGS84 (EPSG:4326), single outer ring, closed. */
export interface PlotGeometry {
  type: 'Polygon';
  coordinates: [LngLat[]];
}

/**
 * A farmer-drawn plot. Approximate and user-defined: not a cadastral parcel,
 * not proof of ownership, and not analysed by anything yet.
 */
export interface PlotSelection {
  municipalityCode: string;
  geometry: PlotGeometry;
  areaM2: number;
  perimeterM: number;
  centroid: LngLat;
  vertexCount: number;
  /** Whether every vertex falls inside the (generalised) municipal boundary. */
  withinMunicipality: 'inside' | 'partial';
  drawnAt: string;
}
