/* Zxyphorz AI — Diagnostics & Self-Test (no frameworks)
 *
 * Goals:
 * - Do NOT interfere with the main app.
 * - Only use existing endpoints:
 *     GET  /api/health
 *     POST /api/chat
 *     GET  /api/kb/search
 *     WS   /ws
 * - Provide a useful report and clear guidance.
 *
 * Open:
 *   http://127.0.0.1:8000/static/diagnostics.html
 */

(function () {
  "use strict";

  // ----------------------------
  // Small utilities (safe, tiny)
  // ----------------------------

  const $ = (sel) => document.querySelector(sel);

  function clamp(n, a, b) {
    return Math.max(a, Math.min(b, n));
  }

  function nowMs() {
    return performance.now();
  }

  function isoTime() {
    return new Date().toISOString();
  }

  function safeJsonParse(text) {
    try { return JSON.parse(text); } catch { return null; }
  }

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function bytesToHuman(n) {
    const units = ["B", "KB", "MB", "GB"];
    let v = n;
    let u = 0;
    while (v >= 1024 && u < units.length - 1) {
      v /= 1024;
      u += 1;
    }
    return `${v.toFixed(2)} ${units[u]}`;
  }

  function makeDownload(filename, text, mime = "application/json") {
    const blob = new Blob([text], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function withTimeout(promise, ms, label = "timeout") {
    let timer = null;
    const t = new Promise((_, rej) => {
      timer = setTimeout(() => rej(new Error(label)), ms);
    });
    return Promise.race([promise, t]).finally(() => {
      if (timer) clearTimeout(timer);
    });
  }

  // ---------------------------------
  // Logger (ring buffer + UI binding)
  // ---------------------------------

  class Logger {
    constructor(limit = 500) {
      this.limit = limit;
      this.lines = [];
      this.onChange = null;
    }

    _push(level, msg) {
      const line = `[${isoTime()}] ${level.toUpperCase()}: ${msg}`;
      this.lines.push(line);
      if (this.lines.length > this.limit) {
        this.lines.splice(0, this.lines.length - this.limit);
      }
      if (typeof this.onChange === "function") this.onChange(this.lines);
    }

    info(msg) { this._push("info", msg); }
    warn(msg) { this._push("warn", msg); }
    error(msg) { this._push("error", msg); }

    clear() {
      this.lines = [];
      if (typeof this.onChange === "function") this.onChange(this.lines);
    }
  }

  const log = new Logger(900);

  // ----------------------------
  // Local settings snapshot
  // ----------------------------

  const LS = {
    sessionId: "zxy.sessionId",
    language: "zxy.language",
    mode: "zxy.mode"
  };

  function getLocalState() {
    return {
      sessionId: localStorage.getItem(LS.sessionId) || null,
      language: localStorage.getItem(LS.language) || "en",
      mode: localStorage.getItem(LS.mode) || "basic"
    };
  }

  function setLocalSession(id) {
    if (id) localStorage.setItem(LS.sessionId, id);
    else localStorage.removeItem(LS.sessionId);
  }

  // ----------------------------
  // HTTP client wrappers
  // ----------------------------

  async function httpGetJson(url, timeoutMs = 8000) {
    const t0 = nowMs();
    const res = await withTimeout(fetch(url, { method: "GET" }), timeoutMs, "GET timeout");
    const txt = await res.text();
    const data = safeJsonParse(txt);
    const dt = nowMs() - t0;
    return { ok: res.ok, status: res.status, data, text: txt, ms: dt };
  }

  async function httpPostJson(url, body, timeoutMs = 12000) {
    const t0 = nowMs();
    const res = await withTimeout(fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }), timeoutMs, "POST timeout");
    const txt = await res.text();
    const data = safeJsonParse(txt);
    const dt = nowMs() - t0;
    return { ok: res.ok, status: res.status, data, text: txt, ms: dt };
  }

  // ----------------------------
  // WebSocket streaming check
  // ----------------------------

  function wsUrl() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${location.host}/ws`;
  }

  async function runWsCheck(payload, timeoutMs = 15000) {
    return new Promise((resolve, reject) => {
      const url = wsUrl();
      const ws = new WebSocket(url);

      let startedAt = nowMs();
      let firstDeltaAt = null;
      let lastDeltaAt = null;

      let gotStart = false;
      let gotEnd = false;

      let sessionId = null;
      let deltas = [];
      let startMeta = null;

      const timer = setTimeout(() => {
        try { ws.close(); } catch {}
        reject(new Error("WebSocket timeout"));
      }, timeoutMs);

      ws.addEventListener("open", () => {
        startedAt = nowMs();
        ws.send(JSON.stringify(payload));
      });

      ws.addEventListener("message", (evt) => {
        const msg = safeJsonParse(evt.data);
        if (!msg) return;

        if (msg.type === "start") {
          gotStart = true;
          sessionId = msg.session_id || null;
          startMeta = msg.meta || null;
          return;
        }

        if (msg.type === "delta") {
          if (!firstDeltaAt) firstDeltaAt = nowMs();
          lastDeltaAt = nowMs();
          if (typeof msg.text === "string") deltas.push(msg.text);
          return;
        }

        if (msg.type === "end") {
          gotEnd = true;
          clearTimeout(timer);
          try { ws.close(); } catch {}
          const full = deltas.join("");
          const totalMs = nowMs() - startedAt;
          const ttfbMs = firstDeltaAt ? (firstDeltaAt - startedAt) : null;

          resolve({
            ok: true,
            gotStart,
            gotEnd,
            sessionId,
            meta: startMeta,
            ttfbMs,
            totalMs,
            chars: full.length,
            textPreview: full.slice(0, 220),
            rawText: full
          });
        }

        if (msg.type === "error") {
          clearTimeout(timer);
          try { ws.close(); } catch {}
          reject(new Error(msg.message || "WebSocket error"));
        }
      });

      ws.addEventListener("error", () => {
        clearTimeout(timer);
        reject(new Error("WebSocket connection error"));
      });

      ws.addEventListener("close", () => {
        // If it closes without end, reject unless already resolved
        if (!gotEnd) {
          clearTimeout(timer);
          if (!gotStart) reject(new Error("WebSocket closed before start"));
          else reject(new Error("WebSocket closed before end"));
        }
      });
    });
  }

  // ----------------------------
  // Check runner + UI model
  // ----------------------------

  const ui = {
    pillEnv: $("#pillEnv"),
    pillOverall: $("#pillOverall"),
    pillTime: $("#pillTime"),
    pillLog: $("#pillLog"),
    checksList: $("#checksList"),
    logBox: $("#logBox"),
    vServer: $("#vServer"),
    vBrowser: $("#vBrowser"),
    vSession: $("#vSession"),
    vMode: $("#vMode"),
    vLang: $("#vLang"),
    vSLM: $("#vSLM"),
    btnRunAll: $("#btnRunAll"),
    btnRunHealth: $("#btnRunHealth"),
    btnRunChat: $("#btnRunChat"),
    btnRunKB: $("#btnRunKB"),
    btnRunWS: $("#btnRunWS"),
    btnExport: $("#btnExport"),
    btnClear: $("#btnClear"),
  };

  function setPill(el, text, state = "idle") {
    if (!el) return;
    el.textContent = text;
    el.classList.remove("ok", "warn", "bad");
    if (state === "ok") el.classList.add("ok");
    if (state === "warn") el.classList.add("warn");
    if (state === "bad") el.classList.add("bad");
  }

  function renderLog(lines) {
    if (!ui.logBox) return;
    ui.logBox.textContent = lines.join("\n");
    if (ui.pillLog) ui.pillLog.textContent = `${lines.length} lines`;
    ui.logBox.scrollTop = ui.logBox.scrollHeight;
  }

  log.onChange = renderLog;

  function envSnapshot() {
    const st = getLocalState();
    return {
      time: isoTime(),
      origin: location.origin,
      ws: wsUrl(),
      userAgent: navigator.userAgent,
      local: st
    };
  }

  function refreshSnapshotUI(healthData = null) {
    const st = getLocalState();
    if (ui.vServer) ui.vServer.textContent = location.origin;
    if (ui.vBrowser) ui.vBrowser.textContent = navigator.userAgent;
    if (ui.vSession) ui.vSession.textContent = st.sessionId || "—";
    if (ui.vMode) ui.vMode.textContent = st.mode || "basic";
    if (ui.vLang) ui.vLang.textContent = st.language || "en";

    if (healthData && healthData.slm) {
      const slm = healthData.slm;
      if (ui.vSLM) {
        ui.vSLM.textContent = slm.available
          ? `READY: ${slm.display_name || "Local SLM"}`
          : `NOT READY: ${slm.reason || "unknown"}`;
      }
    } else {
      if (ui.vSLM) ui.vSLM.textContent = "—";
    }
  }

  // A check definition:
  // { id, name, desc, run: async () => {ok, summary, details, ...} }
  const checks = [];

  function addCheck(def) {
    checks.push(def);
  }

  function renderChecks(stateMap) {
    if (!ui.checksList) return;
    ui.checksList.innerHTML = "";

    for (const c of checks) {
      const state = stateMap[c.id] || { status: "idle", meta: "", desc: c.desc };
      const li = document.createElement("li");
      li.className = "item";

      const top = document.createElement("div");
      top.className = "item-top";

      const name = document.createElement("div");
      name.className = "item-name";
      name.textContent = c.name;

      const meta = document.createElement("div");
      meta.className = "item-meta";
      meta.textContent = state.meta || state.status;

      top.appendChild(name);
      top.appendChild(meta);

      const desc = document.createElement("div");
      desc.className = "item-desc";
      desc.textContent = state.desc || c.desc || "";

      li.appendChild(top);
      li.appendChild(desc);

      ui.checksList.appendChild(li);
    }
  }

  function summarizeOverall(stateMap) {
    const ids = checks.map((c) => c.id);
    let okCount = 0, badCount = 0, runCount = 0;

    for (const id of ids) {
      const st = stateMap[id];
      if (!st) continue;
      if (st.status === "ok" || st.status === "warn" || st.status === "bad") runCount++;
      if (st.status === "ok") okCount++;
      if (st.status === "bad") badCount++;
    }

    if (runCount === 0) return { text: "idle", state: "warn" };
    if (badCount > 0) return { text: `issues (${badCount} failed)`, state: "bad" };
    if (okCount === ids.length) return { text: "all good", state: "ok" };
    return { text: `partial (${okCount}/${ids.length})`, state: "warn" };
  }

  // ----------------------------
  // Define checks (only existing endpoints)
  // ----------------------------

  addCheck({
    id: "health",
    name: "Health endpoint",
    desc: "Verifies /api/health responds and shows SLM readiness (if configured).",
    run: async () => {
      const r = await httpGetJson("/api/health", 8000);
      if (!r.ok || !r.data) {
        return { ok: false, status: "bad", meta: `HTTP ${r.status}`, details: r };
      }
      const slm = r.data.slm || {};
      const slmText = slm.available ? `SLM ready: ${slm.display_name || "Local"}` : `SLM: ${slm.reason || "not ready"}`;
      return {
        ok: true,
        status: slm.available ? "ok" : "warn",
        meta: `${Math.round(r.ms)}ms • ${slmText}`,
        details: r.data
      };
    }
  });

  addCheck({
    id: "kb_search",
    name: "KB search",
    desc: "Verifies /api/kb/search returns hits for a known query (BM25/RAG).",
    run: async () => {
      const q = "BM25";
      const r = await httpGetJson(`/api/kb/search?q=${encodeURIComponent(q)}&k=3&language=en`, 10000);
      if (!r.ok || !r.data) return { ok: false, status: "bad", meta: `HTTP ${r.status}`, details: r };

      const hits = Array.isArray(r.data.hits) ? r.data.hits : [];
      if (hits.length === 0) {
        return { ok: false, status: "bad", meta: "0 hits", details: r.data };
      }
      const top = hits[0];
      const title = top.title || "(no title)";
      const score = (typeof top.score === "number") ? top.score.toFixed(3) : String(top.score);
      return {
        ok: true,
        status: "ok",
        meta: `${Math.round(r.ms)}ms • top=${title} • score=${score}`,
        details: { top }
      };
    }
  });

  addCheck({
    id: "chat_basic",
    name: "Chat (Basic)",
    desc: "POST /api/chat in Basic mode. Confirms session creation and reply shape.",
    run: async () => {
      const body = { message: "hello", session_id: null, language: "en", mode: "basic" };
      const r = await httpPostJson("/api/chat", body, 12000);

      if (!r.ok || !r.data) return { ok: false, status: "bad", meta: `HTTP ${r.status}`, details: r };
      if (!r.data.session_id || !r.data.reply) {
        return { ok: false, status: "bad", meta: "invalid payload", details: r.data };
      }

      setLocalSession(r.data.session_id);

      const ms = r.data.meta && r.data.meta.ms ? `${r.data.meta.ms}ms` : `${Math.round(r.ms)}ms`;
      const preview = String(r.data.reply).slice(0, 60).replace(/\s+/g, " ");
      return { ok: true, status: "ok", meta: `${ms} • "${preview}…"`, details: r.data };
    }
  });

  addCheck({
    id: "chat_advanced",
    name: "Chat (Advanced)",
    desc: "POST /api/chat in Advanced mode. If SLM not ready, should still respond (fallback).",
    run: async () => {
      const st = getLocalState();
      const sid = st.sessionId || null;

      const body = { message: "Explain RAG in one paragraph.", session_id: sid, language: "en", mode: "advanced" };
      const r = await httpPostJson("/api/chat", body, 18000);

      if (!r.ok || !r.data) return { ok: false, status: "bad", meta: `HTTP ${r.status}`, details: r };
      if (!r.data.session_id || !r.data.reply) {
        return { ok: false, status: "bad", meta: "invalid payload", details: r.data };
      }

      setLocalSession(r.data.session_id);

      const meta = r.data.meta || {};
      const advanced = meta.mode === "advanced" || meta.mode === "advanced" || (meta.advanced_available === true);
      const availability = (meta.advanced_available === true) ? "SLM used" : "fallback";
      const ms = meta.ms ? `${meta.ms}ms` : `${Math.round(r.ms)}ms`;

      const preview = String(r.data.reply).slice(0, 60).replace(/\s+/g, " ");
      return {
        ok: true,
        status: advanced ? "ok" : "warn",
        meta: `${ms} • ${availability} • "${preview}…"`,
        details: { mode: meta.mode, advanced_available: meta.advanced_available, ms: meta.ms }
      };
    }
  });

  addCheck({
    id: "ws_stream",
    name: "WebSocket streaming",
    desc: "Connects to /ws and measures time-to-first-token and throughput.",
    run: async () => {
      const st = getLocalState();
      const sid = st.sessionId || null;

      const payload = {
        message: "Give 5 bullet tips for learning Python quickly.",
        session_id: sid,
        language: "en",
        mode: st.mode || "basic"
      };

      const r = await runWsCheck(payload, 20000);

      // Approx token count: chars/4 (very rough; enough for diagnostics)
      const approxTokens = Math.max(1, Math.round(r.chars / 4));
      const tps = r.totalMs > 0 ? (approxTokens / (r.totalMs / 1000)) : 0;

      if (r.sessionId) setLocalSession(r.sessionId);

      const ttfb = r.ttfbMs != null ? `${Math.round(r.ttfbMs)}ms` : "—";
      const total = `${Math.round(r.totalMs)}ms`;
      const meta = `TTFB ${ttfb} • total ${total} • ~${tps.toFixed(1)} tok/s`;

      return {
        ok: true,
        status: "ok",
        meta,
        details: {
          ttfbMs: r.ttfbMs,
          totalMs: r.totalMs,
          chars: r.chars,
          approxTokens,
          approxTokPerSec: tps,
          preview: r.textPreview
        }
      };
    }
  });

  // ----------------------------
  // State & report
  // ----------------------------

  const stateMap = {};
  let lastHealth = null;

  function setCheckState(id, status, meta, details, descOverride = null) {
    stateMap[id] = {
      status,
      meta: meta || status,
      details: details || null,
      desc: descOverride || (checks.find(c => c.id === id)?.desc || "")
    };
    renderChecks(stateMap);

    const overall = summarizeOverall(stateMap);
    setPill(ui.pillOverall, overall.text, overall.state);
  }

  function resetStates() {
    for (const c of checks) {
      stateMap[c.id] = { status: "idle", meta: "idle", details: null, desc: c.desc };
    }
    renderChecks(stateMap);
    setPill(ui.pillOverall, "idle", "warn");
  }

  function buildReport() {
    const snap = envSnapshot();
    const results = {};
    for (const id in stateMap) {
      results[id] = {
        status: stateMap[id].status,
        meta: stateMap[id].meta,
        details: stateMap[id].details || null
      };
    }
    return {
      generated_at: isoTime(),
      snapshot: snap,
      health_cache: lastHealth,
      results,
      log: log.lines.slice(),
    };
  }

  // ----------------------------
  // Runner
  // ----------------------------

  async function runOne(id) {
    const def = checks.find((c) => c.id === id);
    if (!def) return;

    setCheckState(id, "warn", "running…", null);
    log.info(`Running check: ${def.name}`);

    const t0 = nowMs();
    try {
      const out = await def.run();
      const dt = nowMs() - t0;

      if (out && out.ok) {
        const st = out.status || "ok";
        const meta = out.meta ? `${out.meta} • ${Math.round(dt)}ms` : `${Math.round(dt)}ms`;
        setCheckState(id, st, meta, out.details || null);
        log.info(`✓ ${def.name} -> ${st}`);
      } else {
        const meta = out && out.meta ? out.meta : "failed";
        setCheckState(id, "bad", meta, out && out.details ? out.details : null);
        log.error(`✗ ${def.name} -> ${meta}`);
      }

      // After health check, update sidebar snapshot
      if (id === "health") {
        const d = (stateMap[id] && stateMap[id].details) ? stateMap[id].details : null;
        lastHealth = d;
        refreshSnapshotUI(d);
      } else {
        refreshSnapshotUI(lastHealth);
      }

    } catch (e) {
      setCheckState(id, "bad", String(e), { error: String(e) });
      log.error(`✗ ${def.name} threw: ${String(e)}`);
      refreshSnapshotUI(lastHealth);
    }
  }

  async function runAll() {
    log.info("Running all checks…");
    setPill(ui.pillOverall, "running…", "warn");

    // Run in a safe order to avoid confusing failures:
    // 1) health, 2) kb, 3) basic chat, 4) advanced chat, 5) websocket
    const order = ["health", "kb_search", "chat_basic", "chat_advanced", "ws_stream"];

    for (const id of order) {
      await runOne(id);
      await sleep(250);
    }

    const overall = summarizeOverall(stateMap);
    setPill(ui.pillOverall, overall.text, overall.state);
    log.info(`All checks completed: ${overall.text}`);
  }

  // ----------------------------
  // Wire UI
  // ----------------------------

  function boot() {
    // Environment pill
    const env = `origin=${location.origin}`;
    setPill(ui.pillEnv, env, "ok");

    // Time pill updates
    setInterval(() => {
      setPill(ui.pillTime, new Date().toLocaleString(), "ok");
    }, 900);

    // Initial snapshot UI
    refreshSnapshotUI(null);
    if (ui.pillOverall) setPill(ui.pillOverall, "idle", "warn");

    // Render initial check list
    resetStates();

    // Log initialization
    log.info("Diagnostics page loaded.");
    log.info(`Server origin: ${location.origin}`);
    log.info(`WebSocket URL: ${wsUrl()}`);

    // Buttons
    if (ui.btnRunAll) ui.btnRunAll.addEventListener("click", () => runAll());
    if (ui.btnRunHealth) ui.btnRunHealth.addEventListener("click", () => runOne("health"));
    if (ui.btnRunKB) ui.btnRunKB.addEventListener("click", () => runOne("kb_search"));
    if (ui.btnRunChat) ui.btnRunChat.addEventListener("click", async () => {
      await runOne("chat_basic");
      await sleep(200);
      await runOne("chat_advanced");
    });
    if (ui.btnRunWS) ui.btnRunWS.addEventListener("click", () => runOne("ws_stream"));

    if (ui.btnClear) ui.btnClear.addEventListener("click", () => {
      log.clear();
      resetStates();
      lastHealth = null;
      refreshSnapshotUI(null);
      log.info("Cleared logs and reset states.");
    });

    if (ui.btnExport) ui.btnExport.addEventListener("click", () => {
      const report = buildReport();
      const name = `zxyphorz_diagnostics_${Date.now()}.json`;
      makeDownload(name, JSON.stringify(report, null, 2), "application/json");
      log.info(`Exported report: ${name}`);
    });

    // Auto-run a minimal smoke on load (health only, non-intrusive)
    // This helps users quickly see if the server is up.
    runOne("health").catch(() => {});
  }

  // Catch unhandled errors and report nicely
  window.addEventListener("error", (e) => {
    log.error(`Window error: ${e.message || e.type}`);
  });
  window.addEventListener("unhandledrejection", (e) => {
    log.error(`Unhandled rejection: ${String(e.reason || e)}`);
  });

  boot();

})();
