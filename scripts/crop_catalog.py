"""Normaliza el catálogo aportado y opcionalmente evalúa un contexto o guarda borradores."""

import argparse
import json
from pathlib import Path

from packages.contracts.agronomy import CropScreeningContext
from pipelines.ingestion.http import write_json
from pipelines.processing.validation.crop_catalog import normalize_crop_catalog


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("samples/agronomy/ecocrop-user.tsv"))
    parser.add_argument("--output", type=Path, default=Path("ml/configs/ecocrop.catalog.json"))
    parser.add_argument("--context", type=Path, help="Contexto real en JSON para evaluar los requisitos numéricos")
    parser.add_argument("--report", type=Path, help="Destino del informe; requiere --context")
    parser.add_argument("--store-draft", action="store_true", help="Guardar esta versión como borrador inactivo en MongoDB")
    args = parser.parse_args(argv)
    if bool(args.context) != bool(args.report):
        parser.error("context y report deben usarse juntos")
    catalog = normalize_crop_catalog(args.input.read_bytes())
    report = None
    if args.context:
        from ml.recommendations.screening import screen_catalog
        report = screen_catalog(catalog, CropScreeningContext.model_validate_json(args.context.read_text()))
    write_json(args.output, catalog.model_dump(mode="json"))
    if report is not None:
        write_json(args.report, report.model_dump(mode="json"))
    if args.store_draft:
        from apps.api.app.config import Settings
        from apps.api.app.repositories.mongo import MongoResultsRepository
        settings = Settings.from_env()
        store = MongoResultsRepository(settings.mongodb_uri, settings.mongodb_database)
        for crop in catalog.crops:
            # Una nueva versión no desactiva o sustituye otro catálogo ya publicado.
            store.save_catalog_entry(f"{catalog.version}:{crop.crop_id}", {
                "catalog_version": catalog.version, "review_status": catalog.review_status,
                "profile": crop.model_dump(mode="json")}, active=False)
    print(json.dumps({"version": catalog.version, "crop_profiles": len(catalog.crops),
                      "ecocrop_species": len({crop.ecocrop_code for crop in catalog.crops}),
                      "review_status": catalog.review_status, "stored_as_inactive_draft": args.store_draft}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
