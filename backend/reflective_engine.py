#!/usr/bin/env python3
"""
reflective_engine.py — streaming + compact-memory + convergence

Design goals:
 - Keep memory concise and relevant (facts + short reasoning).
 - Keep a separate user profile for preferences (e.g. "likes cars").
 - Feed the model a short, high-signal memory summary (not raw debug outputs).
 - Robust NDJSON streaming parser (handles token/delta/choices shapes).
 - Graceful fallbacks when Ollama/model server is unreachable.
"""

from __future__ import annotations
import os
import json
import requests
import difflib
import traceback
from datetime import datetime
from typing import Generator, List, Dict, Any, Optional

# ----------------- Config -----------------
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL = os.environ.get("GHOST_MODEL", "gemma3:4b")
MEMORY_PATH = os.environ.get("GHOST_MEMORY_PATH", "./ghost_memory.jsonl")
PROFILE_PATH = os.environ.get("GHOST_PROFILE_PATH", "./ghost_profile.json")
MAX_HARD_LOOPS = 200
CONVERGENCE_TOKEN = "###DONE###"
FINISH_SIGNAL = "###FINISH_FOR_DISPLAY###"
REPEAT_SIMILARITY_THRESHOLD = 0.92
REPEAT_COUNT_TO_STOP = 3
MIN_SCORE_IMPROVEMENT = 0.25

# memory record constraints
MAX_ANSWER_SNIPPET = 400   # store only up to this many chars for answer_snip
MAX_REASONING_SNIPPET = 300

# ----------------- Utilities -----------------
def _now_ts() -> str:
    return datetime.utcnow().isoformat() + "Z"

def _truncate(text: Optional[str], n: int) -> str:
    if not text:
        return ""
    t = text.strip()
    return (t[: n - 3] + "...") if len(t) > n else t

def _sanitize_text(s: str) -> str:
    # remove stray nonprintable control chars except newline/tab
    return "".join(ch if (ch == "\n" or ch == "\t" or 0x20 <= ord(ch) <= 0x10FFFF) else "?" for ch in s)

# ----------------- Profile (user preferences) -----------------
def load_profile() -> Dict[str, Any]:
    if not os.path.exists(PROFILE_PATH):
        return {}
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_profile(profile: Dict[str, Any]) -> None:
    try:
        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def update_profile(key: str, value: Any) -> None:
    p = load_profile()
    p[key] = value
    save_profile(p)

# ----------------- Memory helpers (compact) -----------------
def save_memory_record(record: Dict[str, Any]) -> None:
    """
    Persist a concise memory record (JSONL).
    Fields we keep: ts, prompt, answer_snip, reasoning_snip, score
    Avoids storing huge outputs or internal tokens.
    """
    minimal = {
        "ts": record.get("ts", _now_ts()),
        "prompt": _truncate(record.get("prompt", ""), 300),
        "answer_snip": _truncate(record.get("answer", "") or record.get("answer_snip", ""), MAX_ANSWER_SNIPPET),
        "reasoning_snip": _truncate(record.get("reasoning", ""), MAX_REASONING_SNIPPET),
        "score": record.get("score")
    }
    try:
        with open(MEMORY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(minimal, ensure_ascii=False) + "\n")
    except Exception:
        # silently ignore write errors (but print for dev)
        print("WARN: failed to write memory record:", traceback.format_exc())

