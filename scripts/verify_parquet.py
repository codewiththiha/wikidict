#!/usr/bin/env python3
"""Verify the generated Parquet files: schema, sample rows, SQLite round-trip.

Usage:
    python scripts/verify_parquet.py output/*.parquet
    python scripts/verify_parquet.py output/eng-jp.parquet --sqlite   # test SQLite conversion
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


def show(path: Path, sqlite: bool) -> None:
    print("=" * 78)
    print(f"FILE: {path}   ({path.stat().st_size/1e6:.1f} MB)")
    print("=" * 78)

    pf = pq.ParquetFile(path)
    print(f"rows: {pf.metadata.num_rows:,}   row groups: {pf.metadata.num_row_groups}")
    meta = pf.schema_arrow.metadata or {}
    for k in (b"dictionary", b"word_language", b"source_url", b"built_on"):
        if k in meta:
            print(f"  {k.decode()}: {meta[k].decode()}")

    print("\nschema:")
    for field in pf.schema_arrow:
        print(f"  {field.name:<16} {field.type}")

    df = pf.read().to_pandas()
    print("\nsample rows (word | pos | definition):")
    with_def = df[df["definition"].str.len() > 0]
    for _, r in with_def.sample(min(5, len(with_def)), random_state=7).iterrows():
        d = r["definition"][:90] + ("…" if len(r["definition"]) > 90 else "")
        print(f"  {r['word']!s:<20} {r['pos']:<6} {d}")

    print(f"\nempty definitions: {(df['definition'] == '').sum():,}")

    if sqlite:
        print("\n-- SQLite round-trip test --")
        con = sqlite3.connect(":memory:")
        n = df.to_sql("dict", con, index=False, if_exists="replace")
        (count,) = con.execute("SELECT COUNT(*) FROM dict").fetchone()
        q = "SELECT word, pos, definition FROM dict WHERE definition != '' LIMIT 3"
        print(f"inserted {n:,} rows into sqlite in-memory table 'dict' (count={count:,})")
        for w, p, d in con.execute(q):
            print(f"  SQL> {w} ({p}): {d[:70]}")
        con.close()
        print("SQLite round-trip: OK")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--sqlite", action="store_true",
                    help="also convert each file into an in-memory SQLite db as a sanity check")
    args = ap.parse_args()
    for f in args.files:
        show(f, args.sqlite)


if __name__ == "__main__":
    main()
