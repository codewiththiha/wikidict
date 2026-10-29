"""NIKL's Basic Korean Dictionary (krdict) XML: English → Korean."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from lib import gloss

ENGLISH = "영어"
POS = {
    "명사": "noun", "의존 명사": "noun", "대명사": "pronoun", "수사": "number",
    "동사": "verb", "형용사": "adjective", "보조 동사": "auxiliary",
    "보조 형용사": "auxiliary", "부사": "adverb", "관형사": "determiner",
    "조사": "particle", "감탄사": "interjection", "접사": "prefix",
    "어미": "suffix",
}
# Learner levels: beginner, intermediate, advanced; unlevelled come last.
LEVELS = {"초급": 0, "중급": 1, "고급": 2}
# Grammar entries ("-는데") gloss endings, not words.
SKIP_UNITS = {"문법·표현"}


# The 2019 dump has a raw "<" inside one value.
_VALUE = re.compile(r'(val=")(.*)("\s*/>)')


def _nodes(path: Path):
    """Each element of `path` as it closes, with raw "<" in values escaped."""
    parser = ET.XMLPullParser(events=("end",))
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = _VALUE.sub(lambda m: m.group(1) + m.group(2).replace("<", "&lt;")
                              + m.group(3), line)
            parser.feed(line)
            for _, node in parser.read_events():
                yield node
    parser.close()


def _feats(node: ET.Element) -> dict[str, str]:
    return {f.get("att"): f.get("val") for f in node.findall("feat")}


def convert(files: dict[str, Path], packs: list[dict]) -> dict:
    [pack] = packs
    rows, made = [], None
    for name in sorted(files, key=lambda n: int(n.split("-")[1].split(".")[0])):
        for node in _nodes(files[name]):
            if node.tag == "feat" and node.get("att") == "creationDate":
                made = node.get("val", "")[:10].replace("/", "-")
            if node.tag != "LexicalEntry":
                continue
            entry = _feats(node)
            lemma = node.find("Lemma")
            written = _feats(lemma).get("writtenForm") if lemma is not None else None
            if written and entry.get("lexicalUnit") not in SKIP_UNITS:
                pos = POS.get(entry.get("partOfSpeech", ""))
                if entry.get("partOfSpeech") == "접사" and written.startswith("-"):
                    pos = "suffix"
                level = LEVELS.get(entry.get("vocabularyLevel", ""), len(LEVELS))
                for index, sense in enumerate(node.findall("Sense")):
                    for eq in sense.findall("Equivalent"):
                        feats = _feats(eq)
                        if feats.get("language") != ENGLISH:
                            continue
                        for piece in gloss.split(feats.get("lemma") or ""):
                            found = gloss.headword(piece)
                            if not found:
                                continue
                            word, notes = found
                            rows.append({
                                "word": word,
                                "pos": pos,
                                "definition": written,
                                "sense": gloss.sense(notes, feats.get("definition")),
                                "rank": (level, index),
                            })
            node.clear()
    version = f"krdict XML of {made or 'unknown date'}"
    return {pack["id"]: (rows, {"version": version})}
