import { ChangeDetectionStrategy, Component } from '@angular/core';
import { ModulePlaceholder } from '../../shared/ui/module-placeholder/module-placeholder';

/** Module B — Farmer decision-support workspace (upcoming increment). */
@Component({
  selector: 'app-farmer-workspace',
  imports: [ModulePlaceholder],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-module-placeholder
      eyebrow="Módulo B · Agricultores"
      title="Espacio del agricultor"
      description="Describe tu finca, tu historial de cultivos y tus prioridades para comparar estrategias de rotación con sus beneficios, riesgos y evidencia."
      [capabilities]="capabilities"
    />
  `,
})
export class FarmerWorkspace {
  protected readonly capabilities = [
    'Perfil de la finca: ubicación, suelo, agua y manejo.',
    'Historial de cultivos y rotaciones anteriores.',
    'Prioridades y restricciones: agua, suelo, ingresos, mano de obra.',
    'Comparación de al menos tres estrategias de rotación, incluida la práctica actual.',
    'Beneficios, riesgos, supuestos y nivel de respaldo de cada estrategia.',
  ] as const;
}
