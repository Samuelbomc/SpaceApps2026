"""
Modelo climático – La Unión (Antioquia)
Fuente: NASA POWER, punto 5.97 N, -75.36 W, diario 2000-2026

Uso:  python modelo_climatico_launion.py ARCHIVO_POWER.csv
Salidas:
  figuras_launion/*.png
  launion_diario.csv        -> datos diarios limpios + corregidos por altitud
  launion_mensual.csv       -> cada mes de cada año
  launion_climatologia.csv  -> mes típico (promedio 2000-2025)
  launion_temporadas.csv    -> 4 temporadas andinas (para el motor de rotación)
"""
import sys, os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ----------------------------------------------------------------
# PARÁMETROS (ajustables)
# ----------------------------------------------------------------
ALT_POWER = 1848.43     # m, del encabezado del archivo (altitud media de la celda MERRA-2)
ALT_REAL = 2500.0       # m, altitud aproximada de La Unión (cambiar por la de la finca)
GRADIENTE = 0.0065      # °C por metro (gradiente térmico estándar)
UMBRAL_HELADA = 3.0     # °C de mínima a 2 m: riesgo de helada en el cultivo
UMBRAL_HONGOS_HR = 90   # % humedad relativa para riesgo de gota de la papa
AÑOS_REF = (2000, 2025) # periodo histórico de referencia
CORREGIR_IMERG = False  # True aplicaría un factor de una sola estación; no se usa: IMERG ≈ promedio de las 2 estaciones IDEAM

archivo = sys.argv[1]
os.makedirs("figuras_launion", exist_ok=True)
MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]

# ----------------------------------------------------------------
# 1. CARGA Y LIMPIEZA
# ----------------------------------------------------------------
d = pd.read_csv(archivo, skiprows=18).replace(-999, np.nan)
d["FECHA"] = pd.to_datetime(d.YEAR.astype(str), format="%Y") + pd.to_timedelta(d.DOY - 1, unit="D")
d["MES"] = d.FECHA.dt.month
d = d.rename(columns={"IMERG_PRECTOT": "LLUVIA_IMERG", "PRECTOTCORR": "LLUVIA_MERRA2"})

# Corrección de sesgo de IMERG con la estación IDEAM (si existe el archivo de factores)
if CORREGIR_IMERG and os.path.exists("factor_correccion_imerg.csv"):
    f = pd.read_csv("factor_correccion_imerg.csv").set_index("MES").FACTOR_IMERG
    d["LLUVIA_IMERG_ORIGINAL"] = d.LLUVIA_IMERG
    d["LLUVIA_IMERG"] = d.LLUVIA_IMERG * d.MES.map(f)
    print("IMERG corregido con factores mensuales de la estación IDEAM LA UNION [26180170]")

print("=== 1. CALIDAD ===")
print(f"Periodo: {d.FECHA.min().date()} a {d.FECHA.max().date()}  ({len(d)} días)")
print("Datos faltantes por variable:")
print(d.isna().sum()[d.isna().sum() > 0].to_string())

# ----------------------------------------------------------------
# 2. CORRECCIÓN DE TEMPERATURA POR ALTITUD
# ----------------------------------------------------------------
dT = GRADIENTE * (ALT_REAL - ALT_POWER)
if os.path.exists("calibracion_temperatura.csv"):
    # Calibración con la estación IDEAM Mesopotamia (sale de validacion_ideam_temperatura.py).
    # Corrige por separado mínima y máxima: el gradiente funciona para la mínima pero
    # MERRA-2 subestima el rango día-noche, así que la máxima necesita menos corrección.
    cal = pd.read_csv("calibracion_temperatura.csv").set_index("MES")
    off_min, off_max = d.MES.map(cal.OFFSET_TMIN), d.MES.map(cal.OFFSET_TMAX)
    d["T2M_MIN_CORR"] = d.T2M_MIN + off_min
    d["T2M_MAX_CORR"] = d.T2M_MAX + off_max
    d["T2M_CORR"] = d.T2M + (off_min + off_max) / 2
    print("\n=== 2. CORRECCIÓN DE TEMPERATURA ===\nCalibrada con la estación IDEAM MESOPOTAMIA [26185020] (por mes, mínima y máxima)")
else:
    for c in ["T2M", "T2M_MAX", "T2M_MIN"]:
        d[c + "_CORR"] = d[c] - dT
    print(f"\n=== 2. CORRECCIÓN POR ALTITUD ===\nPOWER {ALT_POWER:.0f} m -> real {ALT_REAL:.0f} m : se restan {dT:.1f} °C")

