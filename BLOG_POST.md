# From Tool Checks to Trace Intelligence: Evaluating a Multi-Agent SAP PO Workflow with Solace Agent Mesh

Enterprise agent systems are not hard because of one prompt. They are hard because of orchestration: who called what, in which order, with which data, and why the workflow ended where it did.

This project implements a full SAP purchase-order flow on Solace Agent Mesh (SAM OSE) with five specialist agents and a deterministic tool layer. The key takeaway is simple:

`llm_evaluator` is valuable because it scores the whole trace, not just the final text.

## The Scenario

We modeled a realistic procurement workflow:

1. `OrchestratorAgent` receives the request and delegates.
2. `InventoryAgent` checks SAP stock.
3. `SupplierAgent` runs supplier discovery in parallel.
4. `ComplianceAgent` validates policy and vendor rules.
5. `FinanceAgent` validates budget, assigns cost center, and creates POs.

The tool layer is mocked but structured like production interfaces:

- Inventory checks return stock and shortage.
- Supplier queries return quotes, timeout metadata, and parallel-vs-sequential timing.
- Compliance checks return approval/violations.
- Finance checks budget and creates deterministic PO records.

## Why Three Evaluators Are Better Than One

The experiment uses three scoring methods:

- `tool_match`: did expected tools run?
- `response_match`: did the final output resemble expected text?
- `llm_evaluator`: did the end-to-end execution behavior satisfy the business criterion?

This layering matters. Tool calls can look right while behavior is wrong. Output can look polished while logic is unsafe. A trace-aware evaluator catches those gaps.

## What Changed to Make It Useful for Publication

### 1) Expanded test suite from 10 to 16 cases

The original suite covered happy path, budget failures, out-of-stock handling, split sourcing, timeout resilience, urgency, multi-facility, and performance.

We added six more trace-centric cases:

- `tc11_policy_override_guardrail`: user says “skip compliance,” system must refuse shortcutting.
- `tc12_missing_facility_defaulting`: missing facility context should not cause clarification loops.
- `tc13_urgent_tradeoff_explanation`: urgency decision must explain lead-time/reliability/cost tradeoff.
- `tc14_stage_stop_transparency`: when suppliers are out, response must state exactly where workflow stopped.
- `tc15_timeout_budget_dual_failure`: timeout + budget shortfall in same run, with clean escalation logic.
- `tc16_unapproved_vendor_override`: user asks for cheapest unapproved vendor, policy must still win.

### 2) Added trace-level monitoring signals

`scripts/analyze_results.py` now computes and outputs additional signals:

- `clarification_prompt_rate`
- `risky_po_when_llm_failed_rate`
- `llm_pass_tool_fail_rate`
- `llm_fail_tool_pass_rate`
- `parallel_timing_mention_rate`
- `compliance_before_supplier_rate` (ordering violation signal)

It also renders a new chart:

- `evaluation_results/charts/trace_signals.(png|html)`

These metrics turn evaluation from “did it pass?” into “how is orchestration quality trending?”

## Why Trace-Level Judging Is Interesting

A whole-trace judge can spot issues that output-only checks usually miss:

- The system asked the user for missing details instead of using approved defaults.
- Compliance was invoked too early (before supplier context existed).
- A PO was created even though the policy path should have blocked it.
- Timeout handling “looked fine” in final text but actually skipped critical branches.

This is exactly where production incidents happen: not in isolated tool outputs, but in sequence integrity.

## Monitoring Playbook for Production Readiness

If you want this to run safely in production-like environments, monitor at least these:

1. `llm_pass_tool_fail_rate`
Interpretation: trace judge says behavior is okay even when tool expectations fail. This can reveal brittle test specs or hidden orchestration drift.

2. `llm_fail_tool_pass_rate`
Interpretation: tools fired, but business logic still failed. This is usually a real orchestration issue.

3. `compliance_before_supplier_rate`
Interpretation: policy checks happening before required sourcing context. Strong predictor of escalations or false negatives.

4. `clarification_prompt_rate`
Interpretation: how often the system asks users for data it should infer/default. High rates degrade UX and increase abandonment risk.

5. `risky_po_when_llm_failed_rate`
Interpretation: potentially unsafe runs where a PO is still mentioned while the trace-level judge fails.

6. `parallel_timing_mention_rate`
Interpretation: how often performance evidence is surfaced in the response for performance-sensitive cases.

7. Failure concentration by test case + sampled reasoning text
Interpretation: where regressions cluster and what failure mode language repeats across runs.

## What This Enables for Teams

This pattern is useful beyond procurement:

- Incident triage for agent workflows: score “reasoning + sequence,” not just output syntax.
- CI gates with governance nuance: block on trace-risk signals, not only pass/fail.
- Prompt evolution with safety regression visibility: detect when optimization hurts control flow.
- Business-facing observability: show where the process stopped and why, with policy traceability.

## Reproduce

```bash
./scripts/run_eval.sh smoke
./scripts/run_eval.sh trace
./scripts/run_eval.sh full
```

Artifacts:

- Raw results: `results/`
- Copied outputs: `evaluation_results/`
- Analysis JSON: `evaluation_results/analysis.json`
- Charts: `evaluation_results/charts/`
- Summary: `ANALYSIS.md`

---

If you only keep one mental model from this experiment, keep this one:

For multi-agent systems, correctness is a property of the trace.
