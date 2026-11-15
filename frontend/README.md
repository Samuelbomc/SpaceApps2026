# AgroGeo — frontend Angular

Frontend activo de AgroGeo, integrado con FastAPI y el cliente compartido
`packages/api-client`.

```bash
npm ci --prefix frontend
python -m scripts.dev_stack --with-mongo --with-workers
```

Desde esta carpeta, `npm start` escucha en 3000. El proxy de desarrollo reescribe
`/backend/*` a `/api/v1/*` en `API_INTERNAL_URL` (por defecto 127.0.0.1:8000).

Exploración (`/explorar`) reúne mapa, análisis actual y, con sesión, historial y
nuevas consultas. Es el destino por defecto al entrar. Rutas privadas: `/perfil`,
`/fincas` y `/finca/caracterizacion`. `/panel`, `/finca/lote` y `/analisis` mantienen
compatibilidad mediante redirecciones al explorador. Cuenta opcional mediante
`/acceso` (`/login` redirige) o `/registro`.
Las sesiones son reales con cookie HttpOnly; los guards esperan su restauración.
Los archivos de finca son privados. Recuperación de contraseña y modificación
del nombre de cuenta todavía no tienen endpoint y se muestran como no disponibles.

El mapa usa MapLibre; conserva su diseño, límites municipales y polígonos.
También permite colocar cuadrados por superficie en m², km² y ha. La geometría
GeoJSON se guarda completa junto al bbox; los registros antiguos siguen siendo
compatibles. Las condiciones y análisis se consultan por región con datos
disponibles; seleccionar un municipio no produce una inferencia por lote.

En Docker se sirve el build con Nginx y fallback SPA, y se conserva el proxy
`/backend/`. No se incluyen datos privados en el build.

```bash
npm run build --prefix frontend
npm test --prefix frontend -- --watch=false
npm test --prefix packages/api-client
```

Ver [el contrato del frontend](../docs/reference/frontend.md).