# ----------------------------------------------------------------
# 3. INDICADORES DIARIOS
# ----------------------------------------------------------------
# Evapotranspiración de referencia, Hargreaves (FAO-56):
#   ET0 = 0.0023 * 0.408*Ra * (Tmedia + 17.8) * sqrt(Tmax - Tmin)   [mm/día]
# Ra = radiación en el tope de la atmósfera (TOA_SW_DWN, MJ/m2/día)
rango = (d.T2M_MAX_CORR - d.T2M_MIN_CORR).clip(lower=0)
d["ET0"] = 0.0023 * 0.408 * d.TOA_SW_DWN * (d.T2M_CORR + 17.8) * np.sqrt(rango)
d["BALANCE"] = d.LLUVIA_IMERG - d.ET0
d["DIA_HELADA"] = d.T2M_MIN_CORR <= UMBRAL_HELADA
d["DIA_HONGOS"] = (d.RH2M >= UMBRAL_HONGOS_HR) & d.T2M_CORR.between(10, 20)
d["DIA_LLUVIA_FUERTE"] = d.LLUVIA_IMERG >= 30   # mm/día: riesgo de erosión en ladera

d.to_csv("launion_diario.csv", index=False)

# ----------------------------------------------------------------
# 4. RESUMEN MENSUAL (cada mes de cada año)
# ----------------------------------------------------------------
agg = {
    "T2M_CORR": "mean", "T2M_MAX_CORR": "mean", "T2M_MIN_CORR": ["mean", "min"],
    "RH2M": "mean", "LLUVIA_IMERG": "sum", "LLUVIA_MERRA2": "sum", "ET0": "sum",
    "BALANCE": "sum", "GWETROOT": "mean",
    "DIA_HELADA": "sum", "DIA_HONGOS": "sum", "DIA_LLUVIA_FUERTE": "sum",
}
m = d.groupby(["YEAR", "MES"]).agg(agg)
m.columns = ["T_MEDIA", "T_MAX_MEDIA", "T_MIN_MEDIA", "T_MIN_ABSOLUTA", "HR",
             "LLUVIA_IMERG_mm", "LLUVIA_MERRA2_mm", "ET0_mm", "BALANCE_mm", "HUMEDAD_SUELO",
             "DIAS_HELADA", "DIAS_HONGOS", "DIAS_LLUVIA_FUERTE"]
m = m.round(2).reset_index()
m.to_csv("launion_mensual.csv", index=False)

# ----------------------------------------------------------------
# 5. CLIMATOLOGÍA (mes típico 2000-2025)
# ----------------------------------------------------------------
ref = m[m.YEAR.between(*AÑOS_REF)]
clim = ref.groupby("MES").mean(numeric_only=True).drop(columns="YEAR").round(2)
clim.to_csv("launion_climatologia.csv")
print("\n=== 5. MES TÍPICO (2000-2025) ===")
print(clim[["T_MEDIA", "T_MIN_ABSOLUTA", "LLUVIA_IMERG_mm", "ET0_mm", "BALANCE_mm",
            "DIAS_HELADA", "DIAS_HONGOS"]].to_string())

# ----------------------------------------------------------------
# 6. TEMPORADAS ANDINAS (insumo para la rotación)
# ----------------------------------------------------------------
TEMP = {12: "1_Seca (Dic-Feb)", 1: "1_Seca (Dic-Feb)", 2: "1_Seca (Dic-Feb)",
        3: "2_Lluvia 1 (Mar-May)", 4: "2_Lluvia 1 (Mar-May)", 5: "2_Lluvia 1 (Mar-May)",
        6: "3_Veranillo (Jun-Ago)", 7: "3_Veranillo (Jun-Ago)", 8: "3_Veranillo (Jun-Ago)",
        9: "4_Lluvia 2 (Sep-Nov)", 10: "4_Lluvia 2 (Sep-Nov)", 11: "4_Lluvia 2 (Sep-Nov)"}
clim_t = clim.copy(); clim_t["TEMPORADA"] = clim_t.index.map(TEMP)
temp = clim_t.groupby("TEMPORADA").agg(
    T_MEDIA=("T_MEDIA", "mean"), T_MIN_ABSOLUTA=("T_MIN_ABSOLUTA", "min"),
    LLUVIA_mm=("LLUVIA_IMERG_mm", "sum"), ET0_mm=("ET0_mm", "sum"),
    BALANCE_mm=("BALANCE_mm", "sum"), DIAS_HELADA=("DIAS_HELADA", "sum"),
    DIAS_HONGOS=("DIAS_HONGOS", "sum"), DIAS_LLUVIA_FUERTE=("DIAS_LLUVIA_FUERTE", "sum"),
).round(1)
temp.to_csv("launion_temporadas.csv")
print("\n=== 6. TEMPORADAS (totales por temporada, año típico) ===")
print(temp.to_string())

