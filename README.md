# Field Shift — NASA Space Apps 2026

Plataforma de análisis agroclimático para el Oriente antioqueño. Integra datos
NASA, modelos XGBoost por horizonte y evaluación de cultivos y rotaciones.
El frontend activo es Angular en `frontend/`; FastAPI expone resultados guardados.

**Estado:** los clientes NASA, el entrenamiento sobre datasets procesados y la
inferencia están implementados. Los artefactos recibidos son experimentales.
Los pronósticos actuales necesitan variables recientes completas y las
recomendaciones de siembra requieren modelos, catálogo y reglas revisados.
Consulta [el estado y los pendientes](docs/reference/capabilities.md).

## Inicio local

Python 3.11 o superior para backend; el entorno validado de desarrollo usa
Python 3.14 y Node 26. El lockfile npm del frontend está versionado.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install '.[api,storage,geospatial,local,mongo,ml,test,dev]'
npm ci --prefix frontend
python -m scripts.dev_stack --seed-reference --with-mongo
```

Se requiere `mongod` instalado para ese modo local. En macOS XGBoost necesita
el runtime OpenMP. El comando conserva las bases locales y no inicia workers.
Frontend: http://localhost:3000. API: http://localhost:8000/docs.
La CLI Python recibe variables del entorno; no carga `.env` automáticamente.

Con Docker, preparar `.env` a partir de [.env.example](.env.example) sin
sobrescribir una configuración existente y ejecutar:

```bash
docker compose up --build -d
```

Compose levanta las bases, API, web y tres workers. El motor Docker debe estar
activo. Ver [desarrollo y operación](docs/guides/development.md).

## Flujo y organización

```text
NASA → procesamiento → histórico/variables → candidato XGBoost
     → validación/publicación → inferencia → evaluación de rotación
     → resultados guardados → FastAPI → Angular
```

| Ruta | Responsabilidad |
| --- | --- |
| `apps/api/` | HTTP, autenticación, fincas y repositorios |
| `frontend/` | Aplicación Angular y mapa MapLibre |
| `pipelines/` | Ingesta, procesamiento, entrenamiento, recomendaciones y calendario |
| `ml/` | Recetas, modelos, validación, inferencia y reglas agronómicas |
| `packages/contracts/` | Contratos Python, OpenAPI y tipos generados |
| `packages/api-client/` | Cliente HTTP compartido y utilidades de datos/áreas |
| `infra/` | Migraciones SQL y contenedores |
| `scripts/` | Comandos operativos y herramientas de verificación |
| `modulo_rotacion/` | Adaptadores de entrevista y diagnóstico locales |
| `docs/` | Producto, arquitectura, guías, referencia, operación y calidad |
| `samples/` | Plantillas y muestras identificadas |
| `tests/` | Pruebas de contratos, integración y flujos |

Parquet conserva el histórico y los snapshots; JSON guarda los modelos.
PostgreSQL gestiona cuentas, fincas, observaciones y calendarios; MongoDB conserva
resultados y registro ML. El modo de resultados PostgreSQL es una alternativa
explícita de desarrollo. [Detalle de almacenamiento](docs/architecture/persistence.md).

El entrenamiento usa la receta de los veinte modelos: cinco objetivos por cada
horizonte de 7, 15, 30 y 60 días. Los candidatos se evalúan con separación temporal
y purga. Superar una métrica no sustituye la revisión científica de publicación.
[Contrato del entrenamiento](docs/reference/model-training.md).

## Documentación y verificación

Empieza por [el índice de documentación](docs/README.md). Incluye arquitectura,
happy path, estado real, contratos, operación y evidencia científica.

```bash
ruff check .
ruff format --check .
python -m scripts.check_repository
python -m scripts.verify_automation
npm test --prefix packages/api-client
npm test --prefix frontend -- --watch=false
npm run build --prefix frontend
```

La suite de automatización utiliza PostgreSQL y MongoDB temporales; necesita
`mongod` y los extras indicados. No usa las bases operativas. Las verificaciones
obligatorias están en [CONTRIBUTING.md](CONTRIBUTING.md) y en CI.

Las credenciales, CSV de fincas, bases locales y nuevas descargas no se añaden a
Git. Existen datasets y artefactos científicos previamente versionados por el
equipo: se conservan como evidencia, no como datos privados de usuarios.
