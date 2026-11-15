# Integración del frontend Angular

El frontend está en `frontend/`. FastAPI autentica, valida y consulta resultados.
AgroGeo utiliza una identidad compartida en la navegación, los títulos y las páginas.

## Ejecución y conexión HTTP

```bash
npm ci --prefix frontend
python -m scripts.dev_stack --with-mongo
```

Angular escucha en `http://localhost:3000`. El proxy de desarrollo transforma
`/backend/*` en `/api/v1/*`; `API_INTERNAL_URL` selecciona FastAPI, por defecto
`http://127.0.0.1:8000`. En Compose, Nginx sirve el build con fallback SPA y el
mismo proxy. Los componentes usan `packages/api-client` y los tipos generados;
no deben construir conexiones directas a las bases de datos.

## Flujos y responsabilidades

| Flujo | Contrato y comportamiento |
| --- | --- |
| Cuenta | Registro, login, restauración y logout mediante HTTP y cookie HttpOnly; controles CSRF para mutaciones. Los guards esperan restaurar la sesión. |
| Fincas | Recursos privados autorizados por usuario; catálogo editable y CSV con validación de formato, unidades, revisión y procedencia. |
| Mapa | MapLibre, límites municipales, polígonos y cuadrados por superficie en m², km² o ha. Se persisten GeoJSON y bbox. |
| Análisis | Región compatible y horizonte 7/15/30/60. Consume resultados persistidos y pagina observaciones disponibles sin pedir fechas históricas al agricultor. |
| Presentación | Vista simple de resultados y vista técnica con procedencia, calidad, unidades y versiones. Respeta estados pendientes y alcance regional. |

Rutas públicas: `/`, `/explorar`, `/acceso` y `/registro`.
Rutas de cuenta/finca: `/perfil`, `/fincas` y
`/finca/caracterizacion`. `/login` redirige a `/acceso`. Los enlaces antiguos
`/panel`, `/finca/lote` y `/finca/analisis` abren el explorador público y conservan
los parámetros de consulta. `/analisis` redirige a `/explorar#resultados`.
Login, registro y el guard de invitados usan `/explorar` como destino por defecto;
un retorno interno explícito, como `/fincas`, conserva prioridad.

El inicio presenta el acceso al mapa, tres pasos de uso y las fuentes en un
desplegable. La navegación principal ofrece Exploración con y sin sesión;
la cuenta añade acceso a fincas privadas. Los campos opcionales de suelo y riego se agrupan en la ficha
de la finca; las coordenadas siguen disponibles para edición manual.

`/explorar` reúne búsqueda, municipio, delimitación opcional y análisis en una
misma página. En escritorio, la búsqueda y la lista de municipios se sitúan a la
derecha del mapa; los resultados ocupan todo el ancho debajo. En móvil, los
controles de ubicación preceden al mapa y los resultados lo siguen. El análisis
usa el desplazamiento de la página, sin altura limitada ni barra vertical interna.
El panel de análisis permanece montado mientras cambia o se carga el municipio;
espera una ubicación válida antes de consultar sus resultados.
La navegación ofrece Exploración como acceso al mapa y sus resultados integrados.
No se exige cuenta, formulario de finca ni confirmación intermedia para consultar
o delimitar. Los enlaces antiguos a `/acceso`, `/login` o `/registro` con
`volver=/finca/lote` saltan el formulario de cuenta y abren el mapa público,
conservando el código de municipio válido. Los retornos a fincas privadas sí
requieren sesión; un login explícito sin ese retorno sigue disponible.
El registro es una acción opcional para guardar información privada; conserva la
selección en memoria y vuelve a `/fincas` cuando se inicia desde esa acción.

Con sesión, **Nuevo análisis** inicia una consulta limpia dentro de Exploración:
restablece municipio, polígono, plazo y vista de resultados sin cerrar la sesión
ni borrar fincas o resultados almacenados. No dispara ingesta, entrenamiento ni
inferencia HTTP. Los resultados dependen de los datos y trabajos programados.

