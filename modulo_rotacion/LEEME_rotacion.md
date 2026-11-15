# Módulo del agricultor y rotación basada en XGBoost

El motor consume **AnalysisResult precalculado**, con las predicciones de
clima y suelo del mismo lugar, fecha de referencia y horizonte. La entrevista
aporta historial y restricciones; nunca se convierte fría/templada/caliente en
15/21/26 °C ni se supone un calendario de lluvias para sustituir los modelos.

La lógica de evaluación está en `ml/recommendations/rotation.py`.
`motor_rotacion.py` es el adaptador para la entrevista y los comandos locales.
El job usa esa misma lógica después de inferir, tanto para modelos publicados
como para previews experimentales. No existe un motor paralelo de clima supuesto.

## Entradas y alcance

- Temperaturas media, media de mínimas y media de máximas del periodo (°C).
- Precipitación acumulada del horizonte (mm), con estadística sum.
- Humedad superficial media (m³/m³), con estadística mean.
- Catálogo ECOCROP versionado, familias de cultivos e historial/restricciones.

La temperatura media pronosticada se comprueba contra rangos ECOCROP. Las medias
de extremos diarios no demuestran que no ocurrirá una helada. La lluvia de días
no se anualiza ni se compara con mm/año. No se infiere humedad radicular a partir
de humedad superficial. Las comprobaciones de siembra requieren reglas revisadas para las variables
y el horizonte evaluados.

**El equipo todavía no tiene umbrales por cultivo/horizonte de lluvia y humedad.**
Esas comprobaciones quedan unknown, con el valor real predicho y la razón. El
motor no fabrica límites y la evaluación queda pending_agronomic_requirements.

Las secuencias son escenarios condicionales por familias. Solo el primer cultivo
tiene evaluación parcial del periodo; las etapas posteriores requieren nuevas
inferencias. Un pronóstico de hasta 60 días no valida una rotación de un año.
No se fuerzan tres resultados cuando faltan candidatos.

## Uso desde la raíz del proyecto

```bash
python -m modulo_rotacion.motor_rotacion
# Devuelve pending_forecasts y ninguna rotación aprobada.

python -m modulo_rotacion.motor_rotacion \
  --respuestas modulo_rotacion/datos/respuestas_agricultor_ejemplo.json \
  --analisis /ruta/al/AnalysisResult.json --region-id region-asociada-al-lote
```

Sin `--salida`, imprime JSON sin escribir un archivo.

```python
from modulo_rotacion.motor_rotacion import recomendar

result = recomendar(respuestas, analisis=analysis_result, region_id=region_id)
```

La asociación de región debe ser explícita, en region_id o finca.region_id.
Un municipio con el mismo nombre no autoriza atribuir una predicción regional a
un lote. La función no modifica las respuestas recibidas. Los escenarios nuevos
están en escenarios_condicionales y evaluacion_rotacion; rotaciones permanece
vacío mientras no haya recomendaciones agronómicas aprobadas.

La entrevista de terminal conserva --analisis y --region-id. El diagnóstico de
erosión e historial sigue siendo un diagnóstico basado en respuestas, separado
de las predicciones de humedad. Las entrevistas privadas no entran al job regional.

## Reglas de agua futuras

El contrato `packages/contracts/rotation.py::RotationWaterRules` permite una regla
por crop_id y horizon_days (7/15/30/60), con límites de precipitación acumulada,
humedad superficial, fuente y revisión. Solo se aplican reglas review_status=reviewed.
ROTATION_WATER_RULES_PATH configura un JSON de ese contrato en el worker. No hay
un archivo de límites predeterminado. En Docker usar una ruta montada bajo /app/data.
La publicación de recomendaciones sigue requiriendo modelos validados y reglas
agronómicas completas, además de revisión del catálogo y del contexto local.

Contrato y verificación:
[contrato de rotación](../docs/reference/crop-rotation.md).
