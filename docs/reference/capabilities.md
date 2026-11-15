# Capacidades y límites de integración

Esta referencia distingue capacidades implementadas de restricciones y requisitos
de aceptación. Los estados pendientes forman parte del comportamiento del sistema.

## Implementado y comprobable

- Angular, autenticación HTTP real, sesión por cookie y gestión privada de fincas/CSV.
- Mapa MapLibre, selección de superficies y persistencia del polígono.
- POWER procesado/Parquet; descubrimiento de productos de las demás fuentes.
- Scheduler durable con bloqueos, reintentos y tres jobs independientes.
- Constructor multiespacial de datasets procesados para clima y suelo en 7/15/30/60 días.
- Entrenador XGBoost con parada temprana, humedad residual y evaluación temporal 60/20/20 con purga.
- Políticas versionadas, artefactos inmutables, candidatos y publicación condicionada.
- Adapter de inferencia para campeones publicados; preview separado de los veinte artefactos experimentales.
- Evaluación de rotación conectada a las cinco salidas de los modelos y persistida con ellas.
- Contratos generados, pruebas automáticas y lectura de resultados sin calcular modelos desde HTTP.

## Restricciones y criterios de aceptación

| ID | Prioridad | Pendiente | Criterio para considerarlo resuelto |
| --- | --- | --- | --- |
| DATA-01 | Alta | Alimentación reciente multisensor | La ingesta y el procesamiento producen variables y etiquetas verificables de la receta completa, sin intervención para cada actualización. |
| ML-01 | Alta | Revisión de publicación científica | Evidencia de disponibilidad histórica, alcance espacial, cobertura y políticas revisadas, asociada a hashes de fuentes; candidato que supera baseline y campeón. |
| AGR-01 | Alta | Requisitos de agua y aprobación agronómica | Umbrales por cultivo/horizonte de lluvia y humedad, catálogo revisado y lógica de aprobación validada por el equipo agronómico. |
| FARM-01 | Alta | Contexto de lote en el flujo privado | Combinar las inferencias y el catálogo con la ficha, historial, restricciones y mediciones pertinentes de la finca; verificar efecto, trazabilidad por revisión y aislamiento. Criterios en [contexto de finca](../architecture/farm-personalization.md). |
| AUTH-01 | Media | Recuperación de contraseña y edición de perfil | Endpoints, controles y flujos completos; actualmente la interfaz informa que no están disponibles. |
| OPS-01 | Media | Operación productiva y rendimiento | Despliegue verificado, dependencias Python bloqueadas, backups/restauración probados y mediciones frente a objetivos de carga y latencia acordados. |
| E2E-01 | Alta | Aceptación integral con resultados aprobados | Una corrida real trazable desde NASA hasta la pantalla, con modelos y reglas publicados; ver [aceptación](../quality/acceptance.md). |

Los límites actuales son deliberados: sin datos suficientes no se generan
predicciones; sin revisión no se publican modelos; sin requisitos agronómicos no
se aprueban siembras. No se eliminan estos estados para ocultar trabajo pendiente.

## Distinciones necesarias

- `pending_configuration` indica una dependencia no configurada; el runtime normal
  conecta constructor, entrenador, políticas y factory. Falta de tablas de
  origen se informa como `insufficient_labels`.
- `pending_review` significa que el candidato superó las comprobaciones técnicas,
  pero no puede publicarse con la evidencia/política actuales.
- `pending_recommendations` y `rotation_assessment` provisional no equivalen a una
  recomendación aprobada ni a un calendario anual validado.
- Importar datasets preparados no automatiza la extracción científica de NASA.
- Guardar un CSV de finca no valida sus mediciones ni autoriza entrenamiento regional.
