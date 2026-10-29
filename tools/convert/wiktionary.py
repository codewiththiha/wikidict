"""English Wiktionary's translation tables, via kaikki.org's extract.

Each English entry lists word-level translations per sense, so one pass
over the dump yields every English→X pack at once.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from lib import langs
from lib.fetch import receipt

# Entries that aren't words anyone translates.
SKIP_POS = {
    "abbrev", "soft-redirect", "romanization", "suffix", "prefix", "infix",
    "interfix", "affix", "circumfix", "combining_form", "symbol",
    "character", "punctuation", "letter", "diacritical",
}
# Translations that are spellings or readings of another, not words.
SKIP_TAGS = {"romanization", "alt-of", "form-of", "canonical"}

# Grammatical tags shown in the sense without marking the word unusual.
GRAMMAR = {"masculine", "feminine", "neuter", "common-gender", "plural",
           "singular", "animate", "inanimate", "perfective", "imperfective"}

POS = {
    "noun": "noun", "verb": "verb", "adj": "adjective", "adv": "adverb",
    "name": "name", "pron": "pronoun", "prep": "preposition",
    "postp": "postposition", "conj": "conjunction", "intj": "interjection",
    "det": "determiner", "article": "article", "num": "number",
    "particle": "particle", "contraction": "contraction",
    "proverb": "proverb", "phrase": "phrase", "prep_phrase": "phrase",
    "adv_phrase": "phrase", "classifier": "classifier", "counter": "counter",
}


def _translations(entry: dict):
    yield from entry.get("translations") or []
    for sense in entry.get("senses") or []:
        yield from sense.get("translations") or []


def _sense(tr: dict) -> tuple[str | None, bool]:
    """The sense line for a translation, and whether it is marked unusual."""
    tags = [t for t in tr.get("tags") or [] if t not in SKIP_TAGS]
    marked = [t.replace("-", " ") for t in tags if t not in GRAMMAR]
    grammar = [t for t in tags if t in GRAMMAR]
    sense = (tr.get("sense") or "").strip()
    if sense.lower() == "translations":
        sense = ""
    literal = (tr.get("english") or "").strip()
    parts = [sense, *marked, *grammar, f"literally {literal}" if literal else ""]
    return "; ".join(p for p in parts if p) or None, bool(marked)


def convert(files: dict[str, Path], packs: list[dict]) -> dict:
    dump = files["English.jsonl.gz"]
    wanted = {p["options"]["lang_code"]: p for p in packs}
    names = {code: langs.name(p["to"]) for code, p in wanted.items()}
    scripts = {code: langs.script(p["to"]) for code, p in wanted.items()}
    rows: dict[str, list[dict]] = {code: [] for code in wanted}
    with gzip.open(dump, "rt", encoding="utf-8") as fh:
        for line in fh:
            entry = json.loads(line)
            pos = entry.get("pos", "")
            word = (entry.get("word") or "").strip()
            if pos in SKIP_POS or not word:
                continue
            for tr in _translations(entry):
                code = tr.get("lang_code")
                target = (tr.get("word") or "").strip()
                if code not in wanted or not target:
                    continue
                if tr.get("lang") != names[code]:
                    continue
                if SKIP_TAGS & set(tr.get("tags") or []):
                    continue
                if not scripts[code].search(target):
                    continue
                sense, marked = _sense(tr)
                rows[code].append({
                    "word": word,
                    "pos": POS.get(pos, "other"),
                    "definition": target,
                    "romanization": tr.get("roman"),
                    "sense": sense,
                    "rank": marked,
                })
    dated = receipt(dump).get("modified", "unknown date")
    version = f"English Wiktionary extract of {dated}"
    return {p["id"]: (rows[code], {"version": version})
            for code, p in wanted.items()}
