"""
Componente de predicción: efecto de El Niño / La Niña en La Unión
Entradas: launion_mensual.csv (de modelo_climatico_launion.py) y oni.csv (NOAA CPC)
Uso: python modelo_enso_launion.py
"""
import numpy as np, pandas as pd, matplotlib.pyplot as plt, os
os.makedirs("figuras_launion", exist_ok=True)

UMBRAL = 0.5   # ONI >= +0.5 El Niño ; <= -0.5 La Niña (criterio NOAA)

# ONI: cada trimestre se asigna a su mes central (DJF -> enero, ..., NDJ -> diciembre)
oni = pd.read_csv("oni.csv").melt(id_vars="YEAR", var_name="TRI", value_name="ONI").dropna()
oni["MES"] = oni.TRI.map({t: i + 1 for i, t in enumerate(
    ["DJF","JFM","FMA","MAM","AMJ","MJJ","JJA","JAS","ASO","SON","OND","NDJ"])})
oni["FASE"] = np.select([oni.ONI >= UMBRAL, oni.ONI <= -UMBRAL], ["El Niño", "La Niña"], "Neutral")

m = pd.read_csv("launion_mensual.csv").merge(oni[["YEAR","MES","ONI","FASE"]], on=["YEAR","MES"])
m = m[m.YEAR <= 2025]

TEMP = {12:"Seca (Dic-Feb)",1:"Seca (Dic-Feb)",2:"Seca (Dic-Feb)",
        3:"Lluvia 1 (Mar-May)",4:"Lluvia 1 (Mar-May)",5:"Lluvia 1 (Mar-May)",
        6:"Veranillo (Jun-Ago)",7:"Veranillo (Jun-Ago)",8:"Veranillo (Jun-Ago)",
        9:"Lluvia 2 (Sep-Nov)",10:"Lluvia 2 (Sep-Nov)",11:"Lluvia 2 (Sep-Nov)"}
m["TEMPORADA"] = m.MES.map(TEMP)

# Anomalía de cada mes respecto a su promedio 2000-2025
VARS = ["LLUVIA_IMERG_mm","T_MAX_MEDIA","T_MIN_MEDIA","HR","DIAS_HONGOS","DIAS_LLUVIA_FUERTE","BALANCE_mm"]
clim = m.groupby("MES")[VARS].transform("mean")
for v in VARS:
    m[v + "_ANOM"] = m[v] - clim[v]
m["LLUVIA_PCT"] = 100 * m.LLUVIA_IMERG_mm_ANOM / clim.LLUVIA_IMERG_mm

orden = ["Seca (Dic-Feb)","Lluvia 1 (Mar-May)","Veranillo (Jun-Ago)","Lluvia 2 (Sep-Nov)"]
efecto = m.groupby(["TEMPORADA","FASE"]).agg(
    MESES=("MES","size"),
    LLUVIA_pct=("LLUVIA_PCT","mean"),
    T_MAX_anom=("T_MAX_MEDIA_ANOM","mean"),
    T_MIN_anom=("T_MIN_MEDIA_ANOM","mean"),
    HONGOS_dias_anom=("DIAS_HONGOS_ANOM","mean"),
    LLUVIA_FUERTE_anom=("DIAS_LLUVIA_FUERTE_ANOM","mean"),
).round(2).reindex(orden, level=0)
efecto.to_csv("launion_efecto_enso.csv")
print("=== EFECTO DE EL NIÑO / LA NIÑA POR TEMPORADA (anomalía mensual promedio) ===")
print(efecto.to_string())

# Figura: anomalía de lluvia (%) por temporada y fase
piv = m.groupby(["TEMPORADA","FASE"]).LLUVIA_PCT.mean().unstack().reindex(orden)[["La Niña","Neutral","El Niño"]]
fig, axs = plt.subplots(1, 2, figsize=(11, 4.2))
piv.plot.bar(ax=axs[0], color=["#2e86c1","#a6acaf","#cb4335"], rot=15)
axs[0].axhline(0, color="k", lw=0.7); axs[0].set_ylabel("Anomalía de lluvia (%)"); axs[0].set_xlabel("")
axs[0].set_title("Lluvia según fase ENSO")
pt = m.groupby(["TEMPORADA","FASE"]).T_MAX_MEDIA_ANOM.mean().unstack().reindex(orden)[["La Niña","Neutral","El Niño"]]
pt.plot.bar(ax=axs[1], color=["#2e86c1","#a6acaf","#cb4335"], rot=15, legend=False)
axs[1].axhline(0, color="k", lw=0.7); axs[1].set_ylabel("Anomalía T máx (°C)"); axs[1].set_xlabel("")
axs[1].set_title("Temperatura máxima según fase ENSO")
fig.suptitle("La Unión – efecto de El Niño y La Niña (2000–2025)")
fig.tight_layout(); fig.savefig("figuras_launion/4_efecto_enso.png", dpi=150)

# Estado actual y perspectiva
ult = oni.sort_values(["YEAR","MES"]).iloc[-1]
print(f"\nÚltimo ONI disponible: {ult.TRI} {ult.YEAR} = {ult.ONI:+.1f}  -> {ult.FASE}")
print("Perspectiva para la temporada seca (Dic-Feb) si persiste esta fase:")
print(efecto.loc[("Seca (Dic-Feb)", ult.FASE)].to_string())
