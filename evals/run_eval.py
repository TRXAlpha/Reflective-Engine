#!/usr/bin/env python3
"""Minimal baseline-vs-reflection evaluation runner.

This is intentionally small: it creates reproducible raw output logs, not
publication-grade benchmark claims. Use it to collect evidence before updating
the paper with quantitative results.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = ROOT / "backend" / "reflective_engine.py"


def load_engine():
    spec = importlib.util.spec_from_file_location("reflective_engine_eval", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load engine from {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def grade(task: dict[str, Any], answer: str) -> bool | None:
    grader = task.get("grader")
    raw_expected = task.get("expected", "")
    expected = normalize(str(raw_expected)).strip(".")
    cleaned = normalize(answer).replace("###done###", "").strip(".")
    if grader == "exact":
        return cleaned == expected
    if grader == "yes_no":
        match = re.search(r"\b(yes|no)\b", cleaned)
        return bool(match and match.group(1) == expected)
    if grader == "contains_all":
        if not isinstance(raw_expected, list):
            return None
        return all(normalize(str(item)) in cleaned for item in raw_expected)
    if grader == "contains_any":
        if not isinstance(raw_expected, list):
            return None
        return any(normalize(str(item)) in cleaned for item in raw_expected)
    if grader == "regex":
        try:
            return re.search(str(raw_expected), answer, flags=re.IGNORECASE | re.MULTILINE) is not None
        except re.error:
            return None
    return None


def baseline_answer(prompt: str, model: str, ollama_url: str, timeout: int) -> str:
    response = requests.post(
        ollama_url,
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    return str(payload.get("response", ""))


def reflective_answer(engine, prompt: str, max_loops: int) -> str:
    chunks = list(engine.run_reflective_cycle(prompt, max_loops=max_loops))
    text = "".join(chunks)
    if "[FINAL]" in text:
        text = text.rsplit("[FINAL]", 1)[1]
    return text.replace(engine.CONVERGENCE_TOKEN, "").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", default=str(ROOT / "evals" / "sample_tasks.jsonl"))
    parser.add_argument("--output", default=str(ROOT / "evals" / "results.jsonl"))
    parser.add_argument("--model", default=os.environ.get("GHOST_MODEL", "gemma3:4b"))
    parser.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate"))
    parser.add_argument("--max-loops", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--append", action="store_true", help="Append to output instead of overwriting it.")
    args = parser.parse_args()

    engine = load_engine()
    engine.MODEL = args.model
    engine.OLLAMA_URL = args.ollama_url
    engine.MEMORY_PATH = str(ROOT / "evals" / "eval_memory.jsonl")
    engine.PROFILE_PATH = str(ROOT / "evals" / "eval_profile.json")

    tasks_path = Path(args.tasks)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    mode = "a" if args.append else "w"
    with output_path.open(mode, encoding="utf-8") as out:
        for task in iter_jsonl(tasks_path):
            prompt = task["prompt"]

            start = time.perf_counter()
            base = baseline_answer(prompt, args.model, args.ollama_url, args.timeout)
            base_ms = round((time.perf_counter() - start) * 1000)

            start = time.perf_counter()
            reflected = reflective_answer(engine, prompt, args.max_loops)
            reflected_ms = round((time.perf_counter() - start) * 1000)

            record = {
                "id": task.get("id"),
                "category": task.get("category"),
                "model": args.model,
                "max_loops": args.max_loops,
                "expected": task.get("expected"),
                "baseline_answer": base,
                "reflective_answer": reflected,
                "baseline_correct": grade(task, base),
                "reflective_correct": grade(task, reflected),
                "baseline_latency_ms": base_ms,
                "reflective_latency_ms": reflected_ms,
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(json.dumps(record, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
