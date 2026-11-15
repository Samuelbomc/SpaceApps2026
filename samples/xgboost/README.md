# Muestra histórica real para comprobar la integración XGBoost

`moisture_99_20220108.csv` es una sola fila sin modificar de
`data/prepared/expanded/moisture.csv`, recibida en main. Mantiene los metadatos
originales para auditoría: emisión 2022-01-08, corte 2022-01-06, objetivo
2022-01-09..2022-01-15 y centro de celda SMAP. El importador selecciona solo
las variables predictoras; descarta target y todos los metadatos futuros.

Es una fila incluida en el reajuste de model.json. Su inferencia sirve para
verificar carga, unidades y suma del baseline, no para medir generalización.
No se instala como entrada reciente ni se añade a las bases operativas.

Comando de reproducción y arquitectura: [integración](../../docs/xgboost-integration.md).
