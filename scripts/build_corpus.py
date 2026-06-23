"""
Build the Chanakya Niti corpus for RAG.

Source: gita/Datasets (public, github.com/gita/Datasets) — chanakya/Chanakya-Niti/
        17 chapter JSON files, each a list of {verse_id, text} (authentic English translation).

This fetches all 17 chapters and writes a single normalized corpus file:
    corpus/chanakya_niti.json

Each item is grounding-ready and carries its exact citation. Sanskrit / transliteration
fields are included but empty for now (Phase 3b will fill them from a verified source —
we deliberately do NOT auto-pair Sanskrit to avoid mis-citation).

Run:  python scripts/build_corpus.py
"""

import json
import os
import urllib.request

BASE = "https://raw.githubusercontent.com/gita/Datasets/main/chanakya/Chanakya-Niti"
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "corpus")
OUT_FILE = os.path.join(OUT_DIR, "chanakya_niti.json")


def fetch_chapter(n: int) -> list:
    url = f"{BASE}/chapter{n}.json"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    corpus = []
    for chapter in range(1, 18):
        verses = fetch_chapter(chapter)
        for v in verses:
            verse = str(v.get("verse_id", "")).strip()
            text = (v.get("text") or "").strip()
            if not text:
                continue
            corpus.append({
                "id": f"CN-{chapter}-{verse}",
                "text_type": "chanakya_niti",
                "chapter": chapter,
                "verse": verse,
                "citation": f"Chanakya Niti, Chapter {chapter}, Verse {verse}",
                "sanskrit": "",          # filled later (Phase 3b)
                "transliteration": "",   # filled later (Phase 3b)
                "translation": text,
            })
        print(f"  chapter {chapter:>2}: {len(verses)} verses")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(corpus)} verses -> {OUT_FILE}")


if __name__ == "__main__":
    main()
