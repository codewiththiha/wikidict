# Research

Where each pack's data comes from, what was done to it, and what was looked at
and turned down. Add to this page whenever a source is chosen or rejected.
Exact download URLs and sha256 hashes for each build are in
[`../catalog.json`](../catalog.json).

## Packs

### `wiktionary-en-fr`, `wiktionary-en-es`, `wiktionary-en-de`

- **Source:** the translation tables of the English Wiktionary, as extracted
  by [Wiktextract](https://github.com/tatuylonen/wiktextract) and published
  on [kaikki.org](https://kaikki.org/dictionary/English/):
  `https://kaikki.org/dictionary/English/words/kaikki.org-dictionary-English-words.jsonl.gz`
  (534 MB, extract of 2026-10-25).
- **Licence:** CC BY-SA 4.0 (and GFDL), the
  [Wiktionary licence](https://en.wiktionary.org/wiki/Wiktionary:Copyrights).
- **Pinning:** the URL moves with each weekly extract. The receipt and the
  catalog record the sha256 of the file that was built.
- **Kept:** each translation with its sense line, part of speech, grammatical
  gender and usage tags, plus a literal English meaning where Wiktionary
  gives one. Transliterations go in `romanization`.
- **Dropped:** dialects filed under the main language code ("Bavarian
  German" under `de`); abbreviations, affixes, symbols, letters and
  characters; translations that are only a romanization or another form.
- **Rank:** translations without regional, register or period tags come
  first, in Wiktionary's order.

### `jmdict-en-jp`

- **Source:** [JMdict](https://www.edrdg.org/jmdict/j_jmdict.html) by the
  Electronic Dictionary Research and Development Group, via the JSON release
  of [jmdict-simplified](https://github.com/scriptin/jmdict-simplified):
  `https://github.com/scriptin/jmdict-simplified/releases/download/3.6.2%2B20261026175559/jmdict-eng-3.6.2%2B20261026175559.json.tgz`
  (JMdict 3.6.2, 2026-10-26).
- **Licence:** CC BY-SA 4.0
  ([EDRDG licence](https://www.edrdg.org/edrdg/licence.html)).
- **Read backwards:** each English gloss becomes a headword, with the rest
  of the gloss as its sense. The Japanese spelling is the definition. When
  it is written in kanji, the kana reading fills the romanization column.
- **Rank:** words JMdict marks common first, then by sense order and
  shorter spellings.

### `cedict-en-zh`

- **Source:** [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cc-cedict),
  `https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz`
  (published daily; this build is of 2026-10-29).
- **Licence:** CC BY-SA 4.0.
- **Pinning:** the URL always serves today's file; the sha256 is in the
  catalog.
- **Read backwards:** glosses become headwords. The definition is the
  simplified form, and pinyin is converted from tone numbers to tone marks.
- **Dropped:** pointer glosses ("variant of", "see", "CL:", "surname"),
  which describe an entry instead of translating it.
- **Rank:** common characters before rare ones (CJK Extension A and beyond),
  plain senses before old/literary/dialect/Cantonese ones, then gloss order.

### `krdict-en-ko`

- **Source:** the National Institute of Korean Language's
  [Korean-English Learners' Dictionary](https://krdict.korean.go.kr/)
  (한국어기초사전), from the LMF XML dump mirrored at
  [spellcheck-ko/korean-dict-nikl-krdict](https://github.com/spellcheck-ko/korean-dict-nikl-krdict)
  at commit `e7249562dca526461a347eb2cc5a2e67a17c4488` (dump of
  2019-08-02).
- **Licence:** CC BY-SA 2.0 KR.
- **Age:** the dump is from 2019; no newer openly mirrored dump was found.
  The words it covers change little.
- **Quirk:** `30000.xml` has a raw `<` inside an attribute value, which the
  converter escapes before parsing.
- **Rank:** the dictionary's learner level (beginner, intermediate,
  advanced), then sense order.

### `volubilis-en-th`

- **Source:** [Volubilis](https://belisan-volubilis.blogspot.com/), the
  Thai–English–French dictionary by Francis Bastien:
  `https://downloads.sourceforge.net/project/belisan/VOLUBILIS%20Database.xlsx`
  (v26.2, July 2026).
- **Licence:** CC BY-SA 4.0.
- **Pinning:** the SourceForge name is reused by each release (v26.3 is due
  in November 2026). The catalog records the sha256 that was built.
- **Kept:** the Thai spelling (alternate spellings split into separate
  rows), its romanization, word class, and usage labels spelled out in the
  sense (obsolete, spoken, poetic, regional, royal …).
- **Rank:** unlabelled words first, then by how fully the entry is described
  (French translation, phonetic column, subject domains), then gloss order.
  The Royal Institute tag isn't used as a signal, because literary words
  carry it as often as everyday ones.

### `mcfnlp-en-my`

- **Source:** the [MCF NLP English–Myanmar dictionary](https://github.com/mcfnlp/Dictionary)
  (2016), via its Hugging Face copy
  [chuuhtetnaing/english-myanmar-dictionary-dataset-mcfnlp](https://huggingface.co/datasets/chuuhtetnaing/english-myanmar-dictionary-dataset-mcfnlp)
  at revision `d32893d8f1ef98955c69323258e3805227ab0f69`.
- **Licence:** **unstated.** Neither repository gives a licence. The pack
  was shipped by mareader2 before this repository was restructured, and
  was kept at the owner's request. Replace it if an openly licensed
  English–Burmese source appears.
- **Kept:** word, word class, Burmese definition; exact duplicates merged.

## Rejected

| Source | Language | Why not |
|---|---|---|
| [kengdic](https://github.com/garfieldnate/kengdic) | Korean | MPL/LGPL mix, and noisy machine-gathered glosses. krdict is curated and CC BY-SA. |
| [LEXiTRON](https://www.nectec.or.th/) | Thai | Licence forbids commercial use. |
| [FreeDict](https://freedict.org/) eng-fra | French | Far smaller than the Wiktionary translations, with no senses. |
