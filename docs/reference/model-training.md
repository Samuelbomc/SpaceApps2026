# Contrato del entrenamiento automático

El runtime conecta componentes concretos en `scripts/runtime.py`:
ExpandedTrainingSnapshots, ExpandedTrainingDatasetBuilder, ExpandedXGBoostTrainer,
políticas por tarea y RegisteredPredictorFactory. La configuración se aplica al arranque normal. La política de publicación sigue siendo
restrictiva porque los experimentos recibidos no acreditan disponibilidad histórica
ni validación prospectiva.

## Receta y configuración

La fuente ejecutable es `ml/configs/expanded-training.json`. Sus parámetros vienen
de los informes de los veinte modelos; un override usa TRAINING_CONFIG_PATH y su
hash participa en la identidad del entrenamiento. Cambiar columnas o unidades
requiere otra versión de receta, no modificar silenciosamente expanded-v1.

| Propiedad | Definición |
| --- | --- |
| Modelos/tareas | Cuatro regresores climáticos y uno de humedad; ocho tareas clima/suelo × horizonte |
| Horizontes | 7, 15, 30 y 60 días; objetivos agregados t+1..t+H |
| Entradas | Observaciones hasta t-2, ventanas 7/14/30 y variables estáticas/estacionales |
| Esquemas | 31 variables de clima; 52 de suelo |
| Espacio | Celdas originales agrupadas del AOI configurado; no precisión de parcela |
| XGBoost | hist, profundidad 3, eta 0.03, min_child_weight 5, lambda 10, alpha 0.1, seed 42, nthread 2 |
| Selección de iteraciones | Máximo 800, parada temprana 30 sobre validación; test no selecciona árboles |
| Suelo | Aprende target − smap_mean_7d y suma ese baseline una sola vez al inferir |
| Persistencia climática | Media reciente de 7 días; lluvia reciente de 7 días × H/7 |
| Publicación inicial | Deshabilitada hasta revisión, aunque un candidato supere métricas |

## Fuentes de entrada y captura

TRAINING_DATA_DIRECTORY contiene las tablas procesadas y sus metadatos:

```text
data/prepared/
  expanded/{manifest.json,validation.json,temperature_mean.csv,...,moisture.csv}
  horizons/{15d,30d,60d}/{manifest.json,validation.json,...}
```

El capturador valida esquema, horizonte, conteo y hash de las fuentes. Los CSV
originales se reconocen también tras conversión CRLF/LF de Git, conservando todos
los demás bytes. Un CSV nuevo necesita source_sha256 en su validation.json;
`ml/scripts/validate_expanded_datasets.py` produce ese vínculo al validar las fuentes.

Los CSV se congelan como Parquet comprimido, por objetivo y horizonte, en
`data/datasets/<id>/`, con training-sources.json y hashes. No se sustituye un
snapshot existente. La captura no lee data/farms ni entrevistas privadas.
Si faltan tablas o la región está fuera del ámbito, el job informa insuficiencia.
Corrupción, duplicados o metadatos contradictorios hacen fallar el job y activan
su reintento; no borran modelos anteriores.

**Límite de integración:** este constructor consume datos ya procesados. La ingesta
pública semanal de POWER/CMR no produce todavía todas estas tablas multisensor.
Automatizar esa extracción es DATA-01 en [capacidades y límites](capabilities.md).

## Muestras, fechas y calidad

La identidad de una muestra es fecha de emisión + celda; varias celdas del mismo
día no se colapsan. Se conservan coordenadas, corte de observación, ventana de
etiqueta, disponibilidad, cobertura y procedencia. Las tablas climáticas se unen
por celda/fecha con sus objetivos disponibles: la falta de una etiqueta de lluvia
no descarta etiquetas válidas de temperatura. No se imputan objetivos ausentes.

Todas las features/etiquetas deben ser finitas y coherentes con t-2 y t+1..t+H.
Las fechas explícitas de disponibilidad prevalecen sobre supuestos. Las filas
cuya etiqueta aún no existe en el corte quedan fuera del entrenamiento. Para los
CSV históricos sin esas fechas se conserva una hipótesis versionada de dos días
de latencia; permite evaluación experimental, **no publicación**.

