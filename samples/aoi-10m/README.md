# Muestra real: área de 10 × 10 m

Centro de referencia: **6.2442, -75.5812**, Medellín. Bbox y dimensiones WGS84
verificados en `summary.json`. No representa una región piloto agrícola elegida.

- [summary.json](summary.json): disponibilidad y acceso público por producto en
  enero de 2026 y enero de 2024. Los conteos de archivos están limitados a tres.
- [power-observations.sample.json](power-observations.sample.json): doce filas reales,
  seis variables del primer día de cada periodo, con unidades y calidad.

Solo POWER contiene observaciones científicas leídas. Los demás resultados son
catálogos; sus archivos de muestra devolvieron HTTP 401 a GET sin credenciales.
Un HEAD 200 no fue suficiente para leerlos. No hay valores raster ficticios ni
interpolación a 10 m. `provider_value_unvalidated` no certifica precisión local.

El [informe](../../docs/aoi-10m-validation.md) describe limpieza, resolución,
limitaciones y comandos para repetir la prueba. Los Parquet completos y payloads
originales están en los directorios locales de `data/probes/` indicados en el resumen.
