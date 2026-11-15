"""
Motor de rotacion de cultivos - NASA Space Apps 2026 (Field Shift)

NO usa el modulo climatico. El clima sale de dos respuestas del agricultor:
  - zona: fria / templada / calida  -> temperatura media tipica del piso termico
  - lluvias: dos temporadas (bimodal) o una larga (unimodal)
y los requisitos de cada cultivo salen SOLO de FAO ECOCROP (datos/ecocrop_cultivos.csv).
La aptitud del municipio sale de UPRA (datos/aptitud_transitorios_municipio.csv).

Uso:
  python motor_rotacion.py                                   # respuestas de ejemplo
  python motor_rotacion.py --respuestas datos/fincas/.../entrevista.json

Desde otro programa (la interfaz):
  from motor_rotacion import recomendar
  resultado = recomendar(respuestas_dict)
"""

import argparse
import json
import unicodedata
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).parent
DATOS = AQUI / "datos"

# --------------------------------------------------------------- ajustes
ORDEN_TEMPORADAS = ["Mar-May", "Jun-Ago", "Sep-Nov", "Dic-Feb"]

# Temperatura media tipica de cada piso termico de Colombia (°C).
# Es lo unico que no es ECOCROP: convierte la respuesta del agricultor en un numero.
ZONAS = {
    "fria":     {"t_media": 15.0, "rango": "12-18 °C", "altitud": "2.000-3.000 m"},
    "templada": {"t_media": 21.0, "rango": "18-24 °C", "altitud": "1.000-2.000 m"},
    "calida":   {"t_media": 26.0, "rango": "más de 24 °C", "altitud": "0-1.000 m"},
}

# Que tan lluviosa es cada temporada: 1 = lluvia, 0.5 = intermedia, 0 = seca
LLUVIAS = {
    "bimodal":  {"Mar-May": 1.0, "Jun-Ago": 0.5, "Sep-Nov": 1.0, "Dic-Feb": 0.0},
    "unimodal": {"Mar-May": 0.5, "Jun-Ago": 1.0, "Sep-Nov": 1.0, "Dic-Feb": 0.0},
    "continua": {"Mar-May": 1.0, "Jun-Ago": 1.0, "Sep-Nov": 1.0, "Dic-Feb": 0.5},
}

# Opciones del menu de cultivos que agrupan varios cultivos del motor
GRUPOS = {"name": ["name_criollo", "name_espino"], "hortalizas": ["brocoli", "repollo", "zanahoria", "lechuga"]}
# Que tanto le afectan al agricultor los anios muy secos / muy lluviosos (preguntas q12 y q13)
SENS_SECO = {"riego": 0.0, "poco": 0.3, "baja": 0.7, "pierde": 1.0}
SENS_LLUVIA = {"poco": 0.0, "hongos": 0.6, "pierde": 1.0}

USAR_UPRA = True          # poner False para no filtrar por aptitud UPRA del municipio
APTITUD_MINIMA = 10       # puntaje UPRA minimo (0-100) para aceptar un cultivo
MAX_SOLANACEAS_POR_ANIO = 1
TOLERANCIA = {"baja": 0.0, "media": 0.5, "alta": 1.0}
N_RESULTADOS = 3

# Pesos segun lo MAS importante para el agricultor (pregunta e5)
PESOS = {
    "ingreso": {"ingreso": 0.55, "riesgo": 0.15, "suelo": 0.15, "trabajo": 0.15},
    "riesgo":  {"ingreso": 0.15, "riesgo": 0.55, "suelo": 0.15, "trabajo": 0.15},
    "suelo":   {"ingreso": 0.15, "riesgo": 0.15, "suelo": 0.55, "trabajo": 0.15},
    "trabajo": {"ingreso": 0.15, "riesgo": 0.15, "suelo": 0.15, "trabajo": 0.55},
}

# Familia de cultivos que pueden aparecer en el historial aunque no esten en cultivos.csv
FAMILIAS_HISTORIAL = {"papa": "Solanaceae", "papa_criolla": "Solanaceae", "tomate": "Solanaceae",
                      "tomate_de_arbol": "Solanaceae", "arveja": "Fabaceae", "haba": "Fabaceae",
                      "frijol": "Fabaceae", "avena": "Poaceae", "pasto": "Poaceae", "kikuyo": "Poaceae",
                      "aguacate": "Lauraceae", "cafe": "Rubiaceae", "platano": "Musaceae",
                      "fresa": "Rosaceae", "mora": "Rosaceae",
                      "name": "Dioscoreaceae", "hortalizas": "Brassicaceae"}

