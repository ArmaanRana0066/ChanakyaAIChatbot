// Chanakya AI — frontend
// No API key here. The browser only talks to our backend (/api/chat, /api/verify),
// which holds the keys server-side and does RAG retrieval.

const input = document.querySelector("#inputbox");
const chatcontainer = document.querySelector(".chat-container");
const btn = document.querySelector("#submit");
const newChatBtn = document.querySelector("#newchat");
const welcome = document.querySelector(".chat-before");
const modeBtns = document.querySelectorAll(".mode");

const base = location.protocol === "file:" ? "http://localhost:8000" : "";
const CHAT_URL = base + "/api/chat";
const VERIFY_URL = base + "/api/verify";
const STORAGE_KEY = "chanakya_transcript_v2";

const SOURCES_START = "§§SOURCES§§";
const SOURCES_END = "§§ENDSOURCES§§";

let mode = "ask";                 // "ask" | "verify"
let transcript = loadTranscript();  // render + persistence (chat AND verify)

// ---------------------------------------------------------------- helpers
function loadTranscript() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || []; }
  catch { return []; }
}
function save() { localStorage.setItem(STORAGE_KEY, JSON.stringify(transcript)); }

// The chat context sent to the model = chat turns only (verify cards excluded).
function chatMessages() {
  return transcript
    .filter((t) => t.role === "user" || t.role === "model")
    .map((t) => ({ role: t.role, text: t.text }));
}

function renderMarkdown(text) {
  const raw = window.marked ? window.marked.parse(text) : text;
  return window.DOMPurify ? window.DOMPurify.sanitize(raw) : raw;
}
function el(html, cls) { const d = document.createElement("div"); d.innerHTML = html; if (cls) d.classList.add(cls); return d; }
function escapeHtml(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
function scrollDown() { chatcontainer.scrollTo({ top: chatcontainer.scrollHeight, behavior: "smooth" }); }
function hideWelcome() { if (welcome) welcome.style.display = "none"; }

// ---------------------------------------------------------------- render parts
function addUser(text) {
  chatcontainer.appendChild(
    el(`<img src="user-logo.png" alt="you" id="user-img"><div class="user-input">${escapeHtml(text)}</div>`, "user-chat")
  );
}
function addAiPlaceholder() {
  const box = el(
    `<img src="chanak-logo.png" id="aiprofile" alt="Chanakya">
     <div class="ai-body">
       <div class="chat-output"><img src="UDui.gif" class="load" alt="…" width="70" height="26"></div>
       <div class="chat-sources"></div>
     </div>`, "ai-chat");
  chatcontainer.appendChild(box);
  return box;
}
function renderSources(box, sources) {
  const panel = box.querySelector(".chat-sources");
  if (!panel || !sources || !sources.length) { if (panel) panel.innerHTML = ""; return; }
  const items = sources.map((s) => {
    const skt = s.sanskrit ? `<div class="sanskrit">${escapeHtml(s.sanskrit)}</div>` : "";
    const tr = s.transliteration ? `<div class="translit">${escapeHtml(s.transliteration)}</div>` : "";
    return `<li><span class="cite">${escapeHtml(s.citation)}</span>
       <span class="score">${(s.score * 100).toFixed(0)}% match</span>
       ${skt}${tr}<div class="verse">${escapeHtml(s.translation)}</div></li>`;
  }).join("");
  panel.innerHTML = `<details><summary>📜 ${sources.length} source${sources.length > 1 ? "s" : ""} from the Shastra</summary><ul>${items}</ul></details>`;
}
function renderVerdict(quote, data) {
  addUser(quote);
  const cls = data.verdict.replace(/\s+/g, ""); // "NOT FOUND" -> "NOTFOUND"
  let versesHtml = "";
  if (data.nearest && data.nearest.length) {
    const top = data.nearest[0];
    const skt = top.sanskrit ? `<div class="sanskrit">${escapeHtml(top.sanskrit)}</div>` : "";
    const tr = top.transliteration ? `<div class="translit">${escapeHtml(top.transliteration)}</div>` : "";
    versesHtml = `<div class="vverse"><span class="cite">${escapeHtml(top.citation)}</span>
      <span class="score">${(top.score * 100).toFixed(0)}% match</span>
      ${skt}${tr}<div class="verse">"${escapeHtml(top.translation)}"</div></div>`;
  }
  const card = el(
    `<span class="badge">${escapeHtml(data.verdict)}</span>
     <p class="vmsg">${escapeHtml(data.message)}</p>
     ${versesHtml ? `<div class="vlabel">Closest real verse:</div>${versesHtml}` : ""}`, "verdict");
  card.classList.add(cls);
  chatcontainer.appendChild(card);
  scrollDown();
}

// ---------------------------------------------------------------- chat (ask mode)
async function streamChat(box) {
  const out = box.querySelector(".chat-output");
  let buffer = "", answer = "", sources = [], parsed = false;
  try {
    const res = await fetch(CHAT_URL, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: chatMessages() }),
    });
    if (!res.ok) {
      const d = await res.text().catch(() => "");
      out.innerHTML = `<em>Kshama karein — server error (${res.status}). ${escapeHtml(d.slice(0, 200))}</em>`;
      return;
    }
    const reader = res.body.getReader(), dec = new TextDecoder();
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      const chunk = dec.decode(value, { stream: true });
      if (!parsed) {
        buffer += chunk;
        const end = buffer.indexOf(SOURCES_END);
        if (end !== -1) {
          const start = buffer.indexOf(SOURCES_START);
          try { sources = JSON.parse(buffer.slice(start + SOURCES_START.length, end)); } catch { sources = []; }
          renderSources(box, sources);
          answer = buffer.slice(end + SOURCES_END.length);
          out.innerHTML = renderMarkdown(answer) || "";
          parsed = true;
        }
      } else {
        answer += chunk;
        out.innerHTML = renderMarkdown(answer);
      }
      scrollDown();
    }
    transcript.push({ role: "model", text: answer, sources });
    save();
  } catch (err) {
    out.innerHTML = `<em>Network error — backend chal raha hai? (${escapeHtml(String(err))})</em>`;
  }
}

