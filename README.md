# wikidict

Open English → X dictionary packs for
[mareader2](https://github.com/codewiththiha/mareader2), one Parquet file per
language pair, built from openly licensed dictionary data.

<!-- packs:start -->
| Pack | Languages | Rows | Size | Columns | Source | Licence |
|---|---|---:|---:|---|---|---|
| `mcfnlp-en-my` | English → Burmese | 107,861 | 1.5 MB | pos | [mcfnlp/Dictionary (2016), Hugging Face revision d32893d](https://github.com/mcfnlp/Dictionary) | unstated |
| `jmdict-en-jp` | English → Japanese | 421,385 | 6.9 MB | pos, romanization, sense | [JMdict 3.6.2 (2026-10-26)](https://www.edrdg.org/jmdict/j_jmdict.html) | CC-BY-SA-4.0 |
| `cedict-en-zh` | English → Chinese | 178,950 | 3.8 MB | pos, romanization, sense | [CC-CEDICT of 2026-10-29](https://www.mdbg.net/chinese/dictionary?page=cc-cedict) | CC-BY-SA-4.0 |
| `krdict-en-ko` | English → Korean | 106,822 | 2.5 MB | pos, sense | [krdict XML of 2019-08-02](https://krdict.korean.go.kr/) | CC-BY-SA-2.0-KR |
| `volubilis-en-th` | English → Thai | 191,708 | 3.1 MB | pos, romanization, sense | [Volubilis v. 26.2 (Jul. 2026)](https://belisan-volubilis.blogspot.com/) | CC-BY-SA-4.0 |
| `wiktionary-en-fr` | English → French | 128,246 | 2.7 MB | pos, romanization, sense | [English Wiktionary extract of 2026-10-25](https://en.wiktionary.org/) | CC-BY-SA-4.0 |
| `wiktionary-en-es` | English → Spanish | 146,587 | 2.7 MB | pos, romanization, sense | [English Wiktionary extract of 2026-10-25](https://en.wiktionary.org/) | CC-BY-SA-4.0 |
| `wiktionary-en-de` | English → German | 161,737 | 3.1 MB | pos, romanization, sense | [English Wiktionary extract of 2026-10-25](https://en.wiktionary.org/) | CC-BY-SA-4.0 |
<!-- packs:end -->

Every pack has `word` (English) and `definition`; the Columns cell lists the
optional ones. Rows, sizes and sha256 hashes for each pack are in
[`catalog.json`](catalog.json). Where each source came from, and why others
were turned down, is in [docs/research.md](docs/research.md).

## Using a pack

Download it from a commit hash, so the bytes never change under you:

```
https://raw.githubusercontent.com/codewiththiha/wikidict/<commit>/packs/<id>.parquet
https://cdn.jsdelivr.net/gh/codewiththiha/wikidict@<commit>/packs/<id>.parquet
```

`python3 tools/links.py --ref <commit>` prints these for every pack and checks
each file's sha256 at that commit against the catalog. Any Parquet reader
works:

```python
import pyarrow.parquet as pq
rows = pq.read_table("packs/cedict-en-zh.parquet").to_pylist()
```

The format is described in [docs/pack-format.md](docs/pack-format.md), and
mareader2's use of it in [docs/mareader2.md](docs/mareader2.md).

## Building

```
pip install -r requirements.txt
python3 tools/build.py cedict-en-zh      # one pack
python3 tools/build.py --all             # everything in sources.toml
python3 tools/check.py                   # the CI gate
```

Downloads are cached in `raw/` (git-ignored). Adding a language is described
in [docs/adding-a-pack.md](docs/adding-a-pack.md); contributors and agents
follow [AGENTS.md](AGENTS.md).

## Licences

Each pack keeps its source's licence, given in the
table above; share-alike packs must be shared alike, with credit to the
source. `mcfnlp-en-my` comes from a repository that states no licence, as
recorded in [docs/research.md](docs/research.md).