NOMBRES = {"maiz": "maíz", "arroz": "arroz", "frijol_arbustivo": "fríjol arbustivo",
           "frijol_voluble": "fríjol voluble", "yuca": "yuca", "name_criollo": "ñame criollo",
           "name_espino": "ñame espino", "cebolla_junca": "cebolla junca", "brocoli": "brócoli",
           "repollo": "repollo", "zanahoria": "zanahoria", "lechuga": "lechuga",
           "descanso_cubierto": "descanso con cobertura"}


FEMENINOS = {"yuca", "cebolla_junca", "zanahoria", "lechuga", "papa"}


def el(c, mayus=False):
    """'el maíz' / 'la cebolla junca'."""
    a = "la" if c in FEMENINOS else "el"
    return f"{a.capitalize() if mayus else a} {nombre(c)}"


def nombre(c):
    return NOMBRES.get(c, c.replace("_", " "))


def _norm(txt):
    return unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode().lower().strip()


URABA = {"apartado", "arboletes", "carepa", "chigorodo", "murindo", "mutata", "necocli",
         "san juan de uraba", "san pedro de uraba", "turbo", "vigia del fuerte"}


def normalizar(resp):
    """Convierte las respuestas de la entrevista corta en lo que usan el motor y el diagnostico.
    La interfaz puede mandar solo las respuestas tal cual; esto se encarga del resto."""
    if resp.get("_normalizado"):
        return resp
    for k in ("finca", "lote", "restricciones", "historial", "suelo", "clima_extremo", "mercado"):
        resp.setdefault(k, {})
    f, l, h, r, ce = resp["finca"], resp["lote"], resp["historial"], resp["restricciones"], resp["clima_extremo"]

    # Historial: ultimo cultivo x numero de veces seguidas  (q6, q7)
    if "ultimos_cultivos" not in h:
        ult = h.get("ultimo_texto") if h.get("ultimo") == "otro" else h.get("ultimo")
        ult = _norm(ult).replace(" ", "_") if ult else None
        h["ultimos_cultivos"] = [ult] * int(h.get("veces") or 1) if ult else []

    # Cultivos que no puede sembrar  (q9): los grupos se abren en sus cultivos
    lista = []
    for x in r.get("sin_semilla_o_comprador", []):
        if x != "ninguno":
            lista += GRUPOS.get(x, [x])
    r["sin_semilla_o_comprador"] = lista

    # Aguacero  (q11) -> encharcamiento y erosion
    ag = l.get("aguacero")
    if ag and "drenaje" not in l:
        l["drenaje"] = "encharca" if ag in ("charcos", "ambas") else "normal"
    if ag and "se_lava" not in resp["suelo"]:
        resp["suelo"]["se_lava"] = "mucho" if ag in ("lava", "ambas") else "no"

    # Anios muy secos / muy lluviosos  (q12, q13)
    if "riego" not in l:
        l["riego"] = ce.get("seco") == "riego"
    ce["sens_seco"] = SENS_SECO.get(ce.get("seco"), 0.3)
    ce["sens_lluvia"] = SENS_LLUVIA.get(ce.get("lluvioso"), 0.3)

    # Por defecto se asume que el agricultor necesita vender todas las temporadas
    r.setdefault("aguanta_temporada_sin_venta", False)
    if f.get("lluvias") in (None, "no_se"):
        f["lluvias"] = "unimodal" if _norm(f.get("municipio", "")) in URABA else "bimodal"
    resp["_normalizado"] = True
    return resp


# ----------------------------------------------------------------- clima
def clima_de_la_finca(resp):
    zona = resp["finca"].get("zona") or "templada"
    lluvias = resp["finca"].get("lluvias")
    if lluvias not in LLUVIAS:
        lluvias = "bimodal"     # lo normal en la zona andina de Antioquia
    t = ZONAS[zona]["t_media"]
    return {temp: {"t_media": t, "lluvia": LLUVIAS[lluvias][temp]} for temp in ORDEN_TEMPORADAS}, zona, lluvias


