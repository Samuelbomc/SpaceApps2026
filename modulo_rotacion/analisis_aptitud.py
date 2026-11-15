import sys

import pandas as pd

d = pd.read_excel(sys.argv[1], dtype={"Cod_Municipio": str})
d = d.rename(
    columns={
        "Aptitud_Alta_(Ha)": "HA_ALTA",
        "(%) Aptitud Alta Respecto Área Departamento": "PCT_ALTA",
        "Hectareas_Media": "HA_MEDIA",
        "Porcentaje_Media": "PCT_MEDIA",
        "Área_Departamento": "AREA_MUNICIPIO_HA",
    }
)
TRANSITORIOS = [
    "Arroz",
    "Cebolla junca",
    "Frijol arbustivo",
    "Frijol voluble",
    "Hortalizas clima frio",
    "Maíz",
    "Maíz choclo",
    "Papa",
    "Tomate chonto",
    "Yuca",
    "Ñame",
]
d["GRUPO"] = d["Cadena"].apply(lambda c: "transitorio (rotable)" if c in TRANSITORIOS else "otro")
d["PUNTAJE_APTITUD"] = (d["PCT_ALTA"] + 0.5 * d["PCT_MEDIA"]).round(1)
d["HA_APTAS"] = d["HA_ALTA"] + d["HA_MEDIA"]
t = d[d.GRUPO.str.startswith("transitorio")].copy()

dep = (
    t.groupby("Cadena")
    .agg(
        HA_ALTA=("HA_ALTA", "sum"),
        HA_MEDIA=("HA_MEDIA", "sum"),
        MUNICIPIOS_CON_ALTA=("HA_ALTA", lambda s: int((s > 0).sum())),
    )
    .assign(HA_APTAS=lambda x: x.HA_ALTA + x.HA_MEDIA)
    .sort_values("HA_ALTA", ascending=False)
    .reset_index()
)
dep["PCT_ALTA_ANTIOQUIA"] = (
    dep.HA_ALTA / d.groupby("Municipio")["AREA_MUNICIPIO_HA"].first().sum() * 100
).round(1)
print(dep.to_string())

t = t.sort_values(["Municipio", "PUNTAJE_APTITUD"], ascending=[True, False])
t["PUESTO"] = t.groupby("Municipio").cumcount() + 1
top = t[(t.PUESTO <= 5) & (t.PUNTAJE_APTITUD > 0)]
ancho = top.pivot_table(
    index=["Cod_Municipio", "Municipio"], columns="PUESTO", values="Cadena", aggfunc="first"
).reset_index()
ancho.columns = ["Cod_Municipio", "Municipio"] + [f"Top{i}" for i in ancho.columns[2:]]
# cuantas veces cada cultivo esta en el top 3 de un municipio
print((t[t.PUESTO <= 3].Cadena.value_counts()).to_string())
for m in [
    "La Unión",
    "Santa Rosa de Osos",
    "Jardín",
    "Andes",
    "Apartadó",
    "Caucasia",
    "Rionegro",
    "Sonsón",
]:
    x = t[t.Municipio == m].head(5)
    print(m, list(zip(x.Cadena, x.PCT_ALTA, x.PCT_MEDIA, x.PUNTAJE_APTITUD)))
cols = [
    "Cod_Municipio",
    "Municipio",
    "Cadena",
    "PUESTO",
    "HA_ALTA",
    "PCT_ALTA",
    "HA_MEDIA",
    "PCT_MEDIA",
    "PUNTAJE_APTITUD",
    "AREA_MUNICIPIO_HA",
]
with pd.ExcelWriter("Cultivos_mas_aptos_Antioquia.xlsx") as w:
    pd.DataFrame(
        {
            "Explicación": [
                "Fuente: archivo Aptitud_Cultivos_Antioquia_Consolidado.xlsx (aptitud de UPRA por municipio y cadena).",
                "Solo se ranquean los 11 cultivos transitorios, que son los que se pueden rotar: "
                + ", ".join(TRANSITORIOS)
                + ".",
                "PUNTAJE_APTITUD = % del municipio con aptitud alta + 0,5 x % con aptitud media (0 a 100).",
                "Nota: en el archivo original la columna 'Área_Departamento' es en realidad el área del MUNICIPIO, y el '% aptitud alta' es respecto al municipio.",
                "Arveja, avena, haba y otras leguminosas de cobertura NO están en el archivo de UPRA; hay que buscarlas en otra fuente.",
            ]
        }
    ).to_excel(w, "Leeme", index=False)
    dep.to_excel(w, "Ranking Antioquia", index=False)
    ancho.to_excel(w, "Top 5 por municipio", index=False)
    t[cols].to_excel(w, "Detalle transitorios", index=False)
t[cols].to_csv("aptitud_transitorios_municipio.csv", index=False)
