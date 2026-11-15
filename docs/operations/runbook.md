# Operación y recuperación

Los comandos se ejecutan desde la raíz, con entorno Python activado y las conexiones
correctas. No apuntar pruebas a bases operativas. Configuración en
[variables de entorno](../reference/configuration.md).

## Comprobar el servicio

1. Revisar `/api/v1/health` para liveness.
2. Revisar `/api/v1/status` para ingesta y componentes.
3. Revisar `/api/v1/automation` para calendarios, modelos y último estado de entrenamiento.
4. Consultar el periodo y horizonte exactos del análisis; comprobar fecha de entrada,
   snapshot y versiones. Un resultado antiguo no satisface un periodo nuevo.
5. Revisar logs del worker correspondiente sin publicar URIs o credenciales.

En Compose:

```bash
docker compose ps
docker compose logs --tail=100 worker training-worker recommendation-worker manual-update-worker
```

Los logs pueden incluir información operativa; limitar su acceso. Las conexiones
se comprueban con las variables del entorno, sin imprimir secretos.

## Ejecutar o reintentar un job

```bash
python -m scripts.worker --job ingestion --once
python -m scripts.worker --job training --once
python -m scripts.worker --job recommendations --once
```

Los jobs usan sus locks y calendarios durables. Sin `--once`, el proceso debe
permanecer activo. Una fila de calendario no demuestra que haya un worker ejecutándose.
Ingesta completada adelanta los jobs ML; publicación adelanta recomendaciones.

| Situación | Acción | Condición de recuperación |
| --- | --- | --- |
| Proveedor NASA caído o rate limit | Conservar datos; respetar Retry-After y reintento programado | Fuente vuelve a responder y se completa el periodo pendiente |
| Contenido protegido inaccesible | Configurar Earthdata fuera del código cuando se requiera | GET científico autorizado; catálogo por sí solo no completa extracción |
| Datos o etiquetas insuficientes | Revisar fuentes procesadas, fechas, cobertura y receta | Muestras válidas suficientes; no rellenar targets |
| Candidato rechazado | Inspeccionar métricas sobre particiones comunes | Mantener campeón; nuevos datos o configuración justifican otra evaluación |
| pending_review | Revisar evidencia científica y política | Aprobación explícita y verificable; no forzar publicación por disponibilidad |
| Requisitos agronómicos pendientes | Revisar catálogo y reglas por cultivo/horizonte | Umbrales revisados y evaluación completa |
| MongoDB/PostgreSQL no disponible | Corregir conexión/servicio y permitir reintento | Backend seleccionado responde; no activar fallback silencioso |
| Recomendaciones parcialmente fallidas | Revisar `failed_tasks` en `last_result` del calendario y el tipo de error; dejar actuar el backoff | Las tareas sanas conservan sus resultados; el reintento del mismo día ejecuta las fallidas |
| Hash de fuente o modelo inválido | Detener uso e investigar origen | Artefacto íntegro identificado; no recalcular hashes para ocultar corrupción |
| Conflicto de edición de finca | Recargar ficha y resolver cambios del propietario | Escritura con revisión vigente |

Los reintentos ML usan 1, 2, 4, 8, 16 y hasta 24 horas. La ausencia de reglas o
etiquetas es un estado de negocio, distinto de un fallo técnico. El catálogo NASA
puede estar disponible sin valores científicos extraídos.

`--once` fuerza una revisión completa del job para el día actual. Un reintento que
cruza al siguiente día también revisa todas las tareas; no reutiliza el periodo
fallido como si correspondiera a la nueva consulta. La configuración de cada job
se construye por separado, por lo que corregir entrenamiento no requiere detener
la ingesta.

## Reinicio y persistencia

Un reinicio normal conserva volúmenes y `data/`. No eliminar calendarios, campeones
o resultados para reintentar. No usar eliminación de volúmenes como recuperación.
El histórico POWER puede conservar un `.write.lock` tras una interrupción; retirarlo
solo después de comprobar que no hay escritor activo y de investigar la causa.