def trapecio(x, abs_min, opt_min, opt_max, abs_max):
    """Aptitud ECOCROP: 1 dentro del rango optimo, baja en linea recta hasta 0 en los
    limites absolutos (misma forma que el modelo ECOCROP de la FAO)."""
    if x <= abs_min or x >= abs_max:
        return 0.0
    if opt_min <= x <= opt_max:
        return 1.0
    if x < opt_min:
        return (x - abs_min) / (opt_min - abs_min)
    return (abs_max - x) / (abs_max - opt_max)


def aptitud_temperatura(fila, t):
    return trapecio(t, fila["T_ABS_MIN"], fila["T_OPT_MIN"], fila["T_OPT_MAX"], fila["T_ABS_MAX"])


# -------------------------------------------------------------- cultivos
def cargar_cultivos(resp, descartes):
    c = pd.read_csv(DATOS / "cultivos.csv")
    eco = pd.read_csv(DATOS / "ecocrop_cultivos.csv")
    c = c.merge(eco, on="ESPECIE_ECOCROP", how="left")
    sin = c["T_ABS_MIN"].isna()                       # descanso: nunca se descarta por clima
    c.loc[sin, ["T_ABS_MIN", "T_OPT_MIN", "T_OPT_MAX", "T_ABS_MAX"]] = [-50, -50, 60, 60]
    c.loc[sin, ["P_ABS_MIN", "P_OPT_MIN", "P_OPT_MAX", "P_ABS_MAX"]] = [0, 0, 20000, 20000]

    c["APTITUD_UPRA"] = None
    f_apt = DATOS / "aptitud_transitorios_municipio.csv"
    muni = resp["finca"].get("municipio")
    if USAR_UPRA and muni and f_apt.exists():
        apt = pd.read_csv(f_apt)
        apt = apt[apt["Municipio"].map(_norm) == _norm(muni)]
        if not apt.empty:
            puntajes = dict(zip(apt["Cadena"], apt["PUNTAJE_APTITUD"]))
            c["APTITUD_UPRA"] = c["CADENA_UPRA"].map(lambda k: puntajes.get(k) if isinstance(k, str) else None)
            malos = c["APTITUD_UPRA"].notna() & (c["APTITUD_UPRA"] < APTITUD_MINIMA)
            for cul, val in zip(c.loc[malos, "CULTIVO"], c.loc[malos, "APTITUD_UPRA"]):
                descartes[cul] = f"poco apto en {muni} según UPRA (puntaje {val:.0f} de 100)"
            c = c[~malos]

    if resp.get("mercado", {}).get("tiene_ganado"):
        c.loc[c["CULTIVO"] == "maiz", "INGRESO_REL"] += 0.1
    # Lo que el agricultor quiere sembrar sube de puntaje  [pregunta h4]
    for cul in c["CULTIVO"]:
        if quiere(cul, resp):
            c.loc[c["CULTIVO"] == cul, "INGRESO_REL"] = min(1.0, c.loc[c["CULTIVO"] == cul, "INGRESO_REL"].iloc[0] + 0.15)
    return c.set_index("CULTIVO")


def quiere(cul, resp):
    """True si el cultivo coincide con algo de 'cultivos_interes' (ej. 'frijol' -> los dos frijoles)."""
    for x in resp.get("cultivos_interes", []):
        x = _norm(x).replace(" ", "_").replace("n~", "n")
        if x and (x in cul or x in _norm(nombre(cul)).replace(" ", "_")):
            return True
    return False


def cultivo_posible(cul, fila, temp, clima, resp):
    k = clima[temp]
    r = resp.get("restricciones", {})
    if cul in r.get("sin_semilla_o_comprador", []):
        return False, "el agricultor no puede sembrarlo (semilla, precio o comprador)"
    if not (fila["T_ABS_MIN"] < k["t_media"] < fila["T_ABS_MAX"]):
        return False, (f"no aguanta la temperatura de la zona ({k['t_media']:.0f} °C); "
                       f"según ECOCROP necesita entre {fila['T_ABS_MIN']:.0f} y {fila['T_ABS_MAX']:.0f} °C")
    if r.get("mano_obra") == "baja" and fila["TRABAJO_REL"] > 0.7:
        return False, "necesita más mano de obra de la disponible"
    # sin riego, en la temporada seca no se siembra lo que pide mucha agua (ECOCROP)
    if k["lluvia"] == 0 and not resp.get("lote", {}).get("riego") and fila["P_OPT_MIN"] >= 1000:
        return False, f"en {temp} (seco) y sin riego no le alcanza el agua (ECOCROP pide más de {fila['P_OPT_MIN']:.0f} mm al año)"
    return True, ""


