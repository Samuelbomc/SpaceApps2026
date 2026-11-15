"""Suite completa con PostgreSQL y MongoDB temporales; nunca usa las bases locales."""

import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path


def main():
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError

    from scripts.verify_postgres import main as verify_postgres

    binary = shutil.which("mongod")
    if not binary:
        raise SystemExit(
            "Instala mongod o ejecuta la suite con TEST_DATABASE_URL y TEST_MONGODB_URI de pruebas."
        )
    with tempfile.TemporaryDirectory(prefix="agrogeo-automation-") as folder:
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        directory = Path(folder)
        database = directory / "mongo"
        database.mkdir()
        with (directory / "mongo.log").open("w") as log:
            process = subprocess.Popen(
                [
                    binary,
                    "--dbpath",
                    str(database),
                    "--bind_ip",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--wiredTigerCacheSizeGB",
                    "0.25",
                    "--quiet",
                ],
                stdout=log,
                stderr=log,
            )
            uri = f"mongodb://127.0.0.1:{port}"
            client = MongoClient(uri, serverSelectionTimeoutMS=300)
            try:
                for _ in range(60):
                    if process.poll() is not None:
                        raise RuntimeError("El MongoDB temporal terminó antes de estar disponible.")
                    try:
                        client.admin.command("ping")
                        break
                    except PyMongoError:
                        time.sleep(0.2)
                else:
                    raise RuntimeError("MongoDB temporal no respondió.")
                previous = os.environ.get("TEST_MONGODB_URI")
                os.environ["TEST_MONGODB_URI"] = uri
                try:
                    return verify_postgres()
                finally:
                    if previous is None:
                        os.environ.pop("TEST_MONGODB_URI", None)
                    else:
                        os.environ["TEST_MONGODB_URI"] = previous
            finally:
                client.close()
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
