# Contratos compartidos

`DataQuery`, `SourceResult`, `DataRepository`, `GeoPoint`, `BoundingBox` y
`DateRange` son contratos Python independientes de FastAPI, de los clientes
NASA y de los modelos de ML. `data-query.schema.json` documenta la entrada
JSON para consumidores como Next.js y futuros endpoints.

El contrato Python valida también relaciones entre valores: orden de límites,
orden de fechas y límite puntual de 20 variables POWER. El JSON Schema describe
la forma y los rangos; no sustituye esas validaciones.

`api.py` define los DTOs HTTP e interfaces de salida de modelos/recomendaciones.
`openapi.json` y `api.generated.ts` se generan desde FastAPI mediante
`python -m scripts.export_openapi`. El frontend importa esos tipos; una prueba
comprueba que coincidan con la API actual. La validación de valores se realiza
en Pydantic; TypeScript describe su forma estática.

La base operativa PostgreSQL, los estados de análisis pendientes y los comandos
de generación están descritos en [development.md](../../docs/development.md).


El contrato HTTP `ObservationPage` permite consultar sin fechas y paginar todo el
histórico operativo por `offset`/`limit`, con `total` y `last_updated_at`. El
frontend recorre las páginas automáticamente y muestra la última actualización;
no solicita un periodo histórico al usuario. Los artefactos OpenAPI y TypeScript
se regeneran con `python -m scripts.export_openapi`.


`training.py` define snapshots, muestras etiquetadas, políticas, versiones
publicadas y `AutomationStatus`. `GET /api/v1/automation` es de lectura; no inicia
entrenamientos. `Recommendations.catalog_version` identifica los requisitos
agronómicos utilizados y participa en la identidad de los resultados. El nuevo
job exige esta versión antes de almacenar recomendaciones listas para consultar.


`agronomy.py` describe `CropCatalog` y los contextos e informes de compatibilidad.
El catálogo se expone en `GET /api/v1/crops/catalog`. Las comprobaciones de rangos
son diferentes de `Recommendations`: no declaran siembras o rotaciones listas.
