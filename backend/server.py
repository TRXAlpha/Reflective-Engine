from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
import psutil, time, threading, json, os, sys, importlib
from datetime import datetime
import reflective_engine

# ----------------- Setup -----------------
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

app = Flask(__name__, static_folder="../frontend/dist", static_url_path="/")
CORS(app)

CONFIG_PATH = os.path.join(PROJECT_ROOT, "ghost_config.json")
config = {
    "name": "Ghost Core",
    "model": "gemma3:4b",
    "mode": "local",
    "maxLoops": 5,
    "ollamaUrl": "http://localhost:11434/api/generate"
}


# add these imports near the top if not present
import uuid
import json
from flask import stream_with_context


# after importlib.reload(reflective_engine)
# make reflective_engine use server config values
try:
    # if your server config uses lower-case key 'ollamaUrl' like your snippet:
    reflective_engine.OLLAMA_URL = config.get("ollamaUrl", getattr(reflective_engine, "OLLAMA_URL", None))
    reflective_engine.MODEL = config.get("model", getattr(reflective_engine, "MODEL", None))
    # set memory/profile file paths to absolute paths inside project root so permissions are predictable
    reflective_engine.MEMORY_PATH = os.path.join(PROJECT_ROOT, "ghost_memory.jsonl")
    reflective_engine.PROFILE_PATH = os.path.join(PROJECT_ROOT, "ghost_profile.json")
except Exception as ex:
    print("WARN: couldn't apply server config to reflective_engine:", ex)



import re
from flask import Response

# helper to clean engine text and extract final answer
# The corrected line (use the direct name of the constant)
def extract_final_from_stream_text(text: str, convergence_token=reflective_engine.CONVERGENCE_TOKEN):
    # join lines, remove internal [INFO] or [ERROR] log lines
    lines = text.splitlines()
    useful = []
    for ln in lines:
        if ln.strip().startswith("[INFO]") or ln.strip().startswith("[ERROR]"):
            continue
        # drop lines that are purely engine debug like 'gemma3:4b' alone
        if re.fullmatch(r'\s*\w+:\d+(\.\d+)?\s*', ln):
            continue
        useful.append(ln)
    joined = "\n".join(useful).strip()
    # if convergence token present, take content before the last occurrence
    if convergence_token in joined:
        before = joined.rsplit(convergence_token, 1)[0].strip()
        return before
    # fallback: return the last paragraph-ish chunk
    return joined.strip()

@app.route("/api/generate", methods=["POST"])
def api_generate():
    payload = request.get_json(force=True)
    prompt = payload.get("prompt", "")
    max_loops = int(payload.get("max_loops") or config.get("maxLoops", 5))
    want_stream = bool(payload.get("stream") or payload.get("streaming") or payload.get("stream_response"))

    # reload engine
    try:
        import reflective_engine
        importlib.reload(reflective_engine)
        # apply server config if you want (paths/url)
        reflective_engine.OLLAMA_URL = config.get("ollamaUrl", reflective_engine.OLLAMA_URL)
        reflective_engine.MODEL = config.get("model", reflective_engine.MODEL)
        reflective_engine.MEMORY_PATH = os.path.join(PROJECT_ROOT, "ghost_memory.jsonl")
        reflective_engine.PROFILE_PATH = os.path.join(PROJECT_ROOT, "ghost_profile.json")
    except Exception as e:
        return jsonify({"error": f"could not import reflective_engine: {e}"}), 500

    gen = reflective_engine.run_reflective_cycle(prompt, max_loops=max_loops)

    if want_stream:
        # stream raw chunks back (for debugging or compatible streaming clients)
        def stream_gen():
            for chunk in gen:
                yield chunk
        return Response(stream_gen(), mimetype="text/plain; charset=utf-8")

    # default: collect everything then extract final answer (safe for Open-Notebook non-streaming)
    collected = []
    try:
        for chunk in gen:
            collected.append(chunk)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    big = "".join(collected)
    final = extract_final_from_stream_text(big, convergence_token=reflective_engine.CONVERGENCE_TOKEN)
    final = final.replace(reflective_engine.CONVERGENCE_TOKEN, "").strip()

    # Return Ollama-style response (Open-Notebook will be happy)
    resp = {
        "id": str(uuid.uuid4()),
        "object": "generation",
        "created": int(time.time()),
        "model": reflective_engine.MODEL,
        "choices": [
            {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "content": final
            }
        ]
    }
    return jsonify(resp)

