# Módulo climático – La Unión (Antioquia)
Datos para la interfaz y el motor de rotación de cultivos.
Fuente: NASA POWER (MERRA-2 + GPM IMERG), punto 5.97 N, -75.36 W, 2000–2026. ENSO: índice ONI de NOAA.
Formato: CSV, separador coma, decimales con punto, codificación UTF-8.

## Archivos a usar en la interfaz

| Archivo | Para qué pantalla | Filas |
|---|---|---|
| `launion_temporadas.csv` | Resumen del año por temporada (insumo principal de la rotación) | 4 |
| `launion_efecto_enso.csv` | "Qué esperar la próxima temporada" según El Niño / La Niña | 12 |
| `launion_climatologia.csv` | Gráfica del año típico (enero–diciembre) | 12 |
| `launion_mensual.csv` | Historial / línea de tiempo por año y mes | ~323 |
| `launion_diario.csv` | Solo consulta detallada (archivo pesado) | ~9.800 |

## Columnas

### launion_climatologia.csv y launion_mensual.csv
| Columna | Significado | Unidad |
|---|---|---|
| `YEAR` | Año (solo en mensual) | — |
| `MES` | Mes (1 = enero … 12 = diciembre) | — |
| `T_MEDIA` | Temperatura media del aire, calibrada con IDEAM Mesopotamia | °C |
| `T_MAX_MEDIA` | Promedio de las máximas diarias | °C |
| `T_MIN_MEDIA` | Promedio de las mínimas diarias | °C |
| `T_MIN_ABSOLUTA` | Mínima más baja del mes | °C |
| `HR` | Humedad relativa media | % |
| `LLUVIA_IMERG_mm` | Lluvia total del mes (GPM IMERG **corregido con la estación IDEAM**) — **usar esta** | mm/mes |
| `LLUVIA_MERRA2_mm` | Lluvia total del mes (modelo MERRA-2) — solo comparación | mm/mes |
| `ET0_mm` | Evapotranspiración de referencia (Hargreaves) | mm/mes |
| `BALANCE_mm` | Lluvia IMERG − ET0 (positivo = sobra agua) | mm/mes |
| `HUMEDAD_SUELO` | Humedad en zona de raíces (0 = seco, 1 = saturado) | 0–1 |
| `DIAS_HELADA` | Días con mínima ≤ 3 °C | días |
| `DIAS_HONGOS` | Días con HR ≥ 90 % y T entre 10–20 °C | días |
| `DIAS_LLUVIA_FUERTE` | Días con lluvia ≥ 30 mm (riesgo de erosión) | días |

### launion_temporadas.csv
| Columna | Significado | Unidad |
|---|---|---|
| `TEMPORADA` | 1_Seca (Dic-Feb), 2_Lluvia 1 (Mar-May), 3_Veranillo (Jun-Ago), 4_Lluvia 2 (Sep-Nov) | — |
| `T_MEDIA` | Temperatura media | °C |
| `T_MIN_ABSOLUTA` | Mínima más baja de la temporada | °C |
| `LLUVIA_mm` | Lluvia total de la temporada | mm |
| `ET0_mm` | Evapotranspiración total | mm |
| `BALANCE_mm` | Lluvia − ET0 | mm |
| `DIAS_HELADA`, `DIAS_HONGOS`, `DIAS_LLUVIA_FUERTE` | Días de riesgo en la temporada | días |

### launion_efecto_enso.csv
Cambio respecto a lo normal, promedio por mes, para cada temporada y fase.
| Columna | Significado | Unidad |
|---|---|---|
| `TEMPORADA` | Igual que arriba | — |
| `FASE` | El Niño (ONI ≥ 0.5), La Niña (ONI ≤ −0.5), Neutral | — |
| `MESES` | Meses de datos usados (confiabilidad) | — |
| `LLUVIA_pct` | Cambio de lluvia | % |
| `T_MAX_anom` / `T_MIN_anom` | Cambio de temperatura máxima / mínima | °C |
| `HONGOS_dias_anom` | Cambio en días de riesgo de hongos por mes | días |
| `LLUVIA_FUERTE_anom` | Cambio en días de lluvia fuerte por mes | días |

**Estado actual (nov 2026):** ONI ASO 2026 = +2.5 → El Niño fuerte. Para mostrar la perspectiva
de la próxima temporada, filtrar `TEMPORADA = "Seca (Dic-Feb)"` y `FASE = "El Niño"`.

## Validación
Lluvia validada con dos estaciones IDEAM del municipio (2000–2016, datos definitivos):
LA UNION [26180170] (~2.140 mm/año) y MESOPOTAMIA [26185020] (~3.690 mm/año).
IMERG (~2.870 mm/año) coincide con el promedio de ambas (sesgo −1 %, r anual 0.80).
MERRA-2 no sigue la variación entre años (r anual 0.22): no usar.
La lluvia cambia mucho dentro del municipio: el valor de IMERG es un promedio de zona (~10 km).

Temperatura validada con IDEAM MESOPOTAMIA [26185020] (2000–2017, definitivos).
El gradiente térmico (−4.2 °C) funciona para la mínima (sesgo +0.5 °C) pero enfría de más la máxima
(sesgo −3.0 °C): MERRA-2 subestima el rango día-noche (7.0 vs 10.6 °C en la estación).
Por eso el modelo calibra mínima y máxima por mes con la estación (`calibracion_temperatura.csv`).
POWER no reproduce noches frías individuales; el riesgo de heladas se toma de la estación:
`launion_heladas_ideam.csv` (noches con T mín ≤ 5 °C por mes) y `launion_heladas_enso_ideam.csv` (por fase ENSO).

## Limitaciones a mostrar en la interfaz
- Resolución de la celda ~55 km: POWER no captura heladas (DIAS_HELADA siempre 0). Usar los archivos de heladas de la estación IDEAM.
- Temperatura calibrada con una sola estación (Mesopotamia); otras veredas pueden diferir.
- Porcentajes de El Niño/La Niña son aproximados (13–52 meses de datos por caso).

## Orden para correr los programas
1. `python modelo_climatico_launion.py POWER_Point_Daily_...csv`
2. `python validacion_ideam_temperatura.py`  (crea calibracion_temperatura.csv)
3. `python modelo_climatico_launion.py POWER_Point_Daily_...csv`  (otra vez, ahora con la calibración)
4. `python modelo_enso_launion.py`
5. `python validacion_ideam_lluvia.py`
