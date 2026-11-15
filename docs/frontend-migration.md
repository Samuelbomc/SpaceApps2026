# Sustitución del frontend — contexto para el equipo

## Estado de la preparación

- Rama de trabajo: `codex/prepare-frontend-migration`, basada en `main` remoto
  `bb1ceb9`. No se han integrado ni eliminado archivos del frontend entrante.
- Rama del nuevo frontend: `origin/feature/agricultural-platform-frontend`.
- Commit inspeccionado: `38f010b3520f15e1acf6810b40086387231a1d2b`.
- Frontend entrante: Angular en `frontend/`, con MapLibre GL; script `start`
  (`ng serve`, puerto habitual 4200). La rama ya está descargada como referencia,
  pero todavía no se ha fusionado ni activado en esta preparación.
- Frontend que se retirará: `apps/web/` (Next.js). Actualmente sigue operativo.
- La rama entrante amplía el Angular que ya existía en main; es la referencia
  para preservar el diseño del equipo, no una plantilla que se deba sobrescribir
  con las pantallas Next.js.
- FastAPI, cuentas, fincas, CSV privados, bases, pipelines y modelos permanecen
  independientes del framework de UI. No necesitan migrarse a otra base.
- Los módulos recientes `modulo_rotacion/` y los datasets añadidos por el equipo
  no quedan automáticamente expuestos por FastAPI. Integrarlos es otro trabajo;
  no se deben presentar sus archivos de ejemplo como respuestas del backend.

## Preparación ejecutable

El cliente HTTP e histórico se trasladaron a `packages/api-client/`, con tipos
del OpenAPI compartido, URL base configurable, cookies, errores, cancelación,
multipart y descarga de archivos. `apps/web/src/lib/api.ts` solo conserva un
adaptador compatible mientras se retira Next.js. Su Dockerfile copia el paquete
compartido; el futuro frontend debe hacer lo mismo.

El stack local permite arrancar el backend sin Next.js:

```bash
python -m scripts.dev_stack --with-mongo --api-only
```

Para ensayar un frontend que tenga un script npm `start` en `frontend/`, ya
configurado para escuchar en 4200:

```bash
python -m scripts.dev_stack --with-mongo --web-directory frontend --web-script start --web-port 4200
```

Instalar sus dependencias con su propio lockfile antes de arrancar. `--web-port`
indica el puerto que usa el script; no cambia mágicamente el puerto del framework.
El launcher autoriza los orígenes locales de ese puerto para CORS y CSRF. Con
`--api-only`, exportar `CORS_ORIGINS` antes de arrancar si se usará otro puerto.
El comportamiento por defecto sigue siendo el frontend actual en 3000.
No se detienen servicios ajenos ni se activa el worker como efecto de la prueba.

## Frontera HTTP y autenticación

FastAPI sirve `/api/v1/*`. `/backend/*` es el alias de proxy que tenía Next.js;
no es una ruta que exista directamente en FastAPI. Elegir **una** estrategia:

1. Preferida al desplegar: frontend y API bajo el mismo origen, con proxy
   `/backend/` → `http://api:8000/api/v1/`. El snippet
   `infra/docker/frontend-api.conf` puede incluirse en el servidor Nginx del
   frontend nuevo. Admite el CSV multipart de hasta 5 MiB y no cachea respuestas
   privadas. No es una imagen de despliegue completa del frontend pendiente.
2. Desarrollo directo: cliente con base `http://localhost:8000/api/v1/`, y
   `CORS_ORIGINS` incluyendo exactamente `http://localhost:4200` (u origen real).
   Usar el mismo hostname en web y API; no mezclar `localhost` con `127.0.0.1`.

No cambiar las rutas del backend para adaptarlas a rutas visuales. El servidor
debe conservar `Origin`, `Set-Cookie` y `X-CSRF-Token`; no sustituir el origen de
la UI por uno artificial para eludir CSRF. En producción configurar el origen
HTTPS real en `CORS_ORIGINS` y `AUTH_COOKIE_SECURE=true`.

### Flujo privado a portar

- `POST auth/register` / `POST auth/login`: JSON; devuelven `FarmerSession` y cookie.
- `GET auth/me`: restaura sesión y CSRF después de recargar. Un 401 significa
  que no hay sesión; no inventar un usuario de demostración.
- `POST auth/logout`: encabezado `X-CSRF-Token`; 204 sin cuerpo.
- Guardar el CSRF solo en memoria y adjuntarlo en escrituras privadas. La cookie
  es HttpOnly; no intentar leerla, copiarla o guardarla en localStorage.