def load_memory(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Return most-recent-first list of memory records (each is the minimal dict).
    Filters out empty answers.
    """
    if not os.path.exists(MEMORY_PATH):
        return []
    out: List[Dict[str, Any]] = []
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if r.get("answer_snip"):
                        out.append(r)
                except Exception:
                    continue
    except Exception:
        return []
    out = [r for r in out if r]  # ensure no null
    # most recent last in file, so return tail
    if limit:
        return out[-limit:]
    return out

def summarize_memory(recent_memory: List[Dict[str, Any]], max_items: int = 8) -> str:
    """
    Build a concise memory summary trusted to be fed into model prompts:
      - First user profile / preferences (if any)
      - Then short bullet facts with optional reasoning
    """
    profile = load_profile()
    lines: List[str] = []
    if profile:
        prefs = ", ".join(f"{k}: {v}" for k, v in profile.items())
        lines.append(f"User profile: {prefs}")
    # take latest max_items records
    for r in recent_memory[-max_items:]:
        ts = r.get("ts", "")[:19]
        fact = _truncate(r.get("answer_snip", ""), 160).replace("\n", " ")
        reasoning = _truncate(r.get("reasoning_snip", ""), 150).replace("\n", " ")
        if reasoning:
            lines.append(f"- [{ts}] {fact} (reason: {reasoning})")
        else:
            lines.append(f"- [{ts}] {fact}")
    return "\n".join(lines)

# ----------------- Robust Ollama streaming parser -----------------
def query_ollama_stream(prompt: str, system: Optional[str] = None) -> Generator[str, None, None]:
    """
    Stream from OLLAMA_URL with robustness to different NDJSON schemas.
    Yields sanitized text chunks.
    """
    data = {"model": MODEL, "prompt": prompt, "stream": True}
    if system:
        data["system"] = system

    def extract_text_from_json(obj: Any) -> Optional[str]:
        # try common shapes, nested shapes, choices/delta, token, response, text, content
        if obj is None:
            return None
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            # Ollama streams metadata-only completion records at the end. If a
            # textual response key is present but empty, there is no token to
            # yield; do not fall through and accidentally emit fields like
            # {"model": "gemma3:4b"} as answer text.
            if "response" in obj:
                response = obj.get("response")
                return response if isinstance(response, str) and response else None
            for k in ("response", "text", "content", "message", "output", "result"):
                v = obj.get(k)
                if isinstance(v, str) and v.strip():
                    return v
            if "token" in obj and isinstance(obj["token"], str):
                return obj["token"]
            if "results" in obj and isinstance(obj["results"], list):
                for it in obj["results"]:
                    if isinstance(it, dict):
                        for k2 in ("content", "response", "text"):
                            if k2 in it and isinstance(it[k2], str):
                                return it[k2]
            if "choices" in obj and isinstance(obj["choices"], list):
                for ch in obj["choices"]:
                    if isinstance(ch, dict):
                        delta = ch.get("delta") or ch.get("message") or {}
                        if isinstance(delta, dict):
                            for k3 in ("content", "text", "token"):
                                if k3 in delta and isinstance(delta[k3], str):
                                    return delta[k3]
                        for k4 in ("content", "text", "response"):
                            if k4 in ch and isinstance(ch[k4], str):
                                return ch[k4]
        return None

    try:
        with requests.post(OLLAMA_URL, json=data, stream=True, timeout=300) as resp:
            # if the server returns non-200 we still try to stream text
            buffer = ""
            token_acc: List[str] = []
            for raw in resp.iter_content(chunk_size=4096):
                if not raw:
                    continue
                text = raw.decode("utf-8", errors="replace")
                buffer += text
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    parsed = None
                    try:
                        parsed = json.loads(line)
                    except Exception:
                        parsed = None
                    piece = None
                    if parsed is not None:
                        piece = extract_text_from_json(parsed)
                    if piece is None and parsed is None:
                        piece = line
                    if piece is None:
                        continue
                    if isinstance(piece, str) and len(piece) <= 4:
                        token_acc.append(piece)
                        continue
                    else:
                        if token_acc:
                            yield _sanitize_text("".join(token_acc))
                            token_acc = []
                        yield _sanitize_text(piece)
            # flush remaining buffer
            if buffer:
                rem = buffer.strip()
                if rem:
                    try:
                        parsed = json.loads(rem)
                        piece = extract_text_from_json(parsed) or rem
                    except Exception:
                        piece = rem
                    if token_acc:
                        yield _sanitize_text("".join(token_acc))
                    yield _sanitize_text(piece)
            if token_acc:
                yield _sanitize_text("".join(token_acc))
    except Exception as e:
        # yield a helpful error fragment for the caller to show, don't raise
        yield f"[ERROR] query_ollama_stream exception: {e}\n"

# ----------------- One-shot query helper -----------------
def query_ollama_once(prompt: str, system: Optional[str] = None, timeout: int = 60) -> str:
    """
    Non-streaming call. Returns best-effort string.
    """
    data = {"model": MODEL, "prompt": prompt, "stream": False}
    if system:
        data["system"] = system
    try:
        resp = requests.post(OLLAMA_URL, json=data, timeout=timeout)
    except Exception as e:
        return f"[ERROR] Could not connect to model at {OLLAMA_URL}: {e}"
    # try parse JSON body, else fallback to last NDJSON-like line
    try:
        j = resp.json()
        if isinstance(j, dict):
            if "response" in j and isinstance(j["response"], str):
                return j["response"]
            if "choices" in j and isinstance(j["choices"], list) and j["choices"]:
                ch0 = j["choices"][0]
                if isinstance(ch0, dict) and "content" in ch0:
                    return str(ch0["content"])
        return str(j)
    except Exception:
        text = resp.text
        last_good = None
        for line in text.splitlines():
            try:
                last_good = json.loads(line)
            except Exception:
                continue
        if last_good:
            if isinstance(last_good, dict):
                for k in ("response", "text", "content"):
                    if k in last_good and isinstance(last_good[k], str):
                        return last_good[k]
        return text

# ----------------- Scoring & loops -----------------
def estimate_loops(user_prompt: str, max_loops: int) -> int:
    try:
        txt = query_ollama_once(f'The user asked: "{user_prompt}"\nEstimate loops 1-{max_loops}, reply only an integer.')
        # extract first integer-looking token
        digits = "".join(ch for ch in txt if ch.isdigit())
        if digits:
            n = int(digits)
            return max(1, min(n, max_loops))
    except Exception:
        pass
    return 1

def is_similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(a=a, b=b).ratio()

def score_answer(user_prompt: str, answer: str) -> float:
    try:
        prompt = f'Rate 0-10 for correctness/completeness. User: {user_prompt}\nAnswer: {answer}'
        raw = query_ollama_once(prompt)
        # attempt find float in reply
        for token in raw.replace(",", ".").split():
            try:
                val = float(token)
                if 0 <= val <= 10:
                    return val
            except Exception:
                continue
        # fallback parse digits
        digits = ''.join(ch for ch in raw if ch.isdigit() or ch == ".")
        if digits:
            try:
                v = float(digits)
                return max(0.0, min(10.0, v))
            except Exception:
                pass
    except Exception:
        pass
    return 5.0

# ----------------- Reflective loop (main) -----------------
def reflective_thinking_loop(user_prompt: str, max_loops: int = 5, echo_stream: bool = True) -> Generator[str, None, None]:
    """
    Yields streaming chunks: info lines and model chunks.
    Saves only concise memory records (answer_snip + reasoning_snip).
    """
    recent_memory = load_memory(limit=50)
    mem_summary = summarize_memory(recent_memory, max_items=6)
    profile = load_profile()
    # Print a small preamble for debugging and client display
    yield f"[INFO] Reflective engine online. Max loops = {max_loops}\n"
    if profile:
        yield f"[INFO] User profile: {json.dumps(profile)}\n"
    if mem_summary:
        yield f"[INFO] Memory summary:\n{mem_summary}\n"

    # Decide loops
    loops = max(1, min(estimate_loops(user_prompt, max_loops), max_loops, MAX_HARD_LOOPS))

    init_prompt = (
        "You are a helpful assistant. Answer the user's request concisely and directly. "
        "If you consider the answer complete, append the convergence token "
        f"{CONVERGENCE_TOKEN} at the end of your final answer. Do NOT treat yourself only as a 'reviewer'.\n\n"
        f"User prompt: {user_prompt}\n\nRelevant memory:\n{mem_summary}\n"
    )

    current_answer_parts: List[str] = []
    for chunk in query_ollama_stream(init_prompt):
        current_answer_parts.append(chunk)
        if echo_stream:
            yield chunk
    current_answer = "".join(current_answer_parts)

    answers = [current_answer]
    scores = []

    for i in range(1, loops + 1):
        yield f"\n[INFO] Reflection loop {i}/{loops}\n"
        score = score_answer(user_prompt, current_answer)
        scores.append(score)
        yield f"[SCORE] iteration {i} score = {score}\n"

        try:
            reasoning_prompt = f"Summarize in one short sentence the key reasoning steps that supported your previous answer:\n{current_answer}"
            reasoning = _truncate(query_ollama_once(reasoning_prompt), MAX_REASONING_SNIPPET)
        except Exception:
            reasoning = ""

        save_memory_record({
            "ts": _now_ts(),
            "prompt": user_prompt,
            "answer": _truncate(current_answer, MAX_ANSWER_SNIPPET),
            "reasoning": reasoning,
            "score": score
        })

        if CONVERGENCE_TOKEN in current_answer:
            current_answer = current_answer.replace(CONVERGENCE_TOKEN, "").strip()
            yield "[INFO] Convergence token detected; stopping.\n"
            break
        if len(answers) >= REPEAT_COUNT_TO_STOP:
            last_n = answers[-REPEAT_COUNT_TO_STOP:]
            if all(is_similar(last_n[j], last_n[-1]) >= REPEAT_SIMILARITY_THRESHOLD for j in range(len(last_n)-1)):
                yield "[INFO] Recent answers repeated; stopping.\n"
                break
        if len(scores) >= 2 and (scores[-1] - scores[-2]) < MIN_SCORE_IMPROVEMENT and scores[-1] > 8.0:
            yield "[INFO] Score stabilized; stopping.\n"
            break

        review_prompt = (
            "Review the current answer for correctness, completeness, and clarity. "
            "List 1-3 concrete improvements. Do not answer the user directly.\n\n"
            f"User prompt: {user_prompt}\n\nCurrent answer:\n{current_answer}"
        )
        review_text = "".join(query_ollama_stream(review_prompt))
        if echo_stream:
            yield "\n[REVIEW]\n"
            yield review_text
            yield "\n"

        improve_prompt = (
            "Rewrite the answer using the review. Return only the improved user-facing answer. "
            f"Append {CONVERGENCE_TOKEN} on its own line if the answer is complete.\n\n"
            f"User prompt: {user_prompt}\n\nCurrent answer:\n{current_answer}\n\nReview:\n{review_text}"
        )
        improved_parts: List[str] = []
        for chunk in query_ollama_stream(improve_prompt):
            improved_parts.append(chunk)
            if echo_stream:
                yield chunk
        improved = "".join(improved_parts).strip()
        if improved:
            current_answer = improved
            answers.append(current_answer)

    final_answer = current_answer.replace(CONVERGENCE_TOKEN, "").strip()
    if final_answer:
        yield "\n[FINAL]\n"
        yield final_answer
        yield "\n"


# wrapper used by server.py
def run_reflective_cycle(prompt: str, max_loops: int = 5) -> Generator[str, None, None]:
    yield from reflective_thinking_loop(prompt, max_loops=max_loops, echo_stream=True)

# ----------------- CLI for local testing -----------------
def main():
    print("Ghost reflective engine CLI (compact memory)")
    profile = load_profile()
    if not profile:
        print("No profile found. You can set basic preferences with update_profile(key, value).")
    try:
        while True:
            p = input("\nUser prompt (or 'quit'): ")
            if not p or p.strip().lower() in ("quit", "q", "exit"):
                break
            loops = input("max loops (Enter=2): ")
            try:
                loops_n = int(loops) if loops.strip() else 2
            except:
                loops_n = 2
            for chunk in run_reflective_cycle(p, max_loops=loops_n):
                print(chunk, end="", flush=True)
            print("\n--- done ---")
    except KeyboardInterrupt:
        print("\nInterrupted.")

if __name__ == "__main__":
    main()
