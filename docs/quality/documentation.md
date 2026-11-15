# Convenciones de documentación

La documentación describe contratos y comportamiento del sistema. Git conserva
el historial de cambios; los pull requests explican cambios concretos y su
validación. Las guías no contienen bitácoras, resúmenes de sesiones ni secciones
acumuladas de actualizaciones.

## Organización

Se aplican las categorías de [Diátaxis](https://diataxis.fr/): guías para ejecutar
tareas, referencia técnica y explicaciones de arquitectura. El inicio local
incluye el recorrido de incorporación. No es necesario crear documentos vacíos
para completar categorías.

La arquitectura usa vistas de contexto y contenedores basadas en
[C4](https://c4model.com/), además de estructura de código, ejecución y despliegue.
La cobertura de temas se apoya en [arc42](https://arc42.org/overview/): objetivos,
restricciones, contexto, estrategia, bloques, ejecución, despliegue, conceptos
transversales, decisiones, calidad, riesgos y glosario. Es una aplicación adaptada
al proyecto, no una certificación ni una reproducción de sus plantillas.

| Tema de arquitectura | Referencia principal |
| --- | --- |
| Objetivos y calidad del producto | [Producto](../product/overview.md) |
| Restricciones y riesgos | [Capacidades y límites](../reference/capabilities.md) |
| Contexto, estrategia y contenedores | [Arquitectura](../architecture/overview.md) |
| Bloques de código | [Estructura](../architecture/code-structure.md) |
| Ejecución | [Flujos](../architecture/flows.md) |
| Despliegue | [Servicios y redes](../architecture/deployment.md) |
| Conceptos transversales | [Persistencia](../architecture/persistence.md), [identidad](../reference/accounts-and-farms.md) y [entrenamiento](../reference/model-training.md) |
| Decisiones y consecuencias | [ADR de límites y publicación](../architecture/decisions/0001-runtime-boundaries.md) |
| Verificación | [Calidad](verification.md) |
| Vocabulario | [Glosario](../reference/glossary.md) |

## Contenido y fuente de verdad

- Un tema tiene un documento principal. Los README de módulos enlazan detalles.
- Escribir en presente y distinguir capacidad implementada, requisito y limitación.
- Evitar títulos de migración, corrección o novedades para comportamientos permanentes.
- Describir entradas, salidas, invariantes, errores, persistencia y punto de entrada.
- Mantener comandos desde la raíz del repositorio y requisitos verificables.
- Usar enlaces relativos, rutas reales y Mermaid para diagramas pequeños.
- No duplicar DTOs: enlazar contratos y OpenAPI generados. La configuración se
  contrasta con Settings, `.env.example` y Compose.
- Las fechas, versiones, hashes y métricas de datasets/modelos son procedencia
  técnica; conservan su significado y no se reescriben como novedades del proyecto.
- No publicar credenciales, rutas privadas de operadores ni datos de agricultores.

Las decisiones registran contexto, decisión y consecuencias. Un cambio de decisión
requiere revisión técnica; no se añade una bitácora a cada guía.

## Mantenimiento y controles

El autor de un cambio mantiene la guía de su componente y el contrato afectado.
La revisión de código comprueba coherencia entre implementación y documentación.
Los límites se concentran en [capacidades](../reference/capabilities.md), con
criterios observables de cierre.

```bash
python -m scripts.check_repository
python -m scripts.export_openapi --check
```

CI comprueba enlaces, documentos principales, límites de fixtures y contratos.
La verificación automática de enlaces locales no verifica enlaces externos,
exactitud científica ni coherencia semántica de todos los textos; esa revisión
corresponde al cambio y sus evidencias. Comandos de ejecución en
[verificación](verification.md).
