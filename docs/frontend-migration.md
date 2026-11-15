# Migración del frontend completada

Rama de integración: `feature/prepare-frontend-migration`.
Frontend recibido: `feature/agricultural-platform-frontend`, commit `38f010b`.
Se conservaron el diseño Angular, el explorador MapLibre, los límites municipales
DANE y el flujo de municipio y lote. Se integró también main sin borrar los
avances del equipo en datos, modelos experimentales o rotaciones.

## Organización vigente

- `frontend/`: único frontend activo, Angular. El código Next.js de `apps/web/`
  fue eliminado; no requiere React ni Next para arrancar o compilar.
- `packages/api-client/`: cliente Fetch compartido, tipos del OpenAPI, histórico
  paginado, descarga de archivos, conversión de superficies y utilidades de series.
- `apps/api/`: FastAPI mantiene cuentas, permisos, fincas y archivos privados.
- `infra/docker/web.Dockerfile`: compilación Angular y servidor Nginx con fallback
  SPA. `frontend-api.conf` reescribe `/backend/` a FastAPI `/api/v1/`.
- `frontend/proxy.conf.cjs`: mismo contrato de proxy en desarrollo.

## Flujos conectados

El provider de producción es `HttpAuthGateway`, no `MockAuthGateway`. Los mocks
solo se usan como fixtures de las pruebas anteriores. Registro y login envían
las credenciales a FastAPI; el servidor conserva el hash de contraseña y emite
cookie HttpOnly. El CSRF se conserva en memoria y se adjunta en las escrituras.
Los guards esperan `GET auth/me` antes de decidir si hay sesión. Se comprueba
la sesión al recuperar el foco; los datos del recorrido se limpian al cambiar
entre usuarios. El formulario de registro exige 15 caracteres como el backend.

`/panel` enlaza a `/fincas`. Allí se crean y editan las fincas reales con revisión
optimista, coordenadas, superficie, suelo, pH, riego, cultivos y notas. Se cargan,
descargan y eliminan CSV privados, con plantilla y límites del servidor.
`/finca/caracterizacion` usa este mismo formulario en el recorrido del mapa.

El mapa nuevo permite dibujo libre y cuadrados por superficie en m²/km²/ha.
El polígono confirmado alimenta el formulario. FastAPI admite el campo opcional
`geometry` y conserva todos sus vértices; valida cierre, límites, intersecciones
y correspondencia con el bbox. Las fincas antiguas sin polígono siguen funcionando.
No se requiere una migración SQL: los perfiles se guardaban como JSONB. La versión
del contrato OpenAPI y los tipos TypeScript se actualizaron juntos.

`/analisis` es público; `/finca/analisis` también está disponible en el recorrido
privado. Ambas rutas usan observaciones y resultados realmente almacenados.
Se conservaron los horizontes 7/15/30/60 desde la fecha de consulta en Colombia,
la carga de todo el histórico, la última actualización, vista técnica, series,
paginación y trazabilidad. Los cortes por falta de datos rompen las líneas del
gráfico en lugar de inventar valores. Se muestra el catálogo ECOCROP como requisitos
de referencia con su estado de revisión, separado de recomendaciones publicadas.

## Límites que siguen explícitos

- Editar el nombre de cuenta y recuperar contraseña no tienen endpoints; esas
  pantallas no anuncian cambios guardados o correos enviados.
- La caracterización conecta los campos reales de FarmWrite, no todo el
  cuestionario avanzado de los scripts `modulo_rotacion/`.
- Seleccionar un municipio o guardar un polígono no crea una ingesta NASA ni un
  pronóstico para esa finca. El análisis identifica la región disponible consultada.
- Los modelos experimentales de main ahora tienen un adapter y job conectados
  para 7, 15, 30 y 60 días. No se publican automáticamente en el registro operativo.
  La UI conserva estados reales y muestra variables faltantes. Ver
  [integración XGBoost](xgboost-integration.md).
- Guardar observaciones de una finca no constituye consentimiento de entrenamiento
  ni validación científica de esas mediciones.

## Arranque

```bash
npm ci --prefix frontend
python -m scripts.dev_stack --with-mongo
```

Frontend: http://localhost:3000. API: http://localhost:8000/docs.
Se conservan las bases persistentes y archivos privados existentes. El worker
no se activa como efecto de este comando. Para un backend sin UI: `--api-only`.
También siguen disponibles `--web-directory`, `--web-script` y `--web-port` para
ensayos, pero por defecto se usa `frontend/`, `start` y 3000.

El proxy conserva Origin, cookies y CSRF. Al desplegar configurar el origen real
en CORS_ORIGINS y cookie Secure con HTTPS; no desactivar las validaciones para
hacer funcionar el navegador. Compose mantiene la URL de la web en el puerto 3000.

## Validación

- Build Angular de producción y suite Angular con sus pruebas originales adaptadas
  a guards asíncronos, más pruebas nuevas de HttpAuthGateway.
- Cliente compartido probado sin depender del frontend retirado; las pruebas de
  histórico, geometría y calidad se trasladaron junto con sus funciones.
- Suite Python con PostgreSQL y MongoDB aislados, incluida persistencia y edición
  del polígono completo y rechazo de geometrías inválidas.
- Chrome aislado con FastAPI y PostgreSQL temporal: registro, login, recarga de
  sesión, creación y edición de finca, CSV, descarga/eliminación, histórico
  técnico, horizonte de 30 días, logout y guard de acceso privado.
- Vista de fincas a 390 px sin desbordamiento horizontal. Las capturas y cuentas
  de QA no se guardaron en el repositorio ni en las bases operativas.

```bash
npm run build --prefix frontend
npm test --prefix frontend -- --watch=false
npm test --prefix packages/api-client
python -m scripts.verify_automation
```

La retirada es reversible desde el historial Git, sin borrar bases ni revertir
migraciones. El frontend viejo no queda como una segunda aplicación activa.
