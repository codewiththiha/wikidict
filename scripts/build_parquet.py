#!/usr/bin/env python3
"""Build clean English-bridge dictionary Parquet files from kaikki.org JSONL.

Input : data/raw/<Language>.jsonl   (one Wiktionary entry per line)
Output: output/eng-<code>-<preset>.parquet

Presets
-------
main   columns: word, pos, definition, ipa, romanization
       + WORD-ONLY filtering (rows whose definition is a sentence/phrase or
         contains non-English characters are removed)          [default]
all    columns: every column the pipeline extracts, unfiltered

Both presets are built by default, so each language produces two files,
e.g. eng-jp-main.parquet and eng-jp-all.parquet.

Word-only filter (how "words not sentences" is decided)
-------------------------------------------------------
A definition survives only if ALL of these hold:
  1. it contains no non-ASCII alphabetic characters
     (removes glosses that embed Japanese kana/kanji, Burmese script,
      French accented self-references like "inflection of tuméfier", ...)
  2. it matches none of the definitional-sentence patterns
     ("used to ...", "inflection of X", "plural of X", "synonym of X",
      "one who ...", "the act of ...", "romanization of X", ...)
  3. split on "," and ";", every segment is a short lexeme: at most
     MAX_SEG_TOKENS tokens (hyphenated compounds count as one) and
     ZERO function words (of/for/the/to/with/that/used/who/...).
     Hence "one, single", "rolling pin", "gross domestic product" pass,
     while "counter for floors or stories of a building" and
     "used to express that something was done in vain, for nothing" fail.

Usage:
    python scripts/build_parquet.py                    # all languages, both presets
    python scripts/build_parquet.py --presets main     # only the main preset
    python scripts/build_parquet.py --langs Japanese --presets all
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------
# datasets / presets
# --------------------------------------------------------------------------

DATASETS = {
    "Japanese": {"lang_code": "ja", "output": "eng-jp"},
    "French":   {"lang_code": "fr", "output": "eng-fr"},
    "Burmese":  {"lang_code": "my", "output": "eng-mm"},
}

COLUMNS = [
    "lang", "lang_code", "word", "pos", "sense_index", "definition",
    "raw_definition", "tags", "topics", "examples", "synonyms", "antonyms",
    "form_of", "alt_of", "ipa", "romanization", "etymology_text",
    "entry_id", "source",
]

PRESETS = {
    "main": {
        "columns": ["word", "pos", "definition", "ipa", "romanization"],
        "words_only": True,
    },
    "all": {
        "columns": COLUMNS,
        "words_only": False,
    },
}

#: POS values that are noise for a bilingual dictionary and dropped by default
DEFAULT_DROP_POS = {"romanization", "soft-redirect"}

SOURCE = "English Wiktionary (via kaikki.org)"

# --------------------------------------------------------------------------
# word-vs-sentence classification
# --------------------------------------------------------------------------

#: words that signal a descriptive sentence rather than a lexeme
FUNCTION_WORDS = frozenset("""
a an the
of for in on at to with by from into onto upon about above across after
against along amid among around before behind below beneath beside besides
between beyond during except inside near off outside over past since through
throughout till under underneath until unto up via within without against
and or but nor yet so if then than that which who whom whose what when where
why how because although though while unless
it its this these those there here he him his she her hers they them their
we us our you your someone anyone everyone something anything nothing
somebody anybody everybody oneself itself himself herself themselves
is are was were be been being have has had having do does did doing
can could may might must shall should will would used
""".split())

#: classic Wiktionary definitional sentences
PHRASE_BLACKLIST = re.compile(r"""
    \b(used|use)\s+(to|for)\b
  | \b(used|serves|serve|serving)\s+as\b
  | \binflection\s+of\b | \bform\s+of\b | \bconjugation\s+of\b
  | \bromanization\s+of\b | \btranscription\s+of\b | \bspelling\s+of\b
  | \balternative\s+(spelling|form|name|term)\b
  | \bshort\s+for\b | \bback[-\s]?formation\b
  | \b(diminutive|augmentative|plural|singular|feminine|masculine|neuter)\s+of\b
  | \b(past|present|future|perfect|imperfect|subjunctive|imperative|gerund|participle)\s+of\b
  | \b(synonyms?|antonyms?|hypernyms?|hyponyms?|meronyms?|holonyms?)\s+of\b
  | \b(initialism|acronym|abbreviation|clipping|ellipsis|contraction)\s+of\b
  | \bmisspelling\s+of\b | \bpronunciation\s+of\b | \beye\s+dialect\b
  | \bone\s+who\b | \bsomeone\s+who\b | \banyone\s+who\b
  | \ba\s+(person|man|woman|thing|place|group|member|type|kind|unit|form)\s+(who|that|which|of)\b
  | \bthe\s+(act|sound|state|process|practice|art|science|study|quality|
             condition|fact|instance|event|result|product|material|substance|
             number|amount|degree|extent|use|action|process)\s+of\b
  | \bin\s+order\s+to\b | \bso\s+as\s+to\b | \brefers?\s+to\b | \breferring\s+to\b
  | \bwith\s+(regard|respect)\s+to\b | \bsuch\s+as\b | \bas\s+well\s+as\b
  | \bin\s+the\s+sense\b | \bin\s+terms\s+of\b | \bin\s+vain\b
