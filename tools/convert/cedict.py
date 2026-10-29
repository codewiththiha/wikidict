"""CC-CEDICT, read backwards: English → Chinese (simplified), with pinyin."""

from __future__ import annotations

import gzip
import re
from pathlib import Path

from lib import gloss

LINE = re.compile(r"^(\S+) (\S+) \[([^\]]*)\] /(.*)/\s*$")
# Glosses that point elsewhere or describe the entry instead of meaning it.
POINTERS = re.compile(
    r"^(?:(?:old |archaic |erhua |Japanese |ancient )?variant of|see |"
    r"see also |surname |abbr\. (?:for|of|to) |CL:|Taiwan pr\.|also pr\.|"
    r"used in |(?:also )?written |pr\. |pinyin |classifier for )",
    re.IGNORECASE,
)
# Notes that mark a word few readers want first.
DATED = re.compile(r"\b(?:old|archaic|literary|classical|dialect|variant|"
                   r"Cantonese|obsolete)\b", re.IGNORECASE)
_SYLLABLE = re.compile(r"([A-Za-zü:]+)([1-5])")
_MARKS = {
    "a": "āáǎà", "e": "ēéěè", "i": "īíǐì", "o": "ōóǒò", "u": "ūúǔù",
    "ü": "ǖǘǚǜ",
}


def _mark(syllable: str, tone: int) -> str:
    """One pinyin syllable with its tone mark: ("hao", 3) is "hǎo"."""
    s = syllable.replace("u:", "ü").replace("v", "ü")
    if tone == 5:
        return s
    low = s.lower()
    if "a" in low:
        at = low.index("a")
    elif "e" in low:
        at = low.index("e")
    elif "ou" in low:
        at = low.index("o")
    else:
        vowels = [i for i, ch in enumerate(low) if ch in _MARKS]
        if not vowels:
            return s
        at = vowels[-1]
    marked = _MARKS[low[at]][tone - 1]
    if s[at].isupper():
        marked = marked.upper()
    return s[:at] + marked + s[at + 1:]


def pinyin(numbered: str) -> str:
    """CEDICT's "ni3 hao3" as "nǐ hǎo"."""
    return _SYLLABLE.sub(lambda m: _mark(m.group(1), int(m.group(2))),
                         numbered)


def _rare(text: str) -> bool:
    """Whether `text` uses characters outside the basic CJK block."""
    return any(0x3400 <= ord(ch) <= 0x4DBF or ord(ch) >= 0x20000 for ch in text)


def convert(files: dict[str, Path], packs: list[dict]) -> dict:
    [pack] = packs
    rows, dated = [], "unknown date"
    with gzip.open(files["cedict.txt.gz"], "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#! date="):
                dated = line.split("=", 1)[1].strip()[:10]
            m = LINE.match(line)
            if not m:
                continue
            traditional, simplified, numbered, glosses = m.groups()
            reading = pinyin(numbered)
            other = f"Traditional {traditional}" if traditional != simplified else None
            rare = _rare(simplified)
            for index, text in enumerate(glosses.split("/")):
                if not text or POINTERS.match(text):
                    continue
                verb = text.lower().startswith("to ")
                for piece in gloss.split(text):
                    found = gloss.headword(piece)
                    if not found:
                        continue
                    word, notes = found
                    rows.append({
                        "word": word,
                        "pos": "verb" if verb else None,
                        "definition": simplified,
                        "romanization": reading,
                        "sense": gloss.sense(notes, other),
                        "rank": (rare, bool(DATED.search(text)), index,
                                 len(simplified)),
                    })
    return {pack["id"]: (rows, {"version": f"CC-CEDICT of {dated}"})}
