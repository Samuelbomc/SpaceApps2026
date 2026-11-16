# Producción en agrogeo.app

El checkout `spaceapps2026` se despliega con `compose.production.yaml`, proyecto
Compose `agrogeo`. El túnel Cloudflare existente del host apunta `agrogeo.app`
a `http://localhost:8082`; Nginx sirve Angular y publica solamente `127.0.0.1:8082` y envía
`/backend/*` a FastAPI dentro de la red Docker. No se necesita otro túnel.

Crear `.env.production` con permisos 0600 y una contraseña aleatoria en
`POSTGRES_PASSWORD`. El archivo está excluido de Git y del contexto Docker.
No regenerar la contraseña después de inicializar PostgreSQL.

```bash
bash scripts/deploy_production.sh
```

El script valida la configuración, construye las imágenes, espera los healthchecks
y comprueba `/backend/health` tanto en loopback como en HTTPS público.
La API aplica las migraciones antes de aceptar tráfico. PostgreSQL y MongoDB usan
volúmenes `agrogeo_postgres_data` y `agrogeo_mongo_data`; los uploads privados,
Parquet y artefactos operativos persisten en `./data`. Las bases no publican puertos.
Los servicios se reinician automáticamente con Docker.

```bash
docker compose --env-file .env.production -f compose.production.yaml ps
docker compose --env-file .env.production -f compose.production.yaml logs --tail 50
```

La ingesta se inicia al vencer el calendario durable. Los workers también atienden
actualizaciones manuales y análisis geográficos. El entrenamiento y las
recomendaciones usan la configuración científica y los artefactos del proyecto;
los estados pendientes o datos incompletos se informan en la API.
Se conserva la identidad `fieldshift` de las bases de esta instalación existente.
No ejecutar `down --volumes`: eliminaría los datos persistentes de producción.
