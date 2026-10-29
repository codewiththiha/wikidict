#!/usr/bin/env python3
"""Check every pack against the contract mareader2 reads, and the catalog.

  python3 tools/check.py          # exit 1 on any problem

Each pack in sources.toml must exist, be listed once, follow
docs/pack-format.md, carry matching provenance, read English on the word
side and its language on the definition side, and appear in catalog.json
and the README exactly as tools/catalog.py would write them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import catalog, langs, pack, sources  # noqa: E402

# Shares of rows a side must read in its language's script.
WORD_SHARE = 0.97
DEFINITION_SHARE = 0.95


def _share(values: list[str], code: str) -> float:
    script = langs.script(code)
    return sum(1 for v in values if script.search(v)) / max(len(values), 1)


def check_pack(p: dict) -> list[str]:
    file = sources.path(p)
    if not file.exists():
        return [f"missing; run tools/build.py {p['id']}"]
    found = pack.problems(file)
    if found:
        return found
    meta = pack.metadata(file)
    for key in ("id", "from", "to", "licence"):
        if meta.get(key) != p[key]:
            found.append(f"metadata {key}={meta.get(key)!r}, sources.toml "
                         f"says {p[key]!r}; rebuild it")
    table = pq.read_table(file, columns=["word", "definition"])
    words = table.column("word").to_pylist()
    definitions = table.column("definition").to_pylist()
    if _share(words, p["from"]) < WORD_SHARE:
        found.append(f"under {WORD_SHARE:.0%} of words read as {p['from']}")
    if _share(definitions, p["to"]) < DEFINITION_SHARE:
        found.append(f"under {DEFINITION_SHARE:.0%} of definitions read "
                     f"as {p['to']}")
    return found


def main() -> int:
    failures = []
    listed = sources.packs()
    for p in listed:
        for problem in check_pack(p):
            failures.append(f"{p['id']}: {problem}")
    known = {f"{p['id']}.parquet" for p in listed}
    for file in sorted(sources.PACKS.glob("*")):
        if file.name not in known:
            failures.append(f"packs/{file.name}: not in sources.toml")
    if not sources.CATALOG.exists() or sources.CATALOG.read_text() != catalog.text():
        failures.append("catalog.json is stale; run tools/catalog.py")
    if sources.README.read_text() != catalog.readme():
        failures.append("README.md pack table is stale; run tools/catalog.py")
    for line in failures:
        print(line)
    print(f"{len(listed)} packs checked, {len(failures)} problems")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