- Tras logout limpiar los datos privados de la UI. Manejar 401, 403, 404 y 409.
- No permitir que una respuesta atrasada de otra sesión sustituya al usuario
  actual; cancelar peticiones al cambiar usuario o desmontar pantallas.

Las validaciones completas de campos están en OpenAPI y
[farmer-accounts.md](farmer-accounts.md). Los datos de fincas se autorizan siempre
en FastAPI, no mediante un filtro de propietario en el navegador.

## Contratos de las pantallas

Todas las rutas de esta tabla son relativas a `/api/v1/` o la base del cliente.

| Pantalla | Rutas y comportamiento que hay que conservar |
| --- | --- |
| Estado | `GET health`, `status`, `automation`; no confundir liveness con disponibilidad de todas las fuentes |
| Territorio | `GET regions`, `places/reverse?latitude=&longitude=`; el lugar sigue el centro del mapa, no el GPS del dispositivo |
| Histórico | `GET regions/{id}/observations?limit=1000&offset=0`; paginar todo, mostrar `last_updated_at`, distinguir valor cero de nulo |
| Predicciones | `GET regions/{id}/latest-analysis?horizon_days=7&as_of=YYYY-MM-DD`; horizontes 7/15/30/60 desde la consulta en America/Bogota |
| Análisis almacenado | `POST analyses` consulta un resultado; no ejecuta entrenamiento ni ingesta |
| Catálogo agronómico | `GET crops/catalog`; contiene requisitos con revisión pendiente, no cultivos recomendados automáticamente |
| Fincas | `GET/POST farms`, `GET farms/catalog`, `GET farms/{id}`, `PUT farms/{id}?revision=N`; 409 exige recargar antes de guardar |
| CSV privados | `GET/POST farms/{id}/datasets`; subida con campo multipart `file`, duplicado identificado explícitamente |
| Descargar/eliminar CSV | `GET farms/{id}/datasets/{dataset_id}/download`, `DELETE farms/{id}/datasets/{dataset_id}`; permisos y CSRF en el servidor |
| Entradas de la finca | `GET farms/{id}/model-context`; procedencia y `model_ready=false` mientras falte preparación científica |

Estados de análisis: `pending_model`, `pending_run`, `insufficient_data`,
`pending_recommendations`, `ready`. `latest-analysis` puede responder `null`.
La UI debe representar estas situaciones sin fabricar temperaturas, porcentajes,
recomendaciones o rotaciones. XGBoost y sus adapters agrícolas siguen pendientes
de conectar; este cambio de frontend no los activa.

La fecha de consulta, corte de observaciones e instante de actualización tienen
significados diferentes. Los datos históricos no se recortan a 7/15/30/60 días.
La selección del mapa se expresa como superficie en m²/km²/ha; 1000 m² son un
cuadrado de unos 31,62 m de lado. Geocodificar el centro o dibujar un área no
consulta automáticamente datos NASA para esa parcela.

## Diferencias comprobadas en la rama entrante

La inspección se hizo sobre el commit anterior, sin asumir que sus mocks estén
conectados al backend porque ya existan las pantallas.

| Archivo o flujo entrante | Adaptación necesaria |
| --- | --- |
| `frontend/src/app/app.config.ts` | Sustituir el provider `MockAuthGateway` por el gateway real que consuma el cliente compartido |
| `core/auth/auth-gateway.ts` | `restore()` es síncrono; debe ser asíncrono para consultar `GET auth/me` y esperar la restauración antes de resolver guards |
| `core/auth/auth.service.ts` y guards | Añadir estado de carga/error y controlar respuestas atrasadas; no asumir una sesión demo desde sessionStorage |
| `core/auth/auth.models.ts` | Mapear `display_name` del servidor a `name` de la UI; conservar el CSRF en memoria; `isDemo=false` solo con sesión real |
| Registro | Enviar `display_name`, email y password; alinear la contraseña con el mínimo real de 15 caracteres y los errores 422/409 |
| Perfil | El backend actual no tiene endpoint para cambiar nombre/correo; no mostrar éxito de una edición solo local |
| Recuperar contraseña | No existe endpoint de recuperación ni envío de correos: la pantalla no puede anunciar un correo enviado |
| `core/journey/analysis-journey.store.ts` | Municipio, lote y progreso viven únicamente en memoria; no afirmar persistencia tras recargar hasta conectarlos a fincas reales |
| `features/farm/plot/` | El nuevo mapa dibuja polígonos GeoJSON; `FarmWrite.boundary` actual admite un bbox, no un polígono arbitrario. No descartar vértices silenciosamente ni tratar el bbox como el contorno exacto |
| Caracterización | La pantalla es `StepPlaceholder`; hay campos básicos de suelo/cultivos en FarmWrite, pero no persistencia HTTP completa del cuestionario de `modulo_rotacion/` |
| Análisis | La pantalla es `StepPlaceholder`; conectar resultados almacenados y los estados pendientes, sin fabricar pronósticos |
| CSV privados | Incorporar a Angular subida/lista/descarga/eliminación antes de retirar la pantalla equivalente de Next.js |
| Mapas y geometría | Preservar MapLibre, límites municipales y validaciones del nuevo diseño; decidir y documentar la representación geográfica persistida |

