import React, { useState, useEffect, useRef } from "react";

/*
Ghost Web UI — v2 (single-file React component)
- Dark Tailwind vibe (assumes Tailwind CSS is loaded)
- Full interactive terminal (SSH-like) with command history
- Animated streaming logs (typing effect)
- Start/Stop Ollama reflective engine streaming (/api/run)
- SSH-like command sender (/api/ssh)
- Root-mode panel with system stats and control buttons

Required backend endpoints (examples):
- POST /api/run  -> starts reflective engine stream (proxy to Ollama). Accepts JSON: { prompt, model, max_loops, ollama_url }
  -> respond with a streaming body (chunked text or newline-delimited JSON). Frontend reads and animates chunks.
- POST /api/ssh  -> runs a single command; respond with streaming output for a shell-like session
- GET  /api/system -> returns JSON system stats {cpu, ram, uptime}
- POST /api/restart -> optional: restart backend
- POST /api/killstream -> optional: kill running stream

This file is intentionally self-contained: drop into a Vite React app's src/ and import in App.jsx.
*/


export default function GhostWebUI() {
  // Core config
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState("gemma3:4b");
  const [maxLoops, setMaxLoops] = useState(5);
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434/api/generate");

  // streaming state
  const [isStreaming, setIsStreaming] = useState(false);
  const streamController = useRef(null);

  // terminal state
  const [messages, setMessages] = useState([]); // {id, role: 'user'|'in'|'out'|'info', text}
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const terminalRef = useRef(null);

  // ssh / command history
  const [cmdInput, setCmdInput] = useState("");
  const [history, setHistory] = useState([]);
  const histIndexRef = useRef(-1);

  // snapshot & memory
  const [lastAnswer, setLastAnswer] = useState("");
  const [memoryPreview, setMemoryPreview] = useState("");

  // system stats
  const [sys, setSys] = useState({ cpu: 0, ram: 0, uptime: 0 });
  const [isRoot, setIsRoot] = useState(true); // single-user mode as requested

  // helper to append message
  function pushMessage(msg) {
    setMessages((m) => [...m, { id: Date.now() + Math.random(), ...msg }]);
  }

  // autoscroll when messages change
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [messages]);

  // poll system stats
  useEffect(() => {
    let mounted = true;
    async function poll() {
      try {
        const r = await fetch("/api/system");
        if (!r.ok) return;
        const j = await r.json();
        if (mounted) setSys(j);
      } catch (e) {
        // ignore
      }
    }
    poll();
    const t = setInterval(poll, 2000);
    return () => {
      mounted = false;
      clearInterval(t);
    };
  }, []);

  // typing animation helper: append chunk with small typing effect
  async function animateAppend(text, role = "in", speed = 6) {
    // speed characters per 16ms tick (~60fps)
    const chunkSize = Math.max(1, Math.floor(speed / 2));
    let buffer = "";
    for (let i = 0; i < text.length; i += chunkSize) {
      buffer += text.slice(i, i + chunkSize);
      // replace last 'in' message or create a new one
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === role && last.temp) {
          // update temp
          const copy = prev.slice(0, prev.length - 1);
          copy.push({ ...last, text: last.text + text.slice(i, i + chunkSize) });
          return copy;
        }
        // push a new temp message
        return [...prev, { id: Date.now() + Math.random(), role, text: text.slice(0, i + chunkSize), temp: true }];
      });
      await new Promise((r) => setTimeout(r, Math.max(8, 16)));
    }
    // finalize last message (remove temp flag)
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.role === role) {
        const copy = prev.slice(0, prev.length - 1);
        copy.push({ ...last, text: last.text, temp: false });
        return copy;
      }
      return prev;
    });
  }

  // read streaming response and animate into terminal
  async function streamResponseToTerminal(resp, role = "in") {
    function sanitizeChunk(text) {
      // remove bogus control chars (except newline/tab)
      return text.replace(/[^\t\n\r\u0020-\uFFFF]/g, '?');
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let done = false;
    let full = "";
    while (!done) {
      const { value, done: d } = await reader.read();
      done = d;
      if (value) {
        const chunkRaw = decoder.decode(value);
        const chunk = sanitizeChunk(chunkRaw);
        full += chunk;
        animateAppend(chunk, role);
      }
    }
    return full;
  }

// Start Reflective Engine streaming (patched for local backend)
async function startStream() {
  if (!prompt.trim()) {
    pushMessage({ role: "info", text: "[ERROR] Prompt is empty" });
    return;
  }

  setMessages([]);
  setIsStreaming(true);
  streamController.current = new AbortController();

  // simplified header
  pushMessage({ role: "info", text: `[INFO] Reflective engine online: model=${model}, loops=${maxLoops}` });

  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        max_loops: maxLoops,
      }),
      signal: streamController.current.signal,
    });

    if (!res.ok) {
      const txt = await res.text();
      pushMessage({ role: "info", text: `[ERROR] backend returned ${res.status}: ${txt}` });
      setIsStreaming(false);
      return;
    }

    // stream body and animate
    const full = await streamResponseToTerminal(res, "in");
    setLastAnswer(full);
    pushMessage({ role: "info", text: "[INFO] Reflective cycle complete" });
  } catch (err) {
    if (err.name === "AbortError") pushMessage({ role: "info", text: "[INFO] Stream aborted by user" });
    else pushMessage({ role: "info", text: `[ERROR] ${String(err)}` });
  } finally {
    setIsStreaming(false);
    streamController.current = null;
  }
}


  function stopStream() {
    if (streamController.current) streamController.current.abort();
    setIsStreaming(false);
    pushMessage({ role: "info", text: "[INFO] Stop requested" });
  }

  // SSH-like command send
  async function sendCommand(cmd) {
    if (!cmd.trim()) return;
    pushMessage({ role: "user", text: `> ${cmd}` });
    setHistory((h) => [...h, cmd]);
    histIndexRef.current = -1;
    setCmdInput("");

    try {
      const res = await fetch("/api/ssh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: cmd }),
      });
      if (!res.ok) {
        const txt = await res.text();
        pushMessage({ role: "out", text: `[ERROR] ssh backend returned ${res.status}: ${txt}` });
        return;
      }
      // stream output
      const output = await streamResponseToTerminal(res, "out");
      // optionally save output to lastAnswer
      setLastAnswer((s) => s + "\n" + output);
    } catch (e) {
      pushMessage({ role: "out", text: `[ERROR] ${String(e)}` });
    }
  }

  // CLI handlers
  function handleCmdKey(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      sendCommand(cmdInput);
    } else if (e.key === "ArrowUp") {
      // history nav
      e.preventDefault();
      if (history.length === 0) return;
      if (histIndexRef.current === -1) histIndexRef.current = history.length - 1;
      else histIndexRef.current = Math.max(0, histIndexRef.current - 1);
      setCmdInput(history[histIndexRef.current]);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (history.length === 0) return;
      if (histIndexRef.current === -1) return;
      histIndexRef.current = Math.min(history.length - 1, histIndexRef.current + 1);
      if (histIndexRef.current === history.length - 1) setCmdInput("");
      else setCmdInput(history[histIndexRef.current]);
    }
  }

  // snapshot download
  function downloadSnapshot() {
    const snap = { ts: new Date().toISOString(), prompt, model, maxLoops, ollamaUrl, lastAnswer };
    const blob = new Blob([JSON.stringify(snap, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "ghost_snapshot.json";
    a.click();
    URL.revokeObjectURL(url);
    pushMessage({ role: "info", text: "[INFO] Snapshot downloaded" });
  }

  // upload memory preview
  function uploadSnapshot(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const obj = JSON.parse(reader.result);
        setPrompt(obj.prompt || "");
        setModel(obj.model || model);
        setMaxLoops(obj.maxLoops || obj.max_loops || maxLoops);
        setOllamaUrl(obj.ollamaUrl || obj.ollama_url || ollamaUrl);
        setLastAnswer(obj.lastAnswer || "");
        pushMessage({ role: "info", text: "[INFO] Snapshot loaded" });
      } catch (e) {
        pushMessage({ role: "info", text: "[ERROR] Invalid JSON snapshot" });
      }
    };
    reader.readAsText(f);
  }

  // root actions
  async function restartBackend() {
    try {
      const r = await fetch("/api/restart", { method: "POST" });
      pushMessage({ role: "info", text: `[INFO] restart -> ${r.status}` });
    } catch (e) {
      pushMessage({ role: "info", text: `[ERROR] ${String(e)}` });
    }
  }

  async function killStream() {
    try {
      const r = await fetch("/api/killstream", { method: "POST" });
      pushMessage({ role: "info", text: `[INFO] killstream -> ${r.status}` });
    } catch (e) {
      pushMessage({ role: "info", text: `[ERROR] ${String(e)}` });
    }
  }

  // little helpers for rendering
  function renderMessage(m) {
    if (m.role === "info") return <div className="text-slate-400 text-sm">{m.text}</div>;
    if (m.role === "user") return <div className="text-emerald-300 font-mono">{m.text}</div>;
    if (m.role === "out") return <div className="text-yellow-300 font-mono whitespace-pre-wrap">{m.text}</div>;
    // incoming model text
    return <div className="text-green-300 font-mono whitespace-pre-wrap">{m.text}</div>;
  }

  return (
    <div className="min-h-screen p-6 bg-slate-900 text-slate-100">
      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="p-4 bg-slate-800 rounded-2xl shadow">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-semibold">Ghost — Reflective Engine UI</h1>
                <p className="text-sm text-slate-400 mt-1">Editable controls + streaming terminal — SSH-like experience.</p>
              </div>
              <div className="text-right text-xs text-slate-400">
                <div>Model: <span className="font-medium">{model}</span></div>
                <div>Streaming: {isStreaming ? <span className="text-emerald-400">● live</span> : <span className="text-slate-500">offline</span>}</div>

              </div>
            </div>

            <div className="mt-4 grid grid-cols-1 lg:grid-cols-6 gap-3">
              <input className="col-span-4 bg-slate-700 border border-slate-600 rounded px-3 py-2 text-slate-100" value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} />
              <input className="col-span-2 bg-slate-700 border border-slate-600 rounded px-2 py-2 text-slate-100" value={model} onChange={(e) => setModel(e.target.value)} />
              <textarea rows={6} className="col-span-6 mt-3 w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-slate-100 font-mono" placeholder="Write your prompt here..." value={prompt} onChange={(e) => setPrompt(e.target.value)} />

              <div className="col-span-6 flex items-center gap-3 mt-3">
                <input type="number" min={1} className="w-20 bg-slate-700 border border-slate-600 rounded px-2 py-2 text-slate-100" value={maxLoops} onChange={(e) => setMaxLoops(parseInt(e.target.value || "1"))} />
                <button disabled={isStreaming} onClick={startStream} className="px-4 py-2 rounded bg-emerald-500 text-black font-semibold">Start</button>
                <button disabled={!isStreaming} onClick={stopStream} className="px-4 py-2 rounded bg-rose-500 text-black font-semibold">Stop</button>
                <button onClick={downloadSnapshot} className="px-3 py-1 rounded bg-indigo-600">Download</button>
                <label className="px-3 py-1 rounded bg-slate-600 cursor-pointer"> <input type="file" className="hidden" onChange={uploadSnapshot} /> Upload</label>

                <div className="ml-auto text-xs text-slate-400">Last answer length: {lastAnswer.length}</div>
              </div>

            </div>
          </div>

          <div className="p-4 bg-slate-800 rounded-2xl shadow">
            <h2 className="font-medium">Live Terminal / SSH</h2>
            <div ref={terminalRef} className="mt-3 h-80 overflow-auto bg-black rounded p-3 font-mono text-sm text-green-300 border border-slate-700">
              {messages.length === 0 ? (
                <div className="text-slate-500">(terminal idle — start a stream or run commands)</div>
              ) : (
                messages.map((m) => (
                  <div key={m.id} className="mb-1">{renderMessage(m)}</div>
                ))
              )}
            </div>

            <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); sendCommand(cmdInput); }}>
              <input value={cmdInput} onChange={(e) => setCmdInput(e.target.value)} onKeyDown={handleCmdKey} className="flex-1 bg-slate-700 rounded px-3 py-2 text-slate-100 font-mono" placeholder="Type a command (Enter to send). Up/Down for history" />
              <button type="submit" className="px-3 py-2 rounded bg-slate-600">Send</button>
            </form>

            <div className="mt-2 text-xs text-slate-500">Tip: Commands are sent to <code className="bg-slate-700 px-1 rounded">POST /api/ssh</code> on your backend.</div>
          </div>

        </div>

        <aside className="space-y-4">
          <div className="p-4 bg-slate-800 rounded-2xl shadow">
            <h3 className="font-medium">Quick Preview</h3>
            <div className="mt-2 text-xs text-slate-300">Last answer preview (editable):</div>
            <textarea rows={8} className="mt-2 w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-slate-100 font-mono" value={lastAnswer} onChange={(e) => setLastAnswer(e.target.value)} />
            <div className="flex gap-2 mt-3">
              <button onClick={() => { navigator.clipboard?.writeText(lastAnswer); pushMessage({ role: "info", text: "[INFO] lastAnswer copied to clipboard" }); }} className="px-2 py-1 rounded bg-slate-600">Copy</button>
              <button onClick={() => { downloadSnapshot(); pushMessage({ role: "info", text: "[INFO] Saved preview to memory via download" }); }} className="px-2 py-1 rounded bg-indigo-600">Save</button>
            </div>
          </div>

          <div className="p-4 bg-slate-800 rounded-2xl shadow">
            <h3 className="font-medium">Memory</h3>
            <div className="mt-2 text-xs text-slate-300">Quick snapshot (not a full DB viewer)</div>
            <textarea rows={6} className="mt-2 w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-slate-100 font-mono" value={memoryPreview} onChange={(e) => setMemoryPreview(e.target.value)} />
            <div className="flex gap-2 mt-3">
              <button onClick={() => { pushMessage({ role: "info", text: "[INFO] memory preview saved locally" }); const b = new Blob([memoryPreview || "{}"], { type: "application/json" }); const u = URL.createObjectURL(b); const a = document.createElement("a"); a.href = u; a.download = "ghost_memory_preview.json"; a.click(); URL.revokeObjectURL(u); }} className="px-2 py-1 rounded bg-indigo-600">Export</button>
            </div>
          </div>

          <div className="p-4 bg-slate-800 rounded-2xl shadow text-xs text-slate-400">
            <div className="font-medium">Root Panel</div>
            <div className="mt-2 text-xs text-slate-300">System</div>
            <div className="mt-1 text-sm text-slate-200">CPU: {sys.cpu}%</div>
            <div className="text-sm text-slate-200">RAM: {sys.ram}%</div>
            <div className="text-sm text-slate-200">Uptime: {Math.floor(sys.uptime)}s</div>

            <div className="flex gap-2 mt-3">
              <button onClick={restartBackend} className="px-2 py-1 rounded bg-amber-500 text-black">Restart</button>
              <button onClick={killStream} className="px-2 py-1 rounded bg-rose-500 text-black">Kill Stream</button>
            </div>

            <div className="mt-3 text-xs text-slate-400">Advanced options: open dev console for logs.</div>
          </div>

        </aside>
      </div>

      <footer className="max-w-7xl mx-auto mt-6 text-slate-500 text-sm">Ghost UI v2 — Streaming terminal, SSH-like commands, snapshots. Built for experimentation.</footer>
    </div>
  );
}
