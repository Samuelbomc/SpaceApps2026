import { Component, input } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import type { RotationCheck } from '@agrogeo/api-client';

@Component({
  selector: 'app-crop-condition',
  imports: [DecimalPipe],
  template: `
    @if (check(); as item) {
      @if (item.value !== null && item.value !== undefined) {
        <span
          >{{ item.value | number: '1.1-3' }}
          {{ item.unit === 'm3/m3' ? 'm³/m³' : item.unit }}</span
        >
      } @else {
        <span>Sin predicción</span>
      }
      <small>{{
        item.status === 'within_range'
          ? 'En rango'
          : item.status === 'outside_range'
            ? 'Fuera de rango'
            : 'Sin umbral definido'
      }}</small>
      @if (item.minimum !== null && item.minimum !== undefined) {
        <small
          >Rango: {{ item.minimum }}–{{ item.maximum }}
          {{ item.unit === 'm3/m3' ? 'm³/m³' : item.unit }}</small
        >
      }
    } @else {
      <small>Sin evaluación</small>
    }
  `,
  styles: `
    :host {
      display: grid;
      gap: 0.25rem;
    }
    small {
      color: var(--c-ink-muted);
    }
  `,
})
export class CropCondition {
  readonly check = input<RotationCheck | null>(null);
}
