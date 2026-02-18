#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d .venv ]]; then
  echo "Missing .venv. Create it first." >&2
  exit 1
fi

source .venv/bin/activate

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

# Default UI bind/port (override in environment if needed).
export FASTAPI_HOST="${FASTAPI_HOST:-127.0.0.1}"
export FASTAPI_PORT="${FASTAPI_PORT:-8000}"

echo "Starting WebUI gateway on http://${FASTAPI_HOST}:${FASTAPI_PORT}"
exec sam run \
  configs/webui_gateway.yaml \
  agents/orchestrator_agent.yaml \
  agents/inventory_agent.yaml \
  agents/supplier_agent.yaml \
  agents/compliance_agent.yaml \
  agents/finance_agent.yaml
