"""
Diagnostico del lote: semaforo (verde / amarillo / rojo) con consejos, a partir de las
respuestas del agricultor. No necesita clima ni otros datos.

Areas:  erosion  ·  rotacion y suelo  ·  agua

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
    from motor_rotacion import normalizar
    resp = normalizar(resp)
    lote, suelo = resp.get("lote", {}), resp.get("suelo", {})
    hist = resp.get("historial", {}).get("ultimos_cultivos", [])
    LIMPIOS = {"papa", "papa_criolla", "tomate", "zanahoria", "brocoli", "repollo", "lechuga", "coliflor",
               "cebolla", "cebolla_junca", "maiz", "yuca", "arracacha"}
    areas = []

    # 1. EROSION ---------------------------------------------------------
    er = resp.get("erosion", {})
    loma = lote.get("pendiente") in ("alta", "media")
    pts, por, cons = 0, [], []
    if lote.get("pendiente") == "alta": pts += 2; por.append("el lote es muy inclinado")
    elif lote.get("pendiente") == "media": pts += 1; por.append("el lote es inclinado")
    if loma and lote.get("labranza") == "tractor":
        pts += 1; por.append("se ara con tractor en loma")
        cons.append("Evite el tractor en la loma: prefiera labranza mínima (solo abrir el hueco para sembrar) o bueyes.")
    if loma and er.get("surcos") == "a_favor":
        pts += 2; por.append("los surcos van de arriba hacia abajo")
        cons.append("Haga los surcos atravesados a la bajada, siguiendo curvas a nivel.")
    cob = er.get("cobertura") or ("pelada" if lote.get("descanso") == "desnudo" else None)
    if cob == "pelada":
        pts += 1; por.append("la tierra queda pelada entre cosechas")
        cons.append("No deje la tierra pelada: deje el rastrojo encima o siembre una cobertura.")
    elif hist and hist[0] in LIMPIOS and loma and not cob:
        pts += 1; por.append(f"{hist[0].replace('_', ' ')} deja la tierra suelta y destapada en loma")
    if er.get("quema") == "siempre":
        pts += 2; por.append("quema el rastrojo")
        cons.append("No queme el rastrojo: píquelo y déjelo encima, protege la tierra y la abona.")
    elif er.get("quema") == "a_veces":
        pts += 1; por.append("a veces quema el rastrojo")
        cons.append("Evite quemar: el rastrojo encima protege la tierra.")
    barreras = [x for x in er.get("barreras", []) if x != "ninguna"]
    if loma and "barreras" in er and not barreras:
        pts += 1; por.append("no tiene barreras que frenen el agua")
        cons.append("Siembre barreras vivas de pasto o caña atravesadas cada 10-15 m de bajada.")
    senales = [x for x in er.get("senales", []) if x != "ninguna"]
    if senales:
        pts += 2 if len(senales) >= 2 else 1
        por.append("ya hay señales de erosión (" + ", ".join({"raices": "raíces o piedras al aire", "carcavas": "zanjas",
                   "acumulacion": "tierra amontonada abajo", "agua_turbia": "agua turbia"}[x] for x in senales) + ")")
        if "carcavas" in senales:
            cons.append("Tape las zanjas con ramas, piedras o costales de tierra y siembre pasto en ellas.")
    elif suelo.get("se_lava") == "mucho":
        pts += 2; por.append("la lluvia se lleva la tierra")
    elif suelo.get("se_lava") == "a_veces":
        pts += 1; por.append("a veces se lava la tierra")
    if suelo.get("coberturas") is False and not cob:
        pts += 1; por.append("no deja coberturas")
    c = _color(pts, 2, 4)
    if c == 0:
        cons = ["Siga protegiendo la tierra: no la deje pelada en las temporadas de lluvia."]
    elif not cons:
        cons = ["Siembre atravesado a la bajada y deje rastrojo encima entre cosechas.",
                "Ponga barreras vivas de pasto en curvas a nivel."]
    areas.append({"area": "Erosión", "color": COLOR[c], "puntos": pts, "motivos": por, "consejos": cons})

    # 2. CANSANCIO DEL SUELO ---------------------------------------------
    pts, por = 0, []
    fam = [FAMILIA.get(h) for h in hist[:3] if FAMILIA.get(h)]
    if len(hist) >= 2 and hist[0] == hist[1]:
        pts += 3; por.append(f"repite {hist[0].replace('_', ' ')} en el mismo lote")
    elif len(fam) >= 2 and len(set(fam[:2])) == 1:
        pts += 2; por.append(f"se repite la misma familia de planta ({fam[0]})")
    if suelo.get("produccion") == "mucho_menos": pts += 2; por.append("produce mucho menos que antes")
    elif suelo.get("produccion") == "menos": pts += 1; por.append("produce un poco menos que antes")
    if suelo.get("abono") in ("quimico", "ninguno"):
        pts += 1; por.append("no usa abono orgánico" if suelo.get("abono") == "quimico" else "no abona")
    if lote.get("descanso") == "nunca": pts += 1; por.append("el lote nunca descansa")
    if not any(f == "leguminosa" for f in fam) and hist:
        pts += 1; por.append("no ha sembrado leguminosas (fríjol, arveja)")
    c = _color(pts, 2, 4)
    consejos = {0: ["Va bien: siga cambiando de cultivo y meta fríjol de vez en cuando."],
                1: ["Meta una leguminosa (fríjol) en la próxima siembra: devuelve nitrógeno a la tierra.",
                    "Agregue abono orgánico (gallinaza o compost) al menos una vez al año."],
                2: ["Cambie de familia de planta ya: no repita lo mismo en la próxima siembra.",
                    "Siembre fríjol en la próxima temporada para devolverle nitrógeno a la tierra.",
                    "Repetir cultivo acumula plagas y enfermedades en el lote: rotar las corta.",
                    "Agregue abono orgánico y haga un análisis de suelo (pregunte en la UMATA)."]}[c]
    areas.append({"area": "Rotación y suelo", "color": COLOR[c], "puntos": pts, "motivos": por, "consejos": consejos})

    # 3. AGUA Y AÑOS EXTREMOS -------------------------------------------
    ce = resp.get("clima_extremo", {})
    pts, por = 0, []
    if lote.get("drenaje") == "encharca": pts += 2; por.append("se encharca cuando llueve duro")
    if ce.get("seco") == "pierde": pts += 2; por.append("ha perdido cosechas en años muy secos")
    elif ce.get("seco") == "baja": pts += 1; por.append("la cosecha baja mucho en años muy secos")
    if ce.get("lluvioso") == "pierde": pts += 2; por.append("ha perdido cosechas en años muy lluviosos")
    elif ce.get("lluvioso") == "hongos": pts += 1; por.append("el cultivo se enferma en años muy lluviosos")
    c = _color(pts, 2, 3)
    cons = []
    if lote.get("drenaje") == "encharca" or ce.get("lluvioso") in ("hongos", "pierde"):
        cons += ["Haga zanjas de drenaje o siembre en camas altas antes de las lluvias.",
                 "En años muy lluviosos prefiera los cultivos más resistentes a hongos de su rotación."]
    if ce.get("seco") in ("baja", "pierde"):
        cons += ["Tape la tierra con rastrojo para que guarde humedad en verano.",
                 "Recoja agua lluvia (tanque o reservorio) para los años secos."]
    if not cons:
        cons = ["El lote maneja bien el agua; siga así."]
    areas.append({"area": "Agua y años extremos", "color": COLOR[c], "puntos": pts, "motivos": por, "consejos": cons})

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
