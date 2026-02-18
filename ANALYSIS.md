# SAP PO Evaluation Analysis

Generated at: 2026-02-18T21:14:20Z
Source results: `results/po-eval-full-safe-full`

## Executive Summary
- Model: `runtime-gpt41mini`
- Test cases evaluated: **16**
- llm_evaluator case-level pass rate (>= 0.7): **81.25%**
- tool_match case-level pass rate: **100.00%**
- response_match case-level pass rate: **0.00%**

## Agreement Analysis
- tool_match vs llm_evaluator agreement: **81.25%**
- response_match vs llm_evaluator agreement: **18.75%**

## Performance Metrics
- Average latency across test cases: **45.61s**
- Average tool calls per run: **8.84**

## Trace-Level Monitoring (Whole-Trace LLM Judge)
- Clarification prompt rate: **0.00%**
- Risky PO mention rate when llm_evaluator failed: **50.00%**
- LLM pass with tool_match fail rate: **3.12%**
- LLM fail with tool_match pass rate: **15.62%**
- Parallel timing mention rate: **0.00%**

- Compliance-before-supplier ordering violation rate: **0.00%**
## Failure Analysis
- `tc06_partial_inventory_split_sourcing` failed in **2** run(s).
  - Sample reasoning: The actual response demonstrates a **partial but incomplete execution** of the split sourcing requirement:  **Strengths:** - ✅ Correctly identifies split sourcing as the appropriate approach (200 units internal + 300 uni...
  - Sample reasoning: The actual response significantly fails to meet the stated criterion. Here's the detailed analysis:  **Criterion Requirements:** The evaluation criterion explicitly asks for: 1. Split sourcing correctly reasoned from par...
- `tc05_compliance_unapproved_vendor` failed in **2** run(s).
  - Sample reasoning: The actual response catastrophically fails to meet the evaluation criterion on all three required dimensions:  1. **Unapproved-Vendor Detection - FAILED**: The query explicitly contains "UNAPP" tags in the product code (...
  - Sample reasoning: The actual response fundamentally fails to meet the criterion on all three critical dimensions:  1. **Unapproved-Vendor Detection - FAILED**: The query explicitly requests "X-2847-UNAPP" (note the "UNAPP" suffix indicati...
- `tc10_parallel_supplier_performance` failed in **2** run(s).
  - Sample reasoning: The response **fails to meet the stated criterion** of demonstrating parallel supplier querying with completed PO workflow. Here's the detailed analysis:  **What the criterion requires:** 1. Evidence of parallel supplier...
  - Sample reasoning: **Strengths (Criterion Partially Met):**  1. **Parallel Query Evidence Present:** The response explicitly includes supplier performance data showing "parallel query optimization achieved" with "All supplier responses com...

## Recommendations
- Tighten orchestrator prompts for edge cases with multi-facility decomposition and split sourcing.
- Keep tool outputs machine-readable and pass full context when delegating to reduce reasoning variance.
- Track latency and timeout handling for supplier calls as a dedicated SLO before production rollout.
- Monitor clarification prompt rate and ordering-violation rate to catch trace-level regressions that output-only checks miss.
- Investigate runs where llm_evaluator and tool_match disagree; these usually expose hidden trace-quality issues.

## Artifacts
- `evaluation_results/charts/pass_rates.(png|html)`
- `evaluation_results/charts/agreement_heatmap.(png|html)`
- `evaluation_results/charts/latency_by_test_case.(png|html)`
- `evaluation_results/charts/trace_signals.(png|html)`
- `evaluation_results/analysis.json`
