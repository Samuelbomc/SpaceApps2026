# Flujos de ejecución

Los escenarios distinguen el comportamiento implementado de la integración privada
que aún requiere completarse. Los límites y criterios se centralizan en
[capacidades](../reference/capabilities.md).

## Consulta pública de análisis

```mermaid
sequenceDiagram
    actor User as Usuario
    participant Web as Angular
    participant API as FastAPI
    participant PG as Cola PostgreSQL
    participant Worker as Worker geográfico
    participant Results as Backend de resultados
    User->>Web: Delimitar lote y elegir periodo
    Web->>API: POST geographic-analyses (geometry, horizon_days)
    API->>PG: Persistir selección y solicitud idempotente
    API-->>Web: 202 con UUID y punto de muestreo
    Worker->>PG: Adquirir tarea y lock
    Worker->>Worker: Preparar entradas de la ubicación y emitir inferencias
    Worker->>Results: Guardar predicciones y evaluación agrícola
    Worker->>PG: Estado, resultado y próximo reintento
    Web->>API: GET geographic-analyses/{UUID}
    API-->>Web: Progreso y resultado de esa selección
```

El mapa, delimitación y resultados comparten página y no requieren cuenta.
Cambiar de lote o plazo limpia la presentación y cancela respuestas anteriores.
La solicitud conserva su ubicación; cualquier referencia cercana se identifica
con sus propias coordenadas y fechas. El punto interior conserva
su soporte regional; no se calcula un promedio de todos los píxeles del lote.
Ver [contrato geográfico](../reference/geographic-analysis.md).

El periodo comienza el día de consulta en `America/Bogota`. HTTP no descarga,
entrena ni ejecuta modelos. La preparación y los reintentos pertenecen al worker.
La preparación puntual consulta POWER LST, GPM Late y SMAP L3 Enhanced, extrae
celdas nativas y aplica la receta compartida con entrenamiento antes de publicar
un snapshot. Earthdata y las capas estáticas aprovisionadas condicionan su
ejecución real. La actualización histórica multifuente para reentrenamiento
sigue siendo DATA-01; tener pesos o catálogos no satisface sus entradas.

## Registro, finca y mediciones privadas

1. El usuario se registra o inicia sesión. FastAPI verifica credenciales y emite
   una cookie HttpOnly; el navegador restaura la sesión al recargar.
2. El propietario registra ubicación, polígono y ficha. El backend valida geometría
   y campos; editar exige la revisión vigente para evitar sobrescrituras.
3. El propietario puede subir CSV con fechas, variables, valores y unidades. Se
   valida la carga completa, se conserva el original privado y se normalizan filas.
4. Una repetición idéntica no duplica el dataset. Consultar, descargar y eliminar
   requieren autorización por propietario y, en escrituras, CSRF.
5. El contexto de finca reúne ficha, observaciones y versiones hasta el corte;
   informa conflictos y limita su interpretación a la calidad verificada.

Registrar la ficha aporta contexto local para personalización. Su uso completo
con el análisis y las reglas requiere la asociación privada descrita más abajo.
La aceptación del CSV no certifica mediciones ni una mejora del modelo.

## Actualización manual

Exploración permite encolar una actualización a usuarios autenticados. FastAPI
comprueba sesión/CSRF y conserva la solicitud en PostgreSQL; responde sin ejecutar
los jobs. Un consumidor independiente recorre ingesta, entrenamiento condicionado
y recomendaciones, con los locks de cada job. La pantalla consulta el estado y
relee datos cuando hay progreso. Clics concurrentes comparten ejecución y los
reintentos respetan el backoff; una interrupción permite retomar la etapa pendiente.
La ruta manual utiliza la misma receta, revisión y política de publicación que la
automática. Consultar el mapa sigue siendo público y no inicia estos procesos.

## Procesos autónomos

```mermaid
flowchart TD
    SCHED[Calendarios durables y locks] --> INGEST[Ingesta por fuente]
    INGEST --> POWER[POWER: limpieza y Parquet incremental]
    INGEST --> DISCOVERY[Otras fuentes: descubrimiento y estado de acceso]
    DISCOVERY -. extracción multisensor por completar .-> TABLES[Tablas de la receta]
    SCIENCE[Preparación científica de raster y series] --> TABLES
    TABLES --> SNAP[Captura inmutable por contenido]
    SNAP --> PREP[Construir muestras por celda y horizonte]
    PREP --> FIT[Particiones temporales con purga y entrenamiento]
    FIT --> EVAL[Comparar con baseline y campeón]
    EVAL -->|criterios y revisión completos| PUB[Publicar versión]
    EVAL -->|incumplimiento| KEEP[Conservar campeón]
    EVAL -->|métricas aptas sin aprobación| REVIEW[Pendiente de revisión]
    PUB --> INFER[Inferir con snapshot reciente compatible]
    KEEP --> INFER
    FEATURES[Snapshot de variables reciente] --> INFER
    INFER --> ROTATION[Evaluar catálogo y rotación]
    ROTATION --> STORE[Persistir resultados y versiones]
    STORE --> QUERY[Consulta HTTP]
```

La ingesta y el entrenamiento se revisan diariamente en calendarios independientes;
las recomendaciones se revisan cada hora y al recibir nuevas entradas o modelos.
Las tablas procesadas alimentan cinco tareas diarias con leads 1–60. Una ingesta nueva no
obliga a publicar otra versión. Un campeón vigente puede seguir siendo la versión
utilizada si un candidato falla o no hay etiquetas suficientes.

La inferencia publicada exige variables de la receta y ámbito compatibles.
El bundle experimental permite previews identificados y no registra campeones.
La reconstrucción residual de humedad suma su baseline exactamente una vez.
La evaluación de rotación recibe las cinco salidas del mismo lugar y periodo.

Los estados de entrenamiento están en [su contrato](../reference/model-training.md),
y los de análisis en [HTTP](../reference/http-api.md).

## Personalización de finca — integración requerida

El recorrido de recomendación personalizada exige combinar las inferencias
compatibles, catálogo y contexto autorizado del lote. Historial, suelo, riego y
restricciones deben influir en las comprobaciones pertinentes y en su explicación.
La identidad del resultado debe incluir las revisiones de los insumos privados.

La pantalla de análisis consulta resultados regionales y todavía no utiliza la
ficha privada para este cierre. El adaptador de entrevista admite historial y
exclusiones; eso no completa el flujo desde la ficha guardada. La asociación
finca–región y el contrato de historial fechado son requisitos de FARM-01.
Ver [personalización](farm-personalization.md).

## Fallos y aceptación

Los errores técnicos conservan datos/modelos válidos y reintentos durables.
Ausencias de etiquetas, snapshots o umbrales son estados explícitos; no se
convierten en cero ni en recomendaciones aprobadas. Reinicios, fallos por fuente
y candidatos rechazados no borran el campeón.

Procedimientos en [operación](../operations/runbook.md). La comprobación integral
por región, finca y horizonte se define en [aceptación](../quality/acceptance.md).
