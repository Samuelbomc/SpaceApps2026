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
docker compose logs --tail=100 worker training-worker recommendation-worker
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

La publicación guarda/verifica artefactos antes de cambiar el campeón con control
de concurrencia. Archivos candidatos sin publicar no autorizan borrado de versiones
referenciadas. No hay una limpieza TTL de artefactos evaluables.

## Respaldos y cambios de entorno

Respaldar PostgreSQL, MongoDB cuando sea el backend elegido, CSV privados,
snapshots y modelos con sus manifiestos. Una copia de CSV sin identidad y relaciones
no restaura una instalación. Probar restauración en un entorno aislado antes de
adoptar un procedimiento productivo; el repositorio no incluye un runbook de
backup validado para todos los proveedores.

Aplicar migraciones con `python -m scripts.migrate`; no editar una ya aplicada.
Cambiar RESULTS_BACKEND no migra datos. Validar HTTPS, cookie Secure, CORS,
proxies de confianza y capacidad antes de exponer servicios fuera del entorno local.
