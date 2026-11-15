# Contrato HTTP

FastAPI publica la API bajo `/api/v1`. Angular usa `/backend/` mediante el proxy
web. Los DTOs se definen en `packages/contracts/`; el contrato completo está en
[OpenAPI](../../packages/contracts/openapi.json), con tipos TypeScript generados.
La documentación interactiva local se sirve en `http://localhost:8000/docs`.

## Superficie de consulta

| Ruta | Responsabilidad |
| --- | --- |
| GET /api/v1/health | Liveness; no acredita conexión a las bases |
| GET /api/v1/regions | Regiones operativas configuradas |
| GET /api/v1/status | Ingesta y disponibilidad de componentes |
| GET /api/v1/automation | Calendarios y estado del ciclo de modelos |
| GET /api/v1/models | Catálogo del bundle y sus métricas; no carga Boosters |
| GET /api/v1/regions/{id}/observations | Observaciones operativas paginadas y última actualización |
| GET /api/v1/regions/{id}/latest-analysis | Resultado guardado para inicio y horizonte exactos |
| POST /api/v1/analyses | Consulta resultado/estado; no ejecuta el pipeline |
| GET /api/v1/crops/catalog | Requisitos agronómicos y estado de revisión |
| GET /api/v1/places/reverse | Etiqueta aproximada de coordenadas; no modifica el análisis |

Las rutas de autenticación y fincas se describen en
[cuentas y datasets](accounts-and-farms.md). Los archivos privados requieren
propietario autorizado; no forman parte de las observaciones públicas.

## Fechas, paginación y estados

El análisis operativo usa `as_of` en `America/Bogota`. `reference_date` conserva
el corte real de entrada; el periodo comienza en `forecast_start_date`. No se
cambian las fechas de un resultado antiguo para responder a una consulta nueva.
La interfaz no pide Desde/Hasta para seleccionar el histórico de entrenamiento.

`ObservationPage` incluye items, offset/limit, total y last_updated_at. El cliente
compartido recorre las páginas del histórico operativo; eso no copia el histórico
Parquet completo a PostgreSQL.

| Estado de análisis | Significado |
| --- | --- |
| pending_model | Falta el modelo o adapter necesario |
| pending_run | No existe aún una ejecución para el periodo solicitado |
| insufficient_data | Faltan entradas compatibles; puede existir solo una parte de la predicción |
| pending_recommendations | Clima y suelo disponibles; aprobación agronómica pendiente |
| ready | Recomendaciones disponibles según las condiciones del pipeline |

`rotation_assessment` describe la evaluación explicable, separada de
`recommendations`. Un resultado parcial o experimental no debe mostrarse como
una siembra aprobada. Revisar `validation_status`, versiones y limitaciones.

## Errores y generación

Los contratos prohíben campos extra y validan relaciones entre campos. Una escritura
privada requiere sesión y CSRF. Conflictos de revisión devuelven 409; ausencia de
backend de resultados, 503. El cliente conserva códigos y mensajes sin reintentar
escrituras automáticamente. No se exponen secretos en errores.

```bash
python -m scripts.export_openapi
python -m scripts.export_openapi --check
```

`--check` verifica sin escribir. No editar OpenAPI o tipos generados manualmente.
Ver [cliente compartido](../../packages/api-client/README.md).

## Actualización manual

`POST /api/v1/automation/refresh` acepta una solicitud sin cuerpo y responde
`202` con `ManualUpdate`. Requiere cookie de sesión, origen permitido y
`X-CSRF-Token`. No acepta coordenadas, fuentes ni comandos arbitrarios: ejecuta
la configuración del worker. Solicitudes concurrentes reutilizan la activa;
la espera mínima global entre solicitudes nuevas es cinco minutos (`429` y
`Retry-After`). `GET` devuelve `ManualUpdate | null` y requiere sesión.
Ambas respuestas usan `Cache-Control: no-store`.

El estado incluye identificador, fechas, etapa, próximo reintento, mensaje y
etapas tipadas. No expone al solicitante. API encola/consulta; el consumidor
`--manual-only` ejecuta ingesta, evaluación de candidatos y recomendaciones fuera
de HTTP. Los resultados parciales no se presentan como publicación de modelos.
Ver [operación](../operations/runbook.md).
