# Verificación del sistema

Los controles comprueban contratos, comportamiento, integridad y persistencia.
La evaluación científica conserva un alcance distinto de las pruebas de software.

## Controles de código y contratos

```bash
ruff check .
ruff format --check .
python -m scripts.check_repository
python -m scripts.export_openapi --check
```

El verificador no navega fuentes externas ni consulta bases: revisa documentos
principales, títulos, bloques de código, enlaces locales, ausencia de bitácoras,
límites de fixtures y archivos que no deben versionarse.
`--check` comprueba el contrato generado sin modificar archivos.

## Pruebas de ejecución

```bash
python -m scripts.verify_automation
npm test --prefix packages/api-client
npm test --prefix frontend -- --watch=false
npm run build --prefix frontend
docker compose config --quiet
```

El primer comando crea PostgreSQL y MongoDB temporales y los elimina al finalizar.
Requiere mongod y los extras de desarrollo. Para servicios ya aislados se pueden
proporcionar TEST_DATABASE_URL y TEST_MONGODB_URI y ejecutar unittest discover.
Sin esos recursos algunas integraciones se omiten: no registrar ese resultado
como una validación completa de persistencia.

Se comprueban ingesta/reintentos, cuentas y archivos privados, muestras y cortes
temporales, purga por fecha/celda, entrenamiento/residual, lectura de artefactos,
publicación y rechazos, rotación y lectura HTTP. Los tests que permiten publicación
usan fuentes y revisiones sintéticas identificadas, nunca las bases operativas.

## Datos y modelos reales

```bash
python -m scripts.inspect_training \
  --region-id antioquia-reference --latitude 6.2442 --longitude -75.5812
```

El inspector valida las tablas recibidas y muestra conteos y particiones para
ocho tareas. Los modelos experimentales pueden ejecutar inferencias reales sobre
muestras históricas; esto verifica carga y receta, no generalización prospectiva.
Las métricas científicas originales están en [evaluación a siete días](../reference/ml/seven-day-results.md)
y [evaluación a 15/30/60 días](../reference/ml/horizon-results.md).

La comprobación de Compose valida configuración; no implica que los contenedores
se hayan construido o desplegado. La compilación Angular no sustituye la revisión
del recorrido en navegador. El flujo de aceptación con datos reales y recomendaciones
aprobadas se define en [aceptación](acceptance.md) y
[flujos de ejecución](../architecture/flows.md).
