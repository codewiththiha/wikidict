"""catalog.json and the README's pack table, made from the packs.

Both are generated: edit sources.toml or rebuild a pack, then run
tools/catalog.py. tools/check.py fails when either is out of date.
"""

from __future__ import annotations

import hashlib
import json

import pyarrow.parquet as pq

from lib import langs, pack, sources

START = "<!-- packs:start -->"
END = "<!-- packs:end -->"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def entries() -> list[dict]:
    """One entry per built pack, in sources.toml order."""
    out = []
    for p in sources.packs():
        file = sources.path(p)
        if not file.exists():
            continue
        meta = pack.metadata(file)
        table = pq.read_table(file)
        filled = [c for c in table.column_names
                  if table.column(c).null_count < table.num_rows]
        out.append({
            "id": p["id"],
            "file": f"packs/{file.name}",
            "from": p["from"],
            "to": p["to"],
            "label": f"{langs.name(p['from'])} → {langs.name(p['to'])}",
            "name": p["name"],
            "rows": table.num_rows,
            "bytes": file.stat().st_size,
            "sha256": _sha256(file.read_bytes()),
            "columns": filled,
            "version": meta.get("version"),
            "built": meta.get("built"),
            "licence": p["licence"],
            "homepage": p["homepage"],
            "downloads": meta.get("downloads", []),
        })
    return out


def text() -> str:
    return json.dumps({"packs": entries()}, ensure_ascii=False, indent=2) + "\n"


def table() -> str:
    lines = [
        "| Pack | Languages | Rows | Size | Columns | Source | Licence |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for e in entries():
        extra = ", ".join(c for c in e["columns"] if c not in pack.REQUIRED)
        lines.append(
            f"| `{e['id']}` | {e['label']} | {e['rows']:,} | "
            f"{e['bytes'] / 1e6:.1f} MB | {extra or '–'} | "
            f"[{e['version']}]({e['homepage']}) | {e['licence']} |"
        )
    return "\n".join(lines)


def readme() -> str:
    """README.md with its pack table brought up to date."""
    body = sources.README.read_text()
    head, rest = body.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{table()}\n{END}{tail}"


def write() -> None:
    sources.CATALOG.write_text(text())
    sources.README.write_text(readme())
