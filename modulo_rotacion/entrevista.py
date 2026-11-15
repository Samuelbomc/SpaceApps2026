"""
Entrevista al agricultor (version por terminal; la interfaz hace lo mismo con botones).

  python entrevista.py              # entrevista corta (22 preguntas, casi todas de escoger)
  python entrevista.py --completa   # agrega las preguntas abiertas para el equipo

Al final muestra el diagnostico del lote y la rotacion recomendada, guarda todo en
datos/fincas/<finca>/<lote>/ y deja un resumen corto para WhatsApp.

Durante la entrevista:
  - escriba el NUMERO de la opcion
  - escriba ? para saber por que se hace la pregunta
  - presione Enter para saltarla
"""
import argparse
import json
import unicodedata
from pathlib import Path

import pandas as pd

from diagnostico import diagnosticar, texto_diagnostico
from lotes import guardar, resumen_texto
from motor_rotacion import recomendar

DATOS = Path(__file__).parent / "datos"

DEFECTOS = {
    "finca.nombre": "Mi finca", "lote.nombre": "Lote 1", "finca.zona": "templada", "finca.lluvias": "bimodal",
    "lote.pendiente": "media", "lote.drenaje": "normal", "lote.riego": False, "lote.labranza": "manual",
    "historial.ultimos_cultivos": [], "plagas_recurrentes": [], "restricciones.sin_semilla_o_comprador": [],
    "restricciones.aguanta_temporada_sin_venta": True, "restricciones.mano_obra": "media",
    "mercado.tiene_ganado": False, "prioridad_principal": "ingreso",
}


def _norm(t):
    return unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower().strip()


def municipios():
    f = DATOS / "aptitud_transitorios_municipio.csv"
    return sorted(pd.read_csv(f)["Municipio"].unique()) if f.exists() else []


def leer(prompt="   > "):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def obtener(dic, ruta):
    for p in ruta.split("."):
        if not isinstance(dic, dict) or p not in dic:
            return None
        dic = dic[p]
    return dic


def poner(dic, ruta, valor):
    partes = ruta.split(".")
    for p in partes[:-1]:
        dic = dic.setdefault(p, {})
    dic[partes[-1]] = valor


def preguntar(p, lista_muni):
    """Devuelve la respuesta ya convertida, o None si el agricultor la salta."""
    t = p["tipo"]
    while True:
        if t == "opcion":
            for i, o in enumerate(p["opciones"], 1):
                print(f"   {i}. {o['texto']}")
        elif t == "si_no":
            print("   1. Sí    2. No")
        elif t.startswith("lista"):
            print("   (si son varios, sepárelos con coma)")
        r = leer()
        if r == "?":
            print(f"   ℹ {p.get('ayuda', 'Nos ayuda a darle una mejor recomendación.')}")
            continue
        if not r:
            return None
        if t == "opcion":
            if r.isdigit() and 1 <= int(r) <= len(p["opciones"]):
                return p["opciones"][int(r) - 1]["valor"]
            print("   Escriba el número de una opción.")
        elif t == "si_no":
            if _norm(r) in ("1", "s", "si"):
                return True
            if _norm(r) in ("2", "n", "no"):
                return False
            print("   Escriba 1 (Sí) o 2 (No).")
        elif t == "numero":
            try:
                return float(r.replace(",", "."))
            except ValueError:
                print("   Escriba solo el número.")
        elif t.startswith("lista"):
            items = [x.strip().lower() for x in r.split(",") if x.strip()]
            return [_norm(x).replace(" ", "_") for x in items] if t == "lista_cultivos" else items
        elif t == "municipio":
            encontrados = [m for m in lista_muni if _norm(m) == _norm(r)] or \
                          [m for m in lista_muni if _norm(r) in _norm(m)]
            if len(encontrados) == 1:
                print(f"   ✓ {encontrados[0]}")
                return encontrados[0]
            if len(encontrados) > 1:
                for i, m in enumerate(encontrados[:9], 1):
                    print(f"   {i}. {m}")
                e = leer("   ¿Cuál es? > ")
                if e.isdigit() and 1 <= int(e) <= len(encontrados[:9]):
                    return encontrados[int(e) - 1]
            else:
                print("   No encontramos ese municipio de Antioquia. Escríbalo de nuevo (o Enter para saltar).")
        else:
            return r


def visible(p, resp):
    c = p.get("mostrar_si")
    if not c:
        return True
    v = obtener(resp, c["campo"])
    return bool(v) if c.get("no_vacio") else v == c.get("igual")


def entrevistar(completa=False):
    banco = json.loads((DATOS / "preguntas_agricultor.json").read_text(encoding="utf-8"))["preguntas"]
    banco = [p for p in banco if completa or p["nivel"] == "basico"]
    lista_muni = municipios()
    resp = {}
    print("\nEscriba el número de la opción · ? = por qué preguntamos · Enter = saltar\n")
    tema = None
    hechas = 0
    for p in banco:
        if not visible(p, resp):
            continue
        hechas += 1
        if p["tema"] != tema:
            tema = p["tema"]
            print(f"\n── {tema} ──")
        print(f"\n[{hechas}/{len(banco)}] {p['texto']}")
        r = preguntar(p, lista_muni)
        if r is not None:
            poner(resp, p["campo"], r)
    for ruta, valor in DEFECTOS.items():
        if obtener(resp, ruta) is None:
            poner(resp, ruta, valor)
    return resp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--completa", action="store_true", help="incluye las preguntas abiertas")
    ap.add_argument("--no-guardar", action="store_true")
    a = ap.parse_args()

    resp = entrevistar(a.completa)
    diag = diagnosticar(resp)
    rec = recomendar(resp, diag)

    print("\n" + "=" * 50)
    print(resumen_texto(resp, diag, rec).replace("*", ""))
    print("=" * 50)
    if not a.no_guardar:
        fj, ft = guardar(resp, diag, rec)
        print(f"\nGuardado en: {fj}")
        print(f"Resumen para WhatsApp: {ft}")


if __name__ == "__main__":
    main()
