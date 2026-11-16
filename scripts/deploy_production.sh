#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

if [[ ! -f .env.production ]]; then
  echo 'Falta .env.production; consulta docs/deployment.md.' >&2
  exit 1
fi
docker info >/dev/null
compose=(docker compose --env-file .env.production -f compose.production.yaml)
if [[ $# -gt 0 ]]; then
  echo 'Uso: bash scripts/deploy_production.sh' >&2
  exit 1
fi
"${compose[@]}" config --quiet
"${compose[@]}" up -d --build --wait --wait-timeout 300
"${compose[@]}" ps
curl --fail --silent --show-error http://127.0.0.1:8082/backend/health
curl --fail --silent --show-error https://agrogeo.app/backend/health
