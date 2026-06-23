"""
Embed the corpus and build a local vector store.

Reads:  corpus/chanakya_niti.json
Writes: corpus/embeddings.json   (metadata + embedding vector per verse)

Uses Gemini `gemini-embedding-001` (768 dims). No external vector DB — for a few hundred
verses, brute-force cosine similarity in NumPy at query time is plenty fast, fully
transparent, and commits cleanly to the repo. (Upgrade path: Supabase pgvector — see PLAN.md.)

Run:  python scripts/ingest.py
"""

import json
import os
import time
import urllib.request
import urllib.error

from dotenv import load_dotenv

load_dotenv()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS_FILE = os.path.join(ROOT, "corpus", "chanakya_niti.json")
OUT_FILE = os.path.join(ROOT, "corpus", "embeddings.json")

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
EMBED_MODEL = "gemini-embedding-001"
DIM = 768
BATCH = 20            # keep small to respect free-tier per-minute limits
PAUSE_BETWEEN = 6     # seconds between batches (free tier is rate-limited)


def batch_embed(texts: list[str]) -> list[list[float]]:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{EMBED_MODEL}:batchEmbedContents?key={API_KEY}"
    )
    body = {
        "requests": [
            {
                "model": f"models/{EMBED_MODEL}",
                "content": {"parts": [{"text": t}]},
                "taskType": "RETRIEVAL_DOCUMENT",
                "outputDimensionality": DIM,
            }
            for t in texts
        ]
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
    return [e["values"] for e in data["embeddings"]]


def main() -> None:
    if not API_KEY:
        raise SystemExit("GEMINI_API_KEY not set. Create .env from .env.example first.")

    with open(CORPUS_FILE, encoding="utf-8") as f:
        corpus = json.load(f)

    # Resume support: keep already-embedded ids if OUT_FILE exists.
    by_id = {}
    if os.path.exists(OUT_FILE):
        with open(OUT_FILE, encoding="utf-8") as f:
            for it in json.load(f).get("items", []):
                by_id[it["id"]] = it
        print(f"  resuming: {len(by_id)} already embedded")

    todo = [c for c in corpus if c["id"] not in by_id]
    print(f"  to embed: {len(todo)}")

    def save():
        items = [by_id[c["id"]] for c in corpus if c["id"] in by_id]
        out = {"model": EMBED_MODEL, "dim": DIM, "task": "RETRIEVAL_DOCUMENT", "items": items}
        with open(OUT_FILE, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)

    for start in range(0, len(todo), BATCH):
        chunk = todo[start:start + BATCH]
        texts = [c["translation"] for c in chunk]
        for attempt in range(5):
            try:
                vecs = batch_embed(texts)
                break
            except urllib.error.HTTPError as e:
                wait = 15 * (attempt + 1)  # 15, 30, 45, 60, 75
                print(f"  HTTP {e.code} on batch @{start}; retry in {wait}s")
                time.sleep(wait)
        else:
            save()
            raise SystemExit(f"Failed at batch {start}. Progress saved — just re-run to resume.")

        for c, v in zip(chunk, vecs):
            by_id[c["id"]] = {
                "id": c["id"],
                "text_type": c["text_type"],
                "chapter": c["chapter"],
                "verse": c["verse"],
                "citation": c["citation"],
                "translation": c["translation"],
                "embedding": [round(x, 6) for x in v],
            }
        save()
        print(f"  embedded {len(by_id)}/{len(corpus)}")
        time.sleep(PAUSE_BETWEEN)

    size_mb = os.path.getsize(OUT_FILE) / 1e6
    print(f"\nDone: {len(by_id)} embeddings -> {OUT_FILE} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
