# Pack format

A pack is one Parquet file, `packs/<id>.parquet`, translating English
headwords into one other language. Only `tools/lib/pack.py` writes packs,
and `tools/check.py` holds every pack to this page.

## Name

`<source>-en-<lang>`, for example `cedict-en-zh`. `<source>` is the dataset
(`wiktionary`, `jmdict`, `cedict` …), and `<lang>` is the code mareader2 uses
for the definition language. The id is also the file stem and mareader2's
pack id.

| Code | Language | Code | Language |
|---|---|---|---|
| `de` | German | `ko` | Korean |
| `es` | Spanish | `my` | Burmese |
| `fr` | French | `th` | Thai |
| `jp` | Japanese (not `ja`) | `zh` | Chinese (simplified) |

`tools/lib/langs.py` lists them with the script each side must be written
in.

## Columns

All columns are UTF-8 strings. A blank cell means "none", and a column a
source cannot fill is left out entirely.

| Column | Required | Holds | Example |
|---|---|---|---|
| `word` | yes | English headword | `water` |
| `definition` | yes | One translation in the target language | `水` |
| `pos` | no | Part of speech, from the vocabulary below | `noun` |
| `romanization` | no | Latin-script reading of `definition` | `shuǐ` |
| `sense` | no | Which meaning of `word`, plus usage notes | `liquid H₂O; formal` |

There is one row per (word, translation, sense). A word with ten
translations has ten rows. Nothing else goes in: no IPA, audio, examples,
frequencies or source IDs. mareader2 reads only these five columns.

### `pos` vocabulary

noun, verb, adjective, adverb, pronoun, preposition, postposition,
conjunction, interjection, determiner, article, number, counter, particle,
auxiliary, prefix, suffix, phrase, proverb, name, abbreviation, symbol,
contraction, classifier, other.

mareader2 shows the word as written, so these are full English words, not
abbreviations. The writer refuses anything outside the list.

### `sense`

A short English gloss that tells one meaning from another ("to move quickly
on two feet" against "to flow"). Usage labels follow after a `; `: register
(formal, informal, slang), region (Costa Rica), period (archaic), and
grammatical gender (masculine, feminine, neuter). Labels are always spelled
out, never abbreviated (`obsolete`, not `obsol.`).

## Order

Rows are sorted by headword (case-folded, then exact), and within a word by
the converter's **rank**: the everyday translation first, then rarer,
dated, regional or literary ones. mareader2 shows a word's rows in file
order, so this order is what a reader sees. Each pack's rank is listed in
[research.md](research.md).

## Cleaning

The writer applies the following to every cell:

- Unicode NFC normalisation; zero-width characters removed; runs of
  whitespace collapsed to one space.
- Cut at 2,000 characters, because mareader2 truncates cells there anyway.
- Rows without a `word` or `definition` dropped; exact duplicates merged,
  keeping the best rank.
- At most 5,000,000 rows, mareader2's limit.

## File

- Compression: zstd, level 15 (mareader2 also reads snappy and uncompressed).
- Row groups of 100,000 rows.
- Schema metadata key `mareader.pack`, holding JSON with `id`, `from`, `to`,
  `name`, `licence`, `homepage`, `version`, `downloads` (source URLs),
  `rows` and `built` (date). It travels with the file, so a copied pack
  still names its source.

## catalog.json

`tools/catalog.py` writes this file from the packs and `sources.toml`. It has
one entry per pack with `id`, `file`, `from`, `to`, `label`, `name`, `rows`,
`bytes`, `sha256`, `columns`, `version`, `built`, `licence`, `homepage` and
`downloads` (each with `url`, `bytes` and `sha256` of the raw file). The
README table is generated from the same data, between the `packs:start` and
`packs:end` markers.
