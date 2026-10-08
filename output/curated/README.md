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
| `jmdict-en-jp.parquet` | **3×+ coverage** | 443,207 | [JMdict 3.6.2](https://github.com/scriptin/jmdict-simplified/releases) reversed: English gloss → Japanese word (kanji + kana reading), CC BY-SA |

## EN ↔ FR (French)
| file | role | rows | source |
|---|---|---|---|
| `wiktionary-en-fr.parquet` | solid | 128,263 | English Wiktionary translations (full) |

## Notes
- The mcfnlp file has 3 columns (`word`, `pos`, `definition`); the others
  share the 7-column reverse schema (`word`, `pos`, `definition`,
  `romanization`, `sense`, `lang_code`, `source`). Both have English in
  `word` and the target-language word in `definition`, so the app can query
  them the same way.
- Sentence-style verbose dictionaries (per-language Wiktionary glosses) live
  one level up as `output/eng-*-{main,all}.parquet`.
