# ADR 0001 — Límites del pipeline y publicación de resultados

Estado: adoptada para los límites de software. La publicación científica tiene
sus propios requisitos de revisión.

## Contexto

El sistema combina proveedores con distintas latencias y resoluciones, datos
privados de fincas, entrenamiento temporal y consultas interactivas. Una llamada
al mapa no debe depender de descargas satelitales o del tiempo de entrenamiento.
Los experimentos recibidos tampoco equivalen a modelos publicados para operación.

## Decisión

1. Separar ingesta, entrenamiento y recomendaciones en jobs con locks y calendarios
   durables. HTTP consulta resultados ya almacenados; cada job puede reintentarse
   y conserva datos/modelos válidos ante fallos.
2. Mantener PostgreSQL para identidad, fincas, observaciones y calendarios; MongoDB
   para resultados y registro ML. El adapter PostgreSQL de resultados es una
   alternativa explícita de desarrollo, sin doble escritura ni fallback silencioso.
3. Conservar histórico/snapshots en Parquet y modelos en JSON con hashes. Los
   archivos originales privados no se incorporan al entrenamiento regional.
4. Usar una receta versionada por horizonte, con identidad de celda, separación
   temporal y baseline residual explícito. Publicar requiere criterios técnicos
   y evidencia revisada; aprobar cultivos requiere además reglas agronómicas.
5. Tratar el ámbito del modelo y la geometría del lote como conceptos diferentes.
   Delimitar metros cuadrados no genera resolución satelital o validación predial.

## Alternativas y consecuencias

Calcular al abrir la pantalla encadenaría la disponibilidad de NASA, el cómputo y
la respuesta HTTP. Los jobs desacoplan esas dependencias a cambio de operar
workers, observar su estado y comunicar la fecha real de actualización.

Guardar únicamente inferencias impediría reconstruir entrenamiento y comparar
versiones. Conservar tablas procesadas y artefactos exige respaldos y retención
controlada, con menor volumen que duplicar todos los productos satelitales.

Un solo almacén reduciría operación inicial, pero mezclaría cuentas, histórico y
artefactos de experimentación. La división actual añade dos motores de persistencia;
su conveniencia en producción deberá medirse con el volumen y la carga acordados.
No se declara óptima antes de completar esa medición.

Los estados pendientes forman parte del contrato: la ausencia de reglas o de
variables recientes no debe producir recomendaciones aparentes. Un candidato
rechazado conserva al campeón y un candidato técnicamente apto puede quedar en revisión.

## Verificación y revisiones

Ver [arquitectura](../overview.md), [entrenamiento](../../reference/model-training.md),
[almacenamiento](../persistence.md) y [aceptación integral](../flows.md).
Revisar esta decisión si cambia la resolución requerida, el volumen, el backend
de resultados, la receta o la política de privacidad. Pendientes en
[estado del proyecto](../../reference/capabilities.md).