FALLOS = {}


def generar_rotaciones(cultivos, clima, resp, descartes):
    FALLOS.clear()
    nombres = list(cultivos.index)

    def colocar(slot, secuencia):
        if slot == len(ORDEN_TEMPORADAS):
            yield list(secuencia)
            return
        for cul in nombres:
            fila = cultivos.loc[cul]
            dur = int(fila["TEMPORADAS_CICLO"])
            if slot + dur > len(ORDEN_TEMPORADAS):
                continue
            ok = True
            for s in range(slot, slot + dur):
                bien, motivo = cultivo_posible(cul, fila, ORDEN_TEMPORADAS[s], clima, resp)
                if not bien:
                    FALLOS.setdefault(cul, {})[ORDEN_TEMPORADAS[s]] = motivo
                    ok = False
                    break
            if ok:
                secuencia.append((cul, dur))
                yield from colocar(slot + dur, secuencia)
                secuencia.pop()

    validas = []
    for colocados in colocar(0, []):
        bloques = [c for c, _ in colocados]
        familias = [cultivos.loc[b, "FAMILIA"] for b in bloques]
        ciclo = familias + [familias[0]] if len(familias) > 1 else familias
        if any(a == b and a != "Ninguna" for a, b in zip(ciclo, ciclo[1:])):
            continue
        if familias.count("Solanaceae") > MAX_SOLANACEAS_POR_ANIO:
            continue
        if not resp.get("restricciones", {}).get("aguanta_temporada_sin_venta", False):
            if any(cultivos.loc[b, "INGRESO_REL"] == 0 for b in bloques):
                continue
        validas.append([c for c, d in colocados for _ in range(d)])
    usados = {c for seq in validas for c in seq}
    for c in cultivos.index:
        if c in usados or c in descartes:
            continue
        f = FALLOS.get(c, {})
        if c == "descanso_cubierto" and not resp.get("restricciones", {}).get("aguanta_temporada_sin_venta", False):
            descartes[c] = "el agricultor no puede dejar una temporada sin vender"
        elif f and len(set(f.values())) == 1 and len(f) == len(ORDEN_TEMPORADAS):
            descartes[c] = next(iter(f.values()))
        elif f:
            descartes[c] = "no encaja en una rotación completa del año (" + "; ".join(f"{t}: {m}" for t, m in f.items()) + ")"
        else:
            descartes[c] = "no encaja en una rotación completa del año con las demás reglas (familias, temporadas o venta)"
    return validas


# --------------------------------------------------------------- puntaje
def pesos(resp, diag=None):
    w = dict(PESOS.get(resp.get("prioridad_principal"), {"ingreso": .25, "riesgo": .25, "suelo": .25, "trabajo": .25}))
    # Si el diagnostico del lote sale en rojo en erosion o cansancio del suelo,
    # cuidar la tierra pesa mas (+0.15 por cada area en rojo)
    if diag:
        rojos = sum(a["color"] == "rojo" for a in diag["areas"] if a["area"] in ("Erosión", "Rotación y suelo"))
        w["suelo"] += 0.15 * rojos
        tot = sum(w.values())
        w = {k: v / tot for k, v in w.items()}
    return w


