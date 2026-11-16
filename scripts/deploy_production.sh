#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
compose=(docker compose --env-file .env.production -f compose.production.yaml)
"${compose[@]}" config --quiet
"${compose[@]}" build web api worker
"${compose[@]}" up -d --no-build --wait --wait-timeout 300
"${compose[@]}" ps
curl --fail --silent --show-error https://agrogeo.app/backend/health
