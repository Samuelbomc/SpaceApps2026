# Componentes ML y contratos de artefactos

El código de `ml/` sirve dos recorridos: reproducción de experimentos y ciclo
operativo de candidatos/publicación. Ambos conservan receta y fuentes; ejecutar
un script experimental no registra automáticamente un modelo operativo.

## Experimentación

```mermaid
flowchart LR
    RAW[Descargas de fuentes] --> SRC[dataset_sources.py]
    SRC --> PREP[prepare_expanded_datasets.py]
    PREP --> TABLES[CSV, manifiesto y validación]
    TABLES --> ABS[train_prepared_models.py]
    ABS --> EVAL[evaluation_model.json y métricas]
    ABS --> REFIT[model.json reajustado]
    TABLES --> RES[train_moisture_change.py]
    ABS -->|particiones y comparator| RES
    RES --> MOIST[Modelo residual y baseline]
```

`environmental_conditions/` contiene cuatro regresores climáticos y el comparador
absoluto de humedad. `soil_moisture/` contiene la formulación residual usada para
humedad; `forecasts/{H}d/` contiene variantes por horizonte. Los resultados de
holdout corresponden a `evaluation_model.json`. El `model.json` de experimentación
se reajusta con todas las filas y no tiene una evaluación independiente posterior.

Los archivos de humedad residual predicen un cambio. Sus adaptadores suman el
baseline observado exactamente una vez; cargarlos como regresión absoluta altera
el significado de la salida.

## Ciclo operativo

| Componente | Responsabilidad |
| --- | --- |
| ExpandedTrainingSnapshots | Congelar tablas procesadas, metadatos y hashes |
| ExpandedTrainingDatasetBuilder | Construir muestras multiespaciales con targets/fechas válidos |
| ExpandedXGBoostTrainer | Ajustar por target y guardar el Booster evaluado sin refit posterior |
| ModelTrainingPipeline | Separar fechas, comparar baseline/campeón y decidir publicación |
| ModelArtifactStore | Persistir versiones y comprobar integridad |
| RegisteredPredictorFactory | Cargar campeones con receta y snapshot compatible |
| ExpandedModelBundle | Cargar artefactos experimentales explícitamente provisionales |
| ForecastRotationEngine | Evaluar salidas, requisitos, familias y restricciones |

Los campeones usan los artefactos congelados que se evaluaron en el ciclo operativo.
No se confunden con los refits experimentales. El catálogo de referencia, la
comparación numérica y la evaluación de rotación conservan contratos diferentes
de una recomendación agronómica aprobada.

## Referencias principales

[Entrenamiento](../model-training.md), [inferencia](../model-inference.md),
[catálogo](../agronomic-catalog.md), [rotación](../crop-rotation.md) y
[estructura del repositorio](../../architecture/code-structure.md).