labels_verified identifica comprobaciones de integridad del preparado y su vínculo
con las fuentes recibidas. No certifica mediciones de campo ni disponibilidad
histórica en tiempo real. publication_ready es una comprobación independiente.
La cobertura de SMAP se conserva: un promedio de días observados no se presenta
como un promedio completo de todo el horizonte.

## Separación, entrenamiento y evaluación

Se agrupan las fechas únicas en 60 % entrenamiento, 20 % validación y 20 % test.
Todas las celdas de un día van juntas. Se purgan las etiquetas que alcancen el
corte de observaciones de la siguiente partición. No se barajan muestras.

Los cuatro objetivos climáticos comparten las fronteras temporales del grupo,
con conteos de etiquetas propios. Esto conserva filas parciales y puede cambiar
ligeramente la frontera de precipitación respecto a entrenarla aisladamente.
El modelo residual de suelo usa exactamente la misma reconstrucción al evaluar,
guardar y volver a cargar.

La validación selecciona árboles y se compara candidato, persistencia y campeón
sobre las mismas muestras. El test se evalúa después de fijar árboles. El artefacto
guardado es ese modelo evaluado: no se reajusta con etiquetas de validación/test.
trained_through indica el último periodo realmente usado para ajustar;
evaluated_through permite contar etiquetas nuevas sin confundir ambos conceptos.

Los mínimos se comprueban por objetivo y partición: 100 muestras de entrenamiento,
20 de validación, 20 de test y al menos dos ubicaciones. Un campeón requiere al
menos siete nuevas fechas etiquetadas por objetivo antes de reevaluar.

## Políticas y publicación

Las cotas MAE iniciales se toman de los baselines reportados por horizonte, en sus
unidades; son límites técnicos de referencia, no tolerancias agronómicas.
El candidato debe respetarlas y mejorar al baseline y al campeón en validación y
test por al menos el margen configurado (1 % inicial). No se exige publicar cada semana.

Una tarea que supera esas comparaciones queda pending_review si la publicación
está deshabilitada o faltan evidencias. Para habilitar publicación se necesitan:

- Política explícita publication_allowed y revisión científica de sus criterios.
- publication-evidence.json del origen, con recipe_version, reviewed_by, reviewed_on,
  feature_availability_verified, spatial_scope_verified y sources por objetivo/hash.
- Fechas features_available_on y label_available_on verificables en las filas.
- Cobertura completa de etiquetas de suelo bajo la política actual.

Un booleano de configuración solo no satisface estas condiciones. La evidencia
se incorpora al snapshot y a la identidad de la evaluación. Las pruebas que
habilitan publicación usan datos y evidencias sintéticos identificados.

| Estado | Significado |
| --- | --- |
| insufficient_labels | Faltan tablas, cobertura elegible o muestras suficientes |
| pending_configuration | Falta una dependencia o política; reservado para una composición incompleta |
| rejected | Candidato evaluado que incumple los criterios técnicos |
| pending_review | Supera métricas, pero no puede publicarse con la evidencia/política actuales |
| unchanged | Mismos datos/configuración ya evaluados |
| published | Artefacto comprobado y cambio atómico de la versión vigente |

## Inferencia posterior

RegisteredPredictorFactory carga el campeón verificando hashes, receta, columnas,
unidades, objetivo y ámbito. Fija un snapshot reciente para clima y suelo, usa su
corte real y ejecuta la misma reconstrucción residual. No consulta los CSV de
entrenamiento para sustituir entradas recientes ausentes y no fabrica etiquetas
para predecir. El job guarda después la evaluación de rotación y sus pendientes.

## Comandos

```bash
python -m scripts.inspect_training \
  --region-id antioquia-reference --latitude 6.2442 --longitude -75.5812
python -m scripts.worker --job training --once
python -m scripts.worker --job recommendations --once
```

El inspector no entrena ni publica. Los workers necesitan las conexiones de
operación configuradas. Las evaluaciones de software no sustituyen la revisión
científica prospectiva o agronómica.
