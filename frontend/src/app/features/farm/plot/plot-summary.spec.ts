import { summarizePlot, toPlotSelection } from './plot-summary';
import { BoundaryGeometry } from '../../explorer/models/geo.models';

const municipality = {
  name: 'La Unión',
  geometry: {
    type: 'Polygon',
    coordinates: [
      [
        [-75.45, 5.9],
        [-75.3, 5.9],
        [-75.3, 6.05],
        [-75.45, 6.05],
        [-75.45, 5.9],
      ],
    ],
  } as BoundaryGeometry,
};

describe('summarizePlot', () => {
  it('accepts a plot inside the municipality and reports its geodesic area', () => {
    const s = summarizePlot(
      [
        [-75.36, 5.97],
        [-75.358, 5.97],
        [-75.358, 5.972],
        [-75.36, 5.972],
      ],
      municipality,
    );
    expect(s.valid).toBe(true);
    expect(s.within).toBe('inside');
    expect(s.vertexCount).toBe(4);
    // ≈ 221 m × 221 m ≈ 4.9 ha
    expect(s.areaM2 / 10_000).toBeGreaterThan(4.7);
    expect(s.areaM2 / 10_000).toBeLessThan(5.1);

    const sel = toPlotSelection(s, '05400');
    expect(sel.geometry.coordinates[0].length).toBe(5); // closed GeoJSON ring
    expect(sel.geometry.coordinates[0][0]).toEqual(sel.geometry.coordinates[0][4]);
  });

  it('rejects plots outside the municipality and self-intersecting outlines', () => {
    const outside = summarizePlot(
      [
        [-75.0, 5.97],
        [-74.99, 5.97],
        [-74.99, 5.98],
      ],
      municipality,
    );
    expect(outside.within).toBe('outside');
    expect(outside.valid).toBe(false);

    const bowtie = summarizePlot(
      [
        [-75.36, 5.97],
        [-75.35, 5.98],
        [-75.35, 5.97],
        [-75.36, 5.98],
      ],
      municipality,
    );
    expect(bowtie.valid).toBe(false);
    expect(bowtie.issues.some((i) => i.level === 'error')).toBe(true);
  });

  it('warns (without blocking) when part of the plot crosses the boundary or it is tiny', () => {
    const partial = summarizePlot(
      [
        [-75.31, 5.97],
        [-75.29, 5.97],
        [-75.29, 5.98],
        [-75.31, 5.98],
      ],
      municipality,
    );
    expect(partial.within).toBe('partial');
    expect(partial.valid).toBe(true);
    expect(partial.issues[0].level).toBe('warning');

    const tiny = summarizePlot(
      [
        [-75.36, 5.97],
        [-75.3602, 5.97],
        [-75.3602, 5.9702],
      ],
      municipality,
    );
    expect(tiny.valid).toBe(true);
    expect(tiny.issues.some((i) => i.message.includes('10 m'))).toBe(true);
  });
});
