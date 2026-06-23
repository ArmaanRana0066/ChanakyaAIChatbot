# Corpus sources & provenance

The RAG knowledge base is built **only** from public-domain / openly available text.
Authenticity matters: most "Chanakya quotes" online are misattributed or invented, so the
bot grounds its answers strictly in this curated corpus and cites chapter + verse.

## Chanakya Niti (`chanakya_niti.json`, 319 verses, 17 chapters)
- **Source:** [gita/Datasets](https://github.com/gita/Datasets) — `chanakya/Chanakya-Niti/`
  (a public-domain English translation, organized by chapter and verse).
- **Built by:** `scripts/build_corpus.py` (fetches + normalizes into one file with citations).
- Sanskrit (Devanagari) + transliteration fields are present but empty — to be filled in
  Phase 3b from a verified source (e.g. [sanskritdocuments.org](https://sanskritdocuments.org/sanskrit/chanakya/)),
  carefully aligned to avoid mis-citation.

## Planned: Arthashastra (Phase 3b)
- **Source to use:** R. Shamasastry (1915) English translation — **public domain**.
- **Do NOT ingest** copyrighted translations (Olivelle, Kangle, Rangarajan, Haksar) or scraped
  quote-aggregator sites.

## Embeddings (`embeddings.json`)
- Model: `gemini-embedding-001` (768 dimensions), task type `RETRIEVAL_DOCUMENT`.
- Rebuild with `python scripts/ingest.py` (resumable; respects free-tier rate limits).
