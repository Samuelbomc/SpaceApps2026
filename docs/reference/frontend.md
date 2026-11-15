# Integración del frontend Angular

El frontend está en `frontend/`. FastAPI autentica, valida y consulta resultados.
La marca visual AndesTerra pertenece al frontend integrado de Field Shift.

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

Rutas públicas: `/`, `/explorar`, `/acceso`, `/registro` y `/analisis`.
Rutas de cuenta/finca: `/panel`, `/perfil`, `/fincas`, `/finca/lote` y
`/finca/caracterizacion`. `/login` redirige a `/acceso`.

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
