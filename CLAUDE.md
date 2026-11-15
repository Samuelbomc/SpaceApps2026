# Guía de trabajo para agentes

## Contexto y referencias

AgroGeo integra Angular, FastAPI, pipelines Python y XGBoost para análisis
agroclimático y evaluación de rotaciones. La documentación principal comienza en
[docs/README.md](docs/README.md). Consultar [producto](docs/product/overview.md),
[arquitectura](docs/architecture/overview.md), [estructura](docs/architecture/code-structure.md)
y [capacidades](docs/reference/capabilities.md) antes de ampliar un flujo.

## Reglas de implementación

- Inspeccionar el estado de Git y el código existente; preservar cambios ajenos.
- Respetar módulos, contratos y composition root; no introducir frameworks alternativos
  o reestructurar código sin una necesidad autorizada.
- Mantener Angular como frontend; API y pipelines tienen responsabilidades separadas.
- Ejecutar ingesta, entrenamiento e inferencia fuera de las consultas HTTP de análisis.
- PostgreSQL gestiona identidad, fincas, observaciones y calendarios; MongoDB registra
  resultados ML en Compose. La alternativa PostgreSQL de resultados es explícita.
  La geometría validada usa JSONB; esta implementación no requiere PostGIS.
- Mantener DTOs en packages/contracts y generar tipos/OpenAPI; no duplicarlos a mano.
- Configurar territorio y proveedores mediante datos/entorno; no atribuir al punto
  técnico de referencia el carácter de finca o piloto validado.
- Aplicar migraciones append-only y controles de concurrencia/idempotencia.
- No instalar dependencias innecesarias ni cambiar herramientas externas incidentalmente.

## Privacidad y rigor científico

- Autorizar recursos privados en backend por propietario; guards de UI no sustituyen autorización.
- No incluir credenciales, CSV privados ni entrevistas de fincas en Git o frontend.
- No mezclar mediciones privadas con entrenamiento regional sin autorización y validación.
- La recomendación de finca debe combinar inferencias, catálogo y contexto pertinente
  del agricultor; no confundir guardado del formulario con integración de modelos.
- Conservar fuentes, unidades, fechas de disponibilidad, resolución, calidad y versiones.
- No inventar observaciones, respuestas de proveedores, métricas o evidencia de validación.
- No aumentar resolución por interpolación ni usar predicciones como etiquetas reales.
- Respetar receta temporal, purga y reconstrucción residual; diferenciar experimento,
  candidato y campeón publicado. Una métrica favorable no sustituye revisión científica.
- Conservar estados pendientes y desconocidos; no forzar tres escenarios sin candidatos
  suficientes ni convertir secuencias condicionales en calendarios aprobados.
- No garantizar rendimientos, precisión local o validación comunitaria sin evidencia.

## Entrega y documentación

Seguir [CONTRIBUTING.md](CONTRIBUTING.md),
[ingeniería](docs/quality/engineering.md) y [verificación](docs/quality/verification.md).
Actualizar la guía principal afectada en presente, sin bitácoras o apéndices de
novedades. Mantener enlaces relativos y distinguir comportamiento implementado de
requisitos pendientes. Registrar evidencia del cambio en el pull request.

No usar operaciones Git destructivas, force-push ni reescritura de historia compartida.
No restaurar archivos ajenos para obtener un árbol limpio. Reportar las pruebas
realmente ejecutadas y sus límites; no afirmar despliegues o validaciones no realizados.
