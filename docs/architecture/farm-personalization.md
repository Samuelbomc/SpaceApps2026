# Contexto de finca en la recomendación de rotación

La información registrada por el agricultor es un insumo del análisis de su finca.
Su objetivo es aportar condiciones locales y restricciones que las fuentes
satelitales y los modelos regionales no describen por sí solos. Registrar esa
información es opcional para explorar resultados regionales; utilizarla cuando
existe es un requisito del flujo de recomendación personalizada.

## Uso previsto de cada insumo

| Información | Uso en el flujo de finca | Condición |
| --- | --- | --- |
| Ubicación y polígono | Asociar fuentes y un ámbito de modelo compatible | Correspondencia geográfica explícita; no atribuir resolución predial a un modelo regional |
| pH, textura, altitud y riego | Evaluar requisitos agronómicos y disponibilidad local de agua | Unidades, procedencia y reglas revisadas; conservar desconocidos |
| Cultivos actuales e historial fechado | Evaluar sucesión, repetición de familias y restricciones | No confundir una lista de cultivos actuales con un historial de rotación |
| Restricciones de siembra declaradas | Excluir alternativas que el agricultor no puede implementar | Aplicación trazable al lote y al usuario autorizados |
| Series de temperatura, lluvia y humedad | Evaluar variables locales o corrección del modelo regional | Calidad, disponibilidad temporal y compatibilidad con la receta verificadas |
| Cosechas y rendimiento por cultivo | Evaluar resultados y construir futuros objetivos de aprendizaje | Identidad del cultivo, fechas y contexto de manejo suficientes |

El nombre de la finca, el correo y otros datos de identificación no son variables
predictivas por el hecho de formar parte del registro.

## Dos integraciones diferentes

El motor de rotación debe combinar inferencias XGBoost, catálogo y contexto del
lote. Un dato como el cultivo previo puede modificar una alternativa de rotación
sin alterar el pronóstico climático. Esta personalización debe quedar explicada
en el resultado y mantener las comprobaciones que no se pudieron realizar.

Utilizar mediciones locales como entradas de XGBoost o para calibración requiere
otra integración. Los modelos actuales esperan 31 variables climáticas y 52 de
suelo; no aceptan nuevas columnas del formulario automáticamente. Cambiar su
receta exige entrenamiento y evaluación comparables. La mejora predictiva debe
medirse con observaciones reales reservadas y frente al modelo regional, sin
utilizar datos que todavía no estaban disponibles al emitir el pronóstico.

## Estado comprobado

- La ficha y los CSV se conservan por propietario, con revisión, unidades y hashes.
- `FarmDatasetService.bundle` entrega un contexto consistente y detecta conflictos.
- El adaptador de entrevista permite aportar historial y exclusiones al motor.
- La pantalla de análisis consulta resultados regionales; su cierre programado
  todavía no recibe el contexto privado guardado de una finca.
- La ficha HTTP conserva cultivos actuales, pero no un historial de siembras y
  cosechas fechado ni todas las restricciones de la entrevista.
- No se ha evaluado una mejora de los modelos con las mediciones privadas.

## Criterios de cierre de FARM-01

1. Asociar explícitamente finca, región/modelo compatible y propietario.
2. Completar el contrato del historial y restricciones necesarios para rotación.
3. Combinar el contexto autorizado con inferencias del periodo y catálogo,
   preservando revisión de ficha, datasets y reglas en la identidad del resultado.
4. Comprobar que cambios pertinentes del contexto cambien la evaluación o su
   explicación; no reutilizar un resultado personalizado de otra revisión o finca.
5. Verificar aislamiento entre agricultores y consulta de resultados almacenados
   sin ejecutar entrenamiento desde HTTP.
6. Distinguir personalización agronómica de mejora medida del modelo. Mantener
   pendientes cuando faltan datos o reglas, sin presentar el análisis regional
   como una predicción validada específicamente para la finca.

El registro de una finca no autoriza compartir sus datos para entrenamiento
regional. Ver [cuentas y datasets](../reference/accounts-and-farms.md),
[receta de entrenamiento](../reference/model-training.md),
[arquitectura de rotación](../reference/crop-rotation.md) y
[estado y pendientes](../reference/capabilities.md).
