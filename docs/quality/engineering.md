# Reglas de ingeniería y calidad

Estas son convenciones verificables del proyecto. No constituyen una certificación
externa ni garantizan por sí solas precisión científica o rendimiento productivo.

## Código y límites

- Python: Ruff fijado en el extra dev, reglas E4/E7/E9/F/I/UP y formato de 100 columnas,
  con objetivo de sintaxis Python 3.11. No silenciar errores de imports o variables sin justificación.
- Angular/TypeScript: comprobación estricta del compilador, build de producción y
  pruebas de comportamiento. Prettier sigue frontend/.prettierrc.
- Fixtures en pruebas o frontend/src/app/testing; ningún provider simulado se importa desde producción.
- Clientes externos obtienen datos; procesamiento valida; repositorios almacenan;
  pipelines orquestan; el código ML entrena/predice; HTTP consulta resultados.
- Configuración por entorno y dependencias inyectables. No instalar modelos o consultar NASA al importar HTTP.
- Los DTOs compartidos son Pydantic con campos extra prohibidos. Los tipos TS se generan, no se duplican a mano.

## Datos, modelos y trazabilidad

No se sustituyen ausencias por ceros, etiquetas por predicciones ni resolución
nativa por el tamaño del polígono. Se conservan fuente, fechas, unidades, estadística,
ámbito, calidad y versiones. Un CSV válido no es una medición científicamente validada.

Entrenar únicamente con etiquetas disponibles al corte. Las particiones agrupan
celdas por fecha, purgan solapamientos y reservan test fuera de la selección de
árboles. El archivo evaluado se conserva sin refit posterior. Los modelos residuales
incluyen la reconstrucción de baseline en entrenamiento, carga e inferencia.

Los snapshots y JSON tienen hashes; la publicación compara la versión activa
esperada. Un candidato peor o incompleto conserva el campeón. Modelos y recomendaciones
no cambian a validados por mostrar sus resultados en la interfaz.

## Persistencia y errores

Migraciones append-only, SQL parametrizado, revisiones optimistas de fincas y
locks separados para jobs. La selección MongoDB/PostgreSQL es explícita; no hay
fallback silencioso ni migración automática de datos entre ambos.

Los GET externos tienen reintentos acotados y el scheduler conserva el backoff.
No reintentar escrituras del usuario automáticamente. Los errores HTTP no exponen
credenciales ni cadenas de conexión. Los estados de negocio pendientes se distinguen
de errores técnicos y no se eliminan para aparentar un flujo completo.

## Controles obligatorios

CI verifica lint/formato, enlaces locales, aislamiento de fixtures, generación
de contratos, tests de backend con bases reales de prueba, cliente HTTP, pruebas
y build Angular. Los comandos están en [CONTRIBUTING.md](../../CONTRIBUTING.md).
Las integraciones nunca apuntan a las bases operativas.

Los controles excluyen herramientas externas y datasets de investigación del
formato de código propio. El código de terceros conserva su licencia y versión.
Las guías describen contratos en presente y enlazan una sola referencia de
capacidades. Git y los pull requests conservan el historial de cambios.
Ver [convenciones documentales](documentation.md).

Las versiones transitivas Python usan los rangos declarados actualmente; un lock
multiplataforma de producción y el endurecimiento del despliegue siguen en OPS-01.
No se afirma reproducibilidad binaria de dependencias que todavía no están bloqueadas.