""", re.IGNORECASE | re.VERBOSE)

#: max tokens per comma/semicolon segment ("gross domestic product" = 3)
MAX_SEG_TOKENS = 4

#: hyphenated/apostrophe/dotted compounds count as ONE token
TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['’\-./&][A-Za-z0-9]+)*")


def has_non_english_letters(text: str) -> bool:
    """True if any alphabetic char is outside ASCII a-z/A-Z.

    Catches Japanese kana/kanji, Burmese script, accented French terms, etc.
    """
    return any(ch.isalpha() and ord(ch) > 127 for ch in text)


def wordlike_reason(definition: str) -> str | None:
    """Return None if the definition looks like word(s)/word-list,
    else a short reason code explaining why it was rejected."""
    d = definition.strip()
    if not d:
        return "empty"
    if has_non_english_letters(d):
        return "non_english_chars"
    if PHRASE_BLACKLIST.search(d):
        return "definitional_pattern"
    for seg in re.split(r"[;,]", d):
        seg = seg.strip().strip('“”"\'’‘')
        if not seg:
            continue
        toks = TOKEN_RE.findall(seg)
        if not toks:
            return "no_tokens"
        if len(toks) > MAX_SEG_TOKENS:
            return "too_many_tokens"
        if any(t.lower() in FUNCTION_WORDS for t in toks):
            return "function_words"
    return None


# --------------------------------------------------------------------------
# extraction helpers
# --------------------------------------------------------------------------

def join(values: list[str], sep: str = ", ") -> str:
    seen: dict[str, None] = {}
    for v in values:
        if v and v not in seen:
            seen[v] = None
    return sep.join(seen)


def words_of(items: list[dict]) -> list[str]:
    out = []
    for it in items or []:
        if isinstance(it, dict) and it.get("word"):
            out.append(str(it["word"]))
    return out


def entry_ipa(sounds: list[dict]) -> str:
    return join([s.get("ipa", "") for s in sounds or [] if s.get("ipa")],
                sep=" | ")


def entry_romanization(forms: list[dict]) -> str:
    for f in forms or []:
        if "romanization" in (f.get("tags") or []) and f.get("form"):
            return str(f["form"])
    return ""


def format_examples(examples: list[dict]) -> str:
    parts = []
    for ex in examples or []:
        text = (ex.get("text") or "").strip()
        if not text:
            continue
        transl = (ex.get("translation") or "").strip()
        parts.append(f"{text} -- {transl}" if transl else text)
    return join(parts, sep=" | ")


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def parse_file(path: Path, lang: str, drop_pos: set[str]) -> tuple[pd.DataFrame, dict]:
    stats = {
        "entries": 0, "dropped_pos": 0, "senses": 0,
        "senses_no_gloss": 0, "rows": 0,
        "with_ipa": 0, "with_rom": 0, "with_etym": 0,
        "pos_counts": {},
    }
    rows: list[dict] = []

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            stats["entries"] += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            pos = obj.get("pos", "")
            if pos in drop_pos:
                stats["dropped_pos"] += 1
                continue

            word = obj.get("word", "")
            ipa = entry_ipa(obj.get("sounds"))
            rom = entry_romanization(obj.get("forms"))
            etym = (obj.get("etymology_text") or "").strip()

            for idx, sense in enumerate(obj.get("senses") or []):
                stats["senses"] += 1
                glosses = sense.get("glosses") or []
                if not glosses:
                    stats["senses_no_gloss"] += 1
                    continue

                rows.append({
                    "lang": lang,
                    "lang_code": obj.get("lang_code", ""),
                    "word": word,
                    "pos": pos,
                    "sense_index": idx,
                    "definition": join([g.strip() for g in glosses], sep="; "),
                    "raw_definition": join(
                        [(g or "").strip() for g in sense.get("raw_glosses") or []],
                        sep="; "),
                    "tags": join(sense.get("tags") or []),
                    "topics": join(sense.get("topics") or []),
                    "examples": format_examples(sense.get("examples")),
                    "synonyms": join(words_of(sense.get("synonyms"))),
                    "antonyms": join(words_of(sense.get("antonyms"))),
                    "form_of": join(words_of(sense.get("form_of"))),
                    "alt_of": join(words_of(sense.get("alt_of"))),
                    "ipa": ipa,
                    "romanization": rom,
                    "etymology_text": etym,
                    "entry_id": sense.get("id", ""),
                    "source": SOURCE,
                })
                stats["rows"] += 1
                stats["with_ipa"] += bool(ipa)
                stats["with_rom"] += bool(rom)
                stats["with_etym"] += bool(etym)
                stats["pos_counts"][pos] = stats["pos_counts"].get(pos, 0) + 1

    df = pd.DataFrame(rows, columns=COLUMNS)
    stats["unique_words"] = df["word"].nunique() if len(df) else 0
    return df, stats


def apply_words_only(df: pd.DataFrame) -> tuple[pd.DataFrame, Counter, dict]:
    """Keep only rows whose definition looks like word(s), not a sentence."""
    reasons: Counter = Counter()
    examples: dict[str, list[str]] = {}
    keep_mask = []
    for d in df["definition"]:
        r = wordlike_reason(d)
        if r is None:
            keep_mask.append(True)
        else:
            reasons[r] += 1
            keep_mask.append(False)
            if len(examples.setdefault(r, [])) < 4 and d not in examples[r]:
                examples[r].append(d)
    kept = df[keep_mask]
    # word-lists as bridge keys: drop exact (word, pos, definition) duplicates
    kept = kept.drop_duplicates(subset=["word", "pos", "definition"])
    return kept, reasons, examples


def write_parquet(df: pd.DataFrame, dest: Path, meta: dict) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(df, preserve_index=False)
    table = table.replace_schema_metadata({k: str(v) for k, v in meta.items()})
    dest.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, dest, compression="zstd", row_group_size=100_000)


def build_preset(lang: str, cfg: dict, preset: str, pconf: dict,
                 df_full: pd.DataFrame, st: dict, outdir: Path) -> None:
    df = df_full
    filter_note = "no filter"
    if pconf["words_only"]:
        df, reasons, examples = apply_words_only(df)
        filter_note = "words-only filter"
        print(f"[{lang}/{preset}] words-only filter: "
              f"{st['rows']:,} -> {len(df):,} rows kept")
        for r, n in reasons.most_common():
            print(f"    rejected {r:<22} {n:>8,}")
            for ex in examples.get(r, [])[:2]:
                print(f"        e.g. {ex[:95]!r}")

    df = df[pconf["columns"]].copy()

    dest = outdir / f"{cfg['output']}-{preset}.parquet"
    meta = {
        "dictionary": f"en-{cfg['lang_code']}",
        "preset": preset,
        "word_language": lang,
        "word_language_code": cfg["lang_code"],
        "bridge_language": "en",
        "filter": filter_note,
        "source": SOURCE,
        "source_url": (f"https://kaikki.org/dictionary/{lang}/words/"
                       f"kaikki.org-dictionary-{lang}-words.jsonl"),
        "built_on": date.today().isoformat(),
        "row_granularity": "one row per (word, pos, sense)",
    }
    write_parquet(df, dest, meta)
    print(f"[{lang}/{preset}] wrote {dest} "
          f"({dest.stat().st_size/1e6:.1f} MB, {len(df):,} rows)\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--langs", nargs="*", default=list(DATASETS),
                    help=f"datasets to build (choices: {', '.join(DATASETS)})")
    ap.add_argument("--presets", default=",".join(PRESETS),
                    help=f"comma-separated presets: {', '.join(PRESETS)} (default: both)")
    ap.add_argument("--rawdir", default="data/raw")
    ap.add_argument("--outdir", default="output")
    ap.add_argument("--drop-pos", default=",".join(sorted(DEFAULT_DROP_POS)),
                    help="comma-separated POS values to skip "
                         "(default: romanization,soft-redirect)")
    ap.add_argument("--keep-all", action="store_true",
                    help="disable POS filtering entirely")
    args = ap.parse_args()

    presets = [p.strip() for p in args.presets.split(",") if p.strip()]
    for p in presets:
        if p not in PRESETS:
            raise SystemExit(f"unknown preset '{p}' (choices: {', '.join(PRESETS)})")

    drop_pos = set() if args.keep_all else {p.strip() for p in args.drop_pos.split(",") if p.strip()}
    outdir = Path(args.outdir)

    for lang in args.langs:
        cfg = DATASETS.get(lang)
        if cfg is None:
            raise SystemExit(f"unknown language '{lang}' (choose from {', '.join(DATASETS)})")
        src = Path(args.rawdir) / f"{lang}.jsonl"
        if not src.exists():
            print(f"[{lang}] SKIP: {src} not found (run scripts/download.py first)")
            continue

        t0 = time.time()
        print(f"[{lang}] parsing {src} ...")
        df_full, st = parse_file(src, lang, drop_pos)
        print(f"[{lang}] entries={st['entries']:,}  senses={st['senses']:,}  "
              f"rows={st['rows']:,}  unique words={st['unique_words']:,}  "
              f"({time.time()-t0:.1f}s)")

        for preset in presets:
            build_preset(lang, cfg, preset, PRESETS[preset], df_full, st, outdir)


if __name__ == "__main__":
    main()
