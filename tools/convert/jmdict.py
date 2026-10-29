"""JMdict (jmdict-simplified's JSON), read backwards: English → Japanese."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

from lib import gloss

POS = {
    "n": "noun", "n-adv": "noun", "n-pref": "prefix", "n-suf": "suffix",
    "n-t": "noun", "n-pr": "name", "num": "number", "ctr": "counter",
    "pn": "pronoun", "int": "interjection", "conj": "conjunction",
    "adv": "adverb", "adv-to": "adverb", "pref": "prefix", "suf": "suffix",
    "prt": "particle", "aux": "auxiliary", "aux-v": "auxiliary",
    "aux-adj": "auxiliary", "cop": "auxiliary", "exp": "phrase",
    "unc": "other",
}
# Usually written in kana alone: the kana is the word to show.
KANA_ALONE = "uk"


def _pos(codes: list[str]) -> str | None:
    for code in codes:
        if code in POS:
            return POS[code]
        for prefix, word in (("v", "verb"), ("adj", "adjective"),
                             ("adv", "adverb"), ("n", "noun")):
            if code.startswith(prefix):
                return word
        return "other"
    return None


def _entries(text: str):
    """Each object of the top-level "words" array, decoded one at a time."""
    decoder = json.JSONDecoder()
    at = text.index("[", text.index('"words"')) + 1
    while True:
        while text[at] in " \t\r\n,":
            at += 1
        if text[at] == "]":
            return
        entry, at = decoder.raw_decode(text, at)
        yield entry


def convert(files: dict[str, Path], packs: list[dict]) -> dict:
    [pack] = packs
    with tarfile.open(files["jmdict-eng.json.tgz"]) as tar:
        member = next(m for m in tar.getmembers() if m.name.endswith(".json"))
        text = tar.extractfile(member).read().decode("utf-8")
    head = json.loads(text[: text.index('"words"')].rstrip(", \n") + "}")
    rows = []
    for entry in _entries(text):
        kanji = [k["text"] for k in entry.get("kanji") or []]
        kana = [k["text"] for k in entry.get("kana") or []]
        if not kana:
            continue
        common = any(k.get("common") for k in
                     (entry.get("kanji") or []) + (entry.get("kana") or []))
        for index, sense in enumerate(entry.get("sense") or []):
            alone = KANA_ALONE in (sense.get("misc") or []) or not kanji
            written = kana[0] if alone else kanji[0]
            pos = _pos(sense.get("partOfSpeech") or [])
            for g in sense.get("gloss") or []:
                if g.get("lang") != "eng":
                    continue
                for piece in gloss.split(g.get("text") or ""):
                    found = gloss.headword(piece)
                    if not found:
                        continue
                    word, notes = found
                    rows.append({
                        "word": word,
                        "pos": pos,
                        "definition": written,
                        "romanization": None if written == kana[0] else kana[0],
                        "sense": gloss.sense(notes),
                        "rank": (not common, index, len(written)),
                    })
    version = f"JMdict {head.get('version')} ({head.get('dictDate')})"
    return {pack["id"]: (rows, {"version": version})}
