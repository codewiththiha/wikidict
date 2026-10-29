"""The MCF NLP English–Myanmar word list, via its Hugging Face copy."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

POS = {
    "n": "noun", "ns": "noun", "v": "verb", "vs": "verb",
    "adj": "adjective", "adjs": "adjective", "adv": "adverb",
    "advs": "adverb", "indefadv": "adverb", "advpart": "particle",
    "prep": "preposition", "pron": "pronoun", "indefpron": "pronoun",
    "pers": "pronoun", "possess": "determiner", "det": "determiner",
    "indefdet": "determiner", "indefart": "article", "conj": "conjunction",
    "interj": "interjection", "pref": "prefix", "suff": "suffix",
    "symb": "symbol", "abbr": "abbreviation",
}


def convert(files: dict[str, Path], packs: list[dict]) -> dict:
    [pack] = packs
    table = pq.read_table(files["mcfnlp.parquet"])
    rows = [
        {
            "word": (row["word"] or "").replace("\\/", "/"),
            "pos": POS.get((row["pos"] or "").strip().lower(), "other")
            if row["pos"] else None,
            "definition": row["definition"],
        }
        for row in table.to_pylist()
    ]
    return {pack["id"]: (rows, {"version": pack["version"]})}
