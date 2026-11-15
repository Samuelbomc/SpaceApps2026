"""Stack local persistente sin Docker. No instala servicios ni activa el worker."""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import uuid
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apps.api.app.db.postgres import Database
from apps.api.app.repositories.operational import OperationalRepository
from packages.contracts import DateRange, GeoPoint
from pipelines.ingestion.storage.power import PowerParquetRepository
from scripts.migrate import migrate

ROOT = Path(__file__).resolve().parents[1]


def seed_reference(repository):
    region_id = os.getenv('REGION_ID','antioquia-reference')
    region = repository.region(region_id)
    if not region or repository.observation_page(region_id, 1)['total']:
        return 0
    today = datetime.now(timezone.utc).date()
    period = DateRange(today-timedelta(days=90), today-timedelta(days=1))
    rows = PowerParquetRepository().read(GeoPoint(region['latitude'],region['longitude']),period)
    if not rows:
        return 0
    repository.store_recent(region_id,rows,period.start)
    probe = ROOT/'data/probes/recent-20261114-aoi10m'
    if (probe/'summary.json').is_file() and (probe/'raw/catalog-results.json').is_file():
        report = json.loads((probe/'summary.json').read_text())
        center = report['aoi']['center']
        if (center['latitude'],center['longitude']) == (region['latitude'],region['longitude']):
            run_id = str(uuid.uuid4())
            repository.start_run(run_id,region_id)
            catalogs = json.loads((probe/'raw/catalog-results.json').read_text())
            for source,payload in catalogs['sources'].items():
                repository.snapshot(run_id,source,payload)
            repository.finish_run(run_id,'partial',{'origin':'public_manual_probe','sources':report['sources'],'scientific_extraction_complete':False})
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-directory',type=Path,default=ROOT/'data/local/postgres')
    parser.add_argument('--seed-reference',action='store_true',help='Cargar datos reales Parquet existentes solo si la región no tiene observaciones')
    parser.add_argument('--with-mongo',action='store_true',help='Usar MongoDB local persistente para resultados y registro ML; requiere mongod')
    args = parser.parse_args(argv)
    try:
        import embedded_postgres
    except ImportError:
        raise SystemExit("Instala el extra local: python -m pip install '.[api,storage,geospatial,local]'.")
    os.chdir(ROOT)
    for port in ((8000,3000,27018) if args.with_mongo else (8000,3000)):
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1',port))==0:
                raise SystemExit(f'Puerto {port} ocupado; no se detendrán servicios ajenos.')
    stop = threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):
        signal.signal(sig,lambda *_: stop.set())
    args.database_directory.parent.mkdir(parents=True,exist_ok=True)
    # stop conserva los datos; delete se reserva para servidores de pruebas.
    with ExitStack() as stack:
        postgres = stack.enter_context(embedded_postgres.get_server(args.database_directory,cleanup_mode='stop'))
        database = Database(postgres.get_uri())
        migrate(database)
        if args.seed_reference:
            count = seed_reference(OperationalRepository(database))
            print(f'Datos reales cargados inicialmente: {count}.',flush=True)
        environment = {**os.environ,'DATABASE_URL':postgres.get_uri(),'NEXT_TELEMETRY_DISABLED':'1','API_INTERNAL_URL':'http://127.0.0.1:8000'}
        environment['RESULTS_BACKEND'] = 'mongodb' if args.with_mongo else 'postgresql'
        if args.with_mongo:
            from scripts.local_mongo import local_mongo
            environment['MONGODB_URI'] = stack.enter_context(local_mongo(ROOT/'data/local/mongo'))
        processes=[]
        try:
            processes.append(subprocess.Popen([sys.executable,'-m','uvicorn','apps.api.app.main:app','--host','127.0.0.1','--port','8000','--no-proxy-headers','--reload','--reload-dir','apps/api/app','--reload-dir','packages/contracts','--reload-dir','ml'],env=environment,start_new_session=True))
            processes.append(subprocess.Popen(['npm','run','dev'],cwd=ROOT/'apps/web',env=environment,start_new_session=True))
            print(f"Field Shift: http://localhost:3000 · PostgreSQL persistente · resultados {environment['RESULTS_BACKEND']} · worker no activado.",flush=True)
            while not stop.wait(1):
                if any(process.poll() is not None for process in processes):
                    raise RuntimeError('Un servicio terminó antes de lo esperado.')
        finally:
            for process in processes:
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGTERM)
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL); process.wait()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
