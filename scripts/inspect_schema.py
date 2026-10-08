#!/usr/bin/env python3
"""Research tool: inspect the structure of kaikki.org JSONL dumps.

Answers the question "do all language dumps share the same shape?" by
sampling lines from each file and reporting:

  * how often each top-level key appears,
  * how often each sense-level key appears,
  * the POS (part-of-speech) distribution,
  * example records.

Usage:
    python scripts/inspect_schema.py data/raw/*.jsonl
    python scripts/inspect_schema.py data/raw/Japanese.jsonl --sample 5000
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def sample_lines(path: Path, n: int) -> list[str]:
    """Take n lines spread evenly across the file (fast, no full parse)."""
    size = path.stat().st_size
    if size == 0:
        return []
    with open(path, "rb") as fh:
        if size < 50_000_000:  # small file: just read it all
            lines = fh.read().splitlines()
            step = max(1, len(lines) // n)
            return [l.decode("utf-8", "replace") for l in lines[::step]][:n]
        lines = []
        for i in range(n):
            offset = size * i // n
            fh.seek(offset)
            fh.readline()          # finish the partial line we landed on
            line = fh.readline()   # take the next complete one
            if line:
                lines.append(line.decode("utf-8", "replace"))
        return lines


def inspect(path: Path, n: int) -> dict:
    top_keys = Counter()
    sense_keys = Counter()
    pos = Counter()
    n_lines = 0
    n_senses = 0
    sound_keys = Counter()

    for line in sample_lines(path, n):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        n_lines += 1
        for k in obj:
            top_keys[k] += 1
        pos[obj.get("pos", "?")] += 1
        for s in obj.get("senses", []) or []:
            n_senses += 1
            for k in s:
                sense_keys[k] += 1
        for s in obj.get("sounds", []) or []:
            for k in s:
                sound_keys[k] += 1

    return {
        "file": str(path),
        "sampled_entries": n_lines,
        "sampled_senses": n_senses,
        "top_level_keys": top_keys,
        "sense_keys": sense_keys,
        "sound_keys": sound_keys,
        "pos": pos,
    }


def report(res: dict) -> str:
    out = []
    n = max(res["sampled_entries"], 1)
    ns = max(res["sampled_senses"], 1)
    out.append(f"\n{'='*72}\nFILE: {res['file']}\n"
               f"sampled {n} entries, {ns} senses\n{'='*72}")

    def table(counter: Counter, denom: int, label: str) -> str:
        rows = [f"  {label}:"]
        for k, v in counter.most_common():
            rows.append(f"    {k:<22} {v:>6}  ({v/denom*100:5.1f}%)")
        return "\n".join(rows)

    out.append(table(res["top_level_keys"], n, "top-level keys"))
    out.append(table(res["sense_keys"], ns, "sense-level keys"))
    out.append(table(res["sound_keys"], n, "sound-entry keys"))
    out.append(table(res["pos"], n, "POS values"))
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--sample", type=int, default=3000,
                    help="number of lines to sample per file")
    args = ap.parse_args()

    results = [inspect(f, args.sample) for f in args.files]
    text = "\n".join(report(r) for r in results)
    print(text)

    # cross-file comparison: are the key sets the same?
    if len(results) > 1:
        print("\n" + "=" * 72)
        print("CROSS-FILE COMPARISON (top-level keys, >5% coverage)")
        print("=" * 72)
        sets = {}
        for r in results:
            n = max(r["sampled_entries"], 1)
            sets[r["file"]] = {k for k, v in r["top_level_keys"].items()
                               if v / n > 0.05}
        common = set.intersection(*sets.values())
        print(f"keys present (>5%) in ALL files: {sorted(common)}")
        for f, s in sets.items():
            only = s - common
            if only:
                print(f"extra in {f}: {sorted(only)}")


if __name__ == "__main__":
    main()