# ----------------------------------------------------------------
# 7. IMERG vs MERRA-2 (validación de la lluvia)
# ----------------------------------------------------------------
anual = m[m.YEAR.between(*AÑOS_REF)].groupby("YEAR")[["LLUVIA_IMERG_mm", "LLUVIA_MERRA2_mm"]].sum()
r = anual.corr().iloc[0, 1]
print(f"\n=== 7. LLUVIA ANUAL: IMERG vs MERRA-2 ===\nCorrelación anual: {r:.2f}")
print(anual.loc[[2008, 2010, 2011, 2015, 2021, 2022]].round(0).to_string())

# ----------------------------------------------------------------
# 8. TENDENCIAS
# ----------------------------------------------------------------
an = d[d.YEAR.between(*AÑOS_REF)].groupby("YEAR").agg(
    T_MEDIA=("T2M_CORR", "mean"), T_MIN=("T2M_MIN_CORR", "mean"),
    LLUVIA=("LLUVIA_IMERG", "sum"), HELADAS=("DIA_HELADA", "sum"))
print("\n=== 8. TENDENCIAS 2000-2025 (por década) ===")
for c, u in [("T_MEDIA", "°C"), ("T_MIN", "°C"), ("LLUVIA", "mm/año"), ("HELADAS", "días/año")]:
    pend = np.polyfit(an.index, an[c], 1)[0] * 10
    print(f"  {c}: {pend:+.2f} {u} por década")

# ----------------------------------------------------------------
# FIGURAS
# ----------------------------------------------------------------
x = range(1, 13)

# Fig 1: ciclo anual
fig, ax1 = plt.subplots(figsize=(9, 4.8))
ax1.bar(x, clim.LLUVIA_IMERG_mm, color="#7fb3d5", label="Lluvia IMERG (mm/mes)")
ax1.plot(x, clim.ET0_mm, "s--", color="#117a65", label="ET₀ (mm/mes)")
ax1.set_ylabel("mm / mes"); ax1.set_xticks(x); ax1.set_xticklabels(MESES)
ax2 = ax1.twinx()
ax2.plot(x, clim.T_MAX_MEDIA, "o-", color="#cb4335", label="T máx media")
ax2.plot(x, clim.T_MEDIA, "o-", color="#e59866", label="T media")
ax2.plot(x, clim.T_MIN_MEDIA, "o-", color="#2e86c1", label="T mín media")
ax2.set_ylabel("°C (calibrada con IDEAM)")
ax1.set_title("La Unión – mes típico 2000–2025")
fig.legend(loc="lower center", ncol=3, frameon=False)
fig.tight_layout(rect=(0, 0.1, 1, 1)); fig.savefig("figuras_launion/1_ciclo_anual.png", dpi=150)

# Fig 2: riesgos por mes
fig, ax = plt.subplots(figsize=(9, 4))
w = 0.27
ax.bar([i - w for i in x], clim.DIAS_HELADA, w, color="#2e86c1", label=f"Días con T mín ≤ {UMBRAL_HELADA:.0f} °C")
ax.bar(x, clim.DIAS_HONGOS, w, color="#7d3c98", label="Días con riesgo de hongos")
ax.bar([i + w for i in x], clim.DIAS_LLUVIA_FUERTE, w, color="#ca6f1e", label="Días con lluvia ≥ 30 mm")
ax.set_xticks(x); ax.set_xticklabels(MESES); ax.set_ylabel("días / mes (promedio)")
ax.set_title("La Unión – riesgos climáticos por mes (2000–2025)")
ax.legend(frameon=False)
fig.tight_layout(); fig.savefig("figuras_launion/2_riesgos_por_mes.png", dpi=150)

# Fig 3: IMERG vs MERRA-2
fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(anual.index, anual.LLUVIA_IMERG_mm, "o-", color="#2e86c1", label="IMERG (satélite)")
ax.plot(anual.index, anual.LLUVIA_MERRA2_mm, "o-", color="#a6acaf", label="MERRA-2 (modelo)")
ax.set_ylabel("mm / año"); ax.set_title(f"Lluvia anual en La Unión: dos fuentes (r = {r:.2f})")
ax.legend(frameon=False)
fig.tight_layout(); fig.savefig("figuras_launion/3_imerg_vs_merra2.png", dpi=150)

print("\nListo: figuras_launion/ y archivos launion_*.csv")
