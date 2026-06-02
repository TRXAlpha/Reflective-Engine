#!/usr/bin/env python3
"""Insert computed eval metrics into the research paper.

This script intentionally refuses to update the paper when no graded results
exist. Exact improvement scores should come from eval output, not from guesses.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "docs" / "Reflective_Engine_research_paper.md"
START = "<!-- METRICS_START -->"
END = "<!-- METRICS_END -->"


def load_summary(results: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "evals" / "analyze_results.py"), "--input", str(results)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def metric_line(label: str, value) -> str:
    return f"- {label}: not available" if value is None else f"- {label}: {value}"


def render_block(summary: dict) -> str:
    overall = summary["overall"]
    if overall["graded_records"] == 0:
        raise SystemExit("No graded records found; refusing to write exact paper scores.")

    lines = [
        START,
        "",
        "Exact scores from the latest evaluation run:",
        "",
        metric_line("Graded tasks", overall["graded_records"]),
        metric_line("Baseline correct", overall["baseline_correct"]),
        metric_line("Reflective correct", overall["reflective_correct"]),
        metric_line("Baseline accuracy (%)", overall["baseline_accuracy"]),
        metric_line("Reflective accuracy (%)", overall["reflective_accuracy"]),
        metric_line("Absolute improvement (percentage points)", overall["absolute_improvement_points"]),
        metric_line("Relative performance gain (%)", overall["relative_performance_gain_percent"]),
        metric_line("Error reduction rate (%)", overall["error_reduction_rate_percent"]),
        metric_line("Average baseline latency (ms)", overall["avg_baseline_latency_ms"]),
        metric_line("Average reflective latency (ms)", overall["avg_reflective_latency_ms"]),
        metric_line("Latency overhead (%)", overall["latency_overhead_percent"]),
        "",
        END,
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=str(ROOT / "evals" / "results.jsonl"))
    parser.add_argument("--paper", default=str(PAPER))
    args = parser.parse_args()

    results = Path(args.results)
    paper = Path(args.paper)
    summary = load_summary(results)
    replacement = render_block(summary)

    text = paper.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise SystemExit(f"Paper must contain {START} and {END} markers.")

    before = text.split(START, 1)[0]
    after = text.split(END, 1)[1]
    paper.write_text(before + replacement + after, encoding="utf-8")
    print(f"Updated {paper}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
