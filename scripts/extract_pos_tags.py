#!/usr/bin/env python3
"""Extract the POS tag vocabulary of every Parquet file into .txt reports.

For each parquet under output/ (recursive) that has a `pos` column, writes
    output/pos-tags/<file>.txt      unique pos values with their counts
and a global
    output/pos-tags/SUMMARY.txt     rows/unique-pos per file + cross-file
                                    comparison (how different the tag sets are)

Usage:
    python scripts/extract_pos_tags.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow.parquet as pq


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="output",
                    help="directory scanned for *.parquet (recursive)")
    ap.add_argument("--outdir", default="output/pos-tags")
    args = ap.parse_args()

    root = Path(args.root)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in root.rglob("*.parquet")
                   if outdir not in p.parents)
    per_file: dict[str, dict[str, int]] = {}
    rows_per_file: dict[str, int] = {}

    for path in files:
        table = pq.read_table(path, columns=["pos"]) if "pos" in pq.ParquetFile(path).schema_arrow.names else None
        if table is None:
            continue
        series = table.column("pos").to_pylist()
        rows_per_file[str(path)] = len(series)
        counts: dict[str, int] = {}
        for v in series:
            v = (v if v is not None else "")
            counts[v] = counts.get(v, 0) + 1
        per_file[str(path)] = counts

        flat = str(path.relative_to(root)).replace("/", "__").removesuffix(".parquet")
        dest = outdir / f"{flat}.txt"
        lines = [
            f"# POS tags in {path}",
            f"# rows: {len(series):,}   unique pos values: {len(counts)}",
            "",
            "value\tcount",
        ]
        for v, c in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
            shown = v if v else "(empty)"
            lines.append(f"{shown}\t{c:,}")
        dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{path}  rows={len(series):,}  unique pos={len(counts)}  -> {dest}")

    # ---- cross-file summary ---------------------------------------------
    all_values = sorted(set().union(*[set(c) for c in per_file.values()]))
    lines = [
        "POS TAG COMPARISON ACROSS ALL PARQUET FILES",
        "=" * 60,
        "",
        f"{'file':<52} {'rows':>10} {'unique pos':>10}",
        "-" * 76,
    ]
    for f in sorted(per_file):
        lines.append(f"{f:<52} {rows_per_file[f]:>10,} {len(per_file[f]):>10}")
    lines += [
        "",
        f"UNION of all pos values across files: {len(all_values)} distinct",
        "",
        f"{'pos value':<24} files containing it ({len(per_file)} total)",
        "-" * 76,
    ]
    names = {f: str(Path(f).relative_to(root)) for f in per_file}
    for v in all_values:
        present = sorted(names[f] for f in per_file if v in per_file[f])
        shown = v if v else "(empty)"
        lines.append(f"{shown:<24} {len(present):>2}  {', '.join(present)}")

    summary = outdir / "SUMMARY.txt"
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nsummary -> {summary}")


if __name__ == "__main__":
    main()
