# Producto y alcance

AgroGeo es una plataforma de análisis agroclimático y apoyo a la selección de
cultivos y rotaciones para NASA Space Apps Challenge. Combina observación terrestre,
modelos XGBoost, requisitos agronómicos y conocimiento del agricultor.

## Usuarios y necesidades

| Usuario | Necesidad |
| --- | --- |
| Agricultor | Consultar condiciones, registrar su finca y comprender alternativas de siembra |
| Profesional agronómico | Revisar datos, requisitos, restricciones y razones de cada evaluación |
| Investigador o integrante del equipo | Inspeccionar procedencia, recetas, métricas y versiones |

La interfaz utiliza español y ofrece niveles de detalle simple y técnico. El
análisis expresa incertidumbre, faltantes y soporte espacial de las fuentes.

## Ámbitos del producto

La exploración pública permite consultar territorios, fuentes y resultados
regionales almacenados. El espacio privado permite registrar fincas y mediciones,
con autorización por propietario. La recomendación personalizada debe combinar
las inferencias regionales compatibles con historial, suelo, riego y restricciones
pertinentes del lote; su conexión completa se describe en
[personalización](../architecture/farm-personalization.md).

El ámbito inicial de trabajo es Antioquia. La región operativa y las coordenadas
se configuran; un punto de referencia técnico no acredita un piloto validado.
La expansión a otros territorios requiere verificar cobertura y alcance de modelos.
El mapa distingue región, municipio y finca; una geometría pequeña no aumenta
la resolución de los datos de origen.

## Resultados esperados

- Cinco variables pronosticadas para periodos de 7, 15, 30 o 60 días: temperatura
  media, medias de mínimas y máximas, lluvia acumulada y humedad superficial media.
- Evaluación explicable de cultivos a partir de esas inferencias y requisitos.
- Comparación de escenarios de rotación, incluyendo práctica vigente y alternativas
  cuando existan contexto, reglas y candidatos suficientes.
- Fecha de actualización, unidades, procedencia, alcance y versiones recuperables.

El horizonte comienza en el día de consulta para los resultados operativos. No
representa únicamente el estado del último día ni una trayectoria diaria futura.
Los escenarios condicionales no equivalen a un calendario de siembra aprobado.

## Objetivos de calidad

| Objetivo | Evidencia exigida |
| --- | --- |
| Trazabilidad | Identidad de fuentes, snapshot, receta, modelos, catálogo y reglas |
| Confiabilidad | Reintentos durables, idempotencia y conservación del último resultado válido |
| Privacidad | Autorización por propietario y separación de datos públicos/privados |
| Corrección temporal | Entradas disponibles al emitir y evaluación sin información futura |
| Comprensibilidad | Estados y explicaciones acordes al tipo de dato y su validación |
| Rendimiento | Medición con volumen, entorno y objetivos definidos; no hay SLA publicado |

Los límites funcionales y sus criterios de aceptación están en
[capacidades y límites](../reference/capabilities.md). La aplicación apoya decisiones;
no garantiza rendimientos agrícolas ni reemplaza validación agronómica local.