# near top: add a tiny helper so we always log incoming requests
def log_request(req):
    try:
        body = req.get_data(as_text=True)[:1000]
    except Exception:
        body = "<couldn't read body>"
    print(f"[HTTP] {req.remote_addr} -> {req.method} {req.path} | body_preview: {body!r}")

# ----------------- SSH-like command runner (DEV ONLY) -----------------
# WARNING: this runs shell commands from the frontend. Do NOT expose publicly.
@app.route("/api/ssh", methods=["GET","OPTIONS","POST"])
def api_ssh():
    log_request(request)
    # GET fallback for quick debugging via browser / curl
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
            # run command with shell; stream stdout & stderr
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            # stream lines as they appear
            while True:
                line = proc.stdout.readline()
                if line == "" and proc.poll() is not None:
                    break
                if line:
                    # sanitize line to avoid weird control characters
                    safe = ''.join(ch if (32 <= ord(ch) <= 0x10FFFF) else '?' for ch in line)
                    yield safe
            yield f"\n[EXIT CODE] {proc.returncode}\n"
        except Exception as e:
            yield f"[ERROR] {str(e)}\n"

    return Response(generate(), mimetype="text/plain; charset=utf-8")





def save_config():
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

def load_config():
    global config
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config.update(json.load(f))

# ----------------- API -----------------
@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "POST":
        config.update(request.json or {})
        save_config()
        return jsonify({"ok": True, "config": config})
    return jsonify(config)

@app.route("/api/system")
def api_system():
    return jsonify({
        "cpu": psutil.cpu_percent(interval=0.5),
        "ram": psutil.virtual_memory().percent,
        "uptime": int(time.time() - psutil.boot_time())
    })


@app.route("/health")
def health():
    return jsonify({"ok": True, "msg": "ghost backend healthy", "port": 8181})

# optional: quick GET hint for /api/run (dev-only)
@app.route("/api/run", methods=["GET"])
def api_run_get():
    return jsonify({
       "ok": True,
       "hint": "This endpoint accepts POST only. POST JSON { prompt, model, max_loops, ollama_url } to invoke the reflective engine."
    })