**Análisis anteriores** consulta bajo demanda
`GET /regions/{region_id}/analyses?limit=20`. Muestra los veinte registros más
recientes disponibles de esa ubicación; es un historial regional de resultados,
no un registro privado de consultas del usuario. La pantalla distingue carga,
ausencia y fallo, permite reintentar y cancela respuestas obsoletas al cambiar
ubicación o cerrar la vista. Al abrir un resultado se conservan su fecha objetivo,
corte de entradas, plazo, versiones y estado. No se muestran observaciones actuales
como entradas históricas. **Volver al análisis actual** restaura el periodo desde
el día de consulta. El cierre de sesión desactiva los controles de historial.

Con sesión, **Actualizar datos y modelos** solicita una actualización global de
las ubicaciones configuradas mediante `POST /automation/refresh`. La petición
encola trabajo y recibe `202`; no descarga ni entrena dentro de HTTP. La pantalla
consulta el progreso cada cinco segundos, muestra reintentos/limitaciones y relee
los datos tras las etapas que pueden haberlos actualizado. Una vista histórica
abierta conserva su fecha. Al salir se cancela la consulta del estado, sin cancelar
el trabajo ya aceptado. La consulta pública del mapa no requiere este botón.

Las ubicaciones de datos se filtran por la inclusión de su punto de referencia en
el municipio o polígono seleccionado. Esta coincidencia no acredita cobertura ni
personalización de parcela. Sin referencias coincidentes se muestra la ausencia;
consultar otras ubicaciones exige una acción explícita y se identifica su alcance.
Cambiar el área limpia resultados incompatibles e invalida consultas anteriores.
La API no recibe el polígono para ejecutar inferencias o recortes en tiempo real.

El globo permite acercarse hasta zoom 14, el máximo nivel de las teselas de
Sentinel-2 cloudless, con píxeles originales de 10 m. El mapa de delimitación
permite zoom 17 para dibujar; por encima del nivel 14 amplía la imagen y lo indica.
Las superposiciones de
color se atenúan al acercarse y la imagen local conserva sus colores y opacidad
completa para facilitar la orientación. El acercamiento no cambia la resolución
de los datos analíticos ni permite interpretar el fondo como un lindero catastral.

Resultados abre en nivel **Simple**, con el periodo, la última actualización,
las predicciones disponibles y los últimos valores válidos de todas las variables
observadas, agrupados en temperatura (mínima, media y máxima), lluvia y humedad,
y viento y radiación. Otras variables se presentan en un grupo adicional.
La selección se hace por fecha de observación, independientemente del orden de
recepción; conserva series separadas por fuente, unidad y resolución y omite
valores ausentes o descartados por calidad. Cada tarjeta identifica fuente,
fecha y ubicación de referencia; el nivel técnico añade código y resolución.
Los valores de distintas fechas mantienen su fecha individual. RH2M se presenta
como humedad relativa del aire a 2 m y WS10M como velocidad del viento a 10 m;
estas alturas no describen la resolución espacial ni humedad del suelo.
El periodo seleccionado permanece visible incluso si el área no tiene datos.
El estado de ausencia de predicciones expone su diagnóstico en un desplegable,
sin sustituir las salidas del modelo por observaciones históricas. Los
estados pendientes, experimentales y las evaluaciones provisionales permanecen
visibles. El nivel **Técnico** añade series, registros, métricas y trazabilidad;
los catálogos de modelos y cultivos se solicitan al abrirlo, sin bloquear la
consulta principal si fallan.

El mapa de un lote no activa automáticamente una ingesta privada ni demuestra
precisión a escala de parcela. Consultar resultados no descarga NASA, reentrena
ni ejecuta inferencias. Recuperación de contraseña y edición del nombre aún no
tienen backend; sus controles informan esa limitación.

## Contratos y pruebas

```bash
python -m scripts.export_openapi --check
npm test --prefix packages/api-client
npm test --prefix frontend -- --watch=false
npm run build --prefix frontend
```

Los dobles de autenticación viven exclusivamente en `src/app/testing/` y se
inyectan desde pruebas. El proveedor de producción es `HttpAuthGateway`; no hay
sesión de demostración ni credenciales privadas dentro del build.

Ver [contratos](../../packages/contracts/README.md), [desarrollo](../guides/development.md),
[cuentas y CSV](accounts-and-farms.md), [estado real](capabilities.md) y
[happy path](../architecture/flows.md).
