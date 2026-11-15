# Estructura del código

Las rutas se expresan desde la raíz del repositorio. Las carpetas representan
responsabilidades lógicas; las dependencias se conectan en el composition root.

```text
AgroGeo/
├── apps/api/app/
│   ├── routers/          # HTTP de cuentas, fincas, catálogos y geocodificación
│   ├── services/         # Autenticación, CSV, mapas y consultas NASA
│   ├── repositories/     # Adaptadores PostgreSQL, MongoDB y fuentes externas
│   ├── db/               # Conexión PostgreSQL
│   ├── config.py         # Configuración por entorno
│   └── main.py           # Aplicación FastAPI y rutas públicas
├── frontend/src/app/
│   ├── core/             # HTTP, auth, configuración, navegación y estado
│   ├── features/         # Inicio, explorador, cuenta, finca y análisis
│   ├── shared/           # Geometría y componentes reutilizables
│   └── testing/          # Dobles exclusivos de pruebas
├── pipelines/
│   ├── ingestion/        # Clientes, flujos y almacenamiento de observaciones
│   ├── processing/       # Limpieza, geometría y validación
│   ├── training/         # Ciclo candidato, evaluación y publicación
│   ├── recommendations/  # Inferencia, evaluación agronómica y persistencia
│   └── scheduling/       # Calendarios, locks y reintentos ML
├── ml/
│   ├── configs/          # Recetas y catálogos versionados
│   ├── features/         # Contrato y almacenamiento de snapshots de inferencia
│   ├── training/         # Constructor de datasets, trainer y artefactos
│   ├── evaluation/       # Particiones temporales, métricas y promoción
│   ├── inference/        # Adaptadores de modelos publicados y experimentales
│   ├── recommendations/  # Catálogo, screening y evaluación de rotación
│   ├── scripts/          # Preparación y reproducción de experimentos
│   └── artifacts/        # Artefactos científicos y reportes identificados
├── packages/
│   ├── contracts/        # DTOs Python, JSON Schema, OpenAPI y tipos TS
│   └── api-client/       # Fetch, CSRF, paginación y utilidades compartidas
├── modulo_rotacion/      # Entrevista y diagnóstico locales; adaptador del motor
├── infra/                # Migraciones SQL y contenedores
├── scripts/              # Arranque, workers, migraciones y verificaciones
├── tests/                # Pruebas de integración, contratos y flujos
├── samples/              # Plantillas y muestras identificadas
└── docs/                 # Arquitectura, guías, referencia, operación y calidad
```

## Puntos de entrada

| Necesidad | Archivo o módulo |
| --- | --- |
| Analizar un área pública | `apps/api/app/routers/geographic_analyses.py`, `scripts/geographic_worker.py` |
| Recibir variables de la ubicación | `ml/features/prepared_daily.py` |
| Obtener y preparar entradas por coordenadas | `pipelines/ingestion/flows/model_point.py`, `pipelines/processing/geospatial/model_point.py` |
| Compartir la receta causal con entrenamiento | `ml/features/recipe.py` |
| Servir HTTP | `apps/api/app/main.py` |
| Construir dependencias y jobs | `scripts/runtime.py` |
| Ejecutar trabajos periódicos | `scripts/worker.py` |
| Iniciar stack local persistente | `scripts/dev_stack.py` |
| Consultar fuentes NASA | `apps/api/app/services/nasa_data.py` |
| Capturar y construir datasets | `ml/training/expanded_dataset.py` |
| Definir políticas y receta | `ml/training/expanded_config.py`, `ml/configs/expanded-training.json` |
| Ajustar y cargar modelos | `ml/training/xgboost.py` |
| Evaluar/promover candidatos | `pipelines/training/pipeline.py`, `ml/evaluation/promotion.py` |
| Cargar campeones para inferencia | `ml/inference/registered.py` |
| Cerrar y guardar análisis | `pipelines/recommendations/pipeline.py` |
| Evaluar rotación | `ml/recommendations/rotation.py` |
| Obtener contexto privado consistente | `apps/api/app/services/farm_datasets.py` |
| Generar contrato HTTP | `scripts/export_openapi.py` |

## Reglas de dependencia

Los contratos no importan implementaciones de FastAPI, repositorios o modelos.
Los clientes NASA devuelven información externa; los procesadores la interpretan.
Los pipelines orquestan puertos inyectables y los repositorios implementan persistencia.
El frontend consume contratos HTTP y no accede a bases o archivos científicos.

Los scripts de experimentación utilizan sus dependencias científicas; no se
importan para atender una consulta HTTP. Los mocks viven en pruebas. Las carpetas
`data/` y `tools/` contienen datos/estado local y herramientas externas; no son
capas de dominio. Los datasets científicos ya versionados se distinguen de los
CSV privados y de las salidas operativas generadas.
