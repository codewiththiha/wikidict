"""English glosses into English headwords, for dictionaries read backwards.

A source that explains foreign words in English ("to love; to be fond of")
becomes an English-headed pack by turning each gloss into the word a reader
would look up ("love", "be fond of"), keeping what was cut as the sense.
"""

from __future__ import annotations

import re

# More words than this is a description, not a headword anyone looks up.
MAX_WORDS = 5

_BRACKETS = re.compile(r"\s*[(\[]([^()\[\]]*)[)\]]\s*")
_LEADING = re.compile(r"^(?:to|a|an|the)\s+(?=\S)", re.IGNORECASE)
_EDGE = " \t,;:.!?…\"'“”‘’"
_LETTER = re.compile(r"[A-Za-z]")
_NOT_ENGLISH = re.compile(r"[^\x00-\x7f’‘“”–—…éèàçïöüñ]")


def split(text: str, seps: str = ";") -> list[str]:
    """`text` cut at each of `seps` outside brackets, pieces stripped."""
    out, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch in "([":
            depth += 1
        elif ch in ")]" and depth:
            depth -= 1
        elif ch in seps and not depth:
            out.append(text[start:i])
            start = i + 1
    out.append(text[start:])
    return [p.strip() for p in out if p.strip()]


def headword(gloss: str) -> tuple[str, str] | None:
    """The headword in `gloss` and the notes cut from it; None if none.

    "to run (of a machine)" is ("run", "of a machine"); a gloss that is only
    a note, a sentence or not English is None.
    """
    notes = [n.strip() for n in _BRACKETS.findall(gloss) if n.strip()]
    word = _BRACKETS.sub(" ", gloss)
    word = " ".join(word.split()).strip(_EDGE)
    word = _LEADING.sub("", word).strip(_EDGE)
    if not word or not _LETTER.search(word) or _NOT_ENGLISH.search(word):
        return None
    if len(word.split()) > MAX_WORDS:
        return None
    return word, "; ".join(notes)


def sense(*parts: str | None) -> str | None:
    """The non-empty `parts` joined as one sense line."""
    kept = [p.strip() for p in parts if p and p.strip()]
    return "; ".join(dict.fromkeys(kept)) or None
