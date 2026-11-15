"""Contrato HTTP versionado consumido por el generador de tipos del frontend."""

import json
from pathlib import Path

from apps.api.app.main import app
from pipelines.ingestion.http import write_json


def typescript_type(schema):
    """Tipos estáticos del subconjunto JSON Schema de nuestros DTOs, sin validadores runtime."""
    if "$ref" in schema:
        return f"components['schemas'][{json.dumps(schema['$ref'].rsplit('/', 1)[-1])}]"
    if "enum" in schema:
        return " | ".join(json.dumps(value) for value in schema["enum"])
    if "const" in schema:
        return json.dumps(schema["const"])
    for union in ("anyOf", "oneOf", "allOf"):
        if union in schema:
            separator = " & " if union == "allOf" else " | "
            return "(" + separator.join(typescript_type(item) for item in schema[union]) + ")"
    kind = schema.get("type")
    if isinstance(kind, list):
        return "(" + " | ".join(typescript_type({**schema, "type": item}) for item in kind) + ")"
    if kind == "array":
        if "prefixItems" in schema and schema.get("maxItems") == len(schema["prefixItems"]):
            return "[" + ", ".join(typescript_type(item) for item in schema["prefixItems"]) + "]"
        return f"Array<{typescript_type(schema.get('items', {}))}>"
    if kind == "object":
        properties = schema.get("properties", {})
        if not properties:
            additional = schema.get("additionalProperties", True)
            return f"Record<string, {typescript_type(additional) if isinstance(additional, dict) else 'unknown'}>"
        required = schema.get("required", [])
        fields = [f"{json.dumps(key)}{'' if key in required else '?'}: {typescript_type(value)};"
                  for key, value in properties.items()]
        return "{ " + " ".join(fields) + " }"
    if kind in ("number", "integer"):
        return "number"
    if kind in ("string", "boolean", "null"):
        return kind
    if not schema or set(schema) <= {"title", "description"}:
        return "unknown"
    raise ValueError(f"Tipo OpenAPI sin generador TypeScript: {kind}")


def generate_typescript(openapi):
    lines = ["// Generado por python -m scripts.export_openapi. No editar manualmente.",
             "export interface components {", "  schemas: {"]
    lines += [f"    {json.dumps(name)}: {typescript_type(schema)};"
              for name, schema in openapi["components"]["schemas"].items()]
    return "\n".join([*lines, "  };", "}", ""])


if __name__ == "__main__":
    target = Path("packages/contracts/openapi.json")
    write_json(target, app.openapi())
    target.with_name("api.generated.ts").write_text(generate_typescript(app.openapi()), encoding="utf-8")
    print(target)