Estos puntos impiden reemplazar solo el provider de autenticación y afirmar que
la migración completa está resuelta. Se pueden abordar por etapas en esta rama
manteniendo el frontend actual hasta cubrir los flujos reales.

Referencias listas para comparar sin modificar archivos del compañero:

```bash
git fetch origin feature/agricultural-platform-frontend
git log --oneline origin/feature/agricultural-platform-frontend -3
git diff --stat origin/main...origin/feature/agricultural-platform-frontend -- frontend pipelines/ingestion/sources/colombia
```

## Recepción e integración de la rama entrante

1. Registrar nombre, SHA de la rama entrante, framework, carpeta, versión Node,
   script de arranque, puerto, rutas visuales y estrategia de proxy.
2. Con Git limpio, comparar su diff con main. Integrar la rama en esta rama de
   preparación, resolver conflictos conservando el backend y los datos del equipo.
   No aplicar un `checkout` masivo que sobrescriba contratos o migraciones.
3. Conectar un único servicio de acceso al cliente compartido. En Angular puede
   inyectarse `createAPIClient` en un servicio propio; en otro framework usar su
   mecanismo equivalente. El diseño y componentes son los del frontend entrante.
4. Sustituir sus mocks por las respuestas reales de FastAPI, conservando estados
   vacíos y de error. Comprobar cookies/CSRF desde el origen real de la nueva UI.
5. Verificar los casos de aceptación de abajo. Registrar también los módulos
   del diseño entrante que todavía no tienen endpoint, sin inventar integración.
6. Cuando el nuevo frontend sustituya los flujos necesarios, eliminar los
   archivos versionados de `apps/web/` con `git rm -r -- apps/web` en esta rama.
   Actualizar el Dockerfile web, Compose, defaults del launcher y documentación
   a la carpeta definitiva. No conservar dos frontends activos por defecto.
7. Comprobar las referencias residuales con
   `rg 'apps/web|next dev|next start|next build' scripts infra docker-compose.yml README.md docs`.
   Las menciones históricas de la migración pueden permanecer documentadas.
8. Compilar y probar desde una copia limpia antes de integrar a main. No borrar
   datos locales, cuentas, paquetes compartidos o el otro frontend como parte de
   la retirada de Next.js. Revertir el commit de sustitución permite recuperar la
   UI anterior sin revertir las migraciones o borrar bases.

## Casos de aceptación para completar el cambio

- Acceso público sin sesión; cambio de nombre del centro del mapa y selección
  cuadrada con equivalencia entre m², km² y ha.
- Histórico completo, actualización real, ausencia de datos y error de API.
- Los cuatro horizontes envían el periodo correcto y muestran modelos pendientes.
- Registro, login, recarga con sesión, logout y acceso privado denegado después.
- Dos usuarios no pueden leer ni modificar las fincas o archivos del otro.
- Crear/editar finca y resolver conflicto de revisión sin sobrescribir cambios.
- CSV válido, duplicado, inválido y demasiado grande; descarga y eliminación.
- Cookies/CSRF reales a través del nuevo proxy, no solo requests directos de tests.
- Vista móvil, teclado, navegación y estados simples/técnicos del diseño nuevo.
- Sin importaciones de Next/React en el cliente compartido ni dependencias
  runtime del backend respecto al frontend retirado.

Pruebas disponibles: `npm test --prefix packages/api-client`,
`npm test --prefix apps/web` durante la transición, `python -m scripts.verify_automation`
y generación/verificación del contrato con `python -m scripts.export_openapi`.
Las pruebas de navegador deberán ejecutarse sobre el frontend entrante cuando
esté disponible; las actuales no demuestran que ese diseño futuro esté integrado.
