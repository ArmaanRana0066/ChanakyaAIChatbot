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

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .rag import retrieve, STORE
from .providers import stream_with_fallback, active_provider_names

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


def _client_ip(request: Request) -> str:
    # Behind a host's proxy (Render/HF), the real client IP is in X-Forwarded-For.
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


class Message(BaseModel):
    role: str  # "user" or "model"
    text: str


class ChatRequest(BaseModel):
    messages: list[Message]


class VerifyRequest(BaseModel):
    quote: str


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


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    if not active_provider_names():
        raise HTTPException(
            status_code=500,
            detail="No AI provider keys set. Copy .env.example to .env and add at least GEMINI_API_KEY.",
        )
    _check_rate_limit(_client_ip(request))
    if not req.messages:
        raise HTTPException(status_code=400, detail="No messages provided.")

    # Retrieve relevant verses for the latest user turn (RAG grounding). Query embedding
    # uses Gemini; if its quota is gone, retrieval returns [] and we still answer (via a
    # fallback provider) — just without citations that round.
    last_user = next((m.text for m in reversed(req.messages) if m.role == "user"), "")
    sources = await retrieve(last_user, GEMINI_API_KEY, k=4) if (last_user and GEMINI_API_KEY) else []

    system_text = SYSTEM_PROMPT + _grounding_block(sources)
    history = [{"role": m.role, "text": m.text} for m in req.messages[-MAX_HISTORY_MESSAGES:]]

    async def generate():
        # Send sources first (frontend renders them as a citation panel), then the answer.
        yield SOURCES_START + json.dumps(sources, ensure_ascii=False) + SOURCES_END
        async for delta in stream_with_fallback(system_text, history):
            yield delta

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@app.post("/api/verify")
async def verify_quote(req: VerifyRequest, request: Request):
    """Quote Myth-Buster: check a claimed 'Chanakya quote' against the real corpus.

    Pure retrieval/similarity — no LLM — so the verdict is objective and explainable:
    we show the nearest real verse and how closely it matches.
    """
    _check_rate_limit(_client_ip(request))
    quote = (req.quote or "").strip()
    if not quote:
        raise HTTPException(status_code=400, detail="No quote provided.")
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Verifier needs the embedding key; try again later.")

    matches = await retrieve(quote, GEMINI_API_KEY, k=3, min_score=0.0)
    top = matches[0]["score"] if matches else 0.0

    if top >= 0.86:
        verdict, message = "AUTHENTIC", "This closely matches a real verse in the Chanakya Niti."
    elif top >= 0.70:
        verdict, message = "PARAPHRASED", "The idea exists in the Chanakya Niti, but this wording is a paraphrase — here is the closest real verse."
    else:
        verdict, message = "NOT FOUND", "No close match in the Chanakya Niti corpus. This is likely misattributed or invented (a lot of viral 'Chanakya quotes' are)."

    return {"verdict": verdict, "confidence": round(top, 3), "message": message, "nearest": matches}


@app.get("/health")
def health():
    return {
        "ok": True,
        "providers": active_provider_names(),   # fallback chain, in order
        "rag_available": STORE.available,
        "corpus_size": len(STORE.items) if STORE.available else 0,
    }


# --- serve the frontend (static files at repo root) -----------------------
@app.get("/")
def index():
    # Serve the app directly (no forced splash delay).
    return FileResponse(os.path.join(ROOT_DIR, "Chanakya.html"))


# Mount everything else (Chanakya.html, script.js, style.css, images, favicon/)
app.mount("/", StaticFiles(directory=ROOT_DIR, html=True), name="static")
