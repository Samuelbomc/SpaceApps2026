import { PILOT_TERRITORY, isSupportedMunicipality } from '../../../core/catalog/pilot-territory';
import { normalizeName } from './geo-utils';

export type GeoSearchKind = 'region' | 'municipality' | 'department';

/** pilot = can start the farm workflow; explore = explorable only; outside/reference = no coverage. */
export type GeoSearchStatus = 'pilot' | 'explore' | 'outside' | 'reference';

export interface GeoSearchEntry {
  kind: GeoSearchKind;
  /** DANE code for municipalities/departments, region id for regions. */
  id: string;
  name: string;
  context: string;
  status: GeoSearchStatus;
  /** Normalised name + aliases used for matching. */
  keys: string[];
}

export const STATUS_LABEL: Record<GeoSearchStatus, string> = {
  pilot: 'Región piloto · disponible',
  explore: 'Área de exploración',
  outside: 'Fuera de la región piloto',
  reference: 'Fuera de la cobertura',
};

/**
 * Name variants found in official sources for the same DANE code, so users find
 * a municipality whichever form they type (e.g. the Gobernación's "La Ceja del
 * Tambo" vs DANE's "La Ceja").
 */
const ALIASES: Record<string, string[]> = {
  '05376': ['La Ceja del Tambo'],
  '05674': ['San Vicente'],
  '05541': ['El Peñol'],
  '05607': ['El Retiro'],
  '05148': ['Carmen de Viboral'],
};

export function buildSearchIndex(
  departments: readonly { code: string; name: string }[],
  municipalities: readonly { code: string; name: string }[],
): GeoSearchEntry[] {
  const region = PILOT_TERRITORY.pilotRegion;
  const regionEntry: GeoSearchEntry = {
    kind: 'region',
    id: region.id,
    name: region.name,
    context: `Región de ${PILOT_TERRITORY.department} · ${region.municipalityCodes.length} municipios`,
    status: 'pilot',
    keys: [region.name, `Subregión ${region.subregion}`, region.subregion].map(normalizeName),
  };
  const munis = municipalities.map<GeoSearchEntry>((m) => {
    const pilot = isSupportedMunicipality(m.code);
    return {
      kind: 'municipality',
      id: m.code,
      name: m.name,
      context: pilot ? `Municipio · ${region.name}` : `Municipio · ${PILOT_TERRITORY.department}`,
      status: pilot ? 'pilot' : 'outside',
      keys: [m.name, ...(ALIASES[m.code] ?? [])].map(normalizeName),
    };
  });
  const deps = departments.map<GeoSearchEntry>((d) => ({
    kind: 'department',
    id: d.code,
    name: d.name,
    context: 'Departamento · Colombia',
    status: d.code === PILOT_TERRITORY.departmentCode ? 'explore' : 'reference',
    keys: [normalizeName(d.name)],
  }));
  return [regionEntry, ...munis, ...deps];
}

const KIND_ORDER: Record<GeoSearchKind, number> = { region: 0, municipality: 1, department: 2 };

/**
 * Accent- and case-insensitive search. Ranking: exact > starts with > a word
 * starts with > contains; ties broken by kind (region, municipality, department)
 * and then alphabetically.
 */
export function searchGeo(index: readonly GeoSearchEntry[], query: string, limit = 8): GeoSearchEntry[] {
  const q = normalizeName(query);
  if (q.length < 2) return [];
  const score = (key: string): number => {
    if (key === q) return 0;
    if (key.startsWith(q)) return 1;
    if (key.split(/[\s,-]+/).some((w) => w.startsWith(q))) return 2;
    return key.includes(q) ? 3 : Infinity;
  };
  return index
    .map((entry) => ({ entry, s: Math.min(...entry.keys.map(score)) }))
    .filter((r) => r.s !== Infinity)
    .sort(
      (a, b) =>
        a.s - b.s ||
        KIND_ORDER[a.entry.kind] - KIND_ORDER[b.entry.kind] ||
        a.entry.name.localeCompare(b.entry.name, 'es'),
    )
    .slice(0, limit)
    .map((r) => r.entry);
}
