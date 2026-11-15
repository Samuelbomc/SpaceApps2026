"""
Entrevista al agricultor (version por terminal; la interfaz hace lo mismo con botones).

  python entrevista.py              # entrevista corta (13 preguntas)
  python entrevista.py --completa   # agrega preguntas opcionales

Al final muestra como esta el lote y que sembrar, y ofrece guardarlo
(datos/fincas/<finca>/<lote>/) con un resumen corto para WhatsApp.

Durante la entrevista:
  - escriba el NUMERO de la opcion (si puede marcar varias: 1,3)
  - escriba ? para saber por que se hace la pregunta
  - presione Enter para saltarla
"""
import argparse
import json
import unicodedata
from pathlib import Path

import pandas as pd

from diagnostico import diagnosticar
from lotes import guardar, resumen_texto
from motor_rotacion import recomendar

DATOS = Path(__file__).parent / "datos"
DEFECTOS = {"lote.nombre": "Lote 1", "finca.zona": "templada", "lote.pendiente": "media",
            "mercado.tiene_ganado": False, "restricciones.sin_semilla_o_comprador": []}


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


def opciones_de(p, banco):
    """Las opciones pueden venir escritas o armarse con el menu de los 8 cultivos."""
    o = p.get("opciones", [])
    if isinstance(o, str) and o.startswith("cultivos_menu"):
        o = banco["cultivos_menu"] + p.get("opciones_extra", [])
    return o


def preguntar(p, banco, lista_muni):
    t = p["tipo"]
    ops = opciones_de(p, banco)
    while True:
        if t in ("opcion", "multi_opcion"):
            for i, o in enumerate(ops, 1):
                print(f"   {i}. {o['texto']}")
            if t == "multi_opcion":
                print("   (puede marcar varios, separados por coma: 1,3)")
        elif t == "si_no":
            print("   1. Sí    2. No")
        r = leer()
        if r == "?":
            print(f"   ℹ {p.get('ayuda', 'Nos ayuda a darle una mejor recomendación.')}")
            continue
        if not r:
            return None, None
        if t == "opcion":
            if r.isdigit() and 1 <= int(r) <= len(ops):
                v = ops[int(r) - 1]["valor"]
                extra = leer("   ¿Cuál? > ") if v == p.get("pide_texto_si") else None
                return v, extra
            print("   Escriba el número de una opción.")
        elif t == "multi_opcion":
            nums = [x.strip() for x in r.split(",")]
            if all(n.isdigit() and 1 <= int(n) <= len(ops) for n in nums):
                return [ops[int(n) - 1]["valor"] for n in nums], None
            print("   Escriba los números separados por coma, por ejemplo 1,3.")
        elif t == "si_no":
            if _norm(r) in ("1", "s", "si"):
                return True, None
            if _norm(r) in ("2", "n", "no"):
                return False, None
            print("   Escriba 1 (Sí) o 2 (No).")
        elif t == "municipio":
            enc = [m for m in lista_muni if _norm(m) == _norm(r)] or [m for m in lista_muni if _norm(r) in _norm(m)]
            if len(enc) == 1:
                print(f"   ✓ {enc[0]}")
                return enc[0], None
            if len(enc) > 1:
                for i, m in enumerate(enc[:9], 1):
                    print(f"   {i}. {m}")
                e = leer("   ¿Cuál es? > ")
                if e.isdigit() and 1 <= int(e) <= len(enc[:9]):
                    return enc[int(e) - 1], None
            else:
                print("   No encontramos ese municipio de Antioquia. Escríbalo de nuevo (o Enter para saltar).")
        else:
            return r, None


def visible(p, resp):
    c = p.get("mostrar_si")
    if not c:
        return True
    v = obtener(resp, c["campo"])
    return bool(v) if c.get("no_vacio") else v == c.get("igual")


def entrevistar(completa=False):
    banco = json.loads((DATOS / "preguntas_agricultor.json").read_text(encoding="utf-8"))
    preguntas = [p for p in banco["preguntas"] if completa or p["nivel"] == "basico"]
    lista_muni = municipios()
    resp = {}
    print("\nEscriba el número de la opción · ? = por qué preguntamos · Enter = saltar")
    tema, n = None, 0
    for p in preguntas:
        if not visible(p, resp):
            continue
        n += 1
        if p["tema"] != tema:
            tema = p["tema"]
            print(f"\n── {tema} ──")
        print(f"\n[{n}/{len(preguntas)}] {p['texto']}")
        v, extra = preguntar(p, banco, lista_muni)
        if v is not None:
            poner(resp, p["campo"], v)
            if extra:
                poner(resp, p["campo"] + "_texto", extra)
    for ruta, valor in DEFECTOS.items():
        if obtener(resp, ruta) is None:
            poner(resp, ruta, valor)
    return resp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--completa", action="store_true", help="agrega las preguntas opcionales")
    a = ap.parse_args()

    resp = entrevistar(a.completa)
    diag = diagnosticar(resp)
    rec = recomendar(resp, diag)

    print("\n" + "=" * 55)
    print(resumen_texto(resp, diag, rec).replace("*", ""))
    print("=" * 55)
    finca = leer("\n¿Quiere guardar este lote? Escriba el nombre de la finca (Enter = no guardar): ")
    if finca:
        poner(resp, "finca.nombre", finca)
        fj, ft = guardar(resp, diag, rec)
        print(f"Guardado en: {fj}")
        print(f"Resumen para WhatsApp: {ft}")


if __name__ == "__main__":
    main()
