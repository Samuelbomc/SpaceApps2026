# Documentación de Field Shift

Referencia del producto, su implementación y sus límites de uso. Cada tema tiene
una guía principal; los README de los módulos enlazan esa guía. El historial de
cambios pertenece a Git y a las descripciones de los pull requests.

## Encontrar la información

| Necesidad | Documento principal |
| --- | --- |
| Comprender el producto y su alcance | [Producto](product/overview.md) |
| Entender sistemas, actores y dependencias | [Arquitectura](architecture/overview.md) |
| Ubicar una responsabilidad en el código | [Estructura del repositorio](architecture/code-structure.md) |
| Seguir el recorrido de datos y usuarios | [Flujos de ejecución](architecture/flows.md) |
| Comprender persistencia y versionado | [Almacenamiento](architecture/persistence.md) |
| Incorporar información de la finca | [Personalización](architecture/farm-personalization.md) |
| Conocer la distribución de servicios | [Despliegue](architecture/deployment.md) |
| Preparar el entorno | [Desarrollo local](guides/development.md) |
| Adquirir raster para los experimentos | [Adquisición de datos](guides/data-acquisition.md) |
| Operar workers o resolver fallos | [Operación y recuperación](operations/runbook.md) |
| Configurar conexiones, directorios y proveedores | [Configuración](reference/configuration.md) |
| Consultar alcance implementado y restricciones | [Capacidades y límites](reference/capabilities.md) |
| Verificar un cambio | [Verificación](quality/verification.md) y [aceptación de flujos](quality/acceptance.md) |
| Contribuir o mantener las guías | [Ingeniería](quality/engineering.md) y [documentación](quality/documentation.md) |

## Referencia técnica

| Área | Contratos y comportamiento |
| --- | --- |
| HTTP | [Superficie de API](reference/http-api.md), [DTOs](../packages/contracts/README.md) y [cliente compartido](../packages/api-client/README.md) |
| Datos NASA | [Consulta unificada](reference/nasa-query.md), [POWER](reference/nasa-power.md) y [soporte geoespacial](reference/geospatial.md) |
| Identidad y fincas | [Cuentas, ficha y CSV](reference/accounts-and-farms.md) |
| Procesos autónomos | [Calendario y jobs](reference/scheduler.md) |
| Modelos | [Entrenamiento](reference/model-training.md) e [inferencia](reference/model-inference.md) |
| Agronomía | [Catálogo](reference/agronomic-catalog.md) y [rotación](reference/crop-rotation.md) |
| Web | [Frontend Angular](reference/frontend.md) |
| Vocabulario | [Glosario](reference/glossary.md) |

## Métodos y evaluación de modelos

- [Componentes ML](reference/ml/components.md) y [datasets](reference/ml/datasets.md).
- [Evaluación a siete días](reference/ml/seven-day-results.md).
- [Evaluación a 15/30/60 días](reference/ml/horizon-results.md).
- [Modelo residual de humedad](reference/ml/moisture-model.md).

Las métricas describen los artefactos y las particiones indicadas en cada informe.
No constituyen una validación agronómica de las recomendaciones.

## Decisiones y convenciones

- [Límites de ejecución y publicación](architecture/decisions/0001-runtime-boundaries.md).
- [Organización y mantenimiento documental](quality/documentation.md): aplicación
  de Diátaxis, vistas C4 y cobertura de arquitectura basada en arc42.
