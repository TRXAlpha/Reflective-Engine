#!/usr/bin/env python3
"""
ghost_reflective_engine.py

A self-limiting, persistently-memory-backed reflective loop engine for Ollama-style local models.

Features:
- streaming responses from Ollama and live printing
- persistent memory saved to JSONL file (./ghost_memory.jsonl)
- automatic scoring of iterations by the model (0-10)
- convergence detection via explicit CONVERGENCE_TOKEN (###DONE###)
- finisher prompt: on final iteration model is instructed to format final output for display
- early-stopping heuristics: repeated answers, tiny score improvements, or explicit convergence token

Usage: run this script and follow prompts. Tweak MODEL/OLLAMA_URL constants if needed.

Author: Generated for Chris (Ghost project)
"""

import requests
import json
import os
import time
import difflib
from datetime import datetime
from typing import Generator, List, Dict, Any, Optional

# ----------------- Configuration -----------------
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL = os.environ.get("GHOST_MODEL", "gemma3:4b")
MEMORY_PATH = os.environ.get("GHOST_MEMORY_PATH", "./ghost_memory.jsonl")
MAX_HARD_LOOPS = 200  # absolute safety cap
CONVERGENCE_TOKEN = "###DONE###"  # model emits this when it thinks it's converged
FINISH_SIGNAL = "###FINISH_FOR_DISPLAY###"  # model emits or is prompted to produce final user-ready content
REPEAT_SIMILARITY_THRESHOLD = 0.92  # above this ratio between answers == considered repeat
REPEAT_COUNT_TO_STOP = 3
MIN_SCORE_IMPROVEMENT = 0.25  # minimal meaningful score improvement to continue

# ----------------- Utilities -----------------

