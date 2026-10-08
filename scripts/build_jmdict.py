#!/usr/bin/env python3
"""Convert JMdict (Japanese<->English) JSON into a reversed Parquet table.

JMdict ships Japanese-headword -> English-gloss. For the English-as-bridge
dictionary app we reverse it so English is the key. The output keeps ONLY
the three columns the app needs:

    word          English gloss text      (the bridge key)
    pos           single mapped part of speech (noun/verb/adj/adv/...)
    definition    the Japanese word (kanji if present, else kana)

One row per (English gloss, pos, Japanese word); exact duplicates collapsed.

Usage:
    python scripts/build_jmdict.py
    python scripts/build_jmdict.py --src research/jmdict-eng-3.6.2.json \
                                   --out output/curated/jmdict-en-jp.parquet
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

import pandas as pd

SOURCE_PREFIX = "JMdict"

COLUMNS = ["word", "pos", "definition"]

#: JMdict POS code -> broad category (bridging-friendly)
POS_MAP = {
    "n": "noun", "n-adv": "noun", "n-pref": "noun", "n-suf": "noun",
    "n-t": "noun", "n-pr": "name", "n-adj": "noun",
    "num": "num", "ctr": "counter", "pn": "pron", "int": "intj",
    "conj": "conj", "adv": "adv", "adv-to": "adv",
    "pref": "prefix", "suf": "suffix", "prt": "particle",
    "aux": "aux", "aux-v": "aux", "aux-adj": "aux", "cop": "cop",
    "exp": "phrase", "vs": "verb", "vs-c": "verb", "vs-i": "verb",
    "vs-s": "verb", "unc": "other",
}


def map_pos(codes: list[str]) -> str:
    """Map JMdict POS codes to ONE broad category.

    JMdict lists multiple POS tags per sense in priority order; we keep only
    the primary one so every row carries a single bridge-friendly tag
    (noun / verb / adj / adv / ...) like all the other files.
    """
    for c in codes or []:
        m = POS_MAP.get(c)
        if m is None:
            if c.startswith("v"):
                m = "verb"
            elif c.startswith("adj"):
                m = "adj"
            elif c.startswith("adv"):
                m = "adv"
            elif c.startswith("n"):
                m = "noun"
            else:
                m = "other"
        return m
    return ""


def head_and_reading(entry: dict) -> tuple[str, str]:
    """Return (definition=Japanese word, romanization=kana reading)."""
    kanji = [k.get("text", "") for k in entry.get("kanji") or [] if k.get("text")]
    kana = [k.get("text", "") for k in entry.get("kana") or [] if k.get("text")]
    if kanji:
        return kanji[0], (kana[0] if kana else "")
    if kana:
        return kana[0], kana[0]
    return "", ""


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default="research/jmdict-eng-3.6.2.json",
                    help="path to the jmdict-eng JSON file")
    ap.add_argument("--out", default="output/curated/jmdict-en-jp.parquet")
    args = ap.parse_args()

    src = Path(args.src)
    if not src.exists():
        raise SystemExit(f"{src} not found — download JMdict from "
                         "https://github.com/scriptin/jmdict-simplified/releases")

    t0 = time.time()
    with open(src, encoding="utf-8") as fh:
        data = json.load(fh)

    version = data.get("version", "?")
    dict_date = data.get("dictDate", "")
    source = f"{SOURCE_PREFIX} {version} ({dict_date})"
    words = data.get("words") or []
    print(f"loaded {len(words):,} JMdict entries ({version}, {dict_date})")

    rows: list[dict] = []
    seen: set[tuple] = set()
    skipped_no_gloss = 0
    for entry in words:
        definition, _roman = head_and_reading(entry)
        if not definition:
            continue
        for sense in entry.get("sense") or []:
            pos = map_pos(sense.get("partOfSpeech") or [])
            for gloss in sense.get("gloss") or []:
                if gloss.get("lang") != "eng":
                    continue
                text = (gloss.get("text") or "").strip()
                if not text:
                    skipped_no_gloss += 1
                    continue
                key = (text, pos, definition)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "word": text,
                    "pos": pos,
                    "definition": definition,
                })

    df = pd.DataFrame(rows, columns=COLUMNS)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    import pyarrow as pa
    import pyarrow.parquet as pq
    table = pa.Table.from_pandas(df, preserve_index=False)
    meta = {
        "dictionary": "en-ja",
        "direction": "english gloss -> Japanese word (JMdict, reversed)",
        "preset": "curated (jmdict)",
        "word_language": "en",
        "target_language_code": "ja",
        "source": source,
        "source_url": "https://github.com/scriptin/jmdict-simplified/releases",
        "built_on": date.today().isoformat(),
    }
    table = table.replace_schema_metadata(meta)
    pq.write_table(table, out, compression="zstd", row_group_size=100_000)

    print(f"kept {len(df):,} rows, {df['word'].str.lower().nunique():,} "
          f"unique English glosses (skipped {skipped_no_gloss} empty)")
    print(f"wrote {out} ({out.stat().st_size/1e6:.1f} MB) in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
