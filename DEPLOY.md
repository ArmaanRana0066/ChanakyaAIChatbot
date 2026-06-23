# Deploying Chanakya AI — free, NO credit card

> ⚠️ Before deploying: revoke the OLD leaked key at https://aistudio.google.com/apikey
> and use a fresh key. Never put the key in a file — set it as a secret on the host.

> ℹ️ Render now asks for a credit card even on its free tier, so we use **Hugging Face
> Spaces** instead — genuinely free, no card, and a great fit for an AI project.

---

## Hugging Face Spaces (recommended — Docker, no card)

### 1. Create the Space
1. Go to https://huggingface.co → **Sign Up** (free, no card needed).
2. Top-right **+ → New Space**.
3. Fill in:
   - **Owner:** your username
   - **Space name:** `chanakya-ai`
   - **License:** MIT
   - **SDK:** choose **Docker** → **Blank**
   - **Hardware:** CPU basic (free)
   - Visibility: Public
4. **Create Space.**

### 2. Add your API key as a secret
In the Space: **Settings → Variables and secrets → New secret**
- Name: `GEMINI_API_KEY`
- Value: your new Gemini key
(Also add `GEMINI_MODEL` = `gemini-2.5-flash` as a normal variable if you like.)

### 3. Get the code into the Space — pick ONE:

**Option A — Upload in the browser (easiest, no tokens):**
- In the Space → **Files → Add file → Upload files**.
- Drag in ALL project files **and folders** (`backend/`, `corpus/`, `scripts/`, plus
  `Dockerfile`, `requirements.txt`, `*.html`, `script.js`, `style.css`, images, `README.md`).
- Commit. The Space builds automatically.

**Option B — Push with git (uses an HF token):**
1. Create a token: HF **Settings → Access Tokens → New token** (role: **Write**). Copy it.
2. In your project folder:
   ```bash
   git remote add space https://huggingface.co/spaces/<your-username>/chanakya-ai
   git push space main
   ```
   When asked: username = your HF username, password = paste the **token**.
   (If it rejects history, run `git push space main --force`.)

### 4. Done
The Space builds the Dockerfile and serves at:
`https://<your-username>-chanakya-ai.hf.space` — put this on your resume.
First build takes a few minutes; watch the **Logs** tab.

---

## What gets deployed
- One FastAPI process serves BOTH the frontend (static files) and `/api/chat`.
- The RAG vector store (`corpus/embeddings.json`) is committed, so nothing is re-embedded at
  deploy — the app only needs `GEMINI_API_KEY` for query-embedding + generation.
- Health check: `GET /health` shows model + RAG status.

## render.yaml
Kept in the repo in case you add a card later — but HF Spaces above needs none.