# ----------------- Core reflective endpoint -----------------
@app.route("/api/run", methods=["POST"])
def api_run():
    payload = request.get_json(force=True)
    prompt = payload.get("prompt", "")
    max_loops = int(payload.get("max_loops") or config.get("maxLoops") or 5)

    try:
        import reflective_engine
        importlib.reload(reflective_engine)
    except Exception as e:
        return jsonify({"error": f"could not import reflective_engine: {e}"}), 500

    def generate():
        yield f"[INFO] Reflective engine online (max_loops={max_loops}).\n"
        try:
            for chunk in reflective_engine.run_reflective_cycle(prompt, max_loops=max_loops):
                yield chunk
            yield "\n[INFO] Reflective cycle complete.\n"
        except Exception as e:
            yield f"[ERROR] Engine crashed: {e}\n"

    return Response(generate(), mimetype="text/plain; charset=utf-8")

    def generate():
        try:
            # memory summary
            recent = reflective_engine.load_memory(limit=50)
            memory_summary = ''
            if recent:
                lines = []
                for r in recent[-10:]:
                    t = r.get('ts')
                    s = (r.get('answer') or '')[:120].replace('\n', ' ')
                    s += '...' if len(r.get('answer','')) > 120 else ''
                    lines.append(f"[{t}] {s}")
                memory_summary = '\n'.join(lines)

            loops = reflective_engine.estimate_loops(prompt, max_loops)
            loops = max(1, min(loops, max_loops, getattr(reflective_engine, "MAX_HARD_LOOPS", 200)))
            yield f"[INFO] Model decided on {loops} reflection loops.\n"

            yield "--- Initial Answer ---\n"
            init_prompt = f"{prompt}\n\nMemory summary:\n{memory_summary}\n"
            current_answer = ''
            for chunk in reflective_engine.query_ollama_stream(init_prompt):
                yield chunk
                current_answer += chunk

            answers = [current_answer]
            scores = []

            # Reflection loops
            for i in range(1, loops + 1):
                yield f"\n--- Reflection Loop {i} ---\n"

                score = reflective_engine.score_answer(prompt, current_answer)
                scores.append(score)
                yield f"[SCORE] iteration {i} score = {score}\n"

                # store memory
                try:
                    reflective_engine.save_memory_record({
                        'ts': datetime.utcnow().isoformat() + 'Z',
                        'loop': i,
                        'prompt': prompt,
                        'answer': current_answer,
                        'score': score
                    })
                except Exception:
                    pass

                # early stopping
                if reflective_engine.CONVERGENCE_TOKEN in current_answer:
                    yield f"[INFO] Convergence token detected; stopping.\n"
                    current_answer = current_answer.replace(reflective_engine.CONVERGENCE_TOKEN, '').strip()
                    break

                if len(answers) >= reflective_engin.REPEAT_COUNT_TO_STOP:
                    last_n = answers[-reflective_engin.REPEAT_COUNT_TO_STOP:]
                    ratios = [reflective_engine.is_similar(last_n[j], last_n[-1]) for j in range(len(last_n)-1)]
                    if all(r >= reflective_engine.REPEAT_SIMILARITY_THRESHOLD for r in ratios):
                        yield f"[INFO] Recent answers repeated; stopping.\n"
                        break

                # review and improve
                review_prompt = f"Review this reasoning attempt:\n{current_answer}\nUser prompt: {prompt}\nReply concisely; append {reflective_engine.CONVERGENCE_TOKEN} if converged."
                review_text = ''
                for chunk in reflective_engine.query_ollama_stream(review_prompt):
                    yield chunk
                    review_text += chunk

                final_iteration = (i == loops)
                if final_iteration:
                    improve_prompt = f"Produce FINAL polished answer based on review:\n{review_text}\nCurrent answer:\n{current_answer}\nAppend {reflective_engine.CONVERGENCE_TOKEN}"
                else:
                    improve_prompt = f"Improve answer based on review:\n{review_text}\nCurrent answer:\n{current_answer}\nAppend {reflective_engine.CONVERGENCE_TOKEN} if converged"

                new_answer = ''
                for chunk in reflective_engine.query_ollama_stream(improve_prompt):
                    yield chunk
                    new_answer += chunk

                if new_answer.strip().endswith(reflective_engine.CONVERGENCE_TOKEN):
                    new_answer = new_answer.replace(reflective_engine.CONVERGENCE_TOKEN, '').strip()
                    answers.append(new_answer)
                    current_answer = new_answer
                    try:
                        reflective_engine.save_memory_record({
                            'ts': datetime.utcnow().isoformat() + 'Z',
                            'loop': i,
                            'prompt': prompt,
                            'answer': current_answer,
                            'score': score,
                            'converged': True
                        })
                    except Exception:
                        pass
                    break

                answers.append(new_answer)
                current_answer = new_answer

            # finisher pass
            if reflective_engine.FINISH_SIGNAL not in current_answer and not current_answer.strip().startswith("**"):
                finisher_prompt = f"FINALIZE answer:\n{current_answer}\nAppend {reflective_engine.CONVERGENCE_TOKEN}"
                final_chunk = ''
                for chunk in reflective_engine.query_ollama_stream(finisher_prompt):
                    yield chunk
                    final_chunk += chunk
                current_answer = final_chunk.replace(reflective_engine.CONVERGENCE_TOKEN, '').strip()
                try:
                    reflective_engine.save_memory_record({
                        'ts': datetime.utcnow().isoformat() + 'Z',
                        'loop': 'finisher',
                        'prompt': prompt,
                        'answer': current_answer,
                        'finalized': True
                    })
                except Exception:
                    pass

            yield "\n[INFO] DONE. Final answer below:\n"
            yield current_answer

        except GeneratorExit:
            return
        except Exception as e:
            yield f"[ERROR] {e}\n"

    return Response(generate(), mimetype='text/plain; charset=utf-8')




# debugging helper — add near the top with other routes
@app.route("/.debug-inspect", methods=["GET","POST","HEAD","OPTIONS"])
def debug_inspect():
    try:
        raw = request.get_data()  # raw bytes
        try:
            text = raw.decode('utf-8')
        except Exception:
            text = repr(raw)
        return jsonify({
            "ok": True,
            "method": request.method,
            "path": request.path,
            "content_length": request.content_length,
            "content_type": request.content_type,
            "headers": {k: v for k, v in request.headers.items()},
            "body_preview": text[:2000]
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500





# ----------------- Static frontend -----------------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(app.static_folder, path)

# ----------------- Main -----------------
if __name__ == "__main__":
    load_config()
    print(f"Starting Ghost backend on 0.0.0.0:8181 (project root: {PROJECT_ROOT})")
    app.run(host="0.0.0.0", port=8181, threaded=True)
