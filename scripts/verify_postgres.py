"""Verifica contra PostgreSQL temporal sin modificar bases existentes ni Docker."""

import os
import tempfile
import unittest
from pathlib import Path


def main():
    try:
        import embedded_postgres
    except ImportError:
        raise SystemExit("Instala embedded-postgres para esta verificación opcional, o usa TEST_DATABASE_URL.")
    with tempfile.TemporaryDirectory(prefix="fs-pg-", dir="/private/tmp" if Path("/private/tmp").exists() else None) as folder:
        with embedded_postgres.get_server(Path(folder) / "pg", cleanup_mode="delete") as postgres:
            os.environ["TEST_DATABASE_URL"] = postgres.get_uri()
            # Importar después de definir el entorno para habilitar los tests.
            suite = unittest.defaultTestLoader.discover(".", pattern="test_*.py")
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
