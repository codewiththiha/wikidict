#!/usr/bin/env python3
"""Build an EN<->FR word dictionary from Princeton WordNet + WOLF.

Non-Wiktionary, NLP-mainstream sources:
  * Princeton WordNet 3.0 (English lemmas per synset, via NLTK)  - free license
  * WOLF = Wordnet Libre du Francais (French lemmas per synset,
    distributed by the Open Multilingual Wordnet as wn-data-fra.tab)

Every synset shared by both gives word-level pairs:
    English lemma  ->  French lemma   (+POS + the synset's English gloss)

Output schema matches the other curated files:
    word, pos, definition, romanization, sense, lang_code, source

Usage:
    python scripts/build_wordnet_fr.py
    python scripts/build_wordnet_fr.py --tab research/wn-data-fra.tab \
                                       --out output/curated/wordnet-en-fr.parquet
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

POS_NAMES = {"n": "noun", "v": "verb", "a": "adj", "s": "adj", "r": "adv"}

COLUMNS = ["word", "pos", "definition", "romanization", "sense",
           "lang_code", "source"]

SOURCE = "Princeton WordNet 3.0 + WOLF (Open Multilingual Wordnet)"


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tab", default="research/wn-data-fra.tab",
                    help="WOLF tab file (wn-data-fra.tab from omwn/omw-data)")
    ap.add_argument("--out", default="output/curated/wordnet-en-fr.parquet")
    args = ap.parse_args()

    from nltk.corpus import wordnet as wn

    tab = Path(args.tab)
    if not tab.exists():
        raise SystemExit(f"{tab} not found — download from "
                         "https://github.com/omwn/omw-data/raw/master/wns/fra/wn-data-fra.tab")

    # group French lemmas by synset
    fr_by_synset: dict[str, list[str]] = {}
    for line in tab.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        synset_id, lemma = parts[0].strip(), parts[2].strip()
        if synset_id and lemma:
            fr_by_synset.setdefault(synset_id, []).append(lemma)
    print(f"WOLF: {sum(len(v) for v in fr_by_synset.values()):,} French lemmas "
          f"across {len(fr_by_synset):,} synsets")

    rows: list[dict] = []
    seen: set[tuple] = set()
    missing = 0
    for synset_id, fr_lemmas in sorted(fr_by_synset.items()):
        try:
            ss = wn.synset_from_pos_and_offset(synset_id[-1], int(synset_id[:8]))
        except Exception:
            missing += 1
            continue
        pos = POS_NAMES.get(ss.pos(), ss.pos())
        gloss = ss.definition()
        for en in ss.lemma_names():
            en_clean = en.replace("_", " ").lower()
            for fr in fr_lemmas:
                key = (en_clean, pos, fr)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "word": en_clean,
                    "pos": pos,
                    "definition": fr,
                    "romanization": "",
                    "sense": gloss,
                    "lang_code": "fr",
                    "source": SOURCE,
                })

    df = pd.DataFrame(rows, columns=COLUMNS)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    import pyarrow as pa
    import pyarrow.parquet as pq
    table = pa.Table.from_pandas(df, preserve_index=False)
    table = table.replace_schema_metadata({
        "dictionary": "en-fr",
        "direction": "english word -> french word (WordNet + WOLF)",
        "preset": "curated (wordnet)",
        "word_language": "en",
        "target_language_code": "fr",
        "source": SOURCE,
        "source_url": "https://github.com/omwn/omw-data (wns/fra/wn-data-fra.tab)",
        "built_on": date.today().isoformat(),
    })
    pq.write_table(table, out, compression="zstd", row_group_size=100_000)

    print(f"synsets not resolved in WordNet: {missing}")
    print(f"kept {len(df):,} pairs, {df['word'].nunique():,} unique English words, "
          f"{df['definition'].nunique():,} unique French words")
    print(f"wrote {out} ({out.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
