"""
Guardar y comparar lotes.

Cada entrevista se guarda en  datos/fincas/<finca>/<lote>/<fecha>.json  junto con su
diagnostico y su recomendacion, y un resumen corto (.txt) para imprimir o mandar por WhatsApp.

Uso:
  python lotes.py                                   # lista las fincas guardadas
  python lotes.py --finca "La Esperanza"            # compara los lotes de la finca
  python lotes.py --finca "La Esperanza" --lote "Lote de arriba"   # historia de un lote
"""
import argparse
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

FINCAS = Path(__file__).parent / "datos" / "fincas"
ICONO = {"verde": "🟢", "amarillo": "🟡", "rojo": "🔴"}


def slug(txt):
    t = unicodedata.normalize("NFKD", str(txt or "sin_nombre")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_") or "sin_nombre"


def resumen_texto(resp, diag, rec):
    """Resumen corto, en lenguaje sencillo, para WhatsApp o para imprimir."""
    from motor_rotacion import texto_rotacion
    f, l = resp.get("finca", {}), resp.get("lote", {})
    lin = [f"*{f.get('nombre', 'Finca')} – {l.get('nombre', 'lote')}* ({f.get('municipio', '')})",
           datetime.now().strftime("%d/%m/%Y"), "", "*Cómo está el lote*"]
    for a in diag["areas"]:
        lin.append(f"{ICONO[a['color']]} {a['area']}")
    if diag["prioridad"]:
        a = next(x for x in diag["areas"] if x["area"] == diag["prioridad"])
        lin += ["", f"*Lo más urgente: {a['area']}*"] + [f"- {c}" for c in a["consejos"][:2]]
    if rec["rotaciones"]:
        r = rec["rotaciones"][0]
        lin += ["", "*Qué sembrar este año*", texto_rotacion(r), r["explicacion"]]
        lin += [f"- {x}" for x in (rec.get("alertas_generales", []) + r["alertas"])[:3]]
    else:
        lin += ["", "No encontramos una rotación con estas condiciones; hable con el técnico de la UMATA."]
    return "\n".join(lin)


def guardar(resp, diag, rec):
    """Guarda la entrevista y devuelve (ruta_json, ruta_resumen)."""
    carpeta = FINCAS / slug(resp.get("finca", {}).get("nombre")) / slug(resp.get("lote", {}).get("nombre"))
    carpeta.mkdir(parents=True, exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d_%H%M")
    registro = {"fecha": fecha, "respuestas": resp, "diagnostico": diag, "recomendacion": rec}
    fj = carpeta / f"{fecha}.json"
    fj.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    ft = carpeta / f"{fecha}_resumen.txt"
    ft.write_text(resumen_texto(resp, diag, rec), encoding="utf-8")
    return fj, ft


def _registros(carpeta_lote):
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(carpeta_lote.glob("*.json"))]


def _semaforos(diag):
    return " ".join(ICONO[a["color"]] for a in diag["areas"])


def listar():
    if not FINCAS.exists() or not any(FINCAS.iterdir()):
        print("Todavía no hay entrevistas guardadas.")
        return
    for finca in sorted(FINCAS.iterdir()):
        lotes = [l for l in finca.iterdir() if l.is_dir()]
        nombre = _registros(lotes[0])[-1]["respuestas"]["finca"].get("nombre", finca.name) if lotes else finca.name
        print(f"{nombre}: {len(lotes)} lote(s)")


def comparar_finca(finca):
    carpeta = FINCAS / slug(finca)
    if not carpeta.exists():
        print(f"No hay entrevistas de la finca '{finca}'.")
        return []
    from motor_rotacion import texto_rotacion
    filas = []
    print(f"Lotes de {finca}   (orden de los semáforos: Erosión · Suelo · Plagas · Agua)\n")
    for lote in sorted(l for l in carpeta.iterdir() if l.is_dir()):
        regs = _registros(lote)
        if not regs:
            continue
        r = regs[-1]
        rot = r["recomendacion"]["rotaciones"]
        fila = {"lote": r["respuestas"]["lote"].get("nombre", lote.name), "fecha": r["fecha"][:10],
                "semaforos": _semaforos(r["diagnostico"]), "urgente": r["diagnostico"]["prioridad"] or "nada urgente",
                "rotacion": texto_rotacion(rot[0]) if rot else "sin rotación"}
        filas.append(fila)
        print(f"■ {fila['lote']}  ({fila['fecha']})  {fila['semaforos']}")
        print(f"   Lo más urgente: {fila['urgente']}")
        print(f"   Qué sembrar: {fila['rotacion']}\n")
    if len(filas) > 1:
        rojos = {f["lote"]: f["semaforos"].count("🔴") for f in filas}
        peor = max(rojos, key=rojos.get)
        print(f"El lote que más atención necesita es: {peor} ({rojos[peor]} en rojo).")
    return filas


def historia_lote(finca, lote):
    carpeta = FINCAS / slug(finca) / slug(lote)
    regs = _registros(carpeta) if carpeta.exists() else []
    if not regs:
        print("No hay entrevistas de ese lote.")
        return
    print(f"Historia de {lote} ({finca})   Erosión · Suelo · Plagas · Agua\n")
    for r in regs:
        print(f"{r['fecha'][:10]}  {_semaforos(r['diagnostico'])}   "
              f"último cultivo: {(r['respuestas'].get('historial', {}).get('ultimos_cultivos') or ['-'])[0]}")
    if len(regs) > 1:
        antes = [a["color"] for a in regs[0]["diagnostico"]["areas"]]
        ahora = [a["color"] for a in regs[-1]["diagnostico"]["areas"]]
        orden = ["verde", "amarillo", "rojo"]
        mejoro = sum(orden.index(b) < orden.index(a) for a, b in zip(antes, ahora))
        empeoro = sum(orden.index(b) > orden.index(a) for a, b in zip(antes, ahora))
        print(f"\nDesde la primera visita: {mejoro} área(s) mejoraron y {empeoro} empeoraron.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--finca")
    ap.add_argument("--lote")
    a = ap.parse_args()
    if a.finca and a.lote:
        historia_lote(a.finca, a.lote)
    elif a.finca:
        comparar_finca(a.finca)
    else:
        listar()
