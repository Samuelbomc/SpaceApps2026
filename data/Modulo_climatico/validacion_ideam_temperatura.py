"""
Validación y calibración de la temperatura con la estación IDEAM MESOPOTAMIA [26185020]
Entradas: descargaDhime_mesopotamia_tmin.csv, descargaDhime_mesopotamia_tmax.csv,
          launion_diario.csv (del modelo), oni.csv
Salidas:  calibracion_temperatura.csv  -> la usa modelo_climatico_launion.py
          launion_heladas_ideam.csv, launion_heladas_enso_ideam.csv
          figuras_launion/6_validacion_ideam_temperatura.png
Uso: python validacion_ideam_temperatura.py
"""
import os
import numpy as np, pandas as pd, matplotlib.pyplot as plt

ALT_POWER, ALT_REAL, GRADIENTE = 1848.43, 2500.0, 0.0065
UMBRAL_NOCHE_FRIA = 5.0   # °C a 2 m (en noches despejadas el cultivo puede estar 3-5 °C más frío)
os.makedirs("figuras_launion", exist_ok=True)
MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
dT = GRADIENTE * (ALT_REAL - ALT_POWER)

def estacion(archivo, nombre):
    s = pd.read_csv(archivo)
    s = s[s.NivelAprobacion == "Definitivo"]          # 2018+ es "Preliminar"
    s["FECHA"] = pd.to_datetime(s.Fecha).dt.normalize()
    return s[["FECHA", "Valor"]].rename(columns={"Valor": nombre})

d = pd.read_csv("launion_diario.csv", parse_dates=["FECHA"])[["FECHA", "T2M_MIN", "T2M_MAX"]]
d["TMIN_GRADIENTE"] = d.T2M_MIN - dT
d["TMAX_GRADIENTE"] = d.T2M_MAX - dT
m = (d.merge(estacion("descargaDhime_mesopotamia_tmin.csv", "TMIN_IDEAM"), on="FECHA", how="left")
      .merge(estacion("descargaDhime_mesopotamia_tmax.csv", "TMAX_IDEAM"), on="FECHA", how="left"))
m = m.dropna(subset=["TMIN_IDEAM", "TMAX_IDEAM"], how="all")
m["YEAR"], m["MES"] = m.FECHA.dt.year, m.FECHA.dt.month

# ---- 1. Validación de la corrección por gradiente térmico
print("=== Validación (datos definitivos IDEAM) ===")
for var, est, pw, pg in [("Mínima", "TMIN_IDEAM", "T2M_MIN", "TMIN_GRADIENTE"),
                         ("Máxima", "TMAX_IDEAM", "T2M_MAX", "TMAX_GRADIENTE")]:
    x = m.dropna(subset=[est])
    print(f"T {var}: estación {x[est].mean():.1f} °C | POWER {x[pw].mean():.1f} (sesgo {x[pw].mean()-x[est].mean():+.1f}) "
          f"| POWER con gradiente {x[pg].mean():.1f} (sesgo {x[pg].mean()-x[est].mean():+.1f}) "
          f"| r diaria {np.corrcoef(x[est], x[pw])[0,1]:.2f}")
rango_est = (m.TMAX_IDEAM - m.TMIN_IDEAM).mean(); rango_pw = (m.T2M_MAX - m.T2M_MIN).mean()
print(f"Rango día-noche: estación {rango_est:.1f} °C vs POWER {rango_pw:.1f} °C")
print("-> El gradiente sirve para la mínima, pero enfría de más la máxima: MERRA-2 subestima el rango día-noche.")

# ---- 2. Calibración mensual (POWER crudo -> estación)
cal = pd.DataFrame({
    "OFFSET_TMIN": (m.groupby("MES").TMIN_IDEAM.mean() - m.groupby("MES").T2M_MIN.mean()),
    "OFFSET_TMAX": (m.groupby("MES").TMAX_IDEAM.mean() - m.groupby("MES").T2M_MAX.mean()),
}).round(2)
cal.to_csv("calibracion_temperatura.csv")
print("\n=== Calibración mensual (sumar a POWER crudo) ===")
print(cal.to_string())

# ---- 3. Noches frías según la estación
x = m.dropna(subset=["TMIN_IDEAM"]).copy()
x["NOCHE_FRIA"] = x.TMIN_IDEAM <= UMBRAL_NOCHE_FRIA
heladas = pd.DataFrame({
    "NOCHES_FRIAS_por_mes": (x.groupby("MES").NOCHE_FRIA.sum() / x.groupby("MES").YEAR.nunique()).round(2),
    "PROB_noche_fria_pct": (100 * x.groupby("MES").NOCHE_FRIA.mean()).round(2),
    "TMIN_IDEAM_media": x.groupby("MES").TMIN_IDEAM.mean().round(2),
    "TMIN_IDEAM_absoluta": x.groupby("MES").TMIN_IDEAM.min(),
})
heladas.to_csv("launion_heladas_ideam.csv")
print(f"\n=== Noches con T mín <= {UMBRAL_NOCHE_FRIA} °C (estación) ===")
print(heladas.to_string())

