import { ChangeDetectionStrategy, Component } from '@angular/core';
import { ModulePlaceholder } from '../../shared/ui/module-placeholder/module-placeholder';

/** Module A — Public agricultural and environmental data portal (next increment). */
@Component({
  selector: 'app-data-portal',
  imports: [ModulePlaceholder],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-module-placeholder
      eyebrow="Módulo A · Público"
      title="Portal de datos agroambientales"
      description="Explora información ambiental y agrícola del territorio piloto en Antioquia, con su origen, resolución y limitaciones siempre visibles."
      [capabilities]="capabilities"
    />
  `,
})
export class DataPortal {
  protected readonly capabilities = [
    'Selección de municipios del piloto en Antioquia.',
    'Variables ambientales: lluvia, temperatura, humedad superficial del suelo, vegetación.',
    'Series históricas y comparaciones entre periodos.',
    'Contexto agrícola municipal de fuentes oficiales.',
    'Panel de procedencia, metadatos y limitaciones de cada dato.',
    'Descargas cuando la fuente lo permita.',
  ] as const;
}