function sendChat(text) {
  hideWelcome();
  transcript.push({ role: "user", text });
  save();
  addUser(text);
  const box = addAiPlaceholder();
  scrollDown();
  streamChat(box);
}

// ---------------------------------------------------------------- verify mode
async function verifyQuote(quote) {
  hideWelcome();
  try {
    const res = await fetch(VERIFY_URL, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quote }),
    });
    const data = await res.json();
    if (!res.ok) { renderVerdict(quote, { verdict: "ERROR", message: data.detail || "Server error", nearest: [] }); return; }
    transcript.push({ role: "verify", quote, data });
    save();
    renderVerdict(quote, data);
  } catch (err) {
    renderVerdict(quote, { verdict: "ERROR", message: "Network error: " + String(err), nearest: [] });
  }
}

// ---------------------------------------------------------------- submit flow
function submit() {
  const text = (input.value || "").trim();
  if (!text) return;
  input.value = "";
  if (mode === "verify") verifyQuote(text);
  else sendChat(text);
}

function restore() {
  if (!transcript.length) return;
  hideWelcome();
  for (const t of transcript) {
    if (t.role === "user") addUser(t.text);
    else if (t.role === "model") {
      const box = addAiPlaceholder();
      box.querySelector(".chat-output").innerHTML = renderMarkdown(t.text);
      renderSources(box, t.sources);
    } else if (t.role === "verify") {
      renderVerdict(t.quote, t.data);
    }
  }
  scrollDown();
}

// ---------------------------------------------------------------- events
input.addEventListener("keydown", (e) => { if (e.key === "Enter") submit(); });
btn.addEventListener("click", submit);

modeBtns.forEach((b) => b.addEventListener("click", () => {
  modeBtns.forEach((x) => x.classList.remove("active"));
  b.classList.add("active");
  mode = b.dataset.mode;
  input.placeholder = mode === "verify"
    ? "Paste a “Chanakya quote” to fact-check…"
    : "प्रश्न पूछें — ask Chanakya anything…";
  input.focus();
}));

document.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => {
  mode = "ask";
  modeBtns.forEach((x) => x.classList.toggle("active", x.dataset.mode === "ask"));
  sendChat(c.textContent.trim());
}));

if (newChatBtn) newChatBtn.addEventListener("click", () => {
  transcript = []; save();
  chatcontainer.querySelectorAll(".user-chat, .ai-chat, .verdict").forEach((e) => e.remove());
  if (welcome) welcome.style.display = "";
  input.focus();
});

restore();
