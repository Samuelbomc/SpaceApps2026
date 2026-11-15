import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { AnalysisJourneyStore } from '../../../core/journey/analysis-journey.store';
import { StepPlaceholder, StepPrerequisite } from '../../../shared/ui/step-placeholder/step-placeholder';

/** Step 6 — Analysis and recommendations dashboard (built in Increment 5). */
@Component({
  selector: 'app-analysis',
  imports: [StepPlaceholder],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-step-placeholder
      step="analisis"
      title="Análisis y recomendaciones"
      description="La propuesta de rotación de cultivos para tu lote, con su explicación, y la información ambiental que la respalda."
      [capabilities]="capabilities"
      [prerequisite]="prerequisite()"
      [back]="{ path: '/finca/caracterizacion', label: 'Caracterización' }"
      [next]="{ path: '/panel', label: 'Ir a mi panel' }"
      caveat="Aún no existe un motor de análisis. Ningún lote ha sido analizado y esta pantalla no muestra resultados reales. Las recomendaciones apoyan la decisión y requieren validación agronómica local."
    />
  `,
})
export class Analysis {
  private readonly journey = inject(AnalysisJourneyStore);

  protected readonly capabilities = [
    'Rotación de cultivos recomendada: orden, duración, épocas de siembra y cosecha, beneficios y riesgos.',
    'Comparación entre escenarios de rotación.',
    'Series de precipitación, temperatura y humedad, distinguiendo observaciones, modelos y pronósticos.',
    'Calendario de planificación de siete días.',
    'Riesgo de erosión del suelo y sus factores.',
    'Recomendaciones de manejo del suelo y del cultivo.',
  ] as const;

  protected readonly prerequisite = computed<StepPrerequisite | null>(() =>
    this.journey.questionnaireComplete()
      ? null
      : {
          message: 'completa la caracterización de tu lote.',
          link: { path: '/finca/caracterizacion', label: 'Ir al cuestionario' },
        },
  );
}
