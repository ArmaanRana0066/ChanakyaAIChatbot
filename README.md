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

🔗 **Live demo:** https://armaan006-chanakya-ai.hf.space
&nbsp;·&nbsp; 💻 **Code:** https://github.com/ArmaanRana0066/ChanakyaAIChatbot

Not a "talk to god" bot. Acharya Chanakya was a human teacher, strategist and economist, so
this is a *secular mentor* for career, negotiation, money, leadership and decision-making —
with advice grounded in real classical texts and **verse-level citations** (RAG).

> अनभ्यासे विषं शास्त्रम् — *"Knowledge without practice is poison."* (Chanakya Niti 4.15)

## Features
- **Ask mode** — chat with the Acharya; every answer cites the exact Chanakya Niti chapter
  & verse, shown in a "sources from the Shastra" panel with the original **Devanagari + IAST
  transliteration** (where available).
- **Quote Myth-Buster** — paste a viral "Chanakya quote"; it checks against the real corpus and
  labels it **AUTHENTIC / PARAPHRASED / NOT FOUND** with the closest real verse. (So much
  "Chanakya" content online is fake — this catches it.)
- **Multi-provider failover** — when one provider's free quota is exhausted (HTTP 429) the
  server auto-switches to the next — **Groq → Gemini → OpenRouter → Mistral** — *without losing
  conversation context*. Only providers whose key is set are used.

## Stack
- **Frontend:** vanilla HTML / CSS / JS, streaming UI, markdown rendering (marked + DOMPurify),
  mode toggle, citation panel. No external CDNs required.
- **Backend:** Python **FastAPI** proxy holding keys server-side; conversation memory, streaming,
  per-IP rate limiting, the Chanakya (Acharya, non-deity) persona, RAG retrieval + the verifier.
- **RAG:** Chanakya Niti corpus (319 verses) embedded with `gemini-embedding-001` (768-dim) into
  a local cosine vector store (`corpus/embeddings.json`); 120 verses enriched with public-domain
  Devanagari + transliteration. Cosine top-k grounds every answer in real, cited verses.
- **Models:** Groq `llama-3.3-70b` (primary) with Gemini `gemini-2.5-flash` as fallback.

## Evals
A small suite measures whether RAG actually stops fabricated citations
([`evals/`](evals/), `python evals/run_eval.py`):

| Metric (18 questions) | Naive wrapper | RAG (this app) |
|---|---|---|
| Fabricated citations | 7% | **0%** |
| Citations grounded in a shown verse | n/a | **100%** |

Every citation this app makes is grounded in a real verse retrieved and shown to the user;
a naive wrapper cites from memory — unverifiable, and 7% point to verses that don't exist.

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
python scripts/add_sanskrit.py   # add Devanagari + IAST to the aligned chapters
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