def puntuar(seq, cultivos, clima, resp, w):
    lote = resp.get("lote", {})
    erosion = 1.0 + {"alta": 0.5, "media": 0.2}.get(lote.get("pendiente"), 0) + (0.3 if lote.get("labranza") == "tractor" else 0)
    ce = resp.get("clima_extremo", {})
    humedad = (1.2 if lote.get("drenaje") == "encharca" else 1.0) + 0.3 * ce.get("sens_lluvia", 0.3)
    sens_seco = ce.get("sens_seco", 0.3)

    ingreso, riesgo, suelo, trabajo, apt = [], [], [], [], []
    for temp, cul in zip(ORDEN_TEMPORADAS, seq):
        f, k = cultivos.loc[cul], clima[temp]
        a = aptitud_temperatura(f, k["t_media"])
        r_hongos = k["lluvia"] * (1 - TOLERANCIA[f["TOLERANCIA_HONGOS"]]) * humedad
        r_erosion = k["lluvia"] * (1 - f["APORTE_SUELO"]) * erosion / 1.8
        sed = 1.0 if f["P_OPT_MIN"] >= 1000 else 0.5 if f["P_OPT_MIN"] >= 800 else 0.0   # que tanta agua pide (ECOCROP)
        r_seco = 0.0 if lote.get("riego") else min(1.0, (1 - k["lluvia"]) * sed * (0.5 + sens_seco))
        riesgo.append(min(1.0, 0.40 * (1 - a) + 0.25 * min(1.0, r_hongos) + 0.15 * r_erosion + 0.20 * r_seco))
        ingreso.append(f["INGRESO_REL"]); trabajo.append(f["TRABAJO_REL"]); apt.append(a)
        suelo.append(min(1.0, f["APORTE_SUELO"] + 0.2 * f["FIJA_NITROGENO"]))

    S = sum(suelo) / len(suelo)
    hist = resp.get("historial", {}).get("ultimos_cultivos", [])
    if hist:
        fam = cultivos.loc[hist[0], "FAMILIA"] if hist[0] in cultivos.index else FAMILIAS_HISTORIAL.get(hist[0])
        if fam and fam == cultivos.loc[seq[0], "FAMILIA"]:
            S *= 0.7

    comp = {"ingreso": sum(ingreso) / 4, "riesgo_clima": sum(riesgo) / 4, "suelo": S,
            "trabajo": sum(trabajo) / 4, "aptitud_ecocrop": sum(apt) / 4}
    total = (w["ingreso"] * comp["ingreso"] + w["riesgo"] * (1 - comp["riesgo_clima"])
             + w["suelo"] * comp["suelo"] + w["trabajo"] * (1 - comp["trabajo"]))
    return round(total, 3), {k: round(v, 2) for k, v in comp.items()}, riesgo


def alertas(seq, riesgo, cultivos, clima, resp):
    out, vistos = [], set()
    for temp, cul, r in zip(ORDEN_TEMPORADAS, seq, riesgo):
        f, k = cultivos.loc[cul], clima[temp]
        if cul not in vistos and cul != "descanso_cubierto":
            vistos.add(cul)
            if k["t_media"] < f["T_OPT_MIN"]:
                out.append(f"{el(cul, True)} crece más lento con esta temperatura (le va mejor desde {f['T_OPT_MIN']:.0f} °C): use semilla adaptada a la zona.")
            elif k["t_media"] > f["T_OPT_MAX"]:
                out.append(f"{el(cul, True)} sufre con el calor (le va mejor por debajo de {f['T_OPT_MAX']:.0f} °C).")
        if r >= 0.4 and k["lluvia"] == 1 and cul != "descanso_cubierto":
            out.append(f"{temp}: temporada de lluvia; vigile hongos en {el(cul)}.")
    return out


def alertas_generales(resp):
    out = []
    hist = resp.get("historial", {}).get("ultimos_cultivos", [])
    if len(hist) >= 2 and hist[0] == hist[1]:
        out.append(f"Este lote viene de {nombre(hist[0])} repetido: lo más importante ahora es cambiar de familia de planta.")
    if hist and hist[0] in ("papa", "tomate"):
        out.append(f"No vuelva a sembrar {nombre(hist[0])} en este lote hasta completar la rotación.")
    return out


def alertas_rotacion(seq, cultivos, resp):
    out = []
    if resp.get("perfil", {}).get("tenencia") in ("arrendada", "compania"):
        largos = {c for c in seq if cultivos.loc[c, "TEMPORADAS_CICLO"] >= 3}
        for c in largos:
            out.append(f"{el(c, True)} ocupa el lote casi todo el año: tenga en cuenta el tiempo del arriendo o del acuerdo.")
    ce = resp.get("clima_extremo", {})
    cults = [c for c in dict.fromkeys(seq) if c != "descanso_cubierto"]
    if cults and ce.get("sens_seco", 0) >= 0.7:
        aguanta = min(cults, key=lambda c: cultivos.loc[c, "P_OPT_MIN"])
        out.append(f"Si le avisan que viene un año muy seco, de esta rotación el que mejor aguanta es {el(aguanta)}; "
                   "tape la tierra con rastrojo para guardar humedad.")
    if cults and ce.get("sens_lluvia", 0) >= 0.6:
        resiste = max(cults, key=lambda c: TOLERANCIA[cultivos.loc[c, "TOLERANCIA_HONGOS"]])
        out.append(f"Si le avisan que viene un año muy lluvioso, el más resistente a hongos de esta rotación es {el(resiste)}; "
                   "haga drenajes antes de las lluvias.")
    pedidos = [nombre(c) for c in dict.fromkeys(seq) if quiere(c, resp)]
    if pedidos:
        out.append("Incluye lo que usted quiere sembrar: " + ", ".join(pedidos) + ".")
    return out


