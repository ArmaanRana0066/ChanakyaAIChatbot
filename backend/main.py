"""
Chanakya AI — backend proxy (FastAPI).

Why this exists:
- The Gemini API key MUST stay on the server. The browser talks only to /api/chat,
  it never sees the key. This is the single most important fix vs. the old version
  where the key was hardcoded in client-side script.js.

Run locally:
    pip install -r requirements.txt
    # create .env from .env.example and put your NEW key in it
    uvicorn backend.main:app --reload --port 8000
    # open http://localhost:8000/
"""

import os
import json
import time
from collections import defaultdict, deque

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .rag import retrieve, STORE

# Sentinels: the stream sends retrieved sources (JSON) first, then the answer text.
SOURCES_START = "§§SOURCES§§"
SOURCES_END = "§§ENDSOURCES§§"

# --- config ---------------------------------------------------------------
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "20"))

# Folder that holds the frontend (index.html, Chanakya.html, script.js, style.css ...)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# How many recent turns to keep as context (memory). Keeps token cost bounded.
MAX_HISTORY_MESSAGES = 20

# --- Chanakya persona (the "character card") ------------------------------
# NOTE: framed as a human Acharya / strategist, NOT a deity. This is deliberate:
# it is historically accurate AND avoids the religious-impersonation problems
# that hit Krishna/Gita bots. Until RAG (Phase 3) is wired in, the model is told
# NOT to fabricate exact citations it isn't sure of.
SYSTEM_PROMPT = """You are Acharya Chanakya (Kautilya / Vishnugupta) — the ancient Indian
teacher, strategist and economist, author of the Arthashastra and Chanakya Niti.

PERSONA:
- You are a human mentor and Acharya, NOT a god. Never claim divinity.
- Voice: measured, incisive, pragmatic, a little stern. Speak in short, clear maxims,
  then explain the reasoning — mirroring the sutra style.
- You may answer in English, Hindi, or Hinglish to match how the user writes.

HOW YOU ANSWER:
- Distinguish two registers and say which you are drawing on:
    * NITI (personal life: study, money, friends, character, family) — from Chanakya Niti.
    * STRATEGY / STATECRAFT (leadership, negotiation, competition, decisions) — from the Arthashastra.
- You will often be given RETRIEVED PASSAGES from the Chanakya Niti below. Ground your
  advice in them and cite them inline as (Chanakya Niti, Ch.X, V.Y).
- IMPORTANT: Do NOT invent chapter/verse citations beyond the retrieved passages provided.
  If no passage truly fits, say the text does not directly address it and answer from the
  general principle rather than fabricating a verbatim quote.
- When the text is silent on something, say so honestly instead of fabricating.

BOUNDARIES:
- The Arthashastra discusses espionage, deception (bheda) and force. You may explain these
  as strategic CONCEPTS, but refuse to give operational instructions to deceive, manipulate
  or harm specific real people. Frame it as: "strategy serves dharma, not adharma."
- This is interpretation of a ~2,300-year-old text for guidance — not religious scripture
  and not professional legal/medical/financial advice.
"""

# --- app ------------------------------------------------------------------
app = FastAPI(title="Chanakya AI", version="1.0")

# Naive in-memory per-IP rate limiter (fine for a portfolio project / single instance).
_hits: dict[str, deque] = defaultdict(deque)


def _check_rate_limit(ip: str) -> None:
    now = time.monotonic()
    window = _hits[ip]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="Too many requests. Thoda ruko, vatsa.")
    window.append(now)


class Message(BaseModel):
    role: str  # "user" or "model"
    text: str


class ChatRequest(BaseModel):
    messages: list[Message]


def _grounding_block(sources: list[dict]) -> str:
    """Format retrieved verses into a context block appended to the system instruction."""
    if not sources:
        return ""
    lines = [
        "\n\nRETRIEVED PASSAGES (from the Chanakya Niti corpus). Ground your advice in these",
        "where relevant and cite them inline as (Chanakya Niti, Ch.X, V.Y). If none truly fit,",
        "say the text does not directly address it and answer from general principle. Do NOT",
        "invent citations beyond those listed here.\n",
    ]
    for i, s in enumerate(sources, 1):
        lines.append(f'[{i}] ({s["citation"]}) "{s["translation"]}"')
    return "\n".join(lines)


def _build_gemini_payload(messages: list[Message], sources: list[dict]) -> dict:
    """Convert our message list into Gemini's request body, trimming to recent turns."""
    trimmed = messages[-MAX_HISTORY_MESSAGES:]
    contents = []
    for m in trimmed:
        role = "model" if m.role == "model" else "user"
        text = (m.text or "").strip()
        if not text:
            continue
        contents.append({"role": role, "parts": [{"text": text}]})
    system_text = SYSTEM_PROMPT + _grounding_block(sources)
    return {
        "system_instruction": {"parts": [{"text": system_text}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
            # gemini-2.5-flash is a "thinking" model; without this it spends the whole
            # token budget reasoning and truncates the actual answer. Off = fast chat.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }


async def _stream_gemini(payload: dict):
    """Call Gemini's SSE streaming endpoint and yield plain text deltas to the client."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:streamGenerateContent?alt=sse&key={GEMINI_API_KEY}"
    )
    headers = {"Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", "ignore")
                    yield f"[error] Gemini API returned {resp.status_code}. {body[:300]}"
                    return
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                        parts = obj["candidates"][0]["content"]["parts"]
                        for p in parts:
                            if "text" in p:
                                yield p["text"]
                    except (KeyError, IndexError, json.JSONDecodeError):
                        # Skip keep-alive / non-text chunks.
                        continue
    except httpx.RequestError as e:
        yield f"[error] Could not reach the model: {e}. Internet/API key theek hai?"


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not set on the server. Copy .env.example to .env and add your key.",
        )
    # Behind a host's proxy (Render/HF), the real client IP is in X-Forwarded-For.
    fwd = request.headers.get("x-forwarded-for", "")
    client_ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")
    _check_rate_limit(client_ip)
    if not req.messages:
        raise HTTPException(status_code=400, detail="No messages provided.")

    # Retrieve relevant verses for the latest user turn (RAG grounding).
    last_user = next((m.text for m in reversed(req.messages) if m.role == "user"), "")
    sources = await retrieve(last_user, GEMINI_API_KEY, k=4) if last_user else []
    payload = _build_gemini_payload(req.messages, sources)

    async def generate():
        # Send sources first (frontend renders them as a citation panel), then the answer.
        yield SOURCES_START + json.dumps(sources, ensure_ascii=False) + SOURCES_END
        async for delta in _stream_gemini(payload):
            yield delta

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@app.get("/health")
def health():
    return {
        "ok": True,
        "model": GEMINI_MODEL,
        "key_loaded": bool(GEMINI_API_KEY),
        "rag_available": STORE.available,
        "corpus_size": len(STORE.items) if STORE.available else 0,
    }


# --- serve the frontend (static files at repo root) -----------------------
@app.get("/")
def index():
    return FileResponse(os.path.join(ROOT_DIR, "index.html"))


# Mount everything else (Chanakya.html, script.js, style.css, images, favicon/)
app.mount("/", StaticFiles(directory=ROOT_DIR, html=True), name="static")
