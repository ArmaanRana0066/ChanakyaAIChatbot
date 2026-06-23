"""
Retrieval for "Ask the Shastra".

Loads the local vector store (corpus/embeddings.json) once at startup, embeds the user's
query with Gemini, and returns the top-k most similar verses by cosine similarity.

No external vector DB: for a few hundred verses a NumPy dot-product is sub-millisecond.
"""

import json
import os

import httpx
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMB_FILE = os.path.join(ROOT, "corpus", "embeddings.json")
EMBED_MODEL = "gemini-embedding-001"


def _normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class VectorStore:
    """Lazy-loaded, in-memory cosine-similarity store."""

    def __init__(self) -> None:
        self.ready = False
        self.items: list[dict] = []
        self.matrix: np.ndarray | None = None
        self.dim = 0

    def load(self) -> None:
        if self.ready:
            return
        if not os.path.exists(EMB_FILE):
            return  # RAG simply stays off until ingest.py has been run
        with open(EMB_FILE, encoding="utf-8") as f:
            data = json.load(f)
        self.dim = data.get("dim", 768)
        self.items = data["items"]
        mat = np.array([it["embedding"] for it in self.items], dtype=np.float32)
        self.matrix = _normalize(mat)
        self.ready = True

    @property
    def available(self) -> bool:
        self.load()
        return self.ready and self.matrix is not None and len(self.items) > 0


STORE = VectorStore()


async def _embed_query(text: str, api_key: str) -> np.ndarray | None:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{EMBED_MODEL}:embedContent?key={api_key}"
    )
    body = {
        "model": f"models/{EMBED_MODEL}",
        "content": {"parts": [{"text": text}]},
        "taskType": "RETRIEVAL_QUERY",
        "outputDimensionality": STORE.dim or 768,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=body, headers={"Content-Type": "application/json"})
            if resp.status_code != 200:
                return None
            vals = resp.json().get("embedding", {}).get("values")
            if not vals:
                return None
            v = np.array(vals, dtype=np.float32)
            n = np.linalg.norm(v)
            return v / n if n else v
    except httpx.RequestError:
        return None


async def retrieve(query: str, api_key: str, k: int = 4, min_score: float = 0.35) -> list[dict]:
    """Return up to k verses most relevant to the query, each with a similarity score."""
    if not STORE.available:
        return []
    qv = await _embed_query(query, api_key)
    if qv is None:
        return []
    scores = STORE.matrix @ qv  # cosine (both normalized)
    top_idx = np.argsort(-scores)[:k]
    results = []
    for i in top_idx:
        score = float(scores[i])
        if score < min_score:
            continue
        it = STORE.items[int(i)]
        results.append({
            "id": it["id"],
            "citation": it["citation"],
            "chapter": it["chapter"],
            "verse": it["verse"],
            "translation": it["translation"],
            "score": round(score, 4),
        })
    return results
