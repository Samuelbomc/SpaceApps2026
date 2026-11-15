"""MongoDB local persistente, de uso exclusivo del entorno de desarrollo."""

import shutil
import subprocess
import threading
from contextlib import contextmanager


@contextmanager
def local_mongo(directory, port=27018):
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError

    binary = shutil.which("mongod")
    if binary is None:
        raise RuntimeError("Falta mongod; instala MongoDB o ejecuta dev_stack sin --with-mongo.")
    directory.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            binary,
            "--dbpath",
            str(directory),
            "--bind_ip",
            "127.0.0.1",
            "--port",
            str(port),
            "--wiredTigerCacheSizeGB",
            "0.25",
            "--quiet",
            "--logpath",
            str(directory.parent / "mongo.log"),
            "--logappend",
        ],
        start_new_session=True,
    )
    uri = f"mongodb://127.0.0.1:{port}"
    client = MongoClient(uri, serverSelectionTimeoutMS=300)
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError("MongoDB local terminó; revisa data/local/mongo.log.")
            try:
                client.admin.command("ping")
                break
            except PyMongoError:
                threading.Event().wait(0.2)
        else:
            raise RuntimeError("MongoDB local no respondió.")
        yield uri
    finally:
        client.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
