# Jobs autónomos de entrenamiento y recomendaciones

Los tres procesos son independientes de HTTP y conservan calendarios, bloqueos
y reintentos en PostgreSQL. La implementación concreta, las muestras y los
criterios están en [entrenamiento](model-training.md).

| Job | Cadencia de revisión | Responsabilidad |
| --- | --- | --- |
| nasa-weekly | 604800 s | Ingesta incremental y estados por fuente |
| model-training | 86400 s | Captura procesados, construye datasets, ajusta/evalúa candidatos y publica cuando procede |
| crop-recommendations | 3600 s | Usa versiones activas y snapshots recientes; guarda inferencias y evaluación de rotación |

Una ingesta completada adelanta los jobs ML. Una publicación adelanta las
recomendaciones. La llegada de observaciones no garantiza etiquetas nuevas,
y una revisión programada no implica una publicación.

```bash
python -m scripts.worker --job ingestion --once
python -m scripts.worker --job training --once
python -m scripts.worker --job recommendations --once
```

Sin --once los procesos deben permanecer activos. Compose los ejecuta como
servicios separados; scripts.dev_stack conserva las bases pero no activa workers.
No se dispara NASA ni XGBoost al abrir Angular o consultar FastAPI.

El runtime normal conecta constructor, trainer, políticas y factory de
campeones. El entrenamiento consume tablas procesadas, no catálogos CMR ni CSV
privados. La construcción reciente de toda la receta y la revisión científica de
publicación siguen pendientes; ver [estado actual](capabilities.md).

Las versiones se guardan antes de publicar; la sustitución compara el campeón
esperado. Un rechazo o un fallo conserva el anterior. Los fallos técnicos tienen
backoff; pending_review e insufficient_labels son estados informativos. Los
resultados anteriores no se borran para reintentar.

La rotación utiliza las inferencias y distingue escenarios condicionales de
recomendaciones aprobadas. El preview experimental no convierte sus artefactos
en campeones. Detalle en [contrato de rotación](crop-rotation.md) y
[xgboost-integration.md](model-inference.md).
