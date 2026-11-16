# Calidad de las funciones implementadas

Esta matriz describe el comportamiento del código y los límites de su verificación.
No convierte una integración parcial o un modelo experimental en una función
científicamente aprobada. La referencia de pendientes sigue en
[capacidades](../reference/capabilities.md).

## Comportamiento por función

| Función | Implementación y conducta esperada | Verificación |
| --- | --- | --- |
| Exploración pública | Mapa MapLibre, límites DANE, búsqueda y selección de geometría; acceso sin cuenta. | Pruebas Angular de geometría, búsqueda, límites y navegación; build estricto. |
| Cuenta | Registro, acceso, restauración de sesión, logout, cookie HttpOnly/Secure, CSRF y límites de intentos. | Integración PostgreSQL de cuentas; endpoints privados rechazan anónimos con 401. |
| Fincas y CSV | Autorización por propietario, revisiones optimistas, polígono persistido, validación de unidades y archivos, procedencia y descarga íntegra. | Pruebas reales de DB con dos propietarios, conflictos, límites y manipulación de archivos. |
| Análisis geográfico | POST valida y encola ubicación/polígono y horizonte; GET lee estado por UUID. Un worker recibe datos, prepara variables e infiere fuera de HTTP. | Contratos, cola PostgreSQL, fechas, referencias, recuperación e inferencia con fixtures identificados. |
| Datos NASA | POWER procesado y persistido; catálogos de productos y preparación puntual multisensor con reintentos y checkpoints. | Pruebas de calidad, persistencia, fechas y respuestas de proveedores inyectadas. Credenciales y capas estáticas condicionan la adquisición real. |
| Modelos | Constructor diario, validación temporal purgada, XGBoost, artefactos con hashes y promoción condicionada. Inferencia separada de HTTP. | Pruebas de particiones, fugas temporales, reconstrucción residual, publicación y contratos de cinco salidas. |
| Rotación | Evaluación ligada a predicciones y catálogo; mantiene estados provisionales y razones de rechazo. | Pruebas de requisitos, ventanas y persistencia. No certifica siembras ni rendimiento. |
| Automatización | Tres jobs periódicos, consumidor de actualizaciones manuales y consumidor geográfico; locks, progreso y backoff durables. | Pruebas de idempotencia, interrupciones, aislamiento de dependencias y reintentos. |
| Presentación | Vistas simple/técnica, fuentes, unidades, fechas y faltantes explícitos; cancelación de lecturas incompatibles. | Pruebas Angular y del cliente compartido. La compilación no sustituye una sesión real de navegador. |
| Producción | Nginx sirve Angular; API y bases internas; túnel a loopback 8082, datos persistentes y contextos relativos al checkout. | Validación Compose, nueve servicios en ejecución, checks HTTP públicos y backup PostgreSQL. |

La recuperación de contraseña y edición del perfil muestran su indisponibilidad;
no existen endpoints que permitan completarlas. La integración completa del contexto
privado del lote, la alimentación reciente multisensor y la aprobación científica y
agronómica conservan los criterios de aceptación documentados. No son funciones
completadas por el despliegue.

## Controles de calidad

Los controles incluyen Ruff, formato Python/Prettier, documentos y enlaces,
OpenAPI/tipos generados, contratos de modelos, tests Python con PostgreSQL/MongoDB
exclusivos de pruebas (293 tests aprobados), 105 pruebas Angular y 22 pruebas del
cliente aprobadas, y build de
producción Angular. Las pruebas de cuentas usan el directorio temporal del sistema
y funcionan en Linux sin depender de `/private/tmp` de macOS.

La verificación HTTP pública comprueba `/`, `/explorar`, `/acceso`, `/registro`,
`/backend/health`, `/backend/regions`, `/backend/automation` y
`/backend/crops/catalog` (200), además de `/backend/farms` y
`/backend/auth/me` sin sesión (401). No crea cuentas ni modifica fincas operativas.

PyMongo emite advertencias de recursos al terminar el proceso de pruebas por clientes
compartidos en caché que no se cierran explícitamente. La suite termina en OK; esto
no demuestra un ciclo de cierre completo ni sustituye la validación de recursos
bajo carga.

Los controles de software no certifican precisión prospectiva, aprobación de modelos,
cobertura de todos los sensores, interacción WebGL en navegador, restauración de
backups o rendimiento bajo carga. Esos criterios permanecen explícitos en
[aceptación](acceptance.md) y [operación](../operations/runbook.md).

## Higiene del repositorio

El inicio activo usa Hero, HowItWorks y Sources. Las cuatro secciones antiguas sin
imports se eliminan; no se alteran los componentes visibles. Se retiran 82 archivos
de metadatos macOS y una descarga `.crdownload` incompleta. Los datasets científicos,
artefactos, fixtures de pruebas y la distribución funcional WhiteboxTools con sus
licencias se conservan. `tools/` se excluye del contexto Docker porque no es una
dependencia de ejecución del servidor.

`.gitignore` y el verificador de repositorio excluyen/detectan metadatos y descargas
incompletas. Secretos, archivos privados, backups y datos operativos permanecen fuera
de Git. La limpieza no elimina volúmenes ni archivos de usuarios.