def save_memory_record(record: Dict[str, Any]):
    """Append a memory record (JSON) to MEMORY_PATH."""
    with open(MEMORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_memory(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Load previous memory records (if any). Returns list of records (newest last)."""
    if not os.path.exists(MEMORY_PATH):
        return []
    out = []
    with open(MEMORY_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def is_similar(a: str, b: str) -> float:
    """Return similarity ratio between two strings (0..1)."""
    return difflib.SequenceMatcher(a=a, b=b).ratio()

# ----------------- Ollama helpers -----------------

def query_ollama_stream(prompt: str, system: str = None) -> Generator[str, None, None]:
    """
    Stream generator: yields chunks of text from Ollama as they arrive.
    Each line from the HTTP stream is JSON; we extract the 'response' field.
    """
    data = {"model": MODEL, "prompt": prompt, "stream": True}
    if system:
        data["system"] = system

    with requests.post(OLLAMA_URL, json=data, stream=True, timeout=300) as resp:
        # resp.iter_lines yields raw bytes lines; each line should be a full JSON object
        for raw in resp.iter_lines():
            if not raw:
                continue
            try:
                line = raw.decode("utf-8")
            except Exception:
                line = raw if isinstance(raw, str) else raw.decode(errors="ignore")

            # Some lines might be concatenated JSONs; try to parse safely
            for candidate in _split_json_objects(line):
                try:
                    j = json.loads(candidate)
                except Exception:
                    continue
                chunk = j.get("response") or j.get("text") or j.get("results")
                # handle nested results array common in some APIs
                if isinstance(chunk, list) and len(chunk) > 0 and isinstance(chunk[0], dict):
                    # try to find a textual field
                    for item in chunk:
                        if isinstance(item, dict) and "content" in item:
                            chunk = item["content"]
                            break
                if isinstance(chunk, str) and chunk:
                    yield chunk


def _split_json_objects(s: str) -> List[str]:
    """Split a string that may contain multiple top-level JSON objects into candidates.
    This is a heuristic safe-split using braces balance.
    """
    candidates = []
    start = None
    depth = 0
    for i, ch in enumerate(s):
        if ch == "{" and start is None:
            start = i
            depth = 1
        elif ch == "{" and start is not None:
            depth += 1
        elif ch == "}" and start is not None:
            depth -= 1
            if depth == 0:
                candidates.append(s[start:i + 1])
                start = None
    # fallback: if nothing found, return the whole string
    if not candidates:
        return [s]
    return candidates


def query_ollama_once(prompt: str, system: str = None, timeout: int = 60) -> str:
    """Non-streaming call to Ollama; robustly return a single text response (best-effort).
    Used for short control queries like scoring or loop count estimation.
    """
    data = {"model": MODEL, "prompt": prompt, "stream": False}
    if system:
        data["system"] = system

    resp = requests.post(OLLAMA_URL, json=data, timeout=timeout)
    text = resp.text

    # Try parsing JSON directly
    try:
        j = resp.json()
        # common shapes: {'response': '...', 'done': True} or {'results': [{'content': '...'}]}
        if isinstance(j, dict):
            if "response" in j and isinstance(j["response"], str):
                return j["response"]
            if "results" in j and isinstance(j["results"], list) and j["results"]:
                r0 = j["results"][0]
                if isinstance(r0, dict) and "content" in r0:
                    return r0["content"]
        # fallback: str()
        return str(j)
    except Exception:
        # fallback: try to parse the last JSON object on separate lines2
        last_good = None
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
                last_good = j
            except Exception:
                continue
        if last_good is not None:
            if isinstance(last_good, dict):
                if "response" in last_good:
                    return last_good["response"]
                # results/content fallback
                if "results" in last_good and last_good["results"]:
                    r0 = last_good["results"][0]
                    if isinstance(r0, dict) and "content" in r0:
                        return r0["content"]
            return json.dumps(last_good)

        # absolute fallback: return raw text
        return text

# ----------------- Scoring & Meta helpers -----------------

def estimate_loops(user_prompt: str, max_loops: int) -> int:
    meta_prompt = f"""
The user asked: "{user_prompt}"
Estimate how many reasoning-reflection loops (1–{max_loops}) you should perform to give a high-quality answer. Reply only with an integer.
"""
    txt = query_ollama_once(meta_prompt)
    # attempt to extract integer
    try:
        return max(1, min(max_loops, int(''.join(ch for ch in txt if ch.isdigit()) or 1)))
    except Exception:
        return 1


def score_answer(user_prompt: str, answer: str) -> float:
    """Ask the model to rate the given answer 0–10 on completeness and correctness. Return float score.
    This helps guide convergence.
    """
    scoring_prompt = f"""
You will rate a candidate answer on a scale 0–10 for correctness and completeness regarding the user's question.
Do not provide commentary—reply ONLY with a single numeric score (integer or decimal).\n
User question: {user_prompt}\n
Candidate answer: {answer}\n
Provide a single number (0.0 - 10.0) only.
"""
    raw = query_ollama_once(scoring_prompt)
    # extract first number-like substring
    for token in raw.replace(',', '.').split():
        try:
            val = float(token)
            if 0.0 <= val <= 10.0:
                return val
        except Exception:
            continue
    # fallback: try to parse digits in text
    digits = ''.join(ch for ch in raw if ch.isdigit() or ch == '.')
    try:
        val = float(digits)
        return max(0.0, min(10.0, val))
    except Exception:
        return 5.0

# ----------------- Core reflective loop -----------------

def stream_to_string(gen: Generator[str, None, None], echo: bool = True) -> str:
    """Consume streaming generator, print live (optional), and return full string."""
    pieces = []
    for chunk in gen:
        if echo:
            print(chunk, end="", flush=True)
        pieces.append(chunk)
    if echo:
        print()
    return ''.join(pieces)


def reflective_thinking_loop(user_prompt: str, max_loops: int = 5, echo_stream: bool = True):
    # load some recent memory to help the model be "self-evolving"
    recent_memory = load_memory(limit=50)  # last 50 records
    memory_summary = ''
    if recent_memory:
        # provide short summary: timestamps + short hashes
        lines = []
        for r in recent_memory[-10:]:
            t = r.get('ts')
            s = (r.get('answer') or '')[:120].replace('\n',' ') + ('...' if len(r.get('answer',''))>120 else '')
            lines.append(f"[{t}] {s}")
        memory_summary = '\n'.join(lines)

    # Step 1: ask model how many loops
    loops = estimate_loops(user_prompt, max_loops)
    loops = max(1, min(loops, max_loops, MAX_HARD_LOOPS))
    print(f"\n[INFO] Model decided on {loops} reflection loops. (hard cap {MAX_HARD_LOOPS})\n")

    # Step 2: initial answer
    print("\n--- Initial Answer ---")
    init_prompt = f"{user_prompt}\n\n(Use the context below if helpful)\nMemory summary:\n{memory_summary}\n"
    current_answer = stream_to_string(query_ollama_stream(init_prompt), echo=echo_stream)

    # bookkeeping
    answers = [current_answer]
    scores = []
    timestamp = lambda: datetime.utcnow().isoformat() + 'Z'

    # Step 3: reflect + improve
    for i in range(1, loops + 1):
        print(f"\n--- Reflection Loop {i} ---")

        # score previous answer
        score = score_answer(user_prompt, current_answer)
        scores.append(score)
        print(f"[SCORE] iteration {i} score = {score}\n")

        # store intermediate memory record
        rec = {
            'ts': timestamp(),
            'loop': i,
            'prompt': user_prompt,
            'answer': current_answer,
            'score': score,
        }
        save_memory_record(rec)

        # early stopping: convergence token was already emitted by streaming? check content
        if CONVERGENCE_TOKEN in current_answer:
            print(f"[INFO] Convergence token detected in iteration {i}; stopping loops.")
            current_answer = current_answer.replace(CONVERGENCE_TOKEN, '').strip()
            break

        # early stopping: repeated answers
        if len(answers) >= REPEAT_COUNT_TO_STOP:
            last_n = answers[-REPEAT_COUNT_TO_STOP:]
            ratios = [is_similar(last_n[j], last_n[-1]) for j in range(len(last_n)-1)]
            if all(r >= REPEAT_SIMILARITY_THRESHOLD for r in ratios):
                print(f"[INFO] Recent answers repeated (similarity >= {REPEAT_SIMILARITY_THRESHOLD}); stopping.")
                break

        # early stopping: very small improvement of score over last two iterations
        if len(scores) >= 2:
            if (scores[-1] - scores[-2]) < MIN_SCORE_IMPROVEMENT and scores[-1] > 8.0:
                print(f"[INFO] Score improvement smaller than {MIN_SCORE_IMPROVEMENT} and high score reached; stopping.")
                break

        # Prepare review prompt
        review_prompt = f"""
Review this reasoning attempt and rate its completeness and correctness from 0–10. Suggest specific improvements.\n\nUser question: {user_prompt}\nCurrent reasoning: {current_answer}\n
Reply concisely; if this is the FINAL iteration, only output the string {CONVERGENCE_TOKEN} if no further improvements are possible.
"""
        review_text = stream_to_string(query_ollama_stream(review_prompt), echo=echo_stream)

        # Now ask to rewrite the answer using the review. If this is the last allowed loop, instruct finisher-mode.
        final_iteration = (i == loops)
        if final_iteration:
            improve_prompt = f"""
Based on the following review, produce the FINAL polished user-facing answer ready for display.
- Do NOT include meta-discussion.
- Format the answer with a short titled header, a 1–2 sentence TL;DR, and a bullet list of key points.
- After the user-facing content, append a single line with the exact token {CONVERGENCE_TOKEN} to indicate convergence.

Review: {review_text}\n\nCurrent answer: {current_answer}
"""
        else:
            improve_prompt = f"""
Based on the following review, rewrite the answer improving correctness, completeness and clarity. Provide the full revised answer (no review text). If you believe this is converged, append the single token {CONVERGENCE_TOKEN} on its own line at the end.

Review: {review_text}\n\nCurrent answer: {current_answer}
"""

        new_answer = stream_to_string(query_ollama_stream(improve_prompt), echo=echo_stream)

        # If the model appended convergence token, strip for storage and stop
        if new_answer.strip().endswith(CONVERGENCE_TOKEN):
            print(f"[INFO] Model declared convergence at loop {i}.")
            new_answer = new_answer.replace(CONVERGENCE_TOKEN, '').strip()
            answers.append(new_answer)
            current_answer = new_answer
            save_memory_record({'ts': timestamp(), 'loop': i, 'prompt': user_prompt, 'answer': current_answer, 'score': score, 'converged': True})
            break

        # push new answer
        answers.append(new_answer)
        current_answer = new_answer

    # final: ensure the last iteration is displayed nicely
    # If final answer doesn't look like a user-ready 'finisher', we can ask the model to produce a display-ready version now
    if not current_answer.strip():
        return "(no answer produced)"

    # If current answer doesn't contain a short header or looks like a draft, force a finisher pass
    if FINISH_SIGNAL not in current_answer and not current_answer.strip().startswith("**"):
        finisher_prompt = f"""
FINALIZE: Produce a concise user-facing display of the following answer. Provide a one-line title, a 1–2 sentence TL;DR, and a short bullet list (3–6 bullets). No meta commentary.\n\nAnswer to finalize:\n{current_answer}\n\nAt the very end place the exact token {CONVERGENCE_TOKEN} on its own line.
"""
        print("\n--- Finisher pass (structuring final output for display) ---")
        final_chunk = stream_to_string(query_ollama_stream(finisher_prompt), echo=echo_stream)
        if CONVERGENCE_TOKEN in final_chunk:
            final_chunk = final_chunk.replace(CONVERGENCE_TOKEN, '').strip()
        current_answer = final_chunk
        save_memory_record({'ts': timestamp(), 'loop': 'finisher', 'prompt': user_prompt, 'answer': current_answer, 'score': scores[-1] if scores else None, 'finalized': True})

    return current_answer

# ----------------- CLI -----------------

def main():
    print("Ghost reflective engine — streaming + persistent memory + convergence control")
    prompt = input("chris: ")
    try:
        max_loops = int(input("no. of max thinking loops (press Enter for 5): ") or 5)
    except Exception:
        max_loops = 5

    final_answer = reflective_thinking_loop(prompt, max_loops=max_loops, echo_stream=True)

    print("\n--- ghost final answer ---\n")
    print(final_answer)
    print("\n(Answer saved to memory file: {} )".format(os.path.abspath(MEMORY_PATH)))


if __name__ == '__main__':
    main()
