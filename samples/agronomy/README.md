# Tabla agronómica aportada

`ecocrop-user.tsv` conserva exactamente el texto tabulado compartido por el
usuario: 12 perfiles, 11 especies ECOCROP y 38 columnas. Contiene requisitos de
referencia y descripciones, no observaciones de una finca ni predicciones.

El catálogo normalizado está en `ml/configs/ecocrop.catalog.json`. Se regenera
con `python -m scripts.crop_catalog`; conserva enlaces, atributos originales y
advertencias de calidad. Ver [la documentación agronómica](../../docs/reference/agronomic-catalog.md)
para unidades, límites y responsabilidades.
