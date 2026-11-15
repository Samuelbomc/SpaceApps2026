"""CLI para consumir datos sin desplegar servicios ni entrenar modelos."""

from packages.contracts import DataQuery
from apps.api.app.services.nasa_data import NASADataService

import argparse
import json
import math
import sys
from pathlib import Path

from apps.api.app.repositories import (
    ECOSTRESSRepository, GPMRepository, GRACERepository, LandsatRepository,
    PowerRepository, SMAPRepository, SRTMRepository,
)

from pipelines.ingestion.sources.nasa.catalog import POWER_DOCS, POWER_PARAMETERS, PRODUCTS
from pipelines.ingestion.sources.nasa._cmr import CMRClient
from pipelines.ingestion.download import GranuleDownloader
from pipelines.ingestion.http import IngestionError, JsonHTTPClient, write_json
from packages.contracts.models import ANTIOQUIA_ORIENTE, BoundingBox, DateRange, GeoPoint
from pipelines.ingestion.sources.nasa.power import PowerClient
from pipelines.ingestion.sources.nasa.gpm import GPMClient
from pipelines.ingestion.sources.nasa.smap import SMAPClient
from pipelines.ingestion.sources.nasa.srtm import SRTMClient
from pipelines.ingestion.sources.nasa.grace import GRACEClient
from pipelines.ingestion.sources.nasa.ecostress import ECOSTRESSClient
from pipelines.ingestion.sources.nasa.hls import HLSClient
from pipelines.ingestion.flows.power import PowerIngestionFlow
from pipelines.ingestion.storage.power import PowerParquetRepository


def parser():
    root = argparse.ArgumentParser(description="Ingesta NASA — Oriente antioqueño")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("catalog", help="Fuentes, productos, versiones y limitaciones")
    for name in ("power", "search", "download", "collect", "power-sync"):
        command = commands.add_parser(name)
        command.add_argument("--start", help="Primera fecha inclusiva YYYY-MM-DD")
        command.add_argument("--end", help="Última fecha inclusiva YYYY-MM-DD")
        command.add_argument("--bbox", type=float, nargs=4, metavar=("WEST", "SOUTH", "EAST", "NORTH"),
                             default=None, help="WGS84; por defecto el rectángulo indicado de Antioquia")
        command.add_argument("--cache-dir", type=Path, default=Path("data/cache"))
        command.add_argument("--refresh", action="store_true", help="Consultar sin reutilizar caché")
        command.add_argument("--output", type=Path)
        if name in ("power", "collect", "power-sync"):
            command.add_argument("--parameters", nargs="+", default=POWER_PARAMETERS)
        else:
            command.add_argument("--source", choices=list(PRODUCTS) + (["all"] if name == "search" else []),
                                 required=True)
            command.add_argument("--limit", type=int, default=5, help="Máximo de granules por producto")
        if name in ("collect", "power-sync"):
            command.add_argument("--latitude", type=float)
            command.add_argument("--longitude", type=float)
            command.add_argument("--limit", type=int, default=5)
            command.add_argument("--page-size", type=int, default=100)
        if name == "power-sync":
            command.add_argument("--storage-dir", type=Path, default=Path("data/observations/nasa_power"))
            command.add_argument("--raw-directory", type=Path, default=Path("data/raw/nasa_power"))
            command.add_argument("--refresh-days", type=int, default=90,
                                 help="Reconsultar fechas de los últimos N días respecto a hoy UTC; 0 desactiva")
            command.add_argument("--chunk-days", type=int, default=366)
            command.add_argument("--force", action="store_true", help="Reconsultar todo el periodo solicitado")
        if name == "download":
            command.add_argument("--directory", type=Path, default=Path("data/raw"))
            command.add_argument("--asset", action="append", default=[], help="Glob de nombre, repetible; p. ej. '*B04.tif'")
            command.add_argument("--max-files", type=int, default=3)
            command.add_argument("--max-mb", type=float, default=100, help="Presupuesto total de bytes nuevos, en MiB")
    return root


