#!/usr/bin/env python3
"""Aggregate SAM evaluation outputs and generate analysis artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

PASS_THRESHOLD = 0.7
CLARIFICATION_HINTS = (
    "could you provide",
    "please provide",
    "i need to clarify",
    "need to clarify",
    "missing information",
    "i need the",
)
SUPPLIER_TOOL_TOKENS = {"query_supplier_apis", "peer_supplieragent"}
COMPLIANCE_TOOL_TOKENS = {"validate_compliance_rules", "peer_complianceagent"}


def contains_any(text: str, hints: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in hints)


def first_matching_tool_index(tool_names: list[str], tokens: set[str]) -> int | None:
    for idx, tool_name in enumerate(tool_names):
        if tool_name.lower() in tokens:
            return idx
    return None


def now_utc_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_figure(fig: go.Figure, base_path: Path) -> None:
    png_path = base_path.with_suffix(".png")
    html_path = base_path.with_suffix(".html")
    try:
        fig.write_image(str(png_path), width=1200, height=700, scale=2)
    except Exception:
        fig.write_html(str(html_path), include_plotlyjs="cdn")


def summarize_result_dir(result_dir: Path) -> dict[str, Any]:
    if not result_dir.exists():
        return {"available": False, "path": str(result_dir)}

    stats = read_json(result_dir / "stats.json") or {}
    model_dirs = [d for d in result_dir.iterdir() if d.is_dir() and (d / "results.json").exists()]
    if not model_dirs:
        return {"available": False, "path": str(result_dir), "reason": "No model results.json found"}

    model_dir = sorted(model_dirs)[0]
    model_results = read_json(model_dir / "results.json") or {}

    test_cases = model_results.get("test_cases", [])
    if not test_cases:
        return {
            "available": True,
            "path": str(result_dir),
            "model_name": model_results.get("model_name", model_dir.name),
            "test_case_count": 0,
            "metrics": {},
            "agreements": {},
            "failures": [],
            "latency": {},
        }

    run_rows: list[dict[str, Any]] = []
    per_case_latency: dict[str, float] = {}
    per_case_tool_calls: dict[str, float] = {}

    for test_case in test_cases:
        tc_id = test_case["test_case_id"]
        runs = test_case.get("runs", [])
        durations: list[float] = []
        tool_counts: list[int] = []

        for run in runs:
            row = {
                "test_case_id": tc_id,
                "tool_match": run.get("tool_match"),
                "response_match": run.get("response_match"),
                "llm_eval": (run.get("llm_eval") or {}).get("score"),
                "llm_reasoning": (run.get("llm_eval") or {}).get("reasoning", ""),
                "duration_seconds": run.get("duration_seconds"),
            }

            run_num = run.get("run")
            summary_path = model_dir / tc_id / f"run_{run_num}" / "summary.json"
            summary_data = read_json(summary_path)
            summary_final_message = ""
            tool_names: list[str] = []
            if isinstance(summary_data, dict):
                duration_val = summary_data.get("duration_seconds")
                if isinstance(duration_val, (int, float)):
                    durations.append(float(duration_val))

                summary_final_message = str(summary_data.get("final_message", ""))
                tool_calls = summary_data.get("tool_calls", [])
                if isinstance(tool_calls, list):
                    tool_counts.append(len(tool_calls))
                    for tool_call in tool_calls:
                        if not isinstance(tool_call, dict):
                            continue
                        tool_name = str(tool_call.get("tool_name", "")).strip()
                        if tool_name:
                            tool_names.append(tool_name)

            row["final_message"] = summary_final_message
            row["tool_names"] = tool_names
            row["has_clarification_prompt"] = contains_any(summary_final_message, CLARIFICATION_HINTS)
            final_message_lower = summary_final_message.lower()
            row["mentions_po"] = "po-" in final_message_lower
            row["mentions_parallel_timing"] = (
                "parallel_elapsed_ms" in final_message_lower
                or "sequential_estimate_ms" in final_message_lower
            )

            supplier_idx = first_matching_tool_index(tool_names, SUPPLIER_TOOL_TOKENS)
            compliance_idx = first_matching_tool_index(tool_names, COMPLIANCE_TOOL_TOKENS)
            has_supplier_and_compliance = supplier_idx is not None and compliance_idx is not None
            row["has_supplier_and_compliance"] = has_supplier_and_compliance
            row["compliance_before_supplier"] = bool(
                has_supplier_and_compliance and compliance_idx < supplier_idx
            )

            run_rows.append(row)

        per_case_latency[tc_id] = sum(durations) / len(durations) if durations else 0.0
        per_case_tool_calls[tc_id] = sum(tool_counts) / len(tool_counts) if tool_counts else 0.0

    case_level = {
        "tool_match_pass_rate": 0.0,
        "response_match_pass_rate": 0.0,
        "llm_eval_pass_rate": 0.0,
    }

    tool_case_pass = 0
    response_case_pass = 0
    llm_case_pass = 0

    for test_case in test_cases:
        t_avg = float(test_case.get("tool_match_scores", {}).get("average", 0.0))
        r_avg = float(test_case.get("response_match_scores", {}).get("average", 0.0))
        l_avg = float(test_case.get("llm_eval_scores", {}).get("average", 0.0))

        if t_avg >= PASS_THRESHOLD:
            tool_case_pass += 1
        if r_avg >= PASS_THRESHOLD:
            response_case_pass += 1
        if l_avg >= PASS_THRESHOLD:
            llm_case_pass += 1

    total_cases = len(test_cases)
    case_level["tool_match_pass_rate"] = tool_case_pass / total_cases
    case_level["response_match_pass_rate"] = response_case_pass / total_cases
    case_level["llm_eval_pass_rate"] = llm_case_pass / total_cases

    agreement_tool_vs_llm = []
    agreement_response_vs_llm = []

    failure_counter = Counter()
    failure_reasons: defaultdict[str, list[str]] = defaultdict(list)

    for row in run_rows:
        t = row.get("tool_match")
        r = row.get("response_match")
        l = row.get("llm_eval")

        if isinstance(t, (int, float)) and isinstance(l, (int, float)):
            agreement_tool_vs_llm.append((t >= PASS_THRESHOLD) == (l >= PASS_THRESHOLD))
        if isinstance(r, (int, float)) and isinstance(l, (int, float)):
            agreement_response_vs_llm.append((r >= PASS_THRESHOLD) == (l >= PASS_THRESHOLD))

        if isinstance(l, (int, float)) and l < PASS_THRESHOLD:
            tc_id = row["test_case_id"]
            failure_counter[tc_id] += 1
            reason = (row.get("llm_reasoning") or "").strip()
            if reason:
                failure_reasons[tc_id].append(reason)

    failure_rows = []
    for tc_id, count in failure_counter.most_common():
        reasons = failure_reasons.get(tc_id, [])
        top_reasons = reasons[:2]
        failure_rows.append(
            {
                "test_case_id": tc_id,
                "failed_runs": count,
                "sample_reasons": top_reasons,
            }
        )

    avg_latency = sum(per_case_latency.values()) / len(per_case_latency)
    avg_tool_calls = sum(per_case_tool_calls.values()) / len(per_case_tool_calls)

    total_runs = len(run_rows)
    clarification_runs = sum(1 for row in run_rows if row.get("has_clarification_prompt"))
    po_mention_runs = sum(1 for row in run_rows if row.get("mentions_po"))
    parallel_timing_runs = sum(1 for row in run_rows if row.get("mentions_parallel_timing"))

    ordering_candidates = [row for row in run_rows if row.get("has_supplier_and_compliance")]
    ordering_violations = sum(1 for row in ordering_candidates if row.get("compliance_before_supplier"))

    llm_failed_rows = [
        row
        for row in run_rows
        if isinstance(row.get("llm_eval"), (int, float)) and row["llm_eval"] < PASS_THRESHOLD
    ]
    risky_po_on_failed_runs = sum(1 for row in llm_failed_rows if row.get("mentions_po"))

    llm_pass_tool_fail_runs = sum(
        1
        for row in run_rows
        if isinstance(row.get("llm_eval"), (int, float))
        and isinstance(row.get("tool_match"), (int, float))
        and row["llm_eval"] >= PASS_THRESHOLD
        and row["tool_match"] < PASS_THRESHOLD
    )
    llm_fail_tool_pass_runs = sum(
        1
        for row in run_rows
        if isinstance(row.get("llm_eval"), (int, float))
        and isinstance(row.get("tool_match"), (int, float))
        and row["llm_eval"] < PASS_THRESHOLD
        and row["tool_match"] >= PASS_THRESHOLD
    )

    return {
        "available": True,
        "path": str(result_dir),
        "model_name": model_results.get("model_name", model_dir.name),
        "total_execution_time": (stats or {}).get("total_execution_time"),
        "test_case_count": total_cases,
        "metrics": case_level,
        "agreements": {
            "tool_vs_llm": sum(agreement_tool_vs_llm) / len(agreement_tool_vs_llm)
            if agreement_tool_vs_llm
            else 0.0,
            "response_vs_llm": sum(agreement_response_vs_llm)
            / len(agreement_response_vs_llm)
            if agreement_response_vs_llm
            else 0.0,
        },
        "failures": failure_rows,
        "latency": {
            "average_duration_seconds": avg_latency,
            "per_test_case": per_case_latency,
        },
        "tool_calls": {
            "average_tool_calls_per_run": avg_tool_calls,
            "per_test_case": per_case_tool_calls,
        },
        "trace_monitoring": {
            "total_runs": total_runs,
            "clarification_prompt_rate": (clarification_runs / total_runs) if total_runs else 0.0,
            "po_mention_rate": (po_mention_runs / total_runs) if total_runs else 0.0,
            "parallel_timing_mention_rate": (parallel_timing_runs / total_runs)
            if total_runs
            else 0.0,
            "compliance_before_supplier_rate": (
                ordering_violations / len(ordering_candidates)
                if ordering_candidates
                else None
            ),
            "risky_po_when_llm_failed_rate": (
                risky_po_on_failed_runs / len(llm_failed_rows) if llm_failed_rows else 0.0
            ),
            "llm_pass_tool_fail_rate": (llm_pass_tool_fail_runs / total_runs)
            if total_runs
            else 0.0,
            "llm_fail_tool_pass_rate": (llm_fail_tool_pass_runs / total_runs)
            if total_runs
            else 0.0,
        },
        "raw_stats": stats,
    }


def build_charts(report: dict[str, Any], charts_dir: Path) -> None:
    ensure_dir(charts_dir)

    metrics = report.get("metrics", {})
    if metrics:
        pass_rate_fig = go.Figure(
            data=[
                go.Bar(
                    x=["tool_match", "response_match", "llm_eval"],
                    y=[
                        metrics.get("tool_match_pass_rate", 0.0),
                        metrics.get("response_match_pass_rate", 0.0),
                        metrics.get("llm_eval_pass_rate", 0.0),
                    ],
                    marker_color=["#0a9396", "#ee9b00", "#9b2226"],
                )
            ]
        )
        pass_rate_fig.update_layout(
            title="Pass Rate by Evaluation Method",
            yaxis_title="Pass Rate",
            xaxis_title="Method",
            yaxis=dict(range=[0, 1]),
        )
        save_figure(pass_rate_fig, charts_dir / "pass_rates")

    agreements = report.get("agreements", {})
    if agreements:
        agreement_fig = go.Figure(
            data=go.Heatmap(
                z=[
                    [agreements.get("tool_vs_llm", 0.0)],
                    [agreements.get("response_vs_llm", 0.0)],
                ],
                x=["Agreement with llm_evaluator"],
                y=["tool_match", "response_match"],
                colorscale="YlGnBu",
                zmin=0,
                zmax=1,
            )
        )
        agreement_fig.update_layout(title="Agreement Analysis")
        save_figure(agreement_fig, charts_dir / "agreement_heatmap")

    per_case_latency = (report.get("latency") or {}).get("per_test_case", {})
    if per_case_latency:
        sorted_items = sorted(per_case_latency.items(), key=lambda item: item[1], reverse=True)
        latency_fig = go.Figure(
            data=[
                go.Bar(
                    x=[item[0] for item in sorted_items],
                    y=[item[1] for item in sorted_items],
                    marker_color="#005f73",
                )
            ]
        )
        latency_fig.update_layout(
            title="Average Latency by Test Case",
            xaxis_title="Test Case",
            yaxis_title="Seconds",
            xaxis_tickangle=-35,
        )
        save_figure(latency_fig, charts_dir / "latency_by_test_case")

    trace_monitoring = report.get("trace_monitoring", {})
    if trace_monitoring:
        signal_labels = [
            "clarification_prompt_rate",
            "risky_po_when_llm_failed_rate",
            "llm_pass_tool_fail_rate",
            "llm_fail_tool_pass_rate",
            "parallel_timing_mention_rate",
        ]
        signal_values = [float(trace_monitoring.get(label, 0.0) or 0.0) for label in signal_labels]

        compliance_before_supplier_rate = trace_monitoring.get("compliance_before_supplier_rate")
        if isinstance(compliance_before_supplier_rate, (int, float)):
            signal_labels.append("compliance_before_supplier_rate")
            signal_values.append(float(compliance_before_supplier_rate))

        trace_fig = go.Figure(
            data=[
                go.Bar(
                    x=signal_labels,
                    y=signal_values,
                    marker_color="#7b2cbf",
                )
            ]
        )
        trace_fig.update_layout(
            title="Trace Monitoring Signals",
            xaxis_title="Signal",
            yaxis_title="Rate",
            yaxis=dict(range=[0, 1]),
            xaxis_tickangle=-30,
        )
        save_figure(trace_fig, charts_dir / "trace_signals")


def write_analysis_markdown(
    full_report: dict[str, Any],
    smoke_report: dict[str, Any],
    markdown_path: Path,
) -> None:
    generated_at = now_utc_iso()

    target_report = full_report if full_report.get("available") else smoke_report
    if not target_report.get("available"):
        markdown_path.write_text(
            "# SAP PO Evaluation Analysis\n\nNo evaluation results were found.",
            encoding="utf-8",
        )
        return

    metrics = target_report.get("metrics", {})
    agreements = target_report.get("agreements", {})
    failures = target_report.get("failures", [])
    latency = target_report.get("latency", {})
    tool_calls = target_report.get("tool_calls", {})
    trace_monitoring = target_report.get("trace_monitoring", {})

    lines = [
        "# SAP PO Evaluation Analysis",
        "",
        f"Generated at: {generated_at}",
        f"Source results: `{target_report.get('path')}`",
        "",
        "## Executive Summary",
        f"- Model: `{target_report.get('model_name')}`",
        f"- Test cases evaluated: **{target_report.get('test_case_count', 0)}**",
        f"- llm_evaluator case-level pass rate (>= {PASS_THRESHOLD:.1f}): **{metrics.get('llm_eval_pass_rate', 0.0):.2%}**",
        f"- tool_match case-level pass rate: **{metrics.get('tool_match_pass_rate', 0.0):.2%}**",
        f"- response_match case-level pass rate: **{metrics.get('response_match_pass_rate', 0.0):.2%}**",
        "",
        "## Agreement Analysis",
        f"- tool_match vs llm_evaluator agreement: **{agreements.get('tool_vs_llm', 0.0):.2%}**",
        f"- response_match vs llm_evaluator agreement: **{agreements.get('response_vs_llm', 0.0):.2%}**",
        "",
        "## Performance Metrics",
        f"- Average latency across test cases: **{latency.get('average_duration_seconds', 0.0):.2f}s**",
        f"- Average tool calls per run: **{tool_calls.get('average_tool_calls_per_run', 0.0):.2f}**",
        "",
        "## Trace-Level Monitoring (Whole-Trace LLM Judge)",
        f"- Clarification prompt rate: **{trace_monitoring.get('clarification_prompt_rate', 0.0):.2%}**",
        f"- Risky PO mention rate when llm_evaluator failed: **{trace_monitoring.get('risky_po_when_llm_failed_rate', 0.0):.2%}**",
        f"- LLM pass with tool_match fail rate: **{trace_monitoring.get('llm_pass_tool_fail_rate', 0.0):.2%}**",
        f"- LLM fail with tool_match pass rate: **{trace_monitoring.get('llm_fail_tool_pass_rate', 0.0):.2%}**",
        f"- Parallel timing mention rate: **{trace_monitoring.get('parallel_timing_mention_rate', 0.0):.2%}**",
        "",
        "## Failure Analysis",
    ]

    compliance_before_supplier_rate = trace_monitoring.get("compliance_before_supplier_rate")
    if isinstance(compliance_before_supplier_rate, (int, float)):
        insert_at = lines.index("## Failure Analysis")
        lines.insert(
            insert_at,
            f"- Compliance-before-supplier ordering violation rate: **{compliance_before_supplier_rate:.2%}**",
        )

    if failures:
        for item in failures[:5]:
            lines.append(f"- `{item['test_case_id']}` failed in **{item['failed_runs']}** run(s).")
            for reason in item.get("sample_reasons", []):
                trimmed = reason.replace("\n", " ").strip()
                if len(trimmed) > 220:
                    trimmed = trimmed[:220] + "..."
                lines.append(f"  - Sample reasoning: {trimmed}")
    else:
        lines.append("- No llm_evaluator failures were detected.")

    lines.extend(
        [
            "",
            "## Recommendations",
            "- Tighten orchestrator prompts for edge cases with multi-facility decomposition and split sourcing.",
            "- Keep tool outputs machine-readable and pass full context when delegating to reduce reasoning variance.",
            "- Track latency and timeout handling for supplier calls as a dedicated SLO before production rollout.",
            "- Monitor clarification prompt rate and ordering-violation rate to catch trace-level regressions that output-only checks miss.",
            "- Investigate runs where llm_evaluator and tool_match disagree; these usually expose hidden trace-quality issues.",
            "",
            "## Artifacts",
            "- `evaluation_results/charts/pass_rates.(png|html)`",
            "- `evaluation_results/charts/agreement_heatmap.(png|html)`",
            "- `evaluation_results/charts/latency_by_test_case.(png|html)`",
            "- `evaluation_results/charts/trace_signals.(png|html)`",
            "- `evaluation_results/analysis.json`",
        ]
    )

    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze SAM PO evaluation outputs.")
    parser.add_argument("--smoke-dir", default="results/po-eval-smoke")
    parser.add_argument("--full-dir", default="results/po-eval-full")
    parser.add_argument("--output-dir", default="evaluation_results")
    parser.add_argument("--analysis-md", default="ANALYSIS.md")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    charts_dir = output_dir / "charts"
    ensure_dir(output_dir)
    ensure_dir(charts_dir)

    smoke_report = summarize_result_dir(Path(args.smoke_dir))
    full_report = summarize_result_dir(Path(args.full_dir))

    report_payload = {
        "generated_at": now_utc_iso(),
        "pass_threshold": PASS_THRESHOLD,
        "smoke": smoke_report,
        "full": full_report,
    }

    (output_dir / "analysis.json").write_text(
        json.dumps(report_payload, indent=2), encoding="utf-8"
    )

    target_report = full_report if full_report.get("available") else smoke_report
    if target_report.get("available"):
        build_charts(target_report, charts_dir)

    write_analysis_markdown(full_report, smoke_report, Path(args.analysis_md))


if __name__ == "__main__":
    main()
