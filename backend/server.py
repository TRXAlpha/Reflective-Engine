from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
import time
import uuid

import psutil
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

import reflective_engine


HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

app = Flask(__name__, static_folder="../frontend/dist", static_url_path="/")
CORS(app)

CONFIG_PATH = os.path.join(PROJECT_ROOT, "ghost_config.json")
DEFAULT_CONFIG = {
    "name": "Ghost Core",
    "model": "gemma3:4b",
    "mode": "local",
    "maxLoops": 5,
    "ollamaUrl": "http://localhost:11434/api/generate",
}
config = dict(DEFAULT_CONFIG)


def load_config() -> None:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config.update(json.load(f))


def save_config() -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def apply_engine_config() -> None:
    reflective_engine.OLLAMA_URL = config.get("ollamaUrl", reflective_engine.OLLAMA_URL)
    reflective_engine.MODEL = config.get("model", reflective_engine.MODEL)
    reflective_engine.MEMORY_PATH = os.path.join(PROJECT_ROOT, "ghost_memory.jsonl")
    reflective_engine.PROFILE_PATH = os.path.join(PROJECT_ROOT, "ghost_profile.json")


def reload_engine():
    global reflective_engine
    reflective_engine = importlib.reload(reflective_engine)
    apply_engine_config()
    return reflective_engine


def extract_final_from_stream_text(text: str, convergence_token: str) -> str:
    if "[FINAL]" in text:
        final = text.rsplit("[FINAL]", 1)[1].strip()
        return final.replace(convergence_token, "").strip()

    useful = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("[INFO]", "[ERROR]", "[SCORE]", "[REVIEW]")):
            continue
        if re.fullmatch(r"\s*\w+:\d+(\.\d+)?\s*", line):
            continue
        useful.append(line)
    joined = "\n".join(useful).strip()
    if convergence_token in joined:
        return joined.rsplit(convergence_token, 1)[0].strip()
    return joined


def log_request() -> None:
    body = request.get_data(as_text=True)[:1000]
    print(f"[HTTP] {request.remote_addr} -> {request.method} {request.path} | body_preview: {body!r}")


@app.route("/api/generate", methods=["POST"])
def api_generate():
    payload = request.get_json(force=True)
    prompt = payload.get("prompt", "")
    max_loops = int(payload.get("max_loops") or config.get("maxLoops", 5))
    want_stream = bool(payload.get("stream") or payload.get("streaming") or payload.get("stream_response"))

    try:
        engine = reload_engine()
    except Exception as exc:
        return jsonify({"error": f"could not import reflective_engine: {exc}"}), 500

    gen = engine.run_reflective_cycle(prompt, max_loops=max_loops)

    if want_stream:
        return Response(gen, mimetype="text/plain; charset=utf-8")

    try:
        raw_text = "".join(gen)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    final = extract_final_from_stream_text(raw_text, engine.CONVERGENCE_TOKEN)
    final = final.replace(engine.CONVERGENCE_TOKEN, "").strip()
    return jsonify(
        {
            "id": str(uuid.uuid4()),
            "object": "generation",
            "created": int(time.time()),
            "model": engine.MODEL,
            "choices": [
                {
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": final,
                }
            ],
        }
    )


@app.route("/api/ssh", methods=["GET", "OPTIONS", "POST"])
def api_ssh():
    log_request()
    if request.method == "GET":
        cmd = request.args.get("cmd")
        if not cmd:
            return jsonify({"hint": "POST JSON {command:'...'} or GET ?cmd=..."}), 200
    else:
        payload = request.get_json(silent=True) or {}
        cmd = payload.get("command", "")

    if not cmd:
        return jsonify({"error": "no command provided"}), 400

    def generate():
        try:
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                yield "".join(ch if (32 <= ord(ch) <= 0x10FFFF) else "?" for ch in line)
            yield f"\n[EXIT CODE] {proc.wait()}\n"
        except Exception as exc:
            yield f"[ERROR] {exc}\n"

    return Response(generate(), mimetype="text/plain; charset=utf-8")


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "POST":
        config.update(request.json or {})
        save_config()
        apply_engine_config()
        return jsonify({"ok": True, "config": config})
    return jsonify(config)


@app.route("/api/system")
def api_system():
    return jsonify(
        {
            "cpu": psutil.cpu_percent(interval=0.5),
            "ram": psutil.virtual_memory().percent,
            "uptime": int(time.time() - psutil.boot_time()),
        }
    )


@app.route("/health")
def health():
    return jsonify({"ok": True, "msg": "ghost backend healthy", "port": 8181})


@app.route("/api/run", methods=["GET"])
def api_run_get():
    return jsonify(
        {
            "ok": True,
            "hint": "POST JSON { prompt, model, max_loops, ollama_url } to invoke the reflective engine.",
        }
    )


@app.route("/api/run", methods=["POST"])
def api_run():
    payload = request.get_json(force=True)
    prompt = payload.get("prompt", "")
    max_loops = int(payload.get("max_loops") or config.get("maxLoops") or 5)

    try:
        engine = reload_engine()
    except Exception as exc:
        return jsonify({"error": f"could not import reflective_engine: {exc}"}), 500

    def generate():
        yield f"[INFO] Reflective engine online (max_loops={max_loops}).\n"
        try:
            yield from engine.run_reflective_cycle(prompt, max_loops=max_loops)
            yield "\n[INFO] Reflective cycle complete.\n"
        except Exception as exc:
            yield f"[ERROR] Engine crashed: {exc}\n"

    return Response(generate(), mimetype="text/plain; charset=utf-8")


@app.route("/.debug-inspect", methods=["GET", "POST", "HEAD", "OPTIONS"])
def debug_inspect():
    raw = request.get_data()
    try:
        body = raw.decode("utf-8")
    except Exception:
        body = repr(raw)
    return jsonify(
        {
            "ok": True,
            "method": request.method,
            "path": request.path,
            "content_length": request.content_length,
            "content_type": request.content_type,
            "headers": dict(request.headers.items()),
            "body_preview": body[:2000],
        }
    )


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(app.static_folder, path)


try:
    load_config()
    apply_engine_config()
except Exception as exc:
    print("WARN: could not initialize reflective engine config:", exc)


if __name__ == "__main__":
    print(f"Starting Ghost backend on 0.0.0.0:8181 (project root: {PROJECT_ROOT})")
    app.run(host="0.0.0.0", port=8181, threaded=True)
