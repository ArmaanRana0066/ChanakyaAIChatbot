"""
Enrich the corpus with Sanskrit (Devanagari) + IAST transliteration.

Source: sanskritdocuments.org "chANakyanItisort" ITRANS file (public, personal-study use).
The Sanskrit recension differs slightly from our English (gita/Datasets) corpus, so we ONLY
attach Sanskrit to chapters whose verse counts match EXACTLY and were verified verse-by-verse
(chapters 1, 2, 6, 7, 12) plus chapter 4 verses 1-17 (the aligned head, incl. the famous 4.15).
Other verses keep empty sanskrit/transliteration — accuracy over completeness, never mis-cite.

Run:  python scripts/add_sanskrit.py
"""

import json
import os
import re
import urllib.request

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "corpus", "chanakya_niti.json")
ITX_URL = "https://sanskritdocuments.org/doc_z_misc_major_works/chANakyanItisort.itx"

# Chapters safe to index-align (verse counts match the English corpus exactly).
SAFE_CHAPTERS = {1, 2, 6, 7, 12}
# Chapter 4 aligns for the head only (verified through v17, includes 4.15).
CH4_MAX_VERSE = 17


def fetch_itx() -> str:
    req = urllib.request.Request(ITX_URL, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def parse_verses(content: str) -> dict:
    """Return {(chapter, verse): itrans_text} parsed from the .itx file."""
    content = content.replace("\\", "")  # the file escapes hyphens as 01\-01
    # Split on the chapter-verse markers, keeping the captured numbers.
    parts = re.split(r"\|\|\s*(\d\d)-(\d\d)", content)
    verses = {}
    # parts = [text0, ch, v, text1, ch, v, ...]; text at index 3k belongs to marker 3k+1/3k+2
    for k in range(0, (len(parts) - 1) // 3):
        seg = parts[3 * k]
        ch = int(parts[3 * k + 1])
        v = int(parts[3 * k + 2])
        # The verse is the last up-to-2 non-empty lines before the marker.
        lines = [ln.strip() for ln in seg.splitlines() if ln.strip() and not ln.strip().startswith("%")]
        verse_lines = lines[-2:] if len(lines) >= 2 else lines
        text = " ".join(verse_lines).strip().rstrip("|").strip()
        if text:
            verses[(ch, v)] = text
    return verses


def is_aligned(ch: int, v: int) -> bool:
    if ch in SAFE_CHAPTERS:
        return True
    if ch == 4 and v <= CH4_MAX_VERSE:
        return True
    return False


def main() -> None:
    verses = parse_verses(fetch_itx())
    print(f"  parsed {len(verses)} Sanskrit verses from sanskritdocuments")

    with open(CORPUS, encoding="utf-8") as f:
        corpus = json.load(f)

    filled = 0
    for item in corpus:
        ch, v = item["chapter"], int(item["verse"])
        if not is_aligned(ch, v):
            continue
        itrans = verses.get((ch, v))
        if not itrans:
            continue
        item["sanskrit"] = transliterate(itrans, sanscript.ITRANS, sanscript.DEVANAGARI)
        item["transliteration"] = transliterate(itrans, sanscript.ITRANS, sanscript.IAST)
        item["sanskrit_source"] = f"sanskritdocuments.org chANakyanItisort {ch:02d}-{v:02d}"
        filled += 1

    with open(CORPUS, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=2)
    print(f"  filled Sanskrit for {filled} verses -> {CORPUS}")

    # Sanity check the flagship verse.
    cn415 = next((c for c in corpus if c["id"] == "CN-4-15"), None)
    if cn415:
        print("  CN-4-15 sanskrit:", cn415["sanskrit"][:60], "...")


if __name__ == "__main__":
    main()
