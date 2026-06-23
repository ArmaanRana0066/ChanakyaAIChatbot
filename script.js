// Chanakya AI — frontend
// SECURITY: there is NO API key here. The browser only talks to our own backend
// (/api/chat), which holds the key server-side and does the RAG retrieval.

const input = document.querySelector("#inputbox");
const chatcontainer = document.querySelector(".chat-container");
const btn = document.querySelector("#submit");
const newChatBtn = document.querySelector("#newchat");
const contbefore = document.querySelector(".chat-before");

const API_URL =
  location.protocol === "file:" ? "http://localhost:8000/api/chat" : "/api/chat";

const STORAGE_KEY = "chanakya_chat_history_v1";

// Must match the sentinels in backend/main.py
const SOURCES_START = "§§SOURCES§§";
const SOURCES_END = "§§ENDSOURCES§§";

// Conversation memory: { role: "user"|"model", text, sources? }
let messages = loadHistory();

// ---------------------------------------------------------------- helpers
function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch {
    return [];
  }
}
function saveHistory() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
}
function renderMarkdown(text) {
  const raw = window.marked ? window.marked.parse(text) : text;
  return window.DOMPurify ? window.DOMPurify.sanitize(raw) : raw;
}
function createChat(html, className) {
  const div = document.createElement("div");
  div.innerHTML = html;
  div.classList.add(className);
  return div;
}
function smoothScrollToBottom() {
  chatcontainer.scrollTo({ top: chatcontainer.scrollHeight, behavior: "smooth" });
}
function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// ---------------------------------------------------------------- rendering
function appendUserMessage(text) {
  const html = `<img src="user-logo.png" alt="user" id="user-img" width="50">
    <div class="user-input">${escapeHtml(text)}</div>`;
  chatcontainer.appendChild(createChat(html, "user-chat"));
}

// Returns the whole ai-chat box (has .chat-output for the answer + .chat-sources panel).
function appendAiPlaceholder() {
  const html = `<img src="chanak-logo.png" id="aiprofile" alt="Chanakya" width="50">
    <div class="ai-body">
      <div class="chat-output">
        <img src="UDui.gif" class="load" alt="loading" width="80px" height="30px">
      </div>
      <div class="chat-sources"></div>
    </div>`;
  const box = createChat(html, "ai-chat");
  chatcontainer.appendChild(box);
  return box;
}

// Render the retrieved verses as a collapsible "grounded in" citation panel.
function renderSources(box, sources) {
  const panel = box.querySelector(".chat-sources");
  if (!panel) return;
  if (!sources || !sources.length) {
    panel.innerHTML = "";
    return;
  }
  const items = sources
    .map(
      (s) => `<li><span class="cite">${escapeHtml(s.citation)}</span>
        <span class="score">${(s.score * 100).toFixed(0)}% match</span>
        <div class="verse">${escapeHtml(s.translation)}</div></li>`
    )
    .join("");
  panel.innerHTML = `<details>
      <summary>📜 ${sources.length} source${sources.length > 1 ? "s" : ""} from the Shastra</summary>
      <ul>${items}</ul>
    </details>`;
}

// ---------------------------------------------------------------- networking
async function streamResponse(box) {
  const chatoutput = box.querySelector(".chat-output");
  let buffer = "";
  let answer = "";
  let sources = [];
  let sourcesParsed = false;

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    });

    if (!response.ok) {
      const detail = await response.text().catch(() => "");
      chatoutput.innerHTML = `<em>Kshama karein — server error (${response.status}). ${escapeHtml(
        detail.slice(0, 200)
      )}</em>`;
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });

      if (!sourcesParsed) {
        buffer += chunk;
        const endIdx = buffer.indexOf(SOURCES_END);
        if (endIdx !== -1) {
          const startIdx = buffer.indexOf(SOURCES_START);
          const jsonStr = buffer.slice(startIdx + SOURCES_START.length, endIdx);
          try {
            sources = JSON.parse(jsonStr);
          } catch {
            sources = [];
          }
          renderSources(box, sources);
          answer = buffer.slice(endIdx + SOURCES_END.length);
          chatoutput.innerHTML = renderMarkdown(answer) || "";
          sourcesParsed = true;
        }
        // else: still buffering the sources header; keep showing the loader
      } else {
        answer += chunk;
        chatoutput.innerHTML = renderMarkdown(answer);
      }
      smoothScrollToBottom();
    }

    messages.push({ role: "model", text: answer, sources });
    saveHistory();
  } catch (err) {
    chatoutput.innerHTML = `<em>Network error — backend chal raha hai? (${escapeHtml(
      String(err)
    )})</em>`;
  }
}

// ---------------------------------------------------------------- flow
function sendMessage(text) {
  const message = (text || "").trim();
  if (!message) {
    contbefore.style.display = "block";
    return;
  }
  contbefore.style.display = "none";
  input.value = "";

  messages.push({ role: "user", text: message });
  saveHistory();

  appendUserMessage(message);
  const box = appendAiPlaceholder();
  smoothScrollToBottom();
  streamResponse(box);
}

function restoreConversation() {
  if (!messages.length) return;
  contbefore.style.display = "none";
  for (const m of messages) {
    if (m.role === "user") {
      appendUserMessage(m.text);
    } else {
      const box = appendAiPlaceholder();
      box.querySelector(".chat-output").innerHTML = renderMarkdown(m.text);
      renderSources(box, m.sources);
    }
  }
  smoothScrollToBottom();
}

// ---------------------------------------------------------------- events
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage(input.value);
});
btn.addEventListener("click", () => sendMessage(input.value));

if (newChatBtn) {
  newChatBtn.addEventListener("click", () => {
    messages = [];
    saveHistory();
    chatcontainer.querySelectorAll(".user-chat, .ai-chat").forEach((el) => el.remove());
    contbefore.style.display = "block";
    input.focus();
  });
}

restoreConversation();
