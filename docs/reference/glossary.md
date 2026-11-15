# Glosario

| Término | Significado en el proyecto |
| --- | --- |
| AOI | Área de interés; geometría de selección, distinta de la resolución de una fuente |
| Celda o soporte nativo | Unidad espacial que respalda el valor del producto |
| Región | Identidad operativa con coordenadas y modelos asociados |
| Finca/lote | Recurso privado con ficha, geometría, propietario y revisión |
| Horizonte H | Periodo agregado de 7, 15, 30 o 60 días; no estado exclusivo del día H |
| Emisión t | Fecha base de la receta; los targets cubren t+1..t+H |
| Corte de observación | Última fecha de entrada admitida; t-2 en expanded-v1 |
| Disponibilidad | Fecha en que una observación podía ser conocida; distinta de su fecha de medición |
| Feature | Variable de entrada construida por una receta versionada |
| Target/etiqueta | Valor observado que el modelo intenta predecir |
| Baseline | Referencia de comparación, normalmente persistencia; también base de reconstrucción del modelo residual |
| Snapshot | Copia identificada por contenido de entradas o datasets utilizados |
| Candidato | Modelo entrenado que debe superar evaluación y condiciones de publicación |
| Campeón | Versión publicada para una región, tipo de modelo y horizonte |
| Preview experimental | Inferencia con artefactos de experimentación; no acredita publicación |
| Purga temporal | Exclusión de ventanas de etiquetas que alcanzan el corte de la partición siguiente |
| MAE | Error absoluto medio, expresado en la unidad del target |
| Catálogo agronómico | Perfiles de cultivos y requisitos con procedencia y versión |
| Evaluación de rotación | Comprobaciones de inferencias, requisitos, familias y restricciones |
| Escenario condicional | Secuencia de referencia cuyas condiciones o etapas no están completamente validadas |
| Recomendación aprobada | Resultado que cumple publicación de modelos y requisitos agronómicos completos |
| Backoff | Espera creciente entre reintentos técnicos |
| Idempotencia | Repetir una misma operación lógica no duplica su efecto |
| ADR | Registro de una decisión de arquitectura, contexto y consecuencias |

Los estados de entrenamiento se definen en [entrenamiento](model-training.md),
los estados de análisis en [HTTP](http-api.md) y las fechas operativas en
[inferencia](model-inference.md).
