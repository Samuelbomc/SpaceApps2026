"""Comprueba enlaces locales y límites básicos del repositorio sin acceder a red o bases."""

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
DOC_ROOTS = ("docs", "ml", "packages", "samples", "pipelines", "scripts")
DOC_ENTRYPOINTS = (
    "README.md",
    "CONTRIBUTING.md",
    "CODEX.md",
    "CLAUDE.md",
    "frontend/README.md",
    "ml/README.md",
    "modulo_rotacion/LEEME_rotacion.md",
)
REQUIRED_DOCS = (
    "docs/README.md",
    "docs/product/overview.md",
    "docs/architecture/overview.md",
    "docs/architecture/code-structure.md",
    "docs/architecture/flows.md",
    "docs/architecture/deployment.md",
    "docs/architecture/persistence.md",
    "docs/guides/development.md",
    "docs/operations/runbook.md",
    "docs/reference/capabilities.md",
    "docs/reference/configuration.md",
    "docs/reference/http-api.md",
    "docs/quality/documentation.md",
    "docs/quality/verification.md",
    "docs/quality/acceptance.md",
)
CHANGELOG_HEADING = re.compile(
    r"^#{1,6}\s+(?:changelog|historial de cambios|bitácora|"
    r"registro local de esta revisión|previous iterations|project decision update)\b",
    re.I | re.M,
)


def documentation_files():
    paths = {ROOT / name for name in DOC_ENTRYPOINTS}
    for directory in DOC_ROOTS:
        paths.update((ROOT / directory).rglob("*.md"))
    return sorted(path for path in paths if path.is_file())


def check():
    problems = []
    for name in (*DOC_ENTRYPOINTS, *REQUIRED_DOCS):
        if not (ROOT / name).is_file():
            problems.append(f"{name}: documento principal inexistente")
    if (ROOT / "docs/history").exists():
        problems.append("docs/history: las bitácoras de desarrollo no pertenecen a las guías")
    for path in documentation_files():
        text = path.read_text(encoding="utf-8")
        if len(re.findall(r"^```", text, flags=re.M)) % 2:
            problems.append(f"{path.relative_to(ROOT)}: bloque de código sin cerrar")
        # Los ejemplos de código pueden contener sintaxis similar a enlaces.
        text = re.sub(r"```.*?```", "", text, flags=re.S)
        if len(re.findall(r"^#\s+", text, flags=re.M)) != 1:
            problems.append(f"{path.relative_to(ROOT)}: se requiere un único título principal")
        if CHANGELOG_HEADING.search(text):
            problems.append(f"{path.relative_to(ROOT)}: bitácora en documentación de referencia")
        for href in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", text):
            href = href.split(' "', 1)[0].strip("<>")
            if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I) or href.startswith(("#", "/")):
                continue
            target = unquote(href.split("#", 1)[0])
            if target and not (path.parent / target).exists():
                problems.append(f"{path.relative_to(ROOT)}: enlace local inexistente: {target}")
    for path in (ROOT / "frontend/src").rglob("*.ts"):
        if path.name.endswith(".spec.ts") or "testing" in path.parts:
            continue
        text = path.read_text()
        if "MockAuthGateway" in text or re.search(
            r"(?:from\s*|import\s*\()['\"][^'\"]*testing/", text
        ):
            problems.append(
                f"{path.relative_to(ROOT)}: fixture de pruebas importado desde producción"
            )
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    for name in filter(None, tracked):
        parts = Path(name).parts
        if "node_modules" in parts or "__pycache__" in parts or ".venv" in parts:
            problems.append(f"{name}: artefacto local versionado")
        if (ROOT / name).exists() and (
            "__MACOSX" in parts or Path(name).name == ".DS_Store" or name.endswith(".crdownload")
        ):
            problems.append(f"{name}: metadatos de archivo o descarga incompleta versionados")
        if Path(name).name == ".env":
            problems.append(f"{name}: configuración privada versionada")
        if name.startswith(("data/farms/", "modulo_rotacion/datos/fincas/")) and not name.endswith(
            ".gitkeep"
        ):
            problems.append(f"{name}: datos privados de finca versionados")
    for path in (ROOT / "infra/database/migrations").glob("*.sql"):
        if not re.fullmatch(r"\d{3}_[a-z0-9_]+\.sql", path.name):
            problems.append(f"{path.name}: nombre de migración no válido")
    return problems


def main():
    problems = check()
    if problems:
        print("\n".join(problems))
        return 1
    print("Estructura documental, enlaces, fixtures y límites del repositorio verificados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