oni = pd.read_csv("oni.csv").melt(id_vars="YEAR", var_name="TRI", value_name="ONI").dropna()
oni["MES"] = oni.TRI.map({t: i + 1 for i, t in enumerate(
    ["DJF","JFM","FMA","MAM","AMJ","MJJ","JJA","JAS","ASO","SON","OND","NDJ"])})
oni["FASE"] = np.select([oni.ONI >= 0.5, oni.ONI <= -0.5], ["El Niño", "La Niña"], "Neutral")
x = x.merge(oni[["YEAR", "MES", "FASE"]], on=["YEAR", "MES"])
TEMP = {12:"Seca (Dic-Feb)",1:"Seca (Dic-Feb)",2:"Seca (Dic-Feb)",3:"Lluvia 1 (Mar-May)",4:"Lluvia 1 (Mar-May)",
        5:"Lluvia 1 (Mar-May)",6:"Veranillo (Jun-Ago)",7:"Veranillo (Jun-Ago)",8:"Veranillo (Jun-Ago)",
        9:"Lluvia 2 (Sep-Nov)",10:"Lluvia 2 (Sep-Nov)",11:"Lluvia 2 (Sep-Nov)"}
x["TEMPORADA"] = x.MES.map(TEMP)
enso = x.groupby(["TEMPORADA", "FASE"]).agg(
    DIAS=("NOCHE_FRIA", "size"),
    PROB_noche_fria_pct=("NOCHE_FRIA", lambda v: round(100 * v.mean(), 2)),
    TMIN_media=("TMIN_IDEAM", lambda v: round(v.mean(), 2)))
enso.to_csv("launion_heladas_enso_ideam.csv")
print("\n=== Noches frías según fase ENSO (estación) ===")
print(enso.to_string())

# ---- Figura
c = m.groupby("MES")[["TMIN_IDEAM", "TMAX_IDEAM", "T2M_MIN", "T2M_MAX", "TMIN_GRADIENTE", "TMAX_GRADIENTE"]].mean()
fig, axs = plt.subplots(1, 2, figsize=(12, 4.5))
xx = range(1, 13)
axs[0].plot(xx, c.TMAX_IDEAM, "o-", color="k", lw=2, label="T máx IDEAM")
axs[0].plot(xx, c.TMAX_GRADIENTE, "o-", color="#cb4335", label="T máx POWER con gradiente")
axs[0].plot(xx, c.T2M_MAX, "o--", color="#f1948a", label="T máx POWER crudo")
axs[0].plot(xx, c.TMIN_IDEAM, "s-", color="#555", lw=2, label="T mín IDEAM")
axs[0].plot(xx, c.TMIN_GRADIENTE, "s-", color="#2e86c1", label="T mín POWER con gradiente")
axs[0].plot(xx, c.T2M_MIN, "s--", color="#85c1e9", label="T mín POWER crudo")
axs[0].set_xticks(xx); axs[0].set_xticklabels(MESES); axs[0].set_ylabel("°C")
axs[0].set_title("Temperatura media mensual"); axs[0].legend(frameon=False, fontsize=7, ncol=2)
bins = np.arange(0, 19, 0.5)
axs[1].hist(m.TMIN_IDEAM.dropna(), bins, color="k", alpha=0.6, density=True, label="T mín IDEAM")
axs[1].hist(m.TMIN_GRADIENTE, bins, color="#2e86c1", alpha=0.6, density=True, label="T mín POWER con gradiente")
axs[1].axvline(UMBRAL_NOCHE_FRIA, color="#cb4335", ls="--", label=f"Umbral noche fría ({UMBRAL_NOCHE_FRIA:.0f} °C)")
axs[1].set_xlabel("T mínima diaria (°C)"); axs[1].set_title("Distribución de mínimas diarias")
axs[1].legend(frameon=False, fontsize=8)
fig.suptitle("Validación de la temperatura con IDEAM Mesopotamia [26185020] (datos definitivos)")
fig.tight_layout(); fig.savefig("figuras_launion/6_validacion_ideam_temperatura.png", dpi=150)
print("\nListo: calibracion_temperatura.csv, launion_heladas_*.csv, figuras_launion/6_validacion_ideam_temperatura.png")
