import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { APP_IDENTITY } from '../../../../core/config/app-identity';
import { PILOT_TERRITORY } from '../../../../core/catalog/pilot-territory';

interface LayerShape {
  label: string;
  top: string;
  left: string;
  right: string;
  topFill: string;
  sideFill: string;
  stripes: { x1: number; y1: number; x2: number; y2: number }[];
}

// Isometric slab geometry (SVG user units).
const CX = 200;
const HALF_W = 130;
const HALF_H = 62;
const THICKNESS = 12;

/** Builds the polygon points for one isometric layer centred at y. */
function slab(y: number, label: string, topFill: string, sideFill: string, striped = false): LayerShape {
  const l = [CX - HALF_W, y];
  const t = [CX, y - HALF_H];
  const r = [CX + HALF_W, y];
  const b = [CX, y + HALF_H];
  const p = (pts: number[][]) => pts.map((pt) => pt.join(',')).join(' ');

  // Parallel lines across the bottom layer evoke cultivated plots.
  const stripes = striped
    ? [1, 2, 3, 4, 5].map((k) => {
        const f = k / 6;
        return {
          x1: l[0] + (t[0] - l[0]) * f,
          y1: l[1] + (t[1] - l[1]) * f,
          x2: b[0] + (r[0] - b[0]) * f,
          y2: b[1] + (r[1] - b[1]) * f,
        };
      })
    : [];

  return {
    label,
    top: p([l, t, r, b]),
    left: p([l, b, [b[0], b[1] + THICKNESS], [l[0], l[1] + THICKNESS]]),
    right: p([b, r, [r[0], r[1] + THICKNESS], [b[0], b[1] + THICKNESS]]),
    topFill,
    sideFill,
    stripes,
  };
}

/** Landing hero: positioning statement, entry points to both modules, conceptual diagram. */
@Component({
  selector: 'app-home-hero',
  imports: [RouterLink],
  templateUrl: './hero.html',
  styleUrl: './hero.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomeHero {
  protected readonly identity = APP_IDENTITY;
  protected readonly territory = PILOT_TERRITORY;

  /** Drawn bottom-to-top so upper layers overlap lower ones. */
  protected readonly layers: LayerShape[] = [
    slab(276, 'Finca y prioridades', '#3f7559', '#2a5a45', true),
    slab(221, 'Suelo y relieve', '#b57a52', '#874b26'),
    slab(166, 'Clima y agua', '#9fbfae', '#6f9a83'),
    slab(111, 'Observación satelital', '#3d7d99', '#2c6680'),
  ];

  /** Legend order matches the visual stack (top to bottom). */
  protected readonly legend = [...this.layers].reverse();
}
