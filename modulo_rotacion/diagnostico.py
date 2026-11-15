"""
Diagnostico del lote: semaforo (verde / amarillo / rojo) con consejos, a partir de las
respuestas del agricultor. No necesita clima ni otros datos.

Areas:  erosion  ·  cansancio del suelo  ·  plagas y enfermedades  ·  agua

Uso:
  python diagnostico.py                       # con las respuestas de ejemplo
  from diagnostico import diagnosticar        # desde la interfaz
"""
import json
import sys
from pathlib import Path

DATOS = Path(__file__).parent / "datos"

# Familia de los cultivos que el agricultor puede nombrar (para ver si repite)
FAMILIA = {"papa": "solanácea", "papa_criolla": "solanácea", "tomate": "solanácea", "tomate_de_arbol": "solanácea",
           "frijol": "leguminosa", "frijol_voluble": "leguminosa", "frijol_arbustivo": "leguminosa", "arveja": "leguminosa",
           "haba": "leguminosa", "maiz": "gramínea", "arroz": "gramínea", "avena": "gramínea", "pasto": "gramínea",
           "brocoli": "crucífera", "repollo": "crucífera", "coliflor": "crucífera",
           "cebolla": "cebolla", "cebolla_junca": "cebolla", "zanahoria": "zanahoria", "lechuga": "lechuga",
           "yuca": "yuca", "name": "ñame"}

COLOR = {0: "verde", 1: "amarillo", 2: "rojo"}
ICONO = {"verde": "🟢", "amarillo": "🟡", "rojo": "🔴"}


def _color(puntos, amarillo, rojo):
    return 2 if puntos >= rojo else 1 if puntos >= amarillo else 0


