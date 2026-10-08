#!/usr/bin/env python3
"""Build clean English-bridge dictionary Parquet files from kaikki.org JSONL.

Input : data/raw/<Language>.jsonl   (one Wiktionary entry per line)
Output: output/eng-jp.parquet, output/eng-fr.parquet, output/eng-mm.parquet

The output tables are FLAT (only string / int columns, no nested lists) so
that any consumer can convert them straight into SQLite (or any other store)
without losing information:

    parquet -> pandas.DataFrame -> df.to_sql(...)

Row granularity: one row per (word, POS, sense).

Columns
-------
lang            "Japanese" / "French" / "Burmese"
lang_code       ISO code of the word's language (ja / fr / my)
word            the headword in the target language
pos             part of speech (noun, verb, adj, ...)
sense_index     which sense of the entry (0-based)
definition      the English gloss  <-- the English "bridge"
raw_definition  raw gloss if it differs (contains parenthetical notes)
tags            grammar/usage tags ("archaic", "form-of", ...)
topics          subject topics ("medicine", "law", ...)
examples        example sentences (with translation when available)
synonyms        synonym headwords for this sense
antonyms        antonym headwords for this sense
form_of         lemma this is an inflected form of (French conjugations!)
alt_of          lemma this is an alternative spelling of
ipa             pronunciation(s)
romanization    ja: romaji / my: transliteration ("" for French)
etymology_text  word origin (English)
entry_id        stable unique id from Wiktionary
source          data provenance

Usage:
    python scripts/build_parquet.py
    python scripts/build_parquet.py --langs Japanese
    python scripts/build_parquet.py --keep-all          # no POS filtering
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

import pandas as pd

#: language -> config
DATASETS = {
    "Japanese": {"lang_code": "ja", "output": "eng-jp.parquet"},
    "French":   {"lang_code": "fr", "output": "eng-fr.parquet"},
    "Burmese":  {"lang_code": "my", "output": "eng-mm.parquet"},
}

#: POS values that are noise for a bilingual dictionary and dropped by default
DEFAULT_DROP_POS = {"romanization", "soft-redirect"}

SOURCE = "English Wiktionary (via kaikki.org)"

COLUMNS = [
    "lang", "lang_code", "word", "pos", "sense_index", "definition",
    "raw_definition", "tags", "topics", "examples", "synonyms", "antonyms",
    "form_of", "alt_of", "ipa", "romanization", "etymology_text",
    "entry_id", "source",
]


def join(values: list[str], sep: str = ", ") -> str:
    """Join a list of strings, dropping empties and duplicates (order kept)."""
    seen: dict[str, None] = {}
    for v in values:
        if v and v not in seen:
            seen[v] = None
    return sep.join(seen)


def words_of(items: list[dict]) -> list[str]:
    """Extract the 'word' field from synonym/antonym/form_of style lists."""
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


def parse_file(path: Path, cfg: dict, drop_pos: set[str]) -> tuple[pd.DataFrame, dict]:
    stats = {
        "entries": 0, "dropped_pos": 0, "senses": 0,
        "senses_no_gloss": 0, "rows": 0,
        "with_ipa": 0, "with_rom": 0, "with_etym": 0,
        "pos_counts": {},
    }
    rows: list[dict] = []
    lang = cfg.get("lang", path.stem)

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
                    # no English definition -> useless as bridge entry
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


def write_parquet(df: pd.DataFrame, dest: Path, meta: dict) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(df, preserve_index=False)
    kv = {k: str(v) for k, v in meta.items()}
    table = table.replace_schema_metadata(kv)
    dest.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, dest, compression="zstd", row_group_size=100_000)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--langs", nargs="*", default=list(DATASETS),
                    help=f"which datasets to build (choices: {', '.join(DATASETS)})")
    ap.add_argument("--rawdir", default="data/raw")
    ap.add_argument("--outdir", default="output")
    ap.add_argument("--drop-pos", default=",".join(sorted(DEFAULT_DROP_POS)),
                    help="comma-separated POS values to skip "
                         "(default: romanization,soft-redirect)")
    ap.add_argument("--keep-all", action="store_true",
                    help="disable POS filtering entirely")
    args = ap.parse_args()

    drop_pos = set() if args.keep_all else {p.strip() for p in args.drop_pos.split(",") if p.strip()}

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
        df, st = parse_file(src, cfg | {"lang": lang}, drop_pos)

        dest = Path(args.outdir) / cfg["output"]
        meta = {
            "dictionary": f"en-{cfg['lang_code']}",
            "word_language": lang,
            "word_language_code": cfg["lang_code"],
            "bridge_language": "en",
            "source": SOURCE,
            "source_url": f"https://kaikki.org/dictionary/{lang}/words/kaikki.org-dictionary-{lang}-words.jsonl",
            "built_on": date.today().isoformat(),
            "row_granularity": "one row per (word, pos, sense)",
            "dropped_pos": ",".join(sorted(drop_pos)),
        }
        write_parquet(df, dest, meta)

        n = max(st["rows"], 1)
        dt = time.time() - t0
        print(f"[{lang}] entries={st['entries']:,}  rows={st['rows']:,}  "
              f"unique words={st['unique_words']:,}  "
              f"(dropped pos={st['dropped_pos']:,}, senses w/o gloss={st['senses_no_gloss']:,})")
        print(f"[{lang}] coverage: ipa={st['with_ipa']/n:.0%}  "
              f"romanization={st['with_rom']/n:.0%}  etymology={st['with_etym']/n:.0%}")
        top = sorted(st["pos_counts"].items(), key=lambda x: -x[1])[:6]
        print(f"[{lang}] top POS: " + ", ".join(f"{k}={v:,}" for k, v in top))
        size_mb = dest.stat().st_size / 1e6
        print(f"[{lang}] wrote {dest} ({size_mb:.1f} MB) in {dt:.1f}s\n")


if __name__ == "__main__":
    main()
