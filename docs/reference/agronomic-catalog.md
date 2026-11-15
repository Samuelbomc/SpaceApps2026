# Catálogo agronómico ECOCROP

La tabla compartida por el equipo está incorporada como 12 perfiles de cultivo
correspondientes a 11 especies ECOCROP. No es un dataset de etiquetas para
entrenar XGBoost: es conocimiento de referencia para contrastar condiciones
climáticas y de suelo con requisitos de los cultivos.

## Archivos y responsabilidades

| Ruta | Uso |
| --- | --- |
| `samples/agronomy/ecocrop-user.tsv` | Copia exacta de la tabla aportada, con las 38 columnas originales |
| `pipelines/processing/validation/crop_catalog.py` | Lectura TSV, decimales, faltantes, rangos y procedencia |
| `packages/contracts/agronomy.py` | Requisitos, catálogo y contratos de evaluación |
| `ml/configs/ecocrop.catalog.json` | Catálogo normalizado, versionado y empaquetado |
| `ml/recommendations/catalog.py` | Lectura validada independiente de HTTP o base de datos |
| `ml/recommendations/screening.py` | Comparación explicable de requisitos numéricos |
| `scripts/crop_catalog.py` | Importación, evaluación de un contexto y persistencia de borradores |
| `apps/api/app/routers/crop_catalog.py` | `GET /api/v1/crops/catalog`, lectura del catálogo |

Se conservan todas las columnas originales en `source_attributes`, además de los
campos normalizados. La versión identifica el archivo original, el esquema,
el normalizador y el contenido normalizado. Una modificación relevante produce
otra versión. Los códigos ECOCROP identifican especies y no sustituyen al
identificador del perfil comercial o variedad.

## Normalización y calidad

- Los decimales con coma se convierten en números: pH `4,5` se conserva como 4.5.
- `no input`, `sin dato` y guiones de ausencia se convierten en `null` en los
  campos opcionales. Un cero real, como la temperatura letal temprana de yuca,
  permanece como cero.
- Se valida `absoluto mínimo ≤ óptimo mínimo ≤ óptimo máximo ≤ absoluto máximo`.
  También se verifican pH, unidades, ciclo positivo y correspondencia entre
  código ECOCROP y URL de la ficha.
- Fríjol arbustivo y voluble conservan perfiles diferentes. Ambos usan la especie
  1668 y los mismos requisitos; no se inventan diferencias entre variedades.
- La altitud máxima ausente de ñame espino se mantiene desconocida.
- Las latitudes reportadas no incluyen hemisferios inequívocos en la tabla.
  Se conservan, pero no se utilizan como filtro de Antioquia ni se les asigna
  un signo por suposición.
- Profundidad, textura, fertilidad, drenaje y salinidad se separan en texto óptimo
  y absoluto. Luz, fotoperiodo, ciclo de vida, usos y clasificación Köppen original
  permanecen disponibles. No se traducen a números o categorías de suelo sin
  una correspondencia validada.

Las fichas oficiales consultadas permiten contrastar los rangos. Por ejemplo,
[maíz ECOCROP 238663](https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=238663)
identifica la lluvia como anual y
[Phaseolus vulgaris 1668](https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1668)
es la referencia compartida de los dos perfiles de fríjol. La revisión de enlaces
no equivale a validar una recomendación regional, un cultivar o una estrategia de
rotación. Los registros mantienen estado de revisión agronómica pendiente.

## Evaluación numérica implementada

`screen_catalog(catalog, context)` compara temperatura media, precipitación
anual, pH y el máximo de altitud disponible. Cada comprobación devuelve el valor,
unidad y explicación, con estado `optimal`, `within_absolute`,
`outside_absolute` o `unknown`.

El resultado de cada perfil es `within_checked_ranges`, `outside_checked_ranges`
o `insufficient_data`. Estos estados describen solo los requisitos comprobados;
no son un ranking de rentabilidad, porcentajes de éxito o aptitud integral.
Siempre se conserva `recommendation_ready=false` y `rotations_evaluated=false`.
No se fuerza una lista de tres cultivos cuando faltan condiciones o evidencia.

La temperatura incluye fechas, tipo histórico/pronóstico y procedencia. Un
pronóstico a 7/15/30/60 días se puede comparar como compatibilidad térmica del
periodo, pero no representa las condiciones de todo el ciclo del cultivo.
No se usa una media para evaluar heladas o temperaturas letales: eso exige
mínimos, exposición y fase fenológica.

La lluvia requiere un periodo histórico de 365/366 días, procedencia y cantidad
de días válidos. Si hay huecos queda desconocida. Un acumulado de siete días no
se multiplica por 365/7 ni se compara directamente con mm/año. Un total anual
tampoco representa la distribución estacional o el agua disponible por riego.
No se admiten observaciones históricas posteriores a la fecha de consulta.

## Uso

```bash
python -m scripts.crop_catalog
python -m scripts.crop_catalog --context data/contexto-real.json --report data/compatibilidad.json
```

El contexto debe satisfacer `CropScreeningContext`; no se incluye un archivo de
mediciones ficticias que la aplicación pueda confundir con una consulta real.
La API de catálogo permite al frontend leer requisitos sin ejecutar XGBoost.
El evaluador está separado del motor publicado para no presentar esta comparación
parcial como una recomendación de siembra validada.

Para persistir una versión inactiva en MongoDB:

```bash
MONGODB_URI=mongodb://127.0.0.1:27018 python -m scripts.crop_catalog --store-draft
```

El puerto 27018 corresponde a `scripts.dev_stack --with-mongo`; en Compose el
host de MongoDB es `mongo:27017`. Los borradores usan clave de versión y perfil,
no sustituyen un catálogo activo de otra versión y no generan recomendaciones.

## Integración y pendientes de aprobación

`ForecastRotationEngine` ya combina las cinco salidas de XGBoost con este catálogo,
reglas versionadas y restricciones explícitas del lote. El cierre común de
`CropRecommendationPipeline` persiste la evaluación junto a las inferencias;
`scripts/runtime.py` conecta ese evaluador. La comparación numérica independiente
es un diagnóstico parcial, distinto de una recomendación.

Las transiciones entre familias están implementadas como escenarios condicionales.
No representan un calendario anual aprobado. Faltan umbrales revisados de lluvia
y humedad por cultivo/horizonte, correspondencias de suelo y luz, fase fenológica,
riego, variedades locales y validación de reglas de sucesión, plagas y descansos.
No se deducen de mm/año ni se inventan al faltar. Los CSV privados conservan su
revisión y autorización; no se añaden automáticamente al análisis regional.

Ver [arquitectura de rotación](crop-rotation.md) y el pendiente AGR-01 en
[estado del proyecto](capabilities.md). La publicación de recomendaciones sigue
condicionada a modelos validados, requisitos completos y revisión agronómica.

Pruebas: conservación de perfiles y columnas, duplicados de especie, decimales,
faltantes, límites numéricos, unidades, periodos anuales, ventanas futuras,
contextos incompletos, procedencia, API y consistencia del catálogo generado.
