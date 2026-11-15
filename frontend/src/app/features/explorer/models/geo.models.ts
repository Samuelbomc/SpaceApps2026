/**
 * Minimal GeoJSON types for the boundary files produced by the DANE MGN pipeline.
 * Kept local (instead of a transitive @types/geojson import) so the contract is explicit.
 */
export type Position = [number, number];
export type PolygonCoords = Position[][];

export type BoundaryGeometry =
  | { type: 'Polygon'; coordinates: PolygonCoords }
  | { type: 'MultiPolygon'; coordinates: PolygonCoords[] };

export interface BoundaryFeature<P> {
  type: 'Feature';
  /** Numeric DIVIPOLA code; enables MapLibre feature-state for hover/selection. */
  id: number;
  properties: P;
  geometry: BoundaryGeometry;
}

export interface BoundaryCollection<P> {
  type: 'FeatureCollection';
  features: BoundaryFeature<P>[];
}

interface LabelledArea {
  code: string;
  name: string;
  areaKm2: number | null;
  labelLon: number;
  labelLat: number;
}

export interface DepartmentProperties extends LabelledArea {
  isPilot: boolean;
}

export interface MunicipalityProperties extends LabelledArea {
  departmentCode: string;
  type: string | null;
}

/** [west, south, east, north] */
export type BBox = [number, number, number, number];

/** Subset of boundaries.metadata.json shown in the provenance panel. */
export interface BoundaryMetadata {
  source: {
    institution: string;
    product: string;
    service: string;
    officialLimitsNote: string;
    citation: string;
    termsUrl: string;
  };
  retrievedAt: string;
  processing: {
    outputCrs: string;
    simplification: {
      departmentsToleranceDeg: number;
      municipalitiesToleranceDeg: number;
      caveat: string;
    };
    script: string;
  };
  quality: {
    municipalities: { count: number; areaDeviationPct?: { max: number; mean: number } };
    departments: { count: number };
  };
}

/** Lightweight municipality record for lists, panels and selection. */
export interface MunicipalitySummary {
  id: number;
  code: string;
  name: string;
  areaKm2: number | null;
  bbox: BBox;
}
