# Chanakya AI — Roadmap

**Positioning:** *"Chanakya — your AI strategy mentor, grounded in the Arthashastra."*
Not a deity bot. A secular strategy/negotiation/career mentor whose advice is grounded in
the real Chanakya Niti + Arthashastra texts, with verifiable citations.

This is the open whitespace: every popular competitor (GitaGPT, Krishna AI, Vedh GPT) speaks
*as a god*. Chanakya was a human teacher/economist, so an "Acharya/mentor" persona is both
more authentic and avoids the religious-impersonation backlash those bots faced.

---

## Phase 0 — Security (DONE in code; 2 manual steps left) ⚠️
- [x] Remove hardcoded Gemini key from client JS.
- [x] `.gitignore` (.env, etc.) + `.env.example`.
- [x] Backend proxy holds the key server-side.
- [ ] **YOU: Revoke the old key** at https://aistudio.google.com/apikey and make a new one.
- [ ] **YOU (optional):** scrub the key from old git commits (see "Git history" below) and force-push.

**Resume line:** *"Identified and remediated a leaked API credential; moved secrets server-side,
added a backend proxy with rate limiting and spend controls."*

## Phase 1 — Backend + baseline chat UX (DONE in code)
- [x] Python FastAPI proxy `/api/chat` (key in env var).
- [x] Conversation memory (last 20 turns sent for context).
- [x] Token-by-token streaming responses.
- [x] Markdown rendering (marked) + sanitization (DOMPurify, anti-XSS).
- [x] Chat history persisted to localStorage + "new chat" button.
- [x] Real error handling + per-IP rate limiting.
- [x] **Multi-provider failover** (`backend/providers.py`): Gemini → Groq → OpenRouter →
      Mistral; auto-switch on quota/429, conversation context preserved. Keys optional.
- [ ] **Deploy** (Hugging Face Spaces — free, no card) → get a live demo URL for the resume.

**Resume line:** *"Built a streaming chat app with conversation memory, markdown rendering,
and client/server separation (Python FastAPI + vanilla JS)."*

## Phase 2 — Persona + repo professionalism
- [x] Acharya (not deity) system prompt with safety boundaries + "interpretation, not scripture" framing.
- [ ] Re-theme: parchment/ink-and-gold or deep indigo "ancient scholar" look.
- [ ] Header shloka: show meaning on hover, label it correctly (**Chanakya Niti 4.15**).
- [ ] Story-driven README with an architecture diagram + "what I'd improve next".
- [ ] Restructure folders (/frontend, /backend, /corpus, /scripts, /tests), add LICENSE (MIT).

## Phase 3 — RAG with citations 🌟 (the headline feature) — v1 DONE ✅
- [x] Curated **public-domain** Chanakya Niti corpus (319 verses, 17 chapters) from
      gita/Datasets → `corpus/chanakya_niti.json` (`scripts/build_corpus.py`).
- [x] Ingestion script: embed each verse with `gemini-embedding-001` (768-dim) →
      local vector store `corpus/embeddings.json` (`scripts/ingest.py`, resumable).
- [x] Retrieval in the proxy (`backend/rag.py`): cosine top-k → injected into the prompt;
      model cites only retrieved passages, refuses to fabricate. Verified: citations match sources.
- [x] UI source panel: collapsible "📜 sources from the Shastra" with citation + match% + verse.
- [ ] **Phase 3b:** add Sanskrit (Devanagari) + transliteration per verse (fields already in schema).
- [ ] **Phase 3b:** add Arthashastra passages (Shamasastry 1915, public domain) for the strategy register.
- [ ] **Phase 3b:** "Strategy Analyzer" / "Quote Myth-Buster" modes on top of this corpus.

**Resume line:** *"Built a retrieval-augmented (RAG) citation system over a 319-verse corpus
(gemini-embedding-001 + cosine retrieval); answers cite exact chapter/verse, eliminating
fabricated quotes."*

## Phase 4 — Evals + observability + tool calling
- [ ] Golden set of 40–60 Chanakya questions with known sources.
- [ ] Score groundedness / hallucination rate (before vs. after RAG) → metrics table in README.
- [ ] GitHub Actions CI: unit tests + eval regression on every PR.
- [ ] Log per-request retrieval, tokens, latency, cost.
- [ ] One tool/function call (JSON schema), e.g. "shloka lookup" or "translate".

## Phase 5 — Auth + real persistence + polish
- [ ] Supabase Auth (email + Google), chat history in Postgres (resume across devices).
- [ ] Saved "counsel" threads; two-texts toggle (Niti vs. Arthashastra).
- [ ] Bilingual / Hinglish code-switching (always preserve the Sanskrit original).
- [ ] Hardening: per-user rate limits, billing alerts, input validation, health check.

---

## Standout features to build (ranked)
1. **Ask the Shastra** — verse-level RAG with citations *(headline differentiator)*.
2. **Niti Lens** — situational strategy analyzer (Saptanga / Shadgunya frameworks) *(product identity)*.
3. **Quote Myth-Buster** — paste a viral "Chanakya quote", bot says authentic / paraphrased / fake *(memorable demo)*.
4. **Eval dashboard** — before/after groundedness numbers *(proof layer)*.
5. **Saam-Daam-Dand-Bhed negotiation coach** — four classical options with ethical guardrails.

## Git history (scrubbing the leaked key from old commits)
The key still lives in old commits (e.g. 95017e0, df7a1ca). Once the key is **revoked** it's
harmless, but to also remove it from history:

```bash
pip install git-filter-repo
# put the OLD leaked key (not shown here) on the left of ==>
echo "<OLD_LEAKED_KEY>==>REMOVED" > replace.txt
git filter-repo --replace-text replace.txt
git remote add origin https://github.com/ArmaanRana0066/ChanakyaAIChatbot.git
git push --force --all
```
> ⚠️ Force-push rewrites public history. Revoking the key is the real fix; this is cleanup.
