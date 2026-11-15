"""Motor de rotación: consume AnalysisResult de XGBoost, catálogo y contexto del lote.

Sin predicciones no se reemplaza el clima con la zona o lluvia de la entrevista.
Los escenarios son condicionales; no constituyen recomendaciones anuales aprobadas.
Ejecutar desde la raíz: python -m modulo_rotacion.motor_rotacion --help
"""

import argparse
import json
import unicodedata
from copy import deepcopy
from pathlib import Path

from ml.recommendations.rotation import ForecastRotationEngine, normalized
from packages.contracts.api import AnalysisResult

DATOS = Path(__file__).parent / "datos"

GRUPOS = {
    "name": ["name_criollo", "name_espino"],
    "hortalizas": ["brocoli", "repollo", "zanahoria", "lechuga"],
}

SENS_SECO = {"riego": 0.0, "poco": 0.3, "baja": 0.7, "pierde": 1.0}

SENS_LLUVIA = {"poco": 0.0, "hongos": 0.6, "pierde": 1.0}

FAMILIAS_HISTORIAL = {
    "papa": "Solanaceae",
    "papa_criolla": "Solanaceae",
    "tomate": "Solanaceae",
    "tomate_de_arbol": "Solanaceae",
    "arveja": "Fabaceae",
    "haba": "Fabaceae",
    "frijol": "Fabaceae",
    "avena": "Poaceae",
    "pasto": "Poaceae",
    "kikuyo": "Poaceae",
    "aguacate": "Lauraceae",
    "cafe": "Rubiaceae",
    "platano": "Musaceae",
    "fresa": "Rosaceae",
    "mora": "Rosaceae",
    "name": "Dioscoreaceae",
    "hortalizas": "Brassicaceae",
}

NOMBRES = {
    "maiz": "maíz",
    "arroz": "arroz",
    "frijol_arbustivo": "fríjol arbustivo",
    "frijol_voluble": "fríjol voluble",
    "yuca": "yuca",
    "name_criollo": "ñame criollo",
    "name_espino": "ñame espino",
    "cebolla_junca": "cebolla junca",
    "brocoli": "brócoli",
    "repollo": "repollo",
    "zanahoria": "zanahoria",
    "lechuga": "lechuga",
    "descanso_cubierto": "descanso con cobertura",
}


def nombre(c):
    return NOMBRES.get(c, c.replace("_", " "))


def _norm(txt):
    return (
        unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode().lower().strip()
    )


def normalizar(resp):
    """Convierte las respuestas de la entrevista corta en lo que usan el motor y el diagnostico.
    La interfaz puede mandar solo las respuestas tal cual; esto se encarga del resto."""
    if resp.get("_normalizado"):
        return resp
    for k in ("finca", "lote", "restricciones", "historial", "suelo", "clima_extremo", "mercado"):
        resp.setdefault(k, {})
    lote, h, r, ce = (
        resp["lote"],
        resp["historial"],
        resp["restricciones"],
        resp["clima_extremo"],
    )

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
    ag = lote.get("aguacero")
    if ag and "drenaje" not in lote:
        lote["drenaje"] = "encharca" if ag in ("charcos", "ambas") else "normal"
    if ag and "se_lava" not in resp["suelo"]:
        resp["suelo"]["se_lava"] = "mucho" if ag in ("lava", "ambas") else "no"

    # Anios muy secos / muy lluviosos  (q12, q13)
    if "riego" not in lote:
        lote["riego"] = ce.get("seco") == "riego"
    ce["sens_seco"] = SENS_SECO.get(ce.get("seco"), 0.3)
    ce["sens_lluvia"] = SENS_LLUVIA.get(ce.get("lluvioso"), 0.3)

    # Por defecto se asume que el agricultor necesita vender todas las temporadas
    r.setdefault("aguanta_temporada_sin_venta", False)
    resp["_normalizado"] = True
    return resp