def explicar(comp, w):
    ap = {"le deja buena plata": w["ingreso"] * comp["ingreso"],
          "tiene poco riesgo": w["riesgo"] * (1 - comp["riesgo_clima"]),
          "cuida la tierra": w["suelo"] * comp["suelo"],
          "da poco trabajo": w["trabajo"] * (1 - comp["trabajo"])}
    return f"Se recomienda porque {max(ap, key=ap.get)}."


# -------------------------------------------------------------- principal
def recomendar(resp, diag=None):
    """resp = dict con las respuestas (o ruta a un JSON); diag = salida de diagnostico.diagnosticar
    (opcional). Devuelve un dict listo para la interfaz."""
    if not isinstance(resp, dict):
        resp = json.loads(Path(resp).read_text(encoding="utf-8"))
    resp = normalizar(resp)
    clima, zona, lluvias = clima_de_la_finca(resp)
    descartes = {}
    cultivos = cargar_cultivos(resp, descartes)
    seqs = generar_rotaciones(cultivos, clima, resp, descartes)
    if diag is None:
        from diagnostico import diagnosticar
        diag = diagnosticar(resp)
    w = pesos(resp, diag)
    ev = sorted(((*puntuar(s, cultivos, clima, resp, w), s) for s in seqs), key=lambda x: -x[0])

    res = {
        "municipio": resp["finca"].get("municipio"),
        "perfil": resp.get("perfil", {}),
        "zona": zona, "temperatura_supuesta_C": ZONAS[zona]["t_media"], "lluvias": lluvias,
        "pesos": {k: round(v, 2) for k, v in w.items()}, "n_rotaciones_validas": len(ev), "rotaciones": [],
        "cultivos_descartados": descartes,
        "alertas_generales": alertas_generales(resp),
        "aviso": ("Clima: zona dicha por el agricultor + rangos FAO ECOCROP. Aptitud del municipio: UPRA. "
                  "Tolerancia a hongos, aporte al suelo, ingreso y trabajo son ESTIMADOS (datos/cultivos.csv)."),
    }
    for i, (total, comp, r, seq) in enumerate(ev[:N_RESULTADOS], start=1):
        res["rotaciones"].append({
            "puesto": i, "puntaje": total,
            "secuencia": [{"temporada": t, "cultivo": c, "nombre": nombre(c),
                           "familia": cultivos.loc[c, "FAMILIA"], "tipo": cultivos.loc[c, "TIPO"],
                           "aptitud_ecocrop": round(aptitud_temperatura(cultivos.loc[c], clima[t]["t_media"]), 2)}
                          for t, c in zip(ORDEN_TEMPORADAS, seq)],
            "componentes": comp, "explicacion": explicar(comp, w),
            "alertas": alertas_rotacion(seq, cultivos, resp) + alertas(seq, r, cultivos, clima, resp),
        })
    return res


def texto_rotacion(rot):
    """'Mar-May fríjol voluble → Sep-Nov brócoli → ...' sin repetir un cultivo que ocupa varias temporadas."""
    partes, prev = [], None
    for s in rot["secuencia"]:
        if s["cultivo"] != prev:
            partes.append(f"{s['temporada']}: {s['nombre']}")
        prev = s["cultivo"]
    return "  →  ".join(partes)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--respuestas", default=str(DATOS / "respuestas_agricultor_ejemplo.json"))
    ap.add_argument("--salida", default=str(AQUI / "resultado_rotacion.json"))
    a = ap.parse_args()
    res = recomendar(a.respuestas)
    Path(a.salida).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{res['municipio']} | zona {res['zona']} (~{res['temperatura_supuesta_C']:.0f} °C) | lluvias {res['lluvias']}")
    for x in res["alertas_generales"]:
        print(f"  ! {x}")
    for c, m in res["cultivos_descartados"].items():
        print(f"  no se recomienda {nombre(c)}: {m}")
    print(f"Rotaciones posibles: {res['n_rotaciones_validas']}\n")
    for r in res["rotaciones"]:
        print(f"{r['puesto']}. {texto_rotacion(r)}   [{r['puntaje']}]")
        print(f"   {r['explicacion']}")
        for x in r["alertas"]:
            print(f"   ! {x}")
