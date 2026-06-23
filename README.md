---
title: Chanakya AI
emoji: 🪔
colorFrom: indigo
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Chanakya AI 🪔

**Your AI strategy mentor — grounded in the Arthashastra and Chanakya Niti.**

Not a "talk to god" bot. Acharya Chanakya was a human teacher, strategist and economist, so
this is a *secular mentor* for career, negotiation, money, leadership and decision-making —
with advice grounded in real classical texts and **verse-level citations** (RAG).

> अनभ्यासे विषं शास्त्रम् — *"Knowledge without practice is poison."* (Chanakya Niti 4.15)

## Stack
- **Frontend:** vanilla HTML / CSS / JS, streaming UI, markdown rendering (marked + DOMPurify),
  collapsible "sources from the Shastra" citation panel.
- **Backend:** Python **FastAPI** proxy that holds the Gemini API key server-side, adds
  conversation memory, streaming, rate limiting, the Chanakya persona, and RAG retrieval.
- **RAG:** 319-verse Chanakya Niti corpus embedded with `gemini-embedding-001` (768-dim),
  stored locally (`corpus/embeddings.json`); cosine top-k retrieval grounds every answer so
  it cites the exact chapter/verse instead of fabricating quotes.
- **Model:** Google Gemini (`gemini-2.5-flash`, thinking disabled for fast chat).
- **Multi-provider failover:** when one provider's free quota is exhausted (HTTP 429), the
  server auto-switches to the next in the chain — Gemini → Groq → OpenRouter → Mistral —
  **without losing conversation context**. Only providers whose key is set are used.

## Run locally
```bash
# 1. install deps
pip install -r requirements.txt

# 2. add your key (get one at https://aistudio.google.com/apikey)
cp .env.example .env        # then edit .env and paste your key

# 3. start the server (serves the frontend AND the API)
uvicorn backend.main:app --reload --port 8000

# 4. open http://localhost:8000/
```

## Deploy
Free, no credit card — see **[DEPLOY.md](DEPLOY.md)** (Hugging Face Spaces). This repo includes a
`Dockerfile`, so a Hugging Face **Docker** Space runs it as-is; set `GEMINI_API_KEY` as a Space secret.

## Rebuild the knowledge base
```bash
python scripts/build_corpus.py   # fetch + normalize the 17-chapter corpus
python scripts/ingest.py         # embed verses -> corpus/embeddings.json (resumable)
```

## Security note
The Gemini API key is **never** in client-side code. The browser calls `/api/chat`; only the
server reads `GEMINI_API_KEY` from the environment.

## Roadmap
See **[PLAN.md](PLAN.md)** — phased plan from security hardening → backend → RAG-with-citations
→ evals → auth, plus the standout features (Niti Lens strategy analyzer, Quote Myth-Buster).

---
*Author: Armaan Rana — [@ArmaanRana0066](https://github.com/ArmaanRana0066)*
