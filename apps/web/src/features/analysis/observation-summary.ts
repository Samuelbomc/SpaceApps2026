import type { ObservationPage } from '../../lib/api';

export type Observation = ObservationPage['items'][number];
export type ObservationSeries = { key: string; source: string; variable: string; unit: string; resolution: string; rows: Observation[] };

export function isUsable(row: Observation): row is Observation & { value: number } {
  return row.value !== null && Number.isFinite(row.value) && row.quality === 'provider_value_unvalidated';
}

export function summarizeObservations(rows: Observation[]) {
  const groups = new Map<string, ObservationSeries>();
  const quality: Record<string, number> = {};
  const dates = new Set<string>();
  for (const row of rows) {
    // No mezclar fuentes, unidades ni resoluciones en una serie.
    const key = JSON.stringify([row.source, row.variable, row.unit, row.resolution]);
    if (!groups.has(key)) groups.set(key, { key, source: row.source, variable: row.variable, unit: row.unit, resolution: row.resolution, rows: [] });
    groups.get(key)!.rows.push(row);
    dates.add(row.date);
    quality[row.quality] = (quality[row.quality] || 0) + 1;
  }
  const series = [...groups.values()].map(group => ({ ...group, rows: [...group.rows].sort((a, b) => a.date.localeCompare(b.date)) }));
  const orderedDates = [...dates].sort();
  return { series, quality, usable: rows.filter(isUsable).length,
    missing: rows.filter(row => row.value === null).length, days: dates.size,
    firstDate: orderedDates[0] ?? null, lastDate: orderedDates.at(-1) ?? null };
}

export function latestFor(rows: Observation[], variables: string[]) {
  for (const variable of variables) {
    const candidates = rows.filter(row => row.variable === variable && isUsable(row));
    candidates.sort((a, b) => b.date.localeCompare(a.date));
    if (candidates.length) return candidates[0];
  }
  return null;
}

export function dailySegments(rows: Observation[]) {
  const segments: (Observation & { value: number })[][] = [];
  let segment: (Observation & { value: number })[] = [];
  for (const row of [...rows].sort((a, b) => a.date.localeCompare(b.date))) {
    const previous = segment.at(-1);
    const gap = previous && (Date.parse(row.date) - Date.parse(previous.date)) > 86400000;
    if (!isUsable(row) || gap) {
      if (segment.length) segments.push(segment);
      segment = [];
    }
    if (isUsable(row)) segment.push(row);
  }
  if (segment.length) segments.push(segment);
  return segments;
}