Para trasladar almacenamiento a nombres de AgroGeo, detener API y consumidores
que escriban antes de tomar un respaldo consistente. Conservar los volúmenes
originales y configurar sus nombres explícitos, o restaurar el respaldo en los
destinos nuevos. En MongoDB, preservar documentos, `_id`, opciones e índices de
todas las colecciones y verificar su igualdad antes de cambiar la conexión de
API y workers. Todos los procesos deben usar la misma base de resultados.
No borrar el origen antes de comprobar lecturas, sesiones, archivos y resultados.
La configuración de Compose no migra automáticamente bases o roles existentes.

Las nuevas particiones Parquet usan la clave de metadatos `agrogeo_schema`.
El lector POWER admite también la clave histórica sin reescribir archivos al
consultarlos. Una escritura incremental conserva las observaciones y usa la
clave actual. El nombre comercial no modifica versiones, hashes ni artefactos
científicos existentes.

La publicación guarda/verifica artefactos antes de cambiar el campeón con control
de concurrencia. Archivos candidatos sin publicar no autorizan borrado de versiones
referenciadas. No hay una limpieza TTL de artefactos evaluables.

## Actualización manual desde la aplicación

Un usuario autenticado puede pulsar **Actualizar datos y modelos** en Exploración.
`POST /api/v1/automation/refresh` exige sesión, origen permitido y CSRF; devuelve
`202` con la solicitud durable. `GET` sobre la misma ruta devuelve su estado
más reciente, sin identidad del solicitante. El ámbito es global para los jobs
configurados, no un recorte bajo demanda de la parcela del mapa.

El consumidor se ejecuta con las mismas conexiones y directorios de API/workers:

```bash
python -m scripts.worker --manual-only --poll-seconds 5
```

El stack local incluye este consumidor y Compose lo ejecuta como
`manual-update-worker`. Estar activo no descarga datos: espera solicitudes.
`--manual-only --once` permite revisar una solicitud pendiente una vez. Si se
mantiene `queued`, comprobar que el consumidor está activo y comparte PostgreSQL.

La cola agrupa clics concurrentes en una sola ejecución global y aplica cinco
minutos entre solicitudes nuevas. Respuestas `429` incluyen `Retry-After`.
El worker recorre ingesta → evaluación de entrenamiento → recomendaciones con
los mismos locks y backoff de los procesos periódicos. Respeta un `retry_at`
vigente; tres fallos técnicos de una etapa terminan esa solicitud manual. Los
jobs periódicos mantienen su política de reintento independiente. Al reiniciar
un consumidor se retoma la etapa pendiente, sin repetir etapas ya registradas
como completadas. No se cambian las barreras científicas de publicación.

Los estados son `queued`, `running`, `retry_scheduled`, `completed`,
`completed_with_limitations` y `failed`. Cada etapa informa estado, mensaje,
conteos y limitaciones. `completed_with_limitations` puede indicar ingesta
correcta sin nuevas etiquetas, modelos no publicados o predicciones incompletas.
No equivale a un modelo nuevo. Actualmente la ingesta procesa POWER y descubre
catálogos para otras fuentes; la extracción multifuente y los snapshots recientes
siguen sujetos a [los límites de datos](../reference/capabilities.md).

## Respaldos y cambios de entorno

Respaldar PostgreSQL, MongoDB cuando sea el backend elegido, CSV privados,
snapshots y modelos con sus manifiestos. Una copia de CSV sin identidad y relaciones
no restaura una instalación. Probar restauración en un entorno aislado antes de
adoptar un procedimiento productivo; el repositorio no incluye un runbook de
backup validado para todos los proveedores.

Aplicar migraciones con `python -m scripts.migrate`; no editar una ya aplicada.
Cambiar RESULTS_BACKEND no migra datos. Validar HTTPS, cookie Secure, CORS,
proxies de confianza y capacidad antes de exponer servicios fuera del entorno local.
