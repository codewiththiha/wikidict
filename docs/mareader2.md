# How mareader2 uses the packs

mareader2's dictionary lives in `crates/dict` of
[mareader2](https://github.com/codewiththiha/mareader2). This page lists what
it expects from a pack, and what must change there when a pack is added
here. Keep it in step with that crate.

## What it reads

- **Download:** `crates/dict/src/packs.rs` lists every offered pack in
  `PACKS` (id, source, target, entries, bytes) and fetches
  `<base>/<id>.parquet` from three bases: raw.githubusercontent.com, then
  jsDelivr's cdn and fastly mirrors.
- **Import:** `crates/dict/src/build.rs` copies the Parquet into its own
  index. It needs `word` and `definition`, and reads `pos`, `romanization`
  and `sense` when present. It skips blank rows, cuts cells at 2,000
  characters, refuses files over 5,000,000 rows, and reads zstd or snappy.
- **Display:** `crates/dict/src/entry.rs` shows `pos` through `tag()`, which
  spells out abbreviations and shows unknown tags as written. Every word in
  this repository's `POS` vocabulary already displays correctly.
- **Routing:** every pack is English → X, and lookups between two other
  languages go through English (the hub in `route.rs`). A pack in another
  direction would need routing changes, which is why this repository builds
  only English → X.
- **Languages:** `crates/dict/src/lang.rs` names each code and detects a
  word's language from its script.

## Adding a pack to mareader2

1. Push the pack here, then run `python3 tools/links.py --ref <commit> --rust`.
   It verifies the sha256 of every pack at that commit and prints:
   - the `REPO`/`CDN`/`FASTLY` constants, pinned to the commit;
   - the `PACKS` rows with the exact `entries` and `bytes`.
2. Paste those into `crates/dict/src/packs.rs`, growing the `PACKS` array
   length.
3. For a language mareader2 doesn't know yet, add it to `LANGUAGES` in
   `lang.rs` with its English name and script, or the UI shows the bare code
   ("English → DE").

## Pending mareader2 changes

Recorded here until mareader2 picks them up:

- **Pin the links.** `packs.rs` still points at `@main` and the old
  `output/curated/` folder. That folder is gone, so the links of mareader2
  v0.0.5 and earlier no longer resolve, a break accepted when the repository
  was restructured. The fix is the commit-pinned constants from `links.py`,
  ideally with a sha256 check like the one mareader2 already does for its
  speech models.
- **Update `PACKS`.** All three shipped packs were rebuilt, so their rows and
  bytes changed. Five new packs are available: `cedict-en-zh`,
  `krdict-en-ko`, `volubilis-en-th`, `wiktionary-en-es` and
  `wiktionary-en-de`.
- **New languages in `lang.rs`:** German (`de`), Spanish (`es`) and Chinese
  (`zh`) need names. Korean (`ko`) and Thai (`th`) also need their scripts
  (Hangul `U+AC00–D7AF`, `U+1100–11FF`, `U+3130–318F`; Thai `U+0E00–0E7F`).
- **Han is shared.** With both `jp` and `zh` installed, a word written only
  in Han characters matches two languages, so `detect()` returns none.
  Kana still marks Japanese. mareader2 should prefer the pack the user
  chose, or ask.
