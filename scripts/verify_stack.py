"""Smoke HTTP con PostgreSQL temporal y observaciones POWER reales ya descargadas."""

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from apps.api.app.db.postgres import Database
from apps.api.app.repositories.operational import OperationalRepository
from packages.contracts import DateRange, GeoPoint
from pipelines.ingestion.http import write_json
from pipelines.ingestion.storage.power import PowerParquetRepository
from scripts.migrate import migrate


def main():
    import embedded_postgres  # Herramienta opcional, únicamente de verificación.

    for port in (8000, 3000):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise SystemExit(
                    f"Puerto {port} ocupado; esta prueba no detiene servicios existentes."
                )
    period = DateRange.parse("2025-12-25", "2026-01-01")
    rows = PowerParquetRepository().read(GeoPoint(6.2442, -75.5812), period)
    if not rows:
        raise SystemExit("Falta la muestra histórica real POWER descrita en docs/validation.md.")
    processes = []
    with tempfile.TemporaryDirectory(
        prefix="fs-stack-", dir="/private/tmp" if Path("/private/tmp").exists() else None
    ) as folder:
        with embedded_postgres.get_server(Path(folder) / "pg", cleanup_mode="delete") as pg:
            database = Database(pg.get_uri())
            migrate(database)
            repository = OperationalRepository(database)
            repository.store_recent("antioquia-reference", rows, period.start)
            environment = {**os.environ, "DATABASE_URL": pg.get_uri()}
            with (Path(folder) / "servers.log").open("w") as log:
                try:
                    processes.append(
                        subprocess.Popen(
                            [
                                sys.executable,
                                "-m",
                                "uvicorn",
                                "apps.api.app.main:app",
                                "--host",
                                "127.0.0.1",
                                "--port",
                                "8000",
                            ],
                            env=environment,
                            stdout=log,
                            stderr=log,
                            start_new_session=True,
                        )
                    )
                    processes.append(
                        subprocess.Popen(
                            ["npm", "run", "start"],
                            cwd="frontend",
                            env=environment,
                            stdout=log,
                            stderr=log,
                            start_new_session=True,
                        )
                    )
                    for url in ("http://127.0.0.1:8000/api/v1/health", "http://127.0.0.1:3000/"):
                        for attempt in range(50):
                            try:
                                with urlopen(url, timeout=2) as response:
                                    if response.status == 200:
                                        break
                            except (URLError, TimeoutError):
                                time.sleep(0.2)
                        else:
                            raise RuntimeError("El servicio temporal no respondió.")

                    def get(path):
                        with urlopen(
                            "http://127.0.0.1:3000/backend/" + path, timeout=10
                        ) as response:
                            return json.load(response)

                    regions, status = get("regions"), get("status")
                    observations = get(
                        "regions/antioquia-reference/observations?start=2025-12-25&end=2026-01-01"
                    )
                    request = Request(
                        "http://127.0.0.1:3000/backend/analyses",
                        data=json.dumps(
                            {
                                "region_id": "antioquia-reference",
                                "reference_date": "2026-01-01",
                                "horizon_days": 7,
                            }
                        ).encode(),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urlopen(request, timeout=10) as response:
                        analysis = json.load(response)
                    assert len(observations["items"]) == len(rows)
                    assert analysis["status"] == "pending_model" and analysis["climate"] is None
                    assert status["schedule"]["interval_seconds"] == 604800
                    report = {
                        "status": "ok",
                        "database": "real temporary PostgreSQL",
                        "frontend_http": 200,
                        "proxy_api": True,
                        "regions": len(regions),
                        "real_power_observations": len(rows),
                        "period": period.as_dict(),
                        "analysis_status": analysis["status"],
                        "interval_seconds": status["schedule"]["interval_seconds"],
                        "visual_browser_verification": False,
                        "permanent_worker_activated": False,
                    }
                    write_json(Path("data/manifests/application-smoke.json"), report)
                    print(json.dumps(report, indent=2))
                finally:
                    for process in processes:
                        if process.poll() is None:
                            os.killpg(process.pid, signal.SIGTERM)
                    for process in processes:
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
