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
 scripts/build_parquet.py     flat, tidy tables           (target word + English glosses)
        ▼
 output/eng-jp-{main,all}.parquet ...
        ▼
 scripts/build_reverse.py     English-dump translations   (English word + target word)
        ▼
 output/eng-jp-words.parquet  output/eng-fr-words.parquet output/eng-mm-words.parquet
```

## Quick start

```bash
pip install -r requirements.txt

python scripts/download.py            # download all 3 dumps (resumable)
python scripts/build_parquet.py       # build both presets for all languages
python scripts/verify_parquet.py output/*.parquet --sqlite   # verify + SQLite round-trip test

# clean word-level "reverse" dictionaries (English word -> target word):
python scripts/download.py English    # 3.3 GB English dump
python scripts/build_reverse.py       # -> eng-{jp,fr,mm}-words.parquet
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

## Reverse dictionaries: clean word-level data (`*-words.parquet`)

Wiktionary's *foreign* pages carry verbose English **sentence** definitions.
The **English** pages carry something better for bridging: a `translations`
field with word-level translations of each English headword — target-language
word + romanization + POS + sense label, no sentences:

```
{"word": "cat", "pos": "noun", "translations": [
    {"lang": "Burmese", "word": "ကြောင်", "roman": "kraung", "sense": "domestic species"}]}
```

`scripts/build_reverse.py` streams the 3.3 GB English dump
(1.49 M entries) and extracts translations for ja/fr/my:

```bash
python scripts/download.py English
python scripts/build_reverse.py        # -> output/eng-{jp,fr,mm}-words.parquet
```

Schema (same core as the clean HuggingFace english-myanmar datasets, so the
app can treat both identically): `word` (English, the bridge key), `pos`,
`definition` (**the word in the target language**), `romanization`, `sense`,
`lang_code`, `source`.

| file | pairs | unique English words |
|---|---|---|
| `output/eng-jp-words.parquet` | 69,328 | 37,155 |
| `output/eng-fr-words.parquet` | 127,564 | 71,305 |
| `output/eng-mm-words.parquet` | 8,130 | 5,821 |

Burmese coverage in Wiktionary translations is thin — use the MCFNLP dataset
below as the primary EN→MY table.

## Research: clean word-dictionary sources found

| source | pair(s) | size | notes |
|---|---|---|---|
| [english-myanmar-dictionary-dataset-mcfnlp](https://huggingface.co/datasets/chuuhtetnaing/english-myanmar-dictionary-dataset-mcfnlp) | en→my | **110,640 rows**, parquet, schema `word/pos/definition` (Burmese words) | the cleanest EN→MY found; from the [MCF NLP dictionary](https://github.com/mcfnlp/Dictionary) |
| [english-myanmar-dictionary-dataset-EngMyanDictionary](https://huggingface.co/datasets/chuuhtetnaing/english-myanmar-dictionary-dataset-EngMyanDictionary) | en→my | ~950 MB, 2 parquet shards | messier: HTML-formatted definitions, images, keywords |
| [JMdict (jmdict-simplified)](https://github.com/scriptin/jmdict-simplified/releases) | ja↔en | **218,863 entries**, JSON 11.5 MB (`jmdict-eng-*.json.tgz`), CC BY-SA | the standard Japanese word dictionary (used by Yomichan/10ten); short word-level English glosses, POS, kana+kanji — ideal for JA, usable reversed |
| [Princeton WordNet 3.0 + WOLF (Open Multilingual Wordnet)](https://github.com/omwn/omw-data/blob/master/wns/fra/wn-data-fra.tab) | en↔fr | **208,351 pairs**, built via `build_wordnet_fr.py` | NLP-mainstream, non-Wiktionary; English lemma ↔ French lemma per synset, free/Open licenses |
| [English Wiktionary translations](https://kaikki.org/dictionary/English/words/kaikki.org-dictionary-English-words.jsonl) | en→ja/fr/my… | 3.3 GB JSONL | what `build_reverse.py` parses → the `*-words` tables |
| [Freedict](https://freedict.org/downloads/) | eng↔fra etc. | e.g. [eng-fra 0.1.6 (dictd)](https://download.freedict.org/dictionaries/eng-fra/0.1.6/freedict-eng-fra-0.1.6.dictd.tar.xz), GPL | community dictionaries; eng-fra is small (**8,805 headwords**) so it was not adopted |

No HuggingFace equivalent of the MCFNLP dataset was found for Japanese or
French; JMdict (ja) and WordNet+WOLF (fr) fill those gaps as the primary
non-Wiktionary sources.

## Organized output folders (`output/reverse/` and `output/curated/`)

```
output/
├── eng-*-{main,all}.parquet   verbose dictionaries (sentence glosses, kept)
├── eng-*-words.parquet        filtered word tables (previous builds)
├── reverse/                   build_reverse.py --no-filter (FULL, drops nothing)
│   ├── eng-jp-words.parquet   69,786 rows
│   ├── eng-fr-words.parquet   128,263 rows
│   └── eng-mm-words.parquet   8,149 rows
└── curated/                   recommended PRIMARY datasets per pair (all Parquet)
    ├── mcfnlp-en-my.parquet      110,640 rows  EN↔MY primary (HuggingFace)
    ├── wiktionary-en-my.parquet   8,149 rows  EN↔MY supplement
    ├── wiktionary-en-jp.parquet  69,786 rows  EN↔JP now
    ├── jmdict-en-jp.parquet     441,348 rows  EN↔JP 3x+ coverage (JMdict, 3 cols)
    ├── wordnet-en-fr.parquet    208,351 rows  EN↔FR primary (WordNet+WOLF, non-Wiki)
    └── wiktionary-en-fr.parquet 128,263 rows  EN↔FR supplement

output/pos-tags/               unique `pos` values per parquet + SUMMARY.txt
```

Regenerate them:

```bash
# FULL unfiltered reverse tables (no POS/tag/script filter, no de-dup)
python scripts/build_reverse.py --no-filter --outdir output/reverse

# JMdict reversed to Parquet (3 cols: word, pos, definition)
python scripts/build_jmdict.py            # -> output/curated/jmdict-en-jp.parquet

# EN<->FR from Princeton WordNet 3.0 + WOLF (non-Wiktionary)
python scripts/build_wordnet_fr.py        # -> output/curated/wordnet-en-fr.parquet

# POS-tag vocabulary report (.txt per parquet + SUMMARY.txt)
python scripts/extract_pos_tags.py        # -> output/pos-tags/
```

* `output/curated/` is the app-ready set: English is always the `word`
  column, the target-language word is in `definition`. Two schemas: 3
  columns (`word,pos,definition`) for `mcfnlp-en-my` and `jmdict-en-jp`;
  7 columns (`+ romanization, sense, lang_code, source`) for the rest.
  Each folder has its own `README.md`.
* `build_jmdict.py` reads the JMdict JSON and maps JMdict POS codes to ONE
  broad category (primary tag), so every row has a single bridge-friendly
  `pos`. `build_wordnet_fr.py` joins Princeton WordNet 3.0 English lemmas
  with the French lemmas of WOLF per synset. `extract_pos_tags.py` writes the
  unique `pos` values of every parquet to `output/pos-tags/` (per-file `.txt`
  plus a `SUMMARY.txt` cross-file comparison).

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
