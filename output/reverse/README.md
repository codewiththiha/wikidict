# reverse/ — English word → target-language word (FULL, unfiltered)

Built by `scripts/build_reverse.py --no-filter` from the complete English
Wiktionary dump (1,492,836 entries scanned). **Nothing is dropped**: no POS
filtering, no tag filtering, no script check, no de-duplication.

| file | rows | unique English words |
|---|---|---|
| `eng-jp-words.parquet` | 69,786 | 37,350 |
| `eng-fr-words.parquet` | 128,263 | 71,772 |
| `eng-mm-words.parquet` | 8,149 | 5,835 |

Schema (flat strings, SQLite-friendly):

| column | meaning |
|---|---|
| `word` | the English headword — the bridge key |
| `pos` | part of speech |
| `definition` | **the word in the target language** (never a sentence) |
| `romanization` | romaji (ja) / transliteration (my) |
| `sense` | which English sense this translation belongs to |
| `lang_code` | `ja` / `fr` / `my` |
| `source` | provenance |

Note: the filtered twins of these files live one level up
(`output/eng-*-words.parquet`); this folder is the keep-everything version.
