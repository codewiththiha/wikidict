# curated/ — recommended primary datasets per language pair

All files are Parquet with English as the key column (`word`) wherever
applicable, ready to download and load into SQLite.

## EN ↔ MY (Myanmar / Burmese)
| file | role | rows | source |
|---|---|---|---|
| `mcfnlp-en-my.parquet` | **PRIMARY** | 110,640 | [chuuhtetnaing/english-myanmar-dictionary-dataset-mcfnlp](https://huggingface.co/datasets/chuuhtetnaing/english-myanmar-dictionary-dataset-mcfnlp) (MCF NLP dictionary) — schema `word, pos, definition` |
| `wiktionary-en-my.parquet` | supplement | 8,149 | English Wiktionary translations (full, via `build_reverse.py --no-filter`) — schema adds `romanization, sense, lang_code, source` |

## EN ↔ JP (Japanese)
| file | role | rows | source |
|---|---|---|---|
| `wiktionary-en-jp.parquet` | now | 69,786 | English Wiktionary translations (full) |
| `jmdict-en-jp.parquet` | **3×+ coverage** | 441,348 | [JMdict 3.6.2](https://github.com/scriptin/jmdict-simplified/releases) reversed: English gloss → Japanese word, CC BY-SA — **3 columns only** (`word, pos, definition`), single primary POS per row |

## EN ↔ FR (French)
| file | role | rows | source |
|---|---|---|---|
| `wordnet-en-fr.parquet` | **PRIMARY (non-Wiki)** | 208,351 | Princeton WordNet 3.0 + WOLF (French WordNet) via [Open Multilingual Wordnet](https://github.com/omwn/omw-data) — English lemma → French lemma, `sense` holds the WordNet gloss |
| `wiktionary-en-fr.parquet` | supplement | 128,263 | English Wiktionary translations (full) |

(Freedict eng-fra was evaluated and rejected: only 8,805 headwords.)

## Notes
- Two schemas coexist, but **every file has English in `word` and the
  target-language word in `definition`**, so the app can query them all the
  same way:
  - 3 columns (`word, pos, definition`): `mcfnlp-en-my`, `jmdict-en-jp`
  - 7 columns (`+ romanization, sense, lang_code, source`):
    `wiktionary-en-{my,jp,fr}`, `wordnet-en-fr`
- POS tag vocabularies differ per source. See `output/pos-tags/SUMMARY.txt`
  for the unique `pos` values of every parquet and how they overlap.
- Sentence-style verbose dictionaries (per-language Wiktionary glosses) live
  one level up as `output/eng-*-{main,all}.parquet`.
