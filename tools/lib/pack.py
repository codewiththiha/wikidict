"""Writes and reads packs: the Parquet files mareader2 downloads.

The contract lives in docs/pack-format.md; `write` enforces it and
`problems` reports every way a file breaks it.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Iterable

import pyarrow as pa
import pyarrow.parquet as pq

COLUMNS = ("word", "pos", "definition", "romanization", "sense")
REQUIRED = ("word", "definition")
# mareader2 cuts longer cells and refuses more rows (crates/dict/src/build.rs).
MAX_CELL = 2_000
MAX_ROWS = 5_000_000
# What mareader2's parquet reader decodes.
CODECS = {"ZSTD", "SNAPPY", "UNCOMPRESSED"}
META_KEY = b"mareader.pack"

# The part-of-speech words a pack may use; mareader2 shows them as written.
POS = {
    "noun", "verb", "adjective", "adverb", "pronoun", "preposition",
    "postposition", "conjunction", "interjection", "determiner", "article",
    "number", "counter", "particle", "auxiliary", "prefix", "suffix",
    "phrase", "proverb", "name", "abbreviation", "symbol", "contraction",
    "classifier", "other",
}

_SPACE = re.compile(r"\s+")
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"))


def clean(text: object) -> str | None:
    """A cell as one tidy line, NFC, cut to MAX_CELL; blank is None."""
    if text is None:
        return None
    s = unicodedata.normalize("NFC", str(text)).translate(_INVISIBLE)
    s = _SPACE.sub(" ", s.replace("\xa0", " ")).strip()
    return s[:MAX_CELL] or None


def write(rows: Iterable[dict], out: Path, meta: dict) -> int:
    """Writes `rows` as a pack at `out`; the rows kept.

    Rows lacking a word or definition are dropped, exact repeats show once,
    and rows are grouped by headword. Within one, a row's optional `rank`
    (lower first) orders them, then the source's own order; mareader2 shows
    a headword's first rows when it can't show all.
    """
    seen: dict[tuple, int] = {}
    kept: list[tuple] = []
    ranks: list = []
    for row in rows:
        cells = tuple(clean(row.get(c)) for c in COLUMNS)
        word, pos, definition = cells[0], cells[1], cells[2]
        if not word or not definition:
            continue
        if pos is not None and pos not in POS:
            raise ValueError(f"part of speech {pos!r} is not in pack.POS")
        rank = row.get("rank", 0)
        if cells in seen:
            at = seen[cells]
            ranks[at] = min(ranks[at], rank)
            continue
        seen[cells] = len(kept)
        kept.append(cells)
        ranks.append(rank)
    if not kept:
        raise ValueError("no rows to write")
    if len(kept) > MAX_ROWS:
        raise ValueError(f"{len(kept)} rows is more than mareader2 takes")
    order = sorted(range(len(kept)),
                   key=lambda i: (kept[i][0].casefold(), kept[i][0], ranks[i]))
    kept = [kept[i] for i in order]
    columns = {
        name: pa.array([r[i] for r in kept], type=pa.string())
        for i, name in enumerate(COLUMNS)
    }
    meta = {**meta, "rows": len(kept), "built": date.today().isoformat()}
    table = pa.table(columns).replace_schema_metadata(
        {META_KEY: json.dumps(meta, ensure_ascii=False, sort_keys=True)}
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    pq.write_table(table, tmp, compression="zstd", compression_level=15,
                   row_group_size=100_000)
    tmp.replace(out)
    return len(kept)


def metadata(path: Path) -> dict:
    """The provenance a pack was written with; empty if it has none."""
    raw = (pq.read_schema(path).metadata or {}).get(META_KEY)
    return json.loads(raw) if raw else {}


def problems(path: Path) -> list[str]:
    """Every way the file at `path` breaks the pack contract."""
    out: list[str] = []
    try:
        file = pq.ParquetFile(path)
    except Exception as e:  # noqa: BLE001 - any unreadable file is a problem
        return [f"not readable as Parquet: {e}"]
    schema = file.schema_arrow
    names = schema.names
    for name in REQUIRED:
        if name not in names:
            out.append(f"no {name} column")
    for field in schema:
        if field.name not in COLUMNS:
            out.append(f"column {field.name} is not in the contract")
        elif not pa.types.is_string(field.type):
            out.append(f"column {field.name} is {field.type}, not string")
    meta = file.metadata
    if meta.num_rows > MAX_ROWS:
        out.append(f"{meta.num_rows} rows is more than {MAX_ROWS}")
    codecs = {
        meta.row_group(g).column(c).compression
        for g in range(meta.num_row_groups)
        for c in range(meta.num_columns)
    }
    if not codecs <= CODECS:
        out.append(f"compression {sorted(codecs - CODECS)} mareader2 can't read")
    if out:
        return out
    table = file.read()
    for name in REQUIRED:
        col = table.column(name).to_pylist()
        blank = sum(1 for v in col if not v or not v.strip())
        if blank:
            out.append(f"{blank} rows with a blank {name}")
    for name in names:
        long = sum(1 for v in table.column(name).to_pylist()
                   if v and len(v) > MAX_CELL)
        if long:
            out.append(f"{long} {name} cells longer than {MAX_CELL}")
    if "pos" in names:
        odd = {v for v in table.column("pos").to_pylist() if v} - POS
        if odd:
            out.append(f"parts of speech outside pack.POS: {sorted(odd)[:8]}")
    return out
