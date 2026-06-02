#!/usr/bin/env python3
"""Compute improvement metrics from evals/run_eval.py JSONL output.

The script reports only metrics supported by the provided result file. It does
not invent benchmark results; missing grades are excluded from accuracy math.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def pct(value: float) -> float:
    return round(value * 100.0, 4)


def safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    graded = [
        r
        for r in records
        if isinstance(r.get("baseline_correct"), bool)
        and isinstance(r.get("reflective_correct"), bool)
    ]
    base_latencies = [r["baseline_latency_ms"] for r in records if isinstance(r.get("baseline_latency_ms"), (int, float))]
    refl_latencies = [r["reflective_latency_ms"] for r in records if isinstance(r.get("reflective_latency_ms"), (int, float))]

    n = len(graded)
    base_correct = sum(1 for r in graded if r["baseline_correct"])
    refl_correct = sum(1 for r in graded if r["reflective_correct"])

    base_acc = safe_div(base_correct, n) if n else None
    refl_acc = safe_div(refl_correct, n) if n else None
    absolute_gain = (refl_acc - base_acc) if base_acc is not None and refl_acc is not None else None
    relative_gain = safe_div(absolute_gain, base_acc) if absolute_gain is not None and base_acc else None

    base_error = (1.0 - base_acc) if base_acc is not None else None
    refl_error = (1.0 - refl_acc) if refl_acc is not None else None
    error_reduction = safe_div(base_error - refl_error, base_error) if base_error not in (None, 0) else None

    avg_base_latency = mean(base_latencies) if base_latencies else None
    avg_refl_latency = mean(refl_latencies) if refl_latencies else None
    latency_overhead = (
        safe_div(avg_refl_latency - avg_base_latency, avg_base_latency)
        if avg_base_latency and avg_refl_latency is not None
        else None
    )

    return {
        "records_total": len(records),
        "graded_records": n,
        "baseline_correct": base_correct,
        "reflective_correct": refl_correct,
        "baseline_accuracy": pct(base_acc) if base_acc is not None else None,
        "reflective_accuracy": pct(refl_acc) if refl_acc is not None else None,
        "absolute_improvement_points": round(absolute_gain * 100.0, 4) if absolute_gain is not None else None,
        "relative_performance_gain_percent": pct(relative_gain) if relative_gain is not None else None,
        "error_reduction_rate_percent": pct(error_reduction) if error_reduction is not None else None,
        "avg_baseline_latency_ms": round(avg_base_latency, 4) if avg_base_latency is not None else None,
        "avg_reflective_latency_ms": round(avg_refl_latency, 4) if avg_refl_latency is not None else None,
        "latency_overhead_percent": pct(latency_overhead) if latency_overhead is not None else None,
    }


def by_category(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("category") or "uncategorized")].append(record)
    return {category: summarize(items) for category, items in sorted(grouped.items())}


def by_model(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("model") or "unknown")].append(record)
    return {model: summarize(items) for model, items in sorted(grouped.items())}


def by_model_and_category(records: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for record in records:
        model = str(record.get("model") or "unknown")
        category = str(record.get("category") or "uncategorized")
        grouped[model][category].append(record)
    return {
        model: {category: summarize(items) for category, items in sorted(categories.items())}
        for model, categories in sorted(grouped.items())
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="evals/results.jsonl")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    records = list(iter_jsonl(Path(args.input)))
    report = {
        "formulas": {
            "baseline_accuracy": "baseline_correct / graded_records",
            "reflective_accuracy": "reflective_correct / graded_records",
            "absolute_improvement_points": "(reflective_accuracy - baseline_accuracy) * 100",
            "relative_performance_gain_percent": "((reflective_accuracy - baseline_accuracy) / baseline_accuracy) * 100",
            "error_reduction_rate_percent": "((baseline_error - reflective_error) / baseline_error) * 100",
            "latency_overhead_percent": "((avg_reflective_latency_ms - avg_baseline_latency_ms) / avg_baseline_latency_ms) * 100",
        },
        "overall": summarize(records),
        "by_category": by_category(records),
        "by_model": by_model(records),
        "by_model_and_category": by_model_and_category(records),
    }

    rendered = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
