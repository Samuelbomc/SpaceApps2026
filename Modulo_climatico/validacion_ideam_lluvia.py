"""
Validación de la lluvia satelital con dos estaciones IDEAM del municipio de La Unión
  - LA UNION   [26180170]  (cabecera)
  - MESOPOTAMIA [26185020] (corregimiento)
Entradas: descargaDhime.csv, descargaDhime_mesopotamia.csv, launion_diario.csv
Uso: python validacion_ideam_lluvia.py
"""
import os
import numpy as np, pandas as pd, matplotlib.pyplot as plt

AÑOS = (2000, 2016)   # datos "Definitivo"; en LA UNION 2018+ es "Preliminar" con totales irreales
ESTACIONES = {"LA UNION": "descargaDhime.csv", "MESOPOTAMIA": "descargaDhime_mesopotamia.csv"}
os.makedirs("figuras_launion", exist_ok=True)
MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]

d = pd.read_csv("launion_diario.csv", parse_dates=["FECHA"])
col_imerg = "LLUVIA_IMERG_ORIGINAL" if "LLUVIA_IMERG_ORIGINAL" in d else "LLUVIA_IMERG"
d = d[["FECHA", col_imerg, "LLUVIA_MERRA2"]].rename(columns={col_imerg: "IMERG", "LLUVIA_MERRA2": "MERRA2"})

for nombre, archivo in ESTACIONES.items():
    s = pd.read_csv(archivo)
    s["FECHA"] = pd.to_datetime(s.Fecha).dt.normalize()
    d = d.merge(s[["FECHA", "Valor"]].rename(columns={"Valor": nombre}), on="FECHA", how="left")

d = d[d.FECHA.dt.year.between(*AÑOS)]
d["YEAR"], d["MES"] = d.FECHA.dt.year, d.FECHA.dt.month
cols = list(ESTACIONES) + ["IMERG", "MERRA2"]

# Comparación mensual (el día pluviométrico IDEAM va de 7 a.m. a 7 a.m.; IMERG en días UTC)
mm = d.groupby(["YEAR", "MES"]).agg(**{c: (c, "sum") for c in cols},
                                     **{f"n_{e}": (e, "count") for e in ESTACIONES}).reset_index()
for e in ESTACIONES:
    mm.loc[mm[f"n_{e}"] < 25, e] = np.nan
mm["PROMEDIO_ESTACIONES"] = mm[list(ESTACIONES)].mean(axis=1, skipna=False)
cols_v = list(ESTACIONES) + ["PROMEDIO_ESTACIONES"]

an = mm.dropna().groupby("YEAR")[cols_v + ["IMERG", "MERRA2"]].sum()
clim = mm.dropna().groupby("MES")[cols_v + ["IMERG", "MERRA2"]].mean()

filas = []
for ref in cols_v:
    for sat in ["IMERG", "MERRA2"]:
        x = mm[[ref, sat]].dropna()
        filas.append(dict(REFERENCIA=ref, PRODUCTO=sat,
                          r_mensual=np.corrcoef(x[ref], x[sat])[0, 1],
                          r_anual=np.corrcoef(an[ref], an[sat])[0, 1],
                          sesgo_pct=100 * (an[sat].mean() - an[ref].mean()) / an[ref].mean()))
res = pd.DataFrame(filas).round(2)
res.to_csv("validacion_lluvia_metricas.csv", index=False)

print(f"=== Lluvia anual media {AÑOS[0]}-{AÑOS[1]} (mm/año) ===")
print(an.mean().round(0).to_string())
print("\n=== Métricas ===")
print(res.to_string(index=False))
print("\nCorrelación anual entre las dos estaciones:",
      round(np.corrcoef(an["LA UNION"], an["MESOPOTAMIA"])[0, 1], 2))

# Figura
fig, axs = plt.subplots(1, 2, figsize=(12, 4.3))
x = range(1, 13)
axs[0].fill_between(x, clim["LA UNION"], clim["MESOPOTAMIA"], color="#ccc", alpha=0.5,
                    label="Rango entre estaciones IDEAM")
axs[0].plot(x, clim["LA UNION"], "o-", color="#555", lw=1.5, label="IDEAM La Unión (cabecera)")
axs[0].plot(x, clim["MESOPOTAMIA"], "o-", color="k", lw=1.5, label="IDEAM Mesopotamia")
axs[0].plot(x, clim.IMERG, "o-", color="#2e86c1", lw=2, label="IMERG (satélite)")
axs[0].plot(x, clim.MERRA2, "o--", color="#a6acaf", label="MERRA-2 (modelo)")
axs[0].set_xticks(x); axs[0].set_xticklabels(MESES); axs[0].set_ylabel("mm / mes")
axs[0].set_title("Ciclo anual de lluvia"); axs[0].legend(frameon=False, fontsize=8)

axs[1].fill_between(an.index, an["LA UNION"], an["MESOPOTAMIA"], color="#ccc", alpha=0.5)
axs[1].plot(an.index, an["LA UNION"], "o-", color="#555", lw=1.5, label="IDEAM La Unión")
axs[1].plot(an.index, an["MESOPOTAMIA"], "o-", color="k", lw=1.5, label="IDEAM Mesopotamia")
axs[1].plot(an.index, an.IMERG, "o-", color="#2e86c1", lw=2, label="IMERG")
axs[1].plot(an.index, an.MERRA2, "o--", color="#a6acaf", label="MERRA-2")
axs[1].set_ylabel("mm / año"); axs[1].set_title("Lluvia anual"); axs[1].legend(frameon=False, fontsize=8)
fig.suptitle(f"Validación de la lluvia con estaciones IDEAM del municipio de La Unión ({AÑOS[0]}–{AÑOS[1]})")
fig.tight_layout(); fig.savefig("figuras_launion/5_validacion_ideam_lluvia.png", dpi=150)
print("\nListo: figuras_launion/5_validacion_ideam_lluvia.png y validacion_lluvia_metricas.csv")
