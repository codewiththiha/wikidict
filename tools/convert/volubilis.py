"""Volubilis, the multilingual Thai database: English → Thai."""

from __future__ import annotations

import re
from pathlib import Path

import openpyxl

from lib import gloss

# Volubilis TYPE codes, read by their first label: "n. exp." is a noun.
POS = {
    "n.": "noun", "n": "noun", "v.": "verb", "adj.": "adjective",
    "adv.": "adverb", "pr.": "pronoun", "prep.": "preposition",
    "conj.": "conjunction", "interj.": "interjection", "excl.": "interjection",
    "onomat.": "interjection", "num.": "number", "classif.": "classifier",
    "pref.": "prefix", "suff.": "suffix", "abv.": "abbreviation",
    "acron.": "abbreviation", "part.": "particle", "art.": "article",
    "aux.": "auxiliary", "xp": "phrase", "loc.": "phrase", "prov.": "proverb",
    "org.": "name", "[TM]": "name",
}
PROPER = "n. prop."
# USAGE labels, spelled out for the sense line.
USAGE = {
    "obsol.": "obsolete", "oral": "spoken", "poet.": "poetic",
    "reg.": "regional", "inf.": "informal", "vulg.": "vulgar",
    "f.": "said by women", "m.": "said by men", "form.": "formal",
    "pej.": "pejorative", "relig.": "religious", "lit.": "literary",
    "neo.": "neologism", "fam.": "familiar", "royal": "royal",
    "idiom.": "idiom",
}
# Royal Institute tag: literary words carry it too, so it isn't a domain.
ROYAL_INSTITUTE = "RID"
COLUMNS = {"THAIROM": "roman", "THA": "thai", "ENG": "english",
           "TYPE": "type", "USAGE": "usage", "DOM": "domain",
           "FRA": "french", "THAIPHON": "phonetic"}
VERSION = re.compile(r"v\. ?[\d.]+ \([^)]*\)")


def _pos(code: str | None) -> str | None:
    if not code:
        return None
    code = code.strip()
    if code.startswith(PROPER):
        return "name"
    return POS.get(code.split()[0].strip("()"), "other")


def _usage(text: str | None) -> str | None:
    """"(reg., Isan)" as "regional, Isan"."""
    if not text:
        return None
    labels = [t.strip() for t in re.split(r"[,–-]", text.strip("() "))]
    return ", ".join(USAGE.get(t, t) for t in labels if t) or None


def _richness(line: tuple, at: dict) -> int:
    """How fully a row is described; everyday words carry the most."""
    domains = [d.strip() for d in str(line[at["domain"]] or "").split(";")]
    return (bool(line[at["french"]]) + bool(line[at["phonetic"]])
            + sum(1 for d in domains if d and d != ROYAL_INSTITUTE))


# A second romanization in brackets: "nām [=nam]".
_ALTERNATE = re.compile(r"\s*\[\s*=[^\]]*\]")


def _forms(cell: object) -> list[str]:
    """The spellings in a cell: "a ; b" is two; "x = y" keeps x."""
    text = _ALTERNATE.sub("", str(cell or ""))
    return [part.split(" = ")[0].strip()
            for part in gloss.split(text) if part.strip()]


def convert(files: dict[str, Path], packs: list[dict]) -> dict:
    [pack] = packs
    book = openpyxl.load_workbook(files["volubilis.xlsx"], read_only=True)
    sheet = book.worksheets[0]
    lines = sheet.iter_rows(values_only=True)
    title = " ".join(str(c) for c in next(lines) if c)
    header = [str(c or "").split("\n")[0].split(" ")[0] for c in next(lines)]
    at = {key: header.index(col) for col, key in COLUMNS.items()}
    rows = []
    for line in lines:
        thais, english = _forms(line[at["thai"]]), line[at["english"]]
        if not thais or not english:
            continue
        romans = _forms(line[at["roman"]])
        if len(romans) != len(thais):
            romans = romans[:1] * len(thais)
        pos = _pos(line[at["type"]])
        usage = _usage(line[at["usage"]])
        richness = _richness(line, at)
        for index, piece in enumerate(gloss.split(str(english))):
            found = gloss.headword(piece)
            if not found:
                continue
            word, notes = found
            for thai, roman in zip(thais, romans):
                rows.append({
                    "word": word,
                    "pos": pos,
                    "definition": thai,
                    "romanization": roman,
                    "sense": gloss.sense(notes, usage),
                    "rank": (usage is not None, -richness, index, len(thai)),
                })
    found = VERSION.search(title)
    version = f"Volubilis {found.group(0) if found else title}"
    return {pack["id"]: (rows, {"version": version})}
