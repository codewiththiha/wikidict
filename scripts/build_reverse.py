#!/usr/bin/env python3
"""Build REVERSED dictionaries from the English Wiktionary dump (kaikki.org).

Why reversed?
-------------
Foreign-language Wiktionary dumps (Japanese/French/Burmese pages) carry
verbose English *sentence* definitions. The **English** pages instead carry
a `translations` field: clean, word-level translations of each English word
into every language, with romanization and a sense label:

    {"word": "cat", "pos": "noun",
     "translations": [{"lang": "Burmese", "lang_code": "my",
                       "word": "ကြောင်", "roman": "kraung",
                       "sense": "domestic species"}, ...]}

So this script emits rows shaped like a real word dictionary — the same
schema as the clean HuggingFace english-myanmar dictionaries:

    word          English headword        (the bridge key)
    pos           part of speech
    definition    the word in the target language   <-- not a sentence!
    romanization  romaji / transliteration (ja, my)
    sense         which English sense this translation belongs to
    lang_code     ja / fr / my
    source        provenance

Outputs (one per language):
    output/eng-jp-words.parquet   output/eng-fr-words.parquet
    output/eng-mm-words.parquet

Usage:
    python scripts/build_reverse.py                # all three
    python scripts/build_reverse.py --langs ja my
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import date
from pathlib import Path

import pandas as pd

RAW_FILE = "English.jsonl"
SOURCE = "English Wiktionary translations (via kaikki.org)"

#: lang_code -> (output stem, script the translation must contain)
TARGETS = {
    "ja": ("eng-jp", r"[\u3040-\u30ff\u3400-\u9fff]"),   # kana / kanji
    "fr": ("eng-fr", r"[A-Za-zÀ-ÿ]"),                     # latin
    "my": ("eng-mm", r"[\u1000-\u109f]"),                 # Myanmar script
}

#: English POS values that are not real words worth translating
#: (phrases/verbs/nouns all have legitimate word-level translations, so
#:  only non-lexical categories are skipped)
SKIP_POS = {"abbrev", "soft-redirect", "romanization",
            "suffix", "prefix", "infix", "interfix", "affix",
            "symbol", "character", "punctuation", "letter", "diacritical",
            "circumfix", "combining_form"}

#: translation-level tags marking non-primary translations
SKIP_TR_TAGS = {"romanization", "alt-of", "form-of", "canonical"}

COLUMNS = ["word", "pos", "definition", "romanization", "sense",
           "lang_code", "source"]


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--langs", nargs="*", default=list(TARGETS),
                    help=f"lang codes to extract (choices: {', '.join(TARGETS)})")
    ap.add_argument("--rawdir", default="data/raw")
    ap.add_argument("--outdir", default="output")
    ap.add_argument("--include-pos", action="store_true",
                    help="also keep affix/symbol/phrase POS rows (default: skip)")
    args = ap.parse_args()

    targets = {lc: TARGETS[lc] for lc in args.langs if lc in TARGETS}
    for lc in args.langs:
        if lc not in TARGETS:
            raise SystemExit(f"unknown lang code '{lc}'")
    script_re = {lc: re.compile(pat) for lc, (_, pat) in targets.items()}

    src = Path(args.rawdir) / RAW_FILE
    if not src.exists():
        raise SystemExit(f"{src} not found — run: python scripts/download.py English")

    rows = {lc: [] for lc in targets}
    seen = {lc: set() for lc in targets}
    stats = {lc: {"translations": 0, "duplicates": 0, "bad_script": 0}
             for lc in targets}
    entries = 0
    t0 = time.time()

    with open(src, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            entries += 1
            if entries % 200_000 == 0:
                print(f"  ... {entries:,} entries scanned ({time.time()-t0:.0f}s)",
                      flush=True)
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            pos = obj.get("pos", "")
            if not args.include_pos and pos in SKIP_POS:
                continue
            word = (obj.get("word") or "").strip()
            if not word:
                continue

            # translations live top-level on some entries and/or per-sense
            all_trans = list(obj.get("translations") or [])
            for sense in obj.get("senses") or []:
                all_trans.extend(sense.get("translations") or [])

            for tr in all_trans:
                lc = tr.get("lang_code", "")
                if lc not in targets:
                    continue
                tw = (tr.get("word") or "").strip()
                if not tw:
                    continue
                if SKIP_TR_TAGS & set(tr.get("tags") or []):
                    continue
                if not script_re[lc].search(tw):
                    stats[lc]["bad_script"] += 1
                    continue

                roman = (tr.get("roman") or "").strip()
                sense = (tr.get("sense") or "").strip()
                if sense.lower() == "translations":  # template artifact
                    sense = ""
                key = (word.lower(), pos, tw, roman, sense)
                if key in seen[lc]:
                    stats[lc]["duplicates"] += 1
                    continue
                seen[lc].add(key)

                rows[lc].append({
                    "word": word,
                    "pos": pos,
                    "definition": tw,
                    "romanization": roman,
                    "sense": sense,
                    "lang_code": lc,
                    "source": SOURCE,
                })
                stats[lc]["translations"] += 1

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    import pyarrow as pa
    import pyarrow.parquet as pq

    print(f"\nscanned {entries:,} English entries in {time.time()-t0:.0f}s\n")
    for lc, (stem, _) in targets.items():
        df = pd.DataFrame(rows[lc], columns=COLUMNS)
        dest = outdir / f"{stem}-words.parquet"
        table = pa.Table.from_pandas(df, preserve_index=False)
        meta = {
            "dictionary": f"en-{lc}",
            "direction": "english word -> {lc} word",
            "preset": "words (reverse)",
            "word_language": "en",
            "target_language_code": lc,
            "source": SOURCE,
            "source_url": ("https://kaikki.org/dictionary/English/words/"
                           "kaikki.org-dictionary-English-words.jsonl"),
            "built_on": date.today().isoformat(),
        }
        table = table.replace_schema_metadata(meta)
        pq.write_table(table, dest, compression="zstd", row_group_size=100_000)
        st = stats[lc]
        print(f"[{lc}] kept {len(df):,} pairs "
              f"(dropped {st['duplicates']:,} duplicates, "
              f"{st['bad_script']:,} wrong-script), "
              f"{df['word'].nunique():,} unique English words")
        print(f"[{lc}] wrote {dest} ({dest.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
