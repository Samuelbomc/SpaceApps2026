# Cliente compartido de FastAPI

Cliente Fetch sin React, Next.js, Angular ni dependencias de ejecución. Los tipos
proceden de `packages/contracts/api.generated.ts`; se regeneran con
`python -m scripts.export_openapi`, no se mantienen DTOs paralelos en cada UI.

Se distribuye como TypeScript dentro del monorepo, sin publicar en npm. El
bundler del frontend debe compilarlo. Ejemplo de alias en el `tsconfig` del
frontend, si está en `frontend/` o `apps/web/` respectivamente:

```json
{ "compilerOptions": { "paths": {
  "@field-shift/api-client": ["../packages/api-client/src/index.ts"]
} } }
```

Para `apps/web/`, la ruta es `../../packages/api-client/src/index.ts`.
El alias es una alternativa al enlace de paquetes locales; no requiere copiar
el código o agregar otra versión del contrato.

```typescript
import { createAPIClient, type AuthSession } from '@field-shift/api-client';

// Proxy del mismo origen: /backend/* → FastAPI /api/v1/*.
const client = createAPIClient({ baseURL: '/backend/' });
const session = await client.request<AuthSession>('auth/me');
const history = await client.loadObservationHistory('antioquia-reference');
await client.request('auth/logout', {
  method: 'POST', headers: { 'X-CSRF-Token': session.csrf_token }
});
```

También admite `baseURL: 'http://localhost:8000/api/v1/'` en desarrollo, con el
origen del frontend autorizado en `CORS_ORIGINS`. Las rutas de recursos son
relativas a esa base. El cliente incluye cookies, preserva `AbortSignal`, trata
204 sin JSON y conserva el status en `APIError`. No reintenta escrituras.

Para archivos, usar `FormData` con campo `file`; no establecer `Content-Type`
manualmente. Pasar `X-CSRF-Token` en la subida/eliminación. `download(path)`
devuelve un Blob autenticado y propaga errores de acceso. El consumidor decide
cómo descargarlo y revoca sus object URLs después del uso.

`loadObservationHistory` carga todas las páginas sin filtros de fechas y detecta
cambios de ingestión durante la lectura. No crea series o valores de ejemplo.

Las contraseñas y el CSRF no se guardan en almacenamiento persistente. La sesión
la administra el nuevo frontend en memoria; el identificador es una cookie
HttpOnly emitida por FastAPI. Una respuesta 401 permite mostrar login; no es un
error que deba ocultarse con datos sintéticos.

Pruebas independientes de cualquier frontend (Node con soporte TypeScript,
como Node 22.18+ o 24): `npm test --prefix packages/api-client`.
