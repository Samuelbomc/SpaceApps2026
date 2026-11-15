import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { AnalysisJourneyStore } from '../../../core/journey/analysis-journey.store';
import { StepPlaceholder, StepPrerequisite } from '../../../shared/ui/step-placeholder/step-placeholder';

/** Step 5 — Agricultural and environmental characterization questionnaire (built in Increment 4). */
@Component({
  selector: 'app-characterization',
  imports: [StepPlaceholder],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-step-placeholder
      step="caracterizacion"
      title="Caracteriza tu lote"
      description="Un cuestionario guiado, por secciones, sobre lo que conoces de tu lote. Puedes responder «No sé» cuando no tengas el dato."
      [capabilities]="capabilities"
      [prerequisite]="prerequisite()"
      [back]="{ path: '/finca/lote', label: 'Municipio y lote' }"
      [next]="{ path: '/finca/analisis', label: 'Análisis' }"
      caveat="Tus respuestas son información reportada por ti. Se usarán junto con datos satelitales e institucionales, sin reemplazar un análisis de suelo de laboratorio."
    />
  `,
})
export class Characterization {
  private readonly journey = inject(AnalysisJourneyStore);

  protected readonly capabilities = [
    'Finca y lote: nombre, área aproximada, tipo de producción y uso actual.',
    'Suelo: textura, color, drenaje, compactación y erosión visibles, análisis disponibles.',
    'Clima y agua: lluvias, sequías, encharcamiento, disponibilidad de agua y observaciones locales.',
    'Cultivos anteriores y actuales: fechas, ciclos, rotaciones, descansos, insumos y plagas.',
    'Prácticas y prioridades: riego, conservación del suelo, mano de obra, metas y restricciones.',
    'Progreso visible, revisión de respuestas y confirmación final.',
  ] as const;

  protected readonly prerequisite = computed<StepPrerequisite | null>(() =>
    this.journey.plotConfirmed()
      ? null
      : { message: 'elige tu municipio y confirma el lote que quieres analizar.', link: { path: '/finca/lote', label: 'Ir a Municipio y lote' } },
  );
}
