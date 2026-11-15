export type Coordinate = { latitude: number; longitude: number };
export type AreaSelection = {
  west: number;
  south: number;
  east: number;
  north: number;
  widthM: number;
  heightM: number;
  areaM2: number;
};
export type AreaSizeUnit = 'm2' | 'km2' | 'ha';
const radius = 6371008.8;
const radians = Math.PI / 180;

function coordinate(point: Coordinate) {
  if (
    !Number.isFinite(point.latitude) ||
    !Number.isFinite(point.longitude) ||
    Math.abs(point.latitude) > 80 ||
    Math.abs(point.longitude) > 180
  )
    throw new Error('Selecciona una ubicación válida, entre 80° S y 80° N.');
}
export function rectangleArea(first: Coordinate, second: Coordinate): AreaSelection {
  coordinate(first);
  coordinate(second);
  const west = Math.min(first.longitude, second.longitude),
    east = Math.max(first.longitude, second.longitude);
  const south = Math.min(first.latitude, second.latitude),
    north = Math.max(first.latitude, second.latitude);
  const latitude = (south + north) / 2;
  const widthM = radius * (east - west) * radians * Math.cos(latitude * radians);
  const heightM = radius * (north - south) * radians;
  if (widthM < 1 - 1e-6 || heightM < 1 - 1e-6)
    throw new Error('Separa las esquinas al menos un metro en cada dirección.');
  if (widthM > 10001 || heightM > 10001)
    throw new Error(
      'Esta prueba admite áreas de hasta 10 km de lado. Acerca el mapa para seleccionar tu parcela.',
    );
  const areaM2 =
    radius ** 2 * (east - west) * radians * (Math.sin(north * radians) - Math.sin(south * radians));
  return { west, south, east, north, widthM, heightM, areaM2 };
}
export function squareArea(center: Coordinate, sideM: number): AreaSelection {
  coordinate(center);
  if (!Number.isFinite(sideM) || sideM < 1 || sideM > 10000)
    throw new Error('El lado del cuadrado debe estar entre 1 m y 10 km.');
  const deltaLatitude = sideM / (radius * radians) / 2;
  const deltaLongitude = deltaLatitude / Math.cos(center.latitude * radians);
  return rectangleArea(
    { latitude: center.latitude - deltaLatitude, longitude: center.longitude - deltaLongitude },
    { latitude: center.latitude + deltaLatitude, longitude: center.longitude + deltaLongitude },
  );
}
export function squareSideMetres(value: number, unit: AreaSizeUnit): number {
  if (!Number.isFinite(value) || value <= 0) throw new Error('Escribe un tamaño mayor que cero.');
  if (!['m2', 'km2', 'ha'].includes(unit)) throw new Error('Unidad de área inválida.');
  const sideM = Math.sqrt(value * (unit === 'ha' ? 10000 : unit === 'km2' ? 1000000 : 1));
  if (!Number.isFinite(sideM) || sideM < 1 || sideM > 10000)
    throw new Error('El lado del cuadrado debe estar entre 1 m y 10 km.');
  return sideM;
}
export function convertSquareSize(value: number, from: AreaSizeUnit, to: AreaSizeUnit): number {
  squareSideMetres(value, from);
  if (!['m2', 'km2', 'ha'].includes(to)) throw new Error('Unidad de área inválida.');
  if (from === to) return value;
  const factors = { m2: 1, km2: 1000000, ha: 10000 };
  return (value * factors[from]) / factors[to];
}
export function areaGeoJSON(area: AreaSelection) {
  return {
    type: 'Feature',
    properties: { area_m2_approx: area.areaM2, crs: 'EPSG:4326', selection_only: true },
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [area.west, area.south],
          [area.east, area.south],
          [area.east, area.north],
          [area.west, area.north],
          [area.west, area.south],
        ],
      ],
    },
  };
}
