"""Artefactos JSON inmutables, con manifiesto y verificación antes de cargar."""

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path


class ModelArtifactStore:
    def __init__(self, root=Path("data/models")):
        self.root = Path(root)

    def directory(self, version):
        if len(version) != 32 or any(c not in "0123456789abcdef" for c in version):
            raise ValueError("Versión de artefacto inválida.")
        return self.root / version

    def save(self, version, model, metadata):
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self.directory(version)
        temporary = Path(tempfile.mkdtemp(prefix="candidate-", dir=self.root))
        try:
            model.save(temporary)
            files = sorted(temporary.glob("*.json"))
            if not files:
                raise ValueError("El trainer debe guardar al menos un modelo JSON.")
            hashes = {}
            for path in files:
                json.loads(path.read_text())
                hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            (temporary / "manifest.json").write_text(json.dumps({**metadata, "artifact_sha256": hashes}, sort_keys=True, default=str, indent=2))
            os.rename(temporary, destination)
            return hashes
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    def verify(self, release):
        directory = self.directory(release.version)
        if not release.artifact_sha256:
            raise ValueError("El modelo publicado no tiene hashes de artefactos.")
        for name, digest in release.artifact_sha256.items():
            if Path(name).name != name or not name.endswith(".json"):
                raise ValueError("Ruta de artefacto inválida.")
            if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
                raise ValueError("El artefacto publicado fue alterado; no se puede usar.")
        return directory
