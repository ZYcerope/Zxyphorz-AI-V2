/* Zxyphorz AI — minimal frontend (no frameworks) */

let sessionId = localStorage.getItem("zxy.sessionId") || null;
let language = localStorage.getItem("zxy.language") || "en";
let ws = null;
let wsReady = false;

const elChat = document.getElementById("chat");
const elInput = document.getElementById("input");
const elStatusText = document.getElementById("statusText");
const elStatusMeta = document.getElementById("statusMeta");
const elSessionLabel = document.getElementById("sessionLabel");
const elLangSelect = document.getElementById("langSelect");

function setStatus(text, meta="") {
  elStatusText.textContent = text;
  elStatusMeta.textContent = meta;
}

function setSession(id) {
  sessionId = id;
  if (id) {
    localStorage.setItem("zxy.sessionId", id);
    elSessionLabel.textContent = "Session: " + id;
  } else {
    localStorage.removeItem("zxy.sessionId");
    elSessionLabel.textContent = "Session: —";
  }
}

function addMessage(role, text, meta=null) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + role;
  wrap.textContent = text;

  if (meta && typeof meta === "object") {
    const m = document.createElement("div");
    m.className = "meta";
    m.textContent = meta;
    wrap.appendChild(m);
  }

  elChat.appendChild(wrap);
  elChat.scrollTop = elChat.scrollHeight;
  return wrap;
}

async function postChat(message) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({message, session_id: sessionId, language}),
  });
  if (!res.ok) throw new Error("HTTP " + res.status);
  return await res.json();
}

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.addEventListener("open", () => {
    wsReady = true;
    setStatus("Connected", "WebSocket streaming enabled");
  });

  ws.addEventListener("close", () => {
    wsReady = false;
    setStatus("Disconnected", "Falling back to HTTP");
    // Attempt reconnect after a short delay
    setTimeout(connectWs, 1200);
  });

  ws.addEventListener("error", () => {
    wsReady = false;
    setStatus("Connection error", "Falling back to HTTP");
  });

  let currentAssistantEl = null;

  ws.addEventListener("message", (evt) => {
    let msg = null;
    try { msg = JSON.parse(evt.data); } catch { return; }

    if (msg.type === "start") {
      if (msg.session_id) setSession(msg.session_id);
      currentAssistantEl = addMessage("assistant", "");
    }
    if (msg.type === "delta" && currentAssistantEl) {
      currentAssistantEl.textContent += msg.text;
      elChat.scrollTop = elChat.scrollHeight;
    }
    if (msg.type === "end" && currentAssistantEl) {
      currentAssistantEl = null;
    }
    if (msg.type === "error") {
      addMessage("assistant", msg.message || "Error");
    }
  });
}

async function sendMessage() {
  const text = (elInput.value || "").trim();
  if (!text) return;
  elInput.value = "";
  addMessage("user", text);

  // Prefer websocket for streaming
  if (wsReady && ws) {
    ws.send(JSON.stringify({message: text, session_id: sessionId, language}));
    return;
  }

  // Fallback to HTTP
  try {
    setStatus("Working…", "HTTP mode");
    const data = await postChat(text);
    if (data.session_id) setSession(data.session_id);
    addMessage("assistant", data.reply, data.meta ? `mode=${data.meta.mode || "chat"} • ${data.meta.ms || "?"}ms` : null);
    setStatus("Connected", "HTTP mode");
  } catch (e) {
    addMessage("assistant", "Request failed. Is the server running?");
    setStatus("Error", String(e));
  }
}

document.getElementById("btnSend").addEventListener("click", sendMessage);
elInput.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") sendMessage();
});

document.getElementById("btnHelp").addEventListener("click", () => {
  elInput.value = "/help";
  elInput.focus();
});
document.getElementById("btnMemory").addEventListener("click", () => {
  elInput.value = "/memory";
  elInput.focus();
});
document.getElementById("btnReset").addEventListener("click", async () => {
  addMessage("user", "[Reset session]");
  try {
    await fetch("/api/reset", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: "reset", session_id: sessionId, language}),
    });
  } catch {}
  setSession(null);
  addMessage("assistant", "Session reset. Start a new chat.");
});

document.getElementById("btnExport").addEventListener("click", async () => {
  if (!sessionId) {
    addMessage("assistant", "No session yet. Send a message first.");
    return;
  }
  const url = `/api/export?session_id=${encodeURIComponent(sessionId)}`;
  // Open export in a new tab
  window.open(url, "_blank");
});

(async function boot(){
  setStatus("Connecting…", "Trying WebSocket first");
  setSession(sessionId);
  // Language dropdown
  if (elLangSelect) {
    elLangSelect.value = language;
    elLangSelect.addEventListener("change", () => {
      language = elLangSelect.value || "en";
      localStorage.setItem("zxy.language", language);
      addMessage("assistant", `Language set to ${language}. You can also use /lang ${language}.`);
    });
  }

  connectWs();

  // initial greeting
  addMessage("assistant",
    "Hello — I’m Zxyphorz AI. I run locally (no external AI APIs) and support 7 languages.\n\n" +
    "Try: `/help` or ask me to explain something."
  );
})();
