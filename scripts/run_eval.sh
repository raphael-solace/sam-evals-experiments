#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d .venv ]]; then
  echo "Missing .venv. Create it first." >&2
  exit 1
fi

source .venv/bin/activate
SAM_BIN="$ROOT_DIR/.venv/bin/sam"

if [[ ! -x "$SAM_BIN" ]]; then
  echo "Missing SAM CLI at $SAM_BIN" >&2
  exit 1
fi

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

required_env=(
  "SOLACE_BROKER_URL"
  "SOLACE_BROKER_USERNAME"
  "SOLACE_BROKER_PASSWORD"
  "SOLACE_BROKER_VPN"
  "LLM_SERVICE_ENDPOINT"
  "LLM_SERVICE_API_KEY"
  "LLM_SERVICE_PLANNING_MODEL_NAME"
  "LLM_EVALUATOR_MODEL_NAME"
)

for name in "${required_env[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 1
  fi
done

# sam eval uses a broker subscriber and currently cannot complete in dev-mode-only setups.
if [[ "${SOLACE_DEV_MODE:-false}" == "true" ]]; then
  echo "SOLACE_DEV_MODE=true detected. Overriding to false for sam eval compatibility."
  export SOLACE_DEV_MODE=false
fi

# Fast sanity-check for common OpenAI placeholder keys.
if [[ "${LLM_SERVICE_ENDPOINT}" == "https://api.openai.com/v1" && ${#LLM_SERVICE_API_KEY} -lt 40 ]]; then
  echo "LLM_SERVICE_API_KEY appears invalid for OpenAI endpoint (too short)." >&2
  exit 1
fi

python - <<'PY'
import os
import socket
import sys
import time
from urllib.parse import urlparse

broker_url = os.environ["SOLACE_BROKER_URL"]
parsed = urlparse(broker_url if "://" in broker_url else f"ws://{broker_url}")
host = parsed.hostname
port = parsed.port or (443 if parsed.scheme in {"wss", "https"} else 80)

if not host or not port:
    print(f"Invalid SOLACE_BROKER_URL: {broker_url}", file=sys.stderr)
    sys.exit(1)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(2.0)
try:
    sock.connect((host, port))
finally:
    sock.close()

# Extra readiness check: ensure broker accepts authenticated client connections.
# This prevents transient "Service Unavailable" right after broker container start.
try:
    from solace.messaging.messaging_service import MessagingService
    from solace.messaging.config.solace_properties import (
        authentication_properties,
        service_properties,
        transport_layer_properties,
        transport_layer_security_properties,
    )

    props = {
        transport_layer_properties.HOST: broker_url,
        service_properties.VPN_NAME: os.environ["SOLACE_BROKER_VPN"],
        authentication_properties.SCHEME_BASIC_USER_NAME: os.environ["SOLACE_BROKER_USERNAME"],
        authentication_properties.SCHEME_BASIC_PASSWORD: os.environ["SOLACE_BROKER_PASSWORD"],
        transport_layer_security_properties.CERT_VALIDATED: False,
    }

    max_attempts = 30
    last_error = None
    for attempt in range(1, max_attempts + 1):
        service = None
        try:
            service = MessagingService.builder().from_properties(props).build()
            service.connect()
            service.disconnect()
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            if service is not None:
                try:
                    service.disconnect()
                except Exception:
                    pass
            if attempt < max_attempts:
                time.sleep(2)
    if last_error is not None:
        raise last_error
except ModuleNotFoundError:
    # If solace SDK is unavailable, rely on TCP connectivity check above.
    pass
PY

python - <<'PY'
import os
import socket
import sys

host = os.getenv("REST_API_HOST", "127.0.0.1")
port = int(os.getenv("REST_API_PORT", "8080"))

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind((host, port))
except OSError:
    print(
        f"REST API port is already in use: {host}:{port}. "
        "Stop existing SAM/UI processes (or change REST_API_PORT) and retry.",
        file=sys.stderr,
    )
    sys.exit(1)
finally:
    sock.close()
PY

MODE="${1:-all}"
mkdir -p evaluation_results/charts
TMP_DIR="$ROOT_DIR/.tmp_eval"
mkdir -p "$TMP_DIR"
ANALYZE_SMOKE_DIR=""
ANALYZE_FULL_DIR=""

# Safety defaults (can be overridden via env vars).
DEFAULT_EVAL_RETRIES="${EVAL_RETRIES:-2}"
DEFAULT_STALLED_THRESHOLD="${EVAL_STALLED_THRESHOLD:-0}"
DEFAULT_SAFE_WORKERS="${SAFE_WORKERS:-1}"

build_temp_suite() {
  local suite_path="$1"
  local temp_suite="$2"
  local default_workers="$3"

  python - <<'PY' "$suite_path" "$temp_suite" "$default_workers"
import json
import os
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
default_workers = int(sys.argv[3])

data = json.loads(src.read_text())

runs_override = os.getenv("SAFE_RUNS")
workers_override = os.getenv("SAFE_WORKERS")
results_suffix = os.getenv("SAFE_RESULTS_SUFFIX", "safe")

if runs_override:
    data["runs"] = int(runs_override)
else:
    data["runs"] = int(data.get("runs", 1))

if workers_override:
    data["workers"] = int(workers_override)
else:
    data["workers"] = default_workers

base_results_name = data.get("results_dir_name", src.stem)
data["results_dir_name"] = f"{base_results_name}-{results_suffix}"

dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps(data, indent=2))
print(data["results_dir_name"])
PY
}

stalled_run_count() {
  local results_dir="$1"
  python - <<'PY' "$results_dir"
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
if not root.exists():
    print(999999)
    sys.exit(0)

summaries = list(root.glob("runtime-*/tc*/run_*/summary.json"))
if not summaries:
    print(999999)
    sys.exit(0)

stalled = 0
for summary in summaries:
    try:
        data = json.loads(summary.read_text())
    except Exception:
        stalled += 1
        continue
    if data.get("duration_seconds") is None:
        stalled += 1
        continue
    if not data.get("final_status"):
        stalled += 1
        continue
print(stalled)
PY
}

run_suite_with_retries() {
  local suite_path="$1"
  local results_name="$2"
  local retries="$3"
  local stalled_threshold="$4"
  local attempt=1
  local success=0

  while (( attempt <= retries )); do
    echo "Running suite: ${suite_path} (attempt ${attempt}/${retries})"
    if "$SAM_BIN" eval "$suite_path" --verbose; then
      local results_dir="$ROOT_DIR/results/${results_name}"
      local stalled
      stalled="$(stalled_run_count "$results_dir")"
      echo "Stalled runs detected: ${stalled}"
      if (( stalled <= stalled_threshold )); then
        success=1
        break
      fi
      echo "Stalled runs exceeded threshold (${stalled_threshold}), retrying..."
    else
      echo "sam eval failed on attempt ${attempt}." >&2
    fi
    ((attempt++))
    sleep 5
  done

  if (( success != 1 )); then
    echo "Suite failed after ${retries} attempt(s): ${suite_path}" >&2
    exit 1
  fi

  if [[ -d "results/${results_name}" ]]; then
    rm -rf "evaluation_results/${results_name}"
    cp -R "results/${results_name}" "evaluation_results/${results_name}"
  fi
}

run_suite() {
  local suite_path="$1"
  local results_name="$2"

  echo "Running suite: ${suite_path}"
  "$SAM_BIN" eval "$suite_path" --verbose

  if [[ -d "results/${results_name}" ]]; then
    rm -rf "evaluation_results/${results_name}"
    cp -R "results/${results_name}" "evaluation_results/${results_name}"
  fi
}

case "$MODE" in
  smoke)
    run_suite "test_suites/po_eval_smoke.json" "po-eval-smoke"
    ANALYZE_SMOKE_DIR="results/po-eval-smoke"
    ;;
  smoke-safe)
    SAFE_RESULTS_SUFFIX="${SAFE_RESULTS_SUFFIX:-safe-smoke}"
    export SAFE_RESULTS_SUFFIX
    tmp_suite="$TMP_DIR/po_eval_smoke.safe.json"
    safe_results_name="$(build_temp_suite "test_suites/po_eval_smoke.json" "$tmp_suite" "$DEFAULT_SAFE_WORKERS" | tail -n 1)"
    run_suite_with_retries "$tmp_suite" "$safe_results_name" "$DEFAULT_EVAL_RETRIES" "$DEFAULT_STALLED_THRESHOLD"
    ANALYZE_SMOKE_DIR="results/${safe_results_name}"
    ;;
  trace)
    run_suite "test_suites/po_eval_trace_focus.json" "po-eval-trace-focus"
    ;;
  full)
    run_suite "test_suites/po_eval_full.json" "po-eval-full"
    ANALYZE_FULL_DIR="results/po-eval-full"
    ;;
  full-safe)
    SAFE_RESULTS_SUFFIX="${SAFE_RESULTS_SUFFIX:-safe-full}"
    export SAFE_RESULTS_SUFFIX
    tmp_suite="$TMP_DIR/po_eval_full.safe.json"
    safe_results_name="$(build_temp_suite "test_suites/po_eval_full.json" "$tmp_suite" "$DEFAULT_SAFE_WORKERS" | tail -n 1)"
    run_suite_with_retries "$tmp_suite" "$safe_results_name" "$DEFAULT_EVAL_RETRIES" "$DEFAULT_STALLED_THRESHOLD"
    ANALYZE_FULL_DIR="results/${safe_results_name}"
    ;;
  all)
    run_suite "test_suites/po_eval_smoke.json" "po-eval-smoke"
    run_suite "test_suites/po_eval_full.json" "po-eval-full"
    ANALYZE_SMOKE_DIR="results/po-eval-smoke"
    ANALYZE_FULL_DIR="results/po-eval-full"
    ;;
  all-safe)
    SAFE_RESULTS_SUFFIX="safe-smoke"
    export SAFE_RESULTS_SUFFIX
    smoke_tmp_suite="$TMP_DIR/po_eval_smoke.safe.json"
    smoke_results_name="$(build_temp_suite "test_suites/po_eval_smoke.json" "$smoke_tmp_suite" "$DEFAULT_SAFE_WORKERS" | tail -n 1)"
    run_suite_with_retries "$smoke_tmp_suite" "$smoke_results_name" "$DEFAULT_EVAL_RETRIES" "$DEFAULT_STALLED_THRESHOLD"
    ANALYZE_SMOKE_DIR="results/${smoke_results_name}"

    SAFE_RESULTS_SUFFIX="safe-full"
    export SAFE_RESULTS_SUFFIX
    full_tmp_suite="$TMP_DIR/po_eval_full.safe.json"
    full_results_name="$(build_temp_suite "test_suites/po_eval_full.json" "$full_tmp_suite" "$DEFAULT_SAFE_WORKERS" | tail -n 1)"
    run_suite_with_retries "$full_tmp_suite" "$full_results_name" "$DEFAULT_EVAL_RETRIES" "$DEFAULT_STALLED_THRESHOLD"
    ANALYZE_FULL_DIR="results/${full_results_name}"
    ;;
  *)
    echo "Unknown mode '$MODE'. Use: smoke | smoke-safe | trace | full | full-safe | all | all-safe" >&2
    exit 1
    ;;
esac

if [[ -n "$ANALYZE_SMOKE_DIR" || -n "$ANALYZE_FULL_DIR" ]]; then
  analyze_cmd=(python scripts/analyze_results.py --output-dir "evaluation_results" --analysis-md "ANALYSIS.md")
  if [[ -n "$ANALYZE_SMOKE_DIR" ]]; then
    analyze_cmd+=(--smoke-dir "$ANALYZE_SMOKE_DIR")
  fi
  if [[ -n "$ANALYZE_FULL_DIR" ]]; then
    analyze_cmd+=(--full-dir "$ANALYZE_FULL_DIR")
  fi
  "${analyze_cmd[@]}"
fi

echo "Evaluation and analysis complete."
