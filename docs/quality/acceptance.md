# Aceptación de los flujos

Esta referencia define condiciones observables para validar el sistema. No afirma
que el flujo productivo completo o sus requisitos científicos estén aprobados.
El alcance de cada integración está en [capacidades](../reference/capabilities.md).

## Recorrido principal

Seguir una región, una finca autorizada y un horizonte desde los datos hasta la
pantalla. Conservar identificadores de ejecución, snapshot, receta, modelo,
catálogo/reglas, revisión de finca y resultado en la evidencia de la prueba.

| ID | Condición de aceptación |
| --- | --- |
| ACC-01 | Cuenta, sesión y recursos privados persisten; otro usuario no puede consultarlos o modificarlos |
| ACC-02 | Geometría y ubicación corresponden al lote; las limitaciones de resolución se preservan |
| ACC-03 | Datos reales completos de las fuentes necesarias tienen fechas, unidades, calidad y procedencia |
| ACC-04 | Histórico incremental y captura de datasets son idempotentes y recuperables por versión |
| ACC-05 | Entrenamiento usa solo etiquetas disponibles y particiones purgadas sin mezcla temporal de celdas |
| ACC-06 | Publicación respeta baseline, campeón, política y evidencia científica; un rechazo conserva versión vigente |
| ACC-07 | Inferencia usa el modelo del horizonte y snapshot compatibles, con baseline residual reconstruido una vez |
| ACC-08 | Rotación responde a inferencias, requisitos y contexto privado pertinentes; cambios de revisión no reutilizan resultados incorrectos |
| ACC-09 | Recomendaciones aprobadas exigen reglas revisadas y comprobaciones completas; escenarios parciales permanecen condicionales |
| ACC-10 | Resultados se consultan después de reiniciar sin recalcular modelos desde HTTP |
| ACC-11 | La vista simple y técnica muestran el mismo periodo, valores y estado en escritorio y móvil |
| ACC-12 | La utilización de datos locales en modelos cuenta con validación/autorización y una mejora medida frente a una referencia comparable |

## Escenarios de recuperación

Verificar proveedor caído, rate limit, acceso protegido, nodata, snapshot ausente,
archivo alterado, candidato rechazado, umbral ausente, revisión de finca obsoleta,
base no disponible y reinicio del worker. El comportamiento esperado se define en
[operación](../operations/runbook.md) y los contratos afectados. Ninguno autoriza
fabricar una salida o exponer información privada.

## Calidad y rendimiento

Medir entorno, volumen, concurrencia, duración de jobs, demora hasta actualización,
latencia HTTP, CPU/RAM y crecimiento de almacenamiento. Acordar objetivos antes de
declarar rendimiento suficiente. Las pruebas de componentes y compilación no
sustituyen pruebas de navegador, WebGL, recuperación o evaluación científica.

Los informes de aceptación pertenecen a los artefactos de pruebas y a la revisión
del cambio. La guía conserva el procedimiento y los criterios estables.