def main(argv=None):
    arguments = parser()
    args = arguments.parse_args(argv)
    try:
        if args.command == "catalog":
            result = {"bbox": ANTIOQUIA_ORIENTE.as_dict(),
                      "power": {"documentation": POWER_DOCS, "parameters": POWER_PARAMETERS},
                      "products": {key: value.as_dict() for key, value in PRODUCTS.items()}}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if bool(args.start) != bool(args.end):
            raise ValueError("Especifica ambas fechas --start y --end.")
        period = DateRange.parse(args.start, args.end) if args.start else None
        if period is None and not (args.command in ("search", "download") and args.source == "srtm"):
            raise ValueError("Se requieren --start y --end (excepto SRTM estático).")
        bbox = BoundingBox(*args.bbox) if args.bbox else ANTIOQUIA_ORIENTE
        point = None
        if args.command in ("collect", "power-sync"):
            if (args.latitude is None) != (args.longitude is None):
                raise ValueError("Se requieren --latitude y --longitude juntos.")
            if args.latitude is not None:
                if args.bbox is not None:
                    raise ValueError("Selecciona latitud/longitud o --bbox, no ambos.")
                point, bbox = GeoPoint(args.latitude, args.longitude), None
            elif args.bbox is None:
                raise ValueError("Se requiere latitud/longitud o --bbox explícito.")
            if args.command == "power-sync" and point is None:
                raise ValueError("power-sync requiere --latitude y --longitude; bbox aún no tiene persistencia incremental.")
        query = DataQuery(period=period, point=point, bbox=bbox,
                          limit=getattr(args, "limit", 5), page_size=getattr(args, "page_size", 100),
                          power_parameters=getattr(args, "parameters", POWER_PARAMETERS))
        if args.command == "download" and (
            not math.isfinite(args.max_mb) or args.max_mb <= 0 or args.max_files < 1
        ):
            raise ValueError("--max-mb y --max-files deben ser positivos y finitos.")
        http = JsonHTTPClient(cache_dir=None if args.command == "power-sync" else args.cache_dir,
                              cache_ttl=0 if args.refresh else 86400)
        if args.command == "power-sync":
            result = PowerIngestionFlow(PowerClient(http), PowerParquetRepository(args.storage_dir),
                                        args.raw_directory).run(query, refresh_days=args.refresh_days,
                                                               chunk_days=args.chunk_days, force=args.force)
        elif args.command == "collect":
            result = NASADataService(http).fetch(query)
        elif args.command == "power":
            result = PowerRepository(PowerClient(http)).fetch(query)["data"]
        else:
            cmr = CMRClient(http)
            repositories = {
                "gpm": GPMRepository(GPMClient(cmr)), "smap": SMAPRepository(SMAPClient(cmr)),
                "srtm": SRTMRepository(SRTMClient(cmr)), "grace": GRACERepository(GRACEClient(cmr)),
                "ecostress": ECOSTRESSRepository(ECOSTRESSClient(cmr)),
                "ecostress-lst": ECOSTRESSRepository(ECOSTRESSClient(cmr, product="lst")),
                "landsat": LandsatRepository(HLSClient(cmr)),
            }
            if args.source == "all":
                result = {"products": {}, "errors": {}}
                for source in PRODUCTS:
                    try:
                        result["products"][source] = repositories[source].fetch(query)["data"]
                    except IngestionError as exc:
                        result["errors"][source] = str(exc)
            else:
                result = repositories[args.source].fetch(query)["data"]
            if args.command == "download":
                result["download"] = GranuleDownloader().download(
                    result, args.directory / args.source, patterns=tuple(args.asset),
                    max_files=args.max_files, max_bytes=int(args.max_mb * 1024 * 1024))
        if args.output:
            write_json(args.output, result)
            print(f"Resultado guardado en {args.output}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 1 if result.get("errors") or result.get("status") in ("partial", "error", "incomplete") else 0
    except (IngestionError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
