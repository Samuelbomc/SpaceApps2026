# Contrato del entrenamiento automático

El runtime conecta componentes concretos en `scripts/runtime.py`:
ExpandedTrainingSnapshots, ExpandedTrainingDatasetBuilder, ExpandedXGBoostTrainer,
políticas por tarea y RegisteredPredictorFactory. La configuración se aplica al arranque normal. La política de publicación sigue siendo
restrictiva porque los experimentos recibidos no acreditan disponibilidad histórica
ni validación prospectiva.

## Receta y configuración

La fuente ejecutable es `ml/configs/expanded-training.json` (`expanded-training-v2`). Sus parámetros vienen
de los informes de los veinte modelos; un override usa TRAINING_CONFIG_PATH y su
hash participa en la identidad del entrenamiento. Cambiar columnas o unidades
requiere otra versión de receta, no modificar silenciosamente expanded-v1.

`python -m scripts.export_model_contracts` sincroniza hashes y referencias desde
los artefactos canónicos, comprobando columnas, unidades, modos y candidatos.
No reescribe modelos, resultados ni CSV científicos. `--check` verifica sin
modificar y se ejecuta en CI. El diff generado se revisa junto con los modelos.

| Propiedad | Definición |
| --- | --- |
| Modelos/tareas | Cuatro regresores climáticos y uno de humedad; ocho tareas clima/suelo × horizonte |
| Horizontes | 7, 15, 30 y 60 días; objetivos agregados t+1..t+H |
| Entradas | Observaciones hasta t-2, ventanas 7/14/30 y variables estáticas/estacionales |
| Esquemas | 31 variables de clima; 52 de suelo |
| Espacio | Celdas originales agrupadas del AOI configurado; no precisión de parcela |
| XGBoost | hist, eta 0.03, alpha 0.1, seed 42, nthread 2; candidatos profundidad/peso mínimo/L2: (2,10,20), (3,5,10), (4,10,20) |
| Selección | Cuatro folds temporales; menor MAE agregado elige parámetros y mediana de sus mejores rondas fija árboles; máximo 800 y parada temprana 30 |
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
pública diaria de POWER/CMR no produce todavía todas estas tablas multisensor.
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

Cada objetivo deriva sus propias fechas disponibles: el 20 % final es test y
el desarrollo previo se purga contra su corte de observación. Sobre las fechas
elegibles de desarrollo se forman cuatro ventanas expansivas, con inicios de
validación en 40/55/70/85 %. Todas las celdas de una fecha permanecen juntas.
Las etiquetas de ajuste terminan antes del corte t-2 de validación; las de cada
bloque de validación terminan antes del siguiente corte. Ningún fold incluye test.

Cada objetivo evalúa los tres candidatos y selecciona por MAE agregado de sus
predicciones fuera de muestra. La mediana de mejores rondas de los cuatro folds
fija el número de árboles. El ajuste operativo usa todo el desarrollo elegible y
se congela antes de evaluar test. Se conservan las predicciones de CV, parámetros,
conteos y fronteras por objetivo junto con los modelos y sus hashes.

La comparación con persistencia usa las mismas etiquetas de CV y test. El campeón
se contrasta en test; no se compara sobre CV que pueda contener su propio ajuste.
Si el test se solapa con las etiquetas usadas para ajustar el campeón, la
publicación requiere una evaluación posterior independiente. Las ausencias de
una etiqueta climática no descartan las demás ni cambian su frontera temporal.

El Booster operativo guardado es el evaluado antes del test. A diferencia del
`model.json` científico reajustado con todas las filas, no se reajusta con etiquetas
del test. `trained_through` refleja el ajuste; `evaluated_through` refleja las
etiquetas examinadas y permite contar nuevas fechas sin confundir ambos conceptos.

Los mínimos se comprueban por objetivo y partición: 100 muestras de entrenamiento,
20 de validación, 20 de test y al menos dos ubicaciones. Un campeón requiere al
menos siete nuevas fechas etiquetadas por objetivo antes de reevaluar.

## Políticas y publicación

Las cotas MAE iniciales se toman de los baselines reportados por horizonte, en sus
unidades; son límites técnicos de referencia, no tolerancias agronómicas.
El candidato debe respetarlas y mejorar al baseline en CV y test y al campeón sobre test comparable por al menos el margen configurado (1 % inicial). No se exige publicar un modelo cada día.

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
