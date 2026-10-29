# Adding a pack

The whole loop, from "add Italian" to a link mareader2 can use. AGENTS.md has
the rules; this page has the mechanics.

## 1. Find the data

Look for a dictionary that translates English words, or that can be read
backwards (a Chinese → English dictionary yields English → Chinese by
splitting its glosses). Check, in order:

1. **Licence.** It must allow redistribution and commercial use (CC BY,
   CC BY-SA, CC0, public domain, MIT-style). Stop at NC, ND or no licence.
2. **Direction and richness.** Translations per sense, with parts of speech
   if possible.
3. **A pinned download.** Prefer a release asset, a tag, or a URL with a
   commit hash.
4. **Size.** A full build must fit in about 1.5 GB of RAM.

The English Wiktionary extract already covers many languages. Before
writing a new converter, try a `wiktionary` pack: one `[[pack]]` entry and
no code. A dedicated dictionary is worth adding only when it is clearly
richer or more reliable, as CC-CEDICT is for Chinese.

Record what you chose and what you rejected in [research.md](research.md).

## 2. Describe it in sources.toml

```toml
[[pack]]
id = "wiktionary-en-it"            # <source>-en-<lang>, the file stem
from = "en"
to = "it"                          # mareader2's code; add it to tools/lib/langs.py
name = "English Wiktionary translations into Italian"
converter = "wiktionary"           # tools/convert/<converter>.py
options = { lang_code = "it" }     # passed to the converter, optional
licence = "CC-BY-SA-4.0"           # SPDX id, or "unstated"
homepage = "https://en.wiktionary.org/"
version = "…"                      # optional; most converters read it from the data
downloads = [
  { file = "English.jsonl.gz", url = "https://kaikki.org/…" },
]
```

`file` is the name inside `raw/`. Packs with the same converter and
downloads are built in one pass, so the Wiktionary packs read the 534 MB
extract once.

A new language also needs a line in `tools/lib/langs.py`: its English name
and a regex for its script, which `check.py` uses to verify each side.

## 3. Write a converter (new formats only)

`tools/convert/<name>.py` exposes one function:

```python
def convert(files: dict[str, Path], packs: list[dict]) -> dict:
    """files: download name → path in raw/; packs: the sources.toml entries."""
    ...
    return {pack["id"]: (rows, {"version": "Source 1.2 (2026-10-01)"})}
```

Each row is a dict with `word` and `definition`, plus `pos`, `romanization`
and `sense` where the source has them, and an optional `rank` (any sortable
value; lower comes first within a word). Don't clean, deduplicate or sort,
because `tools/lib/pack.py` does that for every pack. Use `tools/lib/gloss.py`
to turn a dictionary gloss into an English headword plus sense ("to run
(fast)" → `run`, sense `fast`).

Rank so that the everyday translation of a common word comes first. Useful
signals, in rough order of reliability: a source's own frequency or "common"
flag, a learner level, usage labels (dated, literary, regional, slang),
sense order, and how fully the source describes the entry.

## 4. Build and look

```
python3 tools/build.py wiktionary-en-it
python3 - <<'EOF'
import pyarrow.parquet as pq
rows = pq.read_table("packs/wiktionary-en-it.parquet").to_pylist()
for w in ["love", "water", "run", "book", "beautiful"]:
    print(w, [(r["definition"], r.get("sense")) for r in rows if r["word"] == w][:5])
EOF
```

The first translations must be the ones a learner expects. Fix the rank until
they are, then read a random sample for junk: markup, pointers like "see X",
English left in definitions, or dialect forms ranked first.

## 5. Check, commit, link

```
python3 tools/check.py                       # must print 0 problems
python3 tools/comment_check.py tools/convert/<name>.py
git add sources.toml packs/ catalog.json README.md tools/ docs/research.md
git commit -m "feat(wiktionary-en-it): add the Italian pack"
python3 tools/commit_check.py --range origin/main..HEAD
git push
python3 tools/links.py --ref <commit> --rust # pinned URLs + Rust PACKS rows
```

Then hand the `--rust` output to mareader2 (see [mareader2.md](mareader2.md)).

## Updating a source

Delete its file from `raw/` (and its `.json` receipt), bump the URL in
`sources.toml` if it is pinned, rebuild, and compare row counts with the
catalog in the commit body. A changed pack has a new sha256, so mareader2's
pinned link must move to the new commit.
