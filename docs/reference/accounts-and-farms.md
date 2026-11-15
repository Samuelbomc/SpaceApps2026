# Cuentas, fincas y datasets privados

Field Shift permite crear una cuenta, iniciar/cerrar sesión, registrar varias
fincas, editar su información y cargar mediciones históricas CSV. Cada recurso
se consulta y modifica con el propietario de la sesión; conocer el UUID de otra
finca o dataset no concede acceso. El mapa y las observaciones públicas de NASA
siguen disponibles sin cuenta y no incluyen las mediciones privadas.

## Acceso y persistencia

Rutas: `/registro`, `/acceso` y `/fincas`. La guía de
[desarrollo local](../guides/development.md) describe la instalación.
Las fincas y observaciones se guardan en PostgreSQL; los originales privados en
`data/farms`. La recuperación de una instalación necesita tanto la base como
los archivos y sus relaciones. Las bases nativas y de Compose son independientes.

## Registro e inicio de sesión

Son cuentas propias de Field Shift, no cuentas NASA Earthdata. No desbloquean
las descargas científicas protegidas ni solicitan credenciales Earthdata.

Las contraseñas se almacenan con **Argon2id**, con sal aleatoria y parámetros de
[argon2-cffi](https://argon2-cffi.readthedocs.io/en/stable/howto.html). Las sesiones
usan tokens aleatorios de 256 bits; PostgreSQL conserva únicamente su hash. La
cookie es HttpOnly, SameSite=Lax y host-only; caduca a los siete días y se revoca
al cerrar sesión. No se guardan credenciales ni tokens de acceso en localStorage.
Los cambios de sesión se notifican entre pestañas sin transmitir los tokens.

Las escrituras privadas requieren un token CSRF ligado a la sesión. También se
comprueba el origen y se restringe CORS a los orígenes configurados. Los intentos
de acceso y registro se limitan en PostgreSQL. Las respuestas privadas usan
`Cache-Control: no-store`; los errores de validación de estos formularios no
incluyen los valores enviados. Las páginas solo permiten ser enmarcadas por el
mismo origen y mantienen la política de referencia limitada al origen para
recursos externos. La gestión sigue los principios de
[sesiones OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

En localhost HTTP, `AUTH_COOKIE_SECURE=false`. Una instalación HTTPS requiere
`AUTH_COOKIE_SECURE=true` y `CORS_ORIGINS` con sus dominios exactos. El limitador
utiliza la dirección del cliente que ve FastAPI; no confía en cabeceras IP
reenviadas arbitrariamente en los comandos de arranque proporcionados. Tras un
proxy, varias cuentas pueden compartir ese límite de IP; una instalación externa
debe definir su configuración de proxies de confianza. Esta versión local no envía correo de confirmación,
no verifica propiedad del correo, no incluye recuperación por correo ni MFA.
No se presenta como un servicio público desplegado.

## Catálogo de fincas

La ficha guarda nombre, municipio/vereda, coordenadas, superficie, altitud
opcional, textura y pH del suelo, tipo de riego, cultivos actuales y notas. Los
valores no conocidos pueden permanecer sin especificar. El catálogo de opciones
se sirve desde FastAPI; no contiene reglas agronómicas que inventen recomendaciones.

El propietario puede delimitar el área con el mapa. Sus límites se guardan como
bbox WGS84, y la superficie que propone el navegador es aproximada y editable.
El centro debe estar dentro del área. Escribir coordenadas manualmente reemplaza
el límite por un punto. Al crear una finca, las coordenadas comienzan vacías:
no se guarda silenciosamente el punto público de Medellín como su ubicación.

Cada edición incrementa `revision`. Una escritura basada en una revisión vieja
produce 409 para evitar sobrescribir cambios de otra ventana. La ficha describe
la revisión actual; no reconstruye propiedades históricas de la finca.

## Carga CSV

La interfaz descarga una plantilla **sin valores ficticios**. Columnas:

```csv
date,variable,value,unit,crop
```

`crop` es opcional si se omite esa columna completa; cuando figura en el encabezado,
se conserva una celda vacía en las filas a las que no aplique. Se admite coma o
punto y coma como separador, UTF-8 con o sin BOM, fecha `AAAA-MM-DD` y punto decimal.
El rendimiento de cosecha exige identificar el cultivo.

| Variable | Unidad exacta | Significado |
| --- | --- | --- |
| `air_temperature` | `C` | Temperatura media del aire en el día |
| `relative_humidity` | `%` | Humedad relativa media del aire, 0–100 |
| `precipitation` | `mm` | Precipitación acumulada del día, no negativa |
| `soil_moisture` | `m3/m3` | Humedad volumétrica del suelo, 0–1 |
| `soil_ph` | `pH` | Observación de pH, 0–14 |
| `crop_yield` | `t/ha` | Rendimiento de la cosecha identificada, no negativo |

Límites locales: 5 MiB y 20.000 filas por archivo, 20 datasets por finca y 20 fincas
por cuenta. Solo se aceptan CSV; no se ejecutan archivos ni se descomprimen
contenedores. Hay límites de cuerpo HTTP antes del parseo y validación del
contenido independientemente del MIME anunciado. Fechas futuras, valores no
finitos, unidades incorrectas o filas repetidas rechazan la carga completa.

La carga validada conserva el CSV original fuera de las carpetas públicas y
normaliza sus observaciones en PostgreSQL en una transacción. Cada archivo tiene
UUID, SHA-256, fechas, variables, cantidad de filas y fecha de incorporación.
Reenviar exactamente el mismo contenido a la misma finca no lo duplica. La descarga comprueba que el archivo conserve su SHA-256 original. Descargar
y eliminar requieren la sesión propietaria; eliminar retira las observaciones
asociadas y el archivo. El borrado se confirma en la interfaz.

**Formato válido no equivale a medición verificada.** Se conservan el origen
`LOCAL_FARM`, la calidad `format_validated_unverified` y las fechas del calendario
local de Colombia. Las observaciones NASA permanecen separadas. La estrategia
se apoya en [validación y almacenamiento de archivos OWASP](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).

## Preparación para los modelos

La ficha y las mediciones son insumos de la recomendación personalizada. El uso
previsto, la integración actual y sus criterios de cierre se detallan en
[contexto de finca](../architecture/farm-personalization.md). Esta personalización debe combinar
las inferencias con las condiciones e historial del lote, además del catálogo.

`FarmDatasetService.bundle(owner, farm_id, cutoff)` implementa el puerto
`FarmContextProvider`. Obtiene una lectura consistente de:

- La revisión de la ficha de la finca.
- Observaciones locales anteriores o iguales al corte.
- Identidades, hashes y fechas de los datasets utilizados.
- Fechas/variables/cultivos solapados entre archivos que deben revisarse.

El conjunto incluye una huella de entradas reproducible. Cambiar la ficha,
incorporar o eliminar observaciones cambia su identidad. El endpoint privado
`model-context` devuelve el resumen y limitaciones, sin rutas internas del disco.

Actualmente `model_ready=false` y `nasa_status=not_ingested_for_farm`. Los clientes
NASA y el predictor regional no utilizan automáticamente estos archivos. Para
conectar un modelo de finca hay que ingerir NASA para su ubicación real, alinear
resoluciones y fechas locales/UTC, resolver solapamientos, definir profundidad y
método de medición cuando corresponda, construir variables y evaluar el modelo.
No se utiliza el punto de referencia público como sustituto silencioso de una
finca ni se garantiza una mejora de precisión por el simple hecho de cargar CSV.
Tampoco se entrena un modelo compartido entre agricultores de forma automática.

## Endpoints privados

| Método/ruta | Uso |
| --- | --- |
| `POST /api/v1/auth/register` | Crear cuenta y sesión |
| `POST /api/v1/auth/login` | Iniciar sesión |
| `GET /api/v1/auth/me` | Cuenta y token CSRF de la sesión |
| `POST /api/v1/auth/logout` | Revocar sesión y borrar cookie |
| `GET /api/v1/farms/catalog` | Opciones de ficha, variables y límites CSV |
| `GET/POST /api/v1/farms` | Listar propias / registrar finca |
| `GET/PUT /api/v1/farms/{id}` | Consultar / editar con `?revision=N` |
| `GET/POST /api/v1/farms/{id}/datasets` | Listar / cargar CSV multipart |
| `GET /api/v1/farms/{id}/datasets/{dataset}/download` | Descargar original autorizado |
| `DELETE /api/v1/farms/{id}/datasets/{dataset}` | Eliminar archivo y observaciones |
| `GET /api/v1/farms/{id}/model-context` | Inspeccionar preparación de entradas |

OpenAPI y los tipos TypeScript se generan desde los DTOs de cuentas y fincas.

## Verificación del contrato

Las pruebas comprueban hashes, cookies, revocación, caducidad, CSRF, límites,
aislamiento de propietarios, edición con revisión, idempotencia y validación CSV.
También verifican integridad de descargas y cambios de identidad del contexto al
editar la ficha o incorporar/eliminar mediciones. Las pruebas de persistencia
utilizan PostgreSQL aislado. Procedimiento en
[verificación](../quality/verification.md).
