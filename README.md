# dictionary-parquet

Research + pipeline that downloads **Wiktionary** dictionary data from
[kaikki.org](https://kaikki.org/dictionary/index.html) and converts it into
clean, flat **Parquet** files — one per language pair — ready to be downloaded
by an app and loaded into SQLite.

The English glosses inside every language dump make **English the bridge
language**: with `eng-jp` + `eng-mm` + `eng-fr` tables, the app can serve
`mm↔jp`, `mm↔fr`, `jp↔fr` lookups through the shared English definitions.

```
Wiktionary (English edition)
        │  kaikki.org JSONL dumps
        ▼
 scripts/download.py          Japanese.jsonl / French.jsonl / Burmese.jsonl
        ▼
 scripts/build_parquet.py     flat, tidy tables
        ▼
 output/eng-jp.parquet        output/eng-fr.parquet        output/eng-mm.parquet
```

## Quick start

```bash
pip install -r requirements.txt

python scripts/download.py            # download all 3 dumps (resumable)
python scripts/build_parquet.py       # build the 3 parquet files
python scripts/verify_parquet.py output/*.parquet --sqlite   # verify + SQLite round-trip test
```

Individual steps:

```bash
python scripts/download.py Japanese            # one language only
python scripts/inspect_schema.py data/raw/*.jsonl   # re-run the structure research
python scripts/build_parquet.py --langs Burmese --keep-all   # skip POS filtering
```

## Research: do the dumps share the same structure? ✅ Yes

`scripts/inspect_schema.py` sampled thousands of entries from each dump.
All languages are parsed from the **same English Wiktionary**, so they share
one schema:

| field | what it is | Japanese | French | Burmese |
|---|---|---|---|---|
| `word` | headword in target language | 100% | 100% | 100% |
| `pos` | part of speech | 100% | 100% | 100% |
| `senses[].glosses` | **English definition** | 83%* | 100% | 100% |
| `senses[].id` | stable sense id | 100% | 100% | 100% |
| `forms` | inflections / romanization | 70% | 38% | 99% |
| `sounds` | IPA, audio | 50% | 61% | 99% |
| `etymology_text` | origin (English) | 31% | 29% | 75% |
| `senses[].tags/topics/examples/synonyms` | optional extras | ✓ | ✓ | ✓ |

\* missing Japanese glosses are almost all `soft-redirect` / `romanization`
pseudo-entries, which the pipeline drops by default.

Per-language quirks handled by the parser:

* **Japanese** — ~30% of raw entries are noise (`romanization`,
  `soft-redirect`, kana `character` pages); dropped by default. Romaji lives
  in `forms[].tags=["romanization"]` (94% coverage).
* **French** — no romanization (Latin script); ~62% of rows are conjugated
  verb forms whose gloss is *"inflection of …"*; the `form_of` column keeps
  the lemma so the app can resolve them.
* **Burmese** (Myanmar) — smallest dump; transliteration is in
  `forms[].tags=["romanization"]` (100% coverage), IPA 99%.

## Output schema (flat — SQLite friendly)

One row per **(word, pos, sense)**. Only `string` / `int64` columns, no
nested types, so `pandas.read_parquet(...).to_sql(...)` works losslessly.

| column | example |
|---|---|
| `lang` / `lang_code` | `Japanese` / `ja` |
| `word` | `賑やか` |
| `pos` | `adj` |
| `sense_index` | `0` |
| `definition` | `bustling, lively, busy` ← the English bridge |
| `raw_definition` | gloss with parentheticals, when different |
| `tags` | `archaic`, `form-of`, … |
| `topics` | `medicine`, `law`, … |
| `examples` | example sentences (+ translations) |
| `synonyms` / `antonyms` | headwords |
| `form_of` / `alt_of` | lemma pointers (conjugations, spellings) |
| `ipa` | pronunciation |
| `romanization` | ja romaji / my transliteration |
| `etymology_text` | word origin (English) |
| `entry_id` | stable Wiktionary sense id (unique key) |
| `source` | provenance string |

Parquet file metadata carries `dictionary`, `word_language_code`,
`source_url`, `built_on`, etc.

## Current build (2026-10-08)

| file | rows | unique words | size |
|---|---|---|---|
| `output/eng-jp.parquet` | 149,410 | 91,713 | 11.7 MB |
| `output/eng-fr.parquet` | 459,790 | 390,475 | 18.7 MB |
| `output/eng-mm.parquet` | 14,547 | 8,367 | 1.1 MB |

## Notes for the bridge-dictionary app

* `entry_id` is a natural primary key; `(word, pos, sense_index)` is a good
  unique index.
* To cross languages, match through the English `definition` text and `pos`.
  For precision, also pull the **English** Wiktionary dump from kaikki.org
  (`scripts/download.py English`) — it gives canonical English lemmas whose
  senses can be joined against the foreign-language definitions.
* This project deliberately stops at Parquet; SQLite loading lives in the app.

## Adding more languages

Any Wiktionary language works:

```bash
python scripts/download.py Spanish German Thai
# then add the language to DATASETS in scripts/build_parquet.py
```

## Data source & license

Data: [Wiktionary](https://en.wiktionary.org) via
[kaikki.org](https://kaikki.org) (Tatu Ylönen's wiktextract). Dictionary
content is licensed CC BY-SA / GFDL; attribute accordingly in your app.
