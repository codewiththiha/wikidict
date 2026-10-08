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
python scripts/build_parquet.py       # build both presets for all languages
python scripts/verify_parquet.py output/*.parquet --sqlite   # verify + SQLite round-trip test
```

Individual steps:

```bash
python scripts/download.py Japanese            # one language only
python scripts/inspect_schema.py data/raw/*.jsonl   # re-run the structure research
python scripts/build_parquet.py --presets main      # only the main preset
python scripts/build_parquet.py --langs Burmese --presets all
python scripts/build_parquet.py --keep-all          # disable POS filtering
```

## Presets

Each language is exported once per preset; the file name carries the preset:

| preset | columns | filter | files |
|---|---|---|---|
| `main` | `word`, `pos`, `definition`, `ipa`, `romanization` | **words-only** (definitions must be word-like, pure English) | `eng-jp-main.parquet`, … |
| `all` | every extracted column | none | `eng-jp-all.parquet`, … |

`main` is the dictionary-grade export meant for the app's bridge lookups;
`all` keeps everything for analysis.

## Word-only filter ("words, not sentences")

Because English is the bridge key, `main` keeps only definitions that look
like dictionary **words** — single lexemes, compounds, or comma/semicolon
word-lists — and drops descriptive sentences. A definition survives only if
**all** layers pass:

1. **Pure-ASCII letters** — any non-ASCII alphabetic character rejects the
   row. This strips glosses embedding Japanese kana/kanji (`synonym of
   国内総生産 …`), Burmese script (`(~ဂြိုဟ်) Mars`), or accented
   self-references in French (`inflection of tuméfier`).
2. **Definitional-pattern blacklist** — regexes for Wiktionary's sentence
   templates: `used to/for`, `inflection of`, `plural of`, `synonym of`,
   `short for`, `one who`, `the act of`, `romanization of`, `such as`, …
3. **Segment analysis** — the definition is split on `,` and `;`; every
   segment must contain **≤ 4 tokens** (hyphenated compounds count as one)
   and **zero function words** (of, for, the, to, with, that, used, who, …).

What this keeps vs. drops:

| definition | verdict |
|---|---|
| `one, single` | ✅ keep |
| `rolling pin` / `gross domestic product` | ✅ keep (compounds) |
| `bustling, lively, busy` | ✅ keep (word list) |
| `counter for floors or stories of a building` | ❌ sentence |
| `used to express that something was done in vain, for nothing` | ❌ sentence |
| `synonym of 国内総生産 (kokunai sōseisan, …)` | ❌ non-English chars |
| `inflection of oxyder` | ❌ conjugation sentence |

Exact `(word, pos, definition)` duplicates are collapsed in word-only mode.
The build prints a per-reason rejection breakdown with examples so the
classifier's behaviour is auditable (see build log).

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

| file | rows | size |
|---|---|---|
| `output/eng-jp-main.parquet` | 51,199 | 1.4 MB |
| `output/eng-fr-main.parquet` | 69,125 | 1.7 MB |
| `output/eng-mm-main.parquet` | 6,279 | 0.2 MB |
| `output/eng-jp-all.parquet` | 149,410 (91,713 unique words) | 11.7 MB |
| `output/eng-fr-all.parquet` | 459,790 (390,475 unique words) | 18.7 MB |
| `output/eng-mm-all.parquet` | 14,547 (8,367 unique words) | 1.1 MB |

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