def diagnosticar(resp):
    """resp = dict de respuestas (o ruta a JSON). Devuelve lista de areas con color, motivos y consejos."""
    if not isinstance(resp, dict):
        resp = json.loads(Path(resp).read_text(encoding="utf-8"))
    lote, suelo = resp.get("lote", {}), resp.get("suelo", {})
    hist = resp.get("historial", {}).get("ultimos_cultivos", [])
    plagas = [p for p in resp.get("plagas_recurrentes", []) if p]
    fumig = resp.get("plagas_fumigaciones") or 0
    areas = []

    # 1. EROSION ---------------------------------------------------------
    pts, por = 0, []
    if lote.get("pendiente") == "alta": pts += 2; por.append("el lote es muy pendiente")
    elif lote.get("pendiente") == "media": pts += 1; por.append("el lote tiene loma")
    if lote.get("labranza") == "tractor" and lote.get("pendiente") in ("alta", "media"):
        pts += 1; por.append("se ara con tractor en loma")
    if suelo.get("se_lava") == "mucho": pts += 2; por.append("la lluvia se lleva la tierra")
    elif suelo.get("se_lava") == "a_veces": pts += 1; por.append("a veces se lava la tierra")
    if lote.get("descanso") == "desnudo": pts += 1; por.append("descansa con la tierra pelada")
    if suelo.get("coberturas") is False: pts += 1; por.append("no deja coberturas")
    c = _color(pts, 2, 4)
    consejos = {0: ["Siga protegiendo la tierra: no la deje pelada en las temporadas de lluvia."],
                1: ["Siembre en curvas de nivel (atravesado a la pendiente).",
                    "Deje rastrojo o maleza baja entre cosechas para tapar la tierra."],
                2: ["Ponga barreras vivas de pasto en curvas de nivel cada 10-15 m.",
                    "Siembre atravesado a la pendiente, nunca a favor.",
                    "Evite arar con tractor en la loma; prefiera labranza mínima o con bueyes.",
                    "No deje la tierra pelada en marzo-mayo ni en septiembre-noviembre."]}[c]
    areas.append({"area": "Erosión", "color": COLOR[c], "puntos": pts, "motivos": por, "consejos": consejos})

    # 2. CANSANCIO DEL SUELO ---------------------------------------------
    pts, por = 0, []
    fam = [FAMILIA.get(h) for h in hist[:3] if FAMILIA.get(h)]
    if len(fam) >= 2 and len(set(fam[:2])) == 1:
        pts += 2; por.append(f"se repite la misma familia de planta ({fam[0]})")
    if suelo.get("produccion") == "mucho_menos": pts += 2; por.append("produce mucho menos que antes")
    elif suelo.get("produccion") == "menos": pts += 1; por.append("produce un poco menos que antes")
    if suelo.get("abono") in ("quimico", "ninguno"):
        pts += 1; por.append("no usa abono orgánico" if suelo.get("abono") == "quimico" else "no abona")
    if lote.get("descanso") == "nunca": pts += 1; por.append("el lote nunca descansa")
    if not any(f == "leguminosa" for f in fam) and hist:
        pts += 1; por.append("no ha sembrado leguminosas (fríjol, arveja)")
    c = _color(pts, 2, 4)
    consejos = {0: ["Siga rotando y metiendo fríjol de vez en cuando."],
                1: ["Meta una leguminosa (fríjol) en la próxima siembra: devuelve nitrógeno a la tierra.",
                    "Agregue abono orgánico (gallinaza o compost) al menos una vez al año."],
                2: ["Cambie de familia de planta ya: no repita lo mismo en la próxima siembra.",
                    "Siembre fríjol en la próxima temporada para devolverle nitrógeno a la tierra.",
                    "Agregue abono orgánico y haga un análisis de suelo (pregunte en la UMATA)."]}[c]
    areas.append({"area": "Cansancio del suelo", "color": COLOR[c], "puntos": pts, "motivos": por, "consejos": consejos})

    # 3. PLAGAS Y ENFERMEDADES -------------------------------------------
    pts, por = 0, []
    if len(plagas) >= 3: pts += 2; por.append(f"{len(plagas)} plagas o enfermedades")
    elif len(plagas) >= 1: pts += 1; por.append("tiene " + ", ".join(plagas))
    if fumig > 6: pts += 2; por.append(f"fumiga {fumig:.0f} veces por cosecha")
    elif fumig > 3: pts += 1; por.append(f"fumiga {fumig:.0f} veces por cosecha")
    if len(hist) >= 2 and hist[0] == hist[1]: pts += 1; por.append(f"repite {hist[0].replace('_', ' ')}")
    if lote.get("drenaje") == "encharca": pts += 1; por.append("el lote se encharca (favorece hongos)")
    c = _color(pts, 2, 4)
    consejos = {0: ["Siga revisando el cultivo cada semana."],
                1: ["Cambie de cultivo para cortar el ciclo de la plaga.",
                    "Revise el cultivo cada semana y fumigue solo cuando vea el daño."],
                2: ["No repita el mismo cultivo: la plaga ya vive en ese lote.",
                    "Pida a la UMATA o al ICA un plan de manejo integrado de plagas.",
                    "Use semilla sana o certificada y saque las plantas enfermas del lote."]}[c]
    areas.append({"area": "Plagas y enfermedades", "color": COLOR[c], "puntos": pts, "motivos": por, "consejos": consejos})

    # 4. AGUA ------------------------------------------------------------
    pts, por = 0, []
    if lote.get("drenaje") == "encharca": pts += 2; por.append("se encharca")
    if lote.get("drenaje") == "seca_rapido" and not lote.get("riego"): pts += 2; por.append("se seca rápido y no tiene riego")
    elif not lote.get("riego"): pts += 1; por.append("no tiene riego")
    c = _color(pts, 1, 2)
    consejos = {0: ["El manejo del agua está bien."],
                1: ["Sin riego, en diciembre-febrero siembre cultivos que aguanten poca agua o deje cobertura."],
                2: (["Haga zanjas de drenaje o siembre en camas altas para que no se encharque."]
                    if lote.get("drenaje") == "encharca" else
                    ["Tape la tierra con rastrojo para que guarde humedad.",
                     "Recoja agua lluvia (tanque o reservorio) para la temporada seca."])}[c]
    areas.append({"area": "Agua", "color": COLOR[c], "puntos": pts, "motivos": por, "consejos": consejos})

    peor = max(areas, key=lambda a: (["verde", "amarillo", "rojo"].index(a["color"]), a["puntos"]))
    return {"areas": areas, "prioridad": peor["area"] if peor["color"] != "verde" else None}


def texto_diagnostico(d):
    lineas = []
    for a in d["areas"]:
        lineas.append(f"{ICONO[a['color']]} {a['area']}" + (f": {', '.join(a['motivos'])}" if a["motivos"] else ""))
    if d["prioridad"]:
        lineas.append(f"Lo más urgente: {d['prioridad']}.")
    return "\n".join(lineas)


if __name__ == "__main__":
    f = sys.argv[1] if len(sys.argv) > 1 else DATOS / "respuestas_agricultor_ejemplo.json"
    d = diagnosticar(f)
    print(texto_diagnostico(d))
    print()
    for a in d["areas"]:
        print(f"{ICONO[a['color']]} {a['area'].upper()}")
        for c in a["consejos"]:
            print(f"   - {c}")