def recomendar(resp, diag=None, *, analisis=None, region_id=None, motor=None):
    """La entrevista aporta restricciones; el clima y suelo deben venir de XGBoost.

    region_id identifica explícitamente la región asociada al lote. No se asigna
    una predicción regional a una finca por coincidencia de nombre del municipio.
    diag se conserva por compatibilidad; no sustituye predicciones de suelo.
    """
    if not isinstance(resp, dict):
        resp = json.loads(Path(resp).read_text(encoding="utf-8"))
    resp = normalizar(deepcopy(resp))
    result = {
        "municipio": resp["finca"].get("municipio"),
        "rotaciones": [],
        "n_rotaciones_validas": 0,
        "alertas_generales": [],
        "escenarios_condicionales": [],
        "status": "pending_forecasts",
        "evaluacion_rotacion": None,
        "aviso": "Faltan predicciones de clima y suelo de XGBoost para evaluar la rotación.",
    }
    if analisis is None:
        return result
    if isinstance(analisis, (str, Path)):
        analisis = json.loads(Path(analisis).read_text(encoding="utf-8"))
    analysis = (
        analisis
        if isinstance(analisis, AnalysisResult)
        else AnalysisResult.model_validate(analisis)
    )
    declared = resp["finca"].get("region_id")
    if declared and region_id and declared != region_id:
        raise ValueError("La región declarada en la finca difiere de la solicitada.")
    expected = region_id or declared
    if not expected:
        result.update(
            status="pending_region_context",
            aviso="Falta asociar explícitamente el lote con una región de análisis.",
        )
        return result
    if expected != analysis.request.region_id:
        raise ValueError("Las predicciones pertenecen a otra región, no al lote consultado.")
    engine = motor if motor is not None else ForecastRotationEngine()
    history = resp.get("historial", {}).get("ultimos_cultivos", [])
    previous = normalized(history[0]) if history else None
    family = FAMILIAS_HISTORIAL.get(previous)
    if previous and family is None:
        for crop in engine.catalog.crops:
            trait = engine._trait(crop)
            if previous in {
                normalized(v)
                for v in (crop.crop_id, crop.crop_name, crop.chain, trait["legacy_id"])
            }:
                family = trait["family"]
                break
    report = engine.assess(
        analysis.request,
        analysis.climate,
        analysis.soil,
        previous_family=family,
        excluded_crops=resp.get("restricciones", {}).get("sin_semilla_o_comprador", []),
    )
    result.update(
        status=report.status,
        evaluacion_rotacion=report.model_dump(mode="json"),
        escenarios_condicionales=[s.model_dump(mode="json") for s in report.scenarios],
        aviso="Evaluación provisional basada en las inferencias de XGBoost. "
        "Faltan requisitos agronómicos revisados; las etapas posteriores requieren nuevas predicciones.",
    )
    return result


def texto_rotacion(rot):
    """Lectura compatible de registros previos; las secuencias nuevas son condicionales."""
    if "stages" in rot:
        return " → ".join(
            s["crop_name"] + (" (requiere nueva predicción)" if not s["forecast_evaluated"] else "")
            for s in rot["stages"]
        )
    partes, previous = [], None
    for stage in rot.get("secuencia", []):
        if stage["cultivo"] != previous:
            partes.append(f"{stage['temporada']}: {stage['nombre']}")
        previous = stage["cultivo"]
    return " → ".join(partes)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--respuestas", type=Path, default=DATOS / "respuestas_agricultor_ejemplo.json"
    )
    parser.add_argument(
        "--analisis",
        type=Path,
        help="AnalysisResult precalculado; no consulta NASA ni ejecuta XGBoost",
    )
    parser.add_argument("--region-id", help="Región explícitamente asociada al lote")
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args(argv)
    result = recomendar(args.respuestas, analisis=args.analisis, region_id=args.region_id)
    content = json.dumps(result, ensure_ascii=False, indent=2)
    if args.salida:
        args.salida.write_text(content, encoding="utf-8")
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
