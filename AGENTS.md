# AGENTS.md

Rules for anyone, human or agent, changing this repository. Read it before the
first edit of a session.

## Project

wikidict hosts the dictionary packs that
[mareader2](https://github.com/codewiththiha/mareader2) downloads: one Parquet
file per language pair in `packs/`, built from open dictionary data by the
Python tools in `tools/`. The usual job is a request like "add a Korean pack":
find open data on the web, check its licence, write a converter, build, and
document where the data came from so mareader2 can link the file.

```
packs/<id>.parquet     the packs; the only files mareader2 downloads
catalog.json           every pack's rows, size, sha256, source and licence
sources.toml           where each pack's data comes from (the build input)
tools/build.py         download + convert:  build.py <id>… | --all
tools/convert/<x>.py   one converter per source format
tools/lib/             the shared writer, cleaner, fetcher and catalog
tools/check.py         the CI gate for packs, catalog and README
tools/links.py         commit-pinned download links for mareader2
docs/                  pack format, how to add a pack, research, mareader2
raw/                   downloads (git-ignored, re-fetched on demand)
```

## What a pack is

Read [docs/pack-format.md](docs/pack-format.md) before touching a converter.
In short:

- **English → X only.** `word` is English; `definition` is the other language.
  mareader2 routes every lookup through English, so a pack in another
  direction is useless to it.
- **Only the columns mareader2 reads:** `word`, `definition`, and optionally
  `pos`, `romanization` and `sense`. All strings. No pronunciation audio, IPA,
  example sentences or IDs; mareader2 ignores them, and they cost download size.
- **`pos` uses the fixed vocabulary** in `tools/lib/pack.py` (`POS`), all
  words mareader2 already spells out. Map the source's tags onto it. Never
  invent a new tag; add it to `POS` only with a matching mareader2 change.
- **Rich but ordered.** Keep every sense, but rank the everyday translation
  first. mareader2 shows a word's rows in file order.
- **Language codes are mareader2's.** Japanese is `jp`, not `ja`. Any other
  new code needs mareader2 to know it (see [docs/mareader2.md](docs/mareader2.md)).

## Data and licences

- **Use only data whose licence allows redistribution, commercial use
  included.** CC BY, CC BY-SA, CC0, public domain or MIT-style. Reject
  non-commercial (NC), no-derivatives (ND), "research only" and unlicensed
  scrapes. Record every rejection in [docs/research.md](docs/research.md), so
  nobody researches it twice.
- **Pin the source.** Prefer a release asset, a tagged file or a URL with a
  commit hash. When only a moving URL exists, say so in `docs/research.md`.
  The receipt in `raw/` records its sha256, and the catalog copies it.
- **Credit the source.** Every pack has `licence` and `homepage` in
  `sources.toml`. Share-alike data stays share-alike, and that is fine.
- **Never commit `raw/`.** It holds downloads of up to a few hundred MB.

## Workflow

1. Research and record the source in `docs/research.md`: URL, licence, version
   and size, plus what was rejected and why.
2. Add a `[[pack]]` to `sources.toml`, and a converter in `tools/convert/` when
   no existing one reads the format. See
   [docs/adding-a-pack.md](docs/adding-a-pack.md).
3. `python3 tools/build.py <id>`, then look at real rows. Check common words
   ("love", "water", "run", "book") and a random sample. The first rows of
   each word must be the everyday translation.
4. `python3 tools/check.py` must pass. It also proves `catalog.json` and the
   README table are current; `python3 tools/catalog.py` regenerates both.
5. Commit, push, then `python3 tools/links.py --ref <sha> --rust` prints the
   pinned links and the Rust `PACKS` table for mareader2.

Requirements: Python 3.11+ and `pip install -r requirements.txt`. A full
`--all` rebuild needs about 1.5 GB of RAM and a few minutes.

## Code style

- Python 3.11+, standard library plus `pyarrow` and `openpyxl`. Add no other
  dependency without a reason in the commit body.
- One converter per source format, exposing
  `convert(files, packs) -> {id: (rows, info)}`. Converters build row dicts;
  only `tools/lib/pack.py` writes Parquet, cleans text and orders rows.
- File and function names say what they hold: `cedict.py`, not `step2.py`.
- Delete code that nothing calls. Git keeps the history.

### Comments

Write self-documenting code. A comment says why something non-obvious is done,
never what the next line does. It carries a constraint the code cannot show:
a source's quirk ("the 2019 dump has a raw `<` inside one value"), a unit, or
an order that matters.

Measure it with `python3 tools/comment_check.py FILE...`: at most three lines,
eighty columns and fifteen words per block. A comment that truly needs more
says so with `comment-check: allow` on the line above.

Remove, rather than shorten:

- **Narration** of the change ("now uses…", "changed because…"). Git holds
  the change; the file holds the result.
- **Justification** of a design. That goes in the commit body or `docs/`.
- **Restatement** of the code or a well-named variable.
- **History**: what the code used to be.

Docstrings follow the same spirit: one line for a leaf function. Module
docstrings may show usage.

## Commits

- Conventional commits: `type(scope): summary`. Use the imperative, lower
  case, no trailing full stop, and keep the subject to 50 characters or fewer.
  Types: feat, fix, docs, refactor, perf, test, build, ci, chore, revert,
  style. Typical scopes are a pack id or a tool (`feat(krdict-en-ko): …`).
- Enforced: run `python3 tools/commit_check.py --install` once per clone.
  `--status` says whether the hook is armed; CI audits pushed subjects.
- A pack change and its catalog/README update land in the same commit, so
  the catalog never disagrees with the packs it lists.
- The body says why: what the source is, what was dropped and the counts.

## Gates

CI (`.github/workflows/check.yml`) runs on every push and pull request:

- `python3 tools/check.py`: pack schema, POS vocabulary, required columns,
  embedded metadata, catalog and README freshness, no stray files in `packs/`.
- `python3 tools/comment_check.py`: on every tracked source file.
- `python3 tools/commit_check.py --range …`: on the pushed commits.

Run all three locally before pushing.

## Links in mareader2

mareader2 must download a pack from a commit hash, never `@main`. A pinned
URL keeps serving the same bytes after this repository moves on, so the
sha256 mareader2 checks stays valid. `tools/links.py` prints those URLs and
verifies the hashes. Moving or renaming a pack breaks old app versions that
link it, so do it only on purpose and note it in the commit body.

## Definition of done

- Pack built, sample checked, `tools/check.py` clean.
- Source, licence and version recorded in `sources.toml` and
  `docs/research.md`; the README table regenerated.
- Commits pass `commit_check.py`, and touched files pass `comment_check.py`.
- Report: rows, size, source links, licence, and the mareader2 follow-up
  (the `PACKS` row from `tools/links.py`, plus any new language code).
