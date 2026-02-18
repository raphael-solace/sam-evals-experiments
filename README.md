# SAM SAP PO Processing Experiment

This repository contains a full Solace Agent Mesh (SAM OSE) multi-agent purchase-order experiment with:

- 5 specialized agents (`Orchestrator`, `Inventory`, `Supplier`, `Compliance`, `Finance`)
- 5 custom Python tools under `tools/`
- 16 evaluation test cases under `test_suites/test_cases/`
- smoke + full evaluation suites
- analysis automation and chart generation
- blog-ready write-up at `BLOG_POST.md`

## Repository Layout

- `agents/` - 5 SAM agent configuration files
- `tools/` - deterministic mock SAP/supplier/compliance/finance tool implementations
- `test_suites/` - smoke/full suite definitions and 16 test case JSON files
- `configs/` - shared SAM config and eval backend config
- `scripts/run_eval.sh` - run smoke/trace/full suites and post-analysis
- `scripts/analyze_results.py` - parse evaluation outputs and generate charts/analysis
- `evaluation_results/` - copied result artifacts and generated charts
- `ANALYSIS.md` - generated analysis summary
- `BLOG_POST.md` - long-form write-up for publication

## Prerequisites

- Python 3.10+
- Internet access for model API calls
- OpenAI-compatible endpoint and API key
- Local Solace broker reachable at `SOLACE_BROKER_URL` for `sam eval`

## Local Setup

```bash
cd /Users/raphaelcaillon/Documents/github/sam-evals-experiments
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install solace-agent-mesh
pip install "sam-rest-gateway @ git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-rest-gateway"
```

SAM source is vendored for reference at:

```bash
vendor/solace-agent-mesh
```

## Environment Variables

The project uses `.env` (ignored by git). Key defaults included:

- `SOLACE_DEV_MODE=true`
- `REST_API_HOST=127.0.0.1`
- `REST_API_PORT=8080`
- `EXPERIMENT_ROOT=/Users/raphaelcaillon/Documents/github/sam-evals-experiments`
- `LLM_SERVICE_ENDPOINT`
- `LLM_SERVICE_API_KEY`
- `LLM_SERVICE_PLANNING_MODEL_NAME`
- `LLM_EVALUATOR_MODEL_NAME`

## Local Broker (Required for `sam eval`)

`sam eval` requires a broker subscriber connection and does not fully work with dev-mode-only in-memory transport. Start a local broker before running evaluations:

```bash
docker rm -f sam-local-broker >/dev/null 2>&1 || true
docker run -d --name sam-local-broker \
  --shm-size=1g \
  -p 8008:8008 \
  -p 18080:8080 \
  -e username_admin_globalaccesslevel=admin \
  -e username_admin_password=admin \
  -e system_scaling_maxconnectioncount=100 \
  -e system_scaling_maxqueues=200 \
  -e system_scaling_maxtopicendpoints=200 \
  solace/solace-pubsub-standard:latest
```

Default `.env` broker settings should match:

- `SOLACE_BROKER_URL=ws://localhost:8008`
- `SOLACE_BROKER_USERNAME=default`
- `SOLACE_BROKER_PASSWORD=default`
- `SOLACE_BROKER_VPN=default`

## Run Evaluations

Smoke only:

```bash
./scripts/run_eval.sh smoke
```

Trace-focused suite (new `tc11`-`tc16` only):

```bash
./scripts/run_eval.sh trace
```

Full only:

```bash
./scripts/run_eval.sh full
```

Smoke then full (default):

```bash
./scripts/run_eval.sh all
```

Note: `scripts/run_eval.sh` automatically forces `SOLACE_DEV_MODE=false` for evaluation compatibility.

## Run Web UI

The evaluation backend (`configs/eval_backend.yaml`, port `8080`) is API-only and does not serve a frontend at `/`.

To launch the SAM Web UI gateway:

```bash
./scripts/run_webui.sh
```

Then open:

- `http://127.0.0.1:8000/`

If needed, override host/port:

```bash
FASTAPI_HOST=127.0.0.1 FASTAPI_PORT=8000 ./scripts/run_webui.sh
```

## Manual Commands

```bash
source .venv/bin/activate
set -a && source .env && set +a
export SOLACE_DEV_MODE=false
sam eval test_suites/po_eval_smoke.json --verbose
sam eval test_suites/po_eval_trace_focus.json --verbose
sam eval test_suites/po_eval_full.json --verbose
python scripts/analyze_results.py --smoke-dir results/po-eval-smoke --full-dir results/po-eval-full --output-dir evaluation_results --analysis-md ANALYSIS.md
```

## Outputs

SAM writes raw outputs to:

- `results/po-eval-smoke/`
- `results/po-eval-trace-focus/`
- `results/po-eval-full/`

Automation copies them into:

- `evaluation_results/po-eval-smoke/`
- `evaluation_results/po-eval-trace-focus/`
- `evaluation_results/po-eval-full/`

Analysis assets:

- `evaluation_results/analysis.json`
- `evaluation_results/charts/pass_rates.(png|html)`
- `evaluation_results/charts/agreement_heatmap.(png|html)`
- `evaluation_results/charts/latency_by_test_case.(png|html)`
- `evaluation_results/charts/trace_signals.(png|html)`
- `ANALYSIS.md`
- `BLOG_POST.md`
