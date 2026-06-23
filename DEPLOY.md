# Deploying Chanakya AI (free, no credit card)

Both options below are free and need only a GitHub login — no card. **Render is the easiest.**

> ⚠️ Before deploying: revoke the OLD leaked key at https://aistudio.google.com/apikey
> and use a fresh key. Never paste the key into any file — set it as an env var in the host.

---

## Option A — Render (recommended)
1. Push this repo to GitHub (already done).
2. Go to https://render.com → sign up with GitHub (free, no card).
3. **New → Web Service** → pick the `ChanakyaAIChatbot` repo.
4. Render reads `render.yaml` automatically. Confirm:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
5. Under **Environment**, add a secret:
   - `GEMINI_API_KEY` = your new key  (do NOT commit it)
6. **Create Web Service**. First build takes a few minutes.
7. You get a live URL like `https://chanakya-ai.onrender.com` — put it on your resume.

> Free tier sleeps after ~15 min idle, so the first hit after a pause is slow (~50s).
> That's fine for a demo; mention it's the free tier if asked.

---

## Option B — Hugging Face Spaces (great for an ML portfolio)
1. Go to https://huggingface.co → sign up (free, no card).
2. **New Space** → SDK: **Docker** → blank. It uses the `Dockerfile` in this repo.
3. Push this repo to the Space (or connect GitHub).
4. Space **Settings → Variables and secrets** → add secret `GEMINI_API_KEY`.
5. The Space builds and serves at `https://<user>-<space>.hf.space`.

---

## What's deployed
- The FastAPI app serves BOTH the frontend (static files) and `/api/chat` from one process.
- The RAG vector store (`corpus/embeddings.json`) is committed, so no ingestion runs at deploy —
  the app only needs `GEMINI_API_KEY` for query-embedding + generation.
- Health check: `GET /health` returns model + RAG status.
