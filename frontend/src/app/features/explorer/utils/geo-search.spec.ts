import { buildSearchIndex, searchGeo } from './geo-search';

const deps = [
  { code: '05', name: 'Antioquia' },
  { code: '17', name: 'Caldas' },
];
const munis = [
  { code: '05400', name: 'La Unión' },
  { code: '05376', name: 'La Ceja' },
  { code: '05001', name: 'Medellín' },
  { code: '05129', name: 'Caldas' }, // Antioquia municipality named like a department
];

describe('geo search', () => {
  const index = buildSearchIndex(deps, munis);

  it('ignores accents and case', () => {
    expect(searchGeo(index, 'union')[0].name).toBe('La Unión');
    expect(searchGeo(index, 'MEDELLIN')[0].name).toBe('Medellín');
  });

  it('finds official name variants through aliases', () => {
    expect(searchGeo(index, 'La Ceja del Tambo')[0].id).toBe('05376');
  });

  it('finds the pilot region and labels coverage honestly', () => {
    const region = searchGeo(index, 'oriente')[0];
    expect(region.kind).toBe('region');
    expect(region.status).toBe('pilot');
    expect(searchGeo(index, 'la union')[0].status).toBe('pilot');
    expect(searchGeo(index, 'medellin')[0].status).toBe('outside');
    expect(searchGeo(index, 'antioquia').find((e) => e.kind === 'department')?.status).toBe('explore');
  });

  it('distinguishes a municipality from a department with the same name', () => {
    const results = searchGeo(index, 'caldas');
    expect(results.map((r) => r.kind)).toEqual(['municipality', 'department']);
    expect(results[1].status).toBe('reference');
  });

  it('needs at least two characters', () => {
    expect(searchGeo(index, 'l')).toEqual([]);
  });
});
