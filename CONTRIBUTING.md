# Contribuir a AgroGeo

Leer [el estado real](docs/reference/capabilities.md), [la arquitectura](docs/architecture/overview.md)
y [las reglas de ingeniería](docs/quality/engineering.md) antes de ampliar un flujo.
Trabajar en una rama de funcionalidad y describir comportamiento, validación y límites.

## Entorno y controles

```bash
python -m pip install '.[api,storage,geospatial,local,mongo,ml,test,dev]'
npm ci --prefix frontend
ruff check .
ruff format --check .
python -m scripts.check_repository
python -m scripts.export_openapi --check
python -m scripts.verify_automation
npm test --prefix packages/api-client
npm test --prefix frontend -- --watch=false
npm run build --prefix frontend
```

La suite completa necesita mongod; inicia bases temporales. CI usa servicios
PostgreSQL/MongoDB de prueba y ejecuta unittest con esas conexiones. Para formatos,
usar `ruff format .` y Prettier con la configuración de frontend. No formatear ni
modificar código externo de `tools/` como parte de cambios de la aplicación.

## Cambios revisables

- Mantener cada cambio ligado a un caso de uso; evitar refactors sin relación.
- Escribir pruebas que comprueben conducta, integridad o recuperación; no copiar la implementación.
- Generar OpenAPI/tipos después de cambiar contratos y verificar el diff.
- Agregar una migración nueva; nunca editar el contenido de una ya aplicada.
- Mantener la guía principal en presente; registrar cambios y evidencia en el pull request.
- Acompañar cambios de modelos o receta con fuentes, versión, métricas y procedimiento de reproducción.
- Reservar `ready` y las recomendaciones aprobadas para el flujo que cumple sus validaciones.

No incluir contraseñas, tokens, bases locales, archivos de fincas ni sus entrevistas.
Los fixtures se identifican como sintéticos y no se usan como datos operativos.
Las nuevas descargas permanecen fuera de Git; los datasets científicos ya
versionados no se borran como una limpieza incidental.

Seguir las [convenciones documentales](docs/quality/documentation.md).
