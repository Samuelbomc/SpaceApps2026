# Modelos y experimentación

`ml/` contiene recetas, entrenamiento, evaluación e inferencia XGBoost para cinco
objetivos y horizontes 7/15/30/60. Los artefactos experimentales y los modelos del
registro operativo tienen contratos de publicación distintos.

| Carpeta | Responsabilidad |
| --- | --- |
| configs | Receta de entrenamiento, bundle y catálogos/reglas empaquetados |
| features | Snapshots recientes de entrada para inferencia |
| training | Constructor multiespacial, trainer residual y artefactos inmutables |
| evaluation | Particiones con purga, MAE y promoción |
| inference | Interfaces y carga de modelos registrados/experimentales |
| recommendations | Evaluación de requisitos y rotación |
| scripts | Preparación, ajuste y reproducción de experimentos |
| artifacts | Boosters, metadatos, predicciones y métricas científicas |

## Contratos de aplicación

- [Entrenamiento](../docs/reference/model-training.md): configuración, fuentes,
  disponibilidad temporal, muestras, particiones y publicación.
- [Inferencia](../docs/reference/model-inference.md): fechas, columnas, unidades,
  versión y reconstrucción residual.
- [Componentes ML](../docs/reference/ml/components.md).
- [Rotación](../docs/reference/crop-rotation.md) y
  [personalización de finca](../docs/architecture/farm-personalization.md).

El runtime conecta constructor, trainer, políticas y factory de campeones. La
publicación exige revisión científica. Los pronósticos actuales necesitan
snapshots recientes completos; las muestras históricas no los sustituyen.

## Metodología y reproducción

Los comandos se ejecutan desde la raíz. La preparación científica utiliza numpy,
pandas, rasterio y h5py además de XGBoost. Consultar:

- [Receta de datos](../docs/reference/ml/datasets.md).
- [Evaluación de siete días](../docs/reference/ml/seven-day-results.md).
- [Evaluaciones 15/30/60](../docs/reference/ml/horizon-results.md).
- [Humedad residual](../docs/reference/ml/moisture-model.md).
- [Adquisición de raster](../docs/guides/data-acquisition.md).

Los reportes indican el archivo evaluado y su partición. Un modelo reajustado con
todo el dataset no hereda una evaluación independiente posterior al reajuste.
