#!/usr/bin/env python3
"""Print pinned download links for mareader2, checked against a commit.

  python3 tools/links.py                 # pin to origin/main
  python3 tools/links.py --ref 1a2b3c4   # pin to a given commit
  python3 tools/links.py --rust          # also print packs.rs constants

A link names a full commit hash, never a branch, so what mareader2
downloads can't change under it. Every pack at that commit is checked
against catalog.json first, so the printed sizes and hashes are its own.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import sources  # noqa: E402

REPO = "codewiththiha/wikidict"
MIRRORS = (
    "https://raw.githubusercontent.com/{repo}/{sha}/packs",
    "https://cdn.jsdelivr.net/gh/{repo}@{sha}/packs",
    "https://fastly.jsdelivr.net/gh/{repo}@{sha}/packs",
)


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=sources.ROOT, check=True,
                          capture_output=True).stdout


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--rust", action="store_true")
    args = ap.parse_args()
    sha = git("rev-parse", "--verify", f"{args.ref}^{{commit}}").decode().strip()
    listed = json.loads(git("show", f"{sha}:catalog.json"))["packs"]
    bases = [m.format(repo=REPO, sha=sha) for m in MIRRORS]
    bad = 0
    for e in listed:
        data = git("show", f"{sha}:{e['file']}")
        if hashlib.sha256(data).hexdigest() != e["sha256"]:
            print(f"{e['id']}: differs from catalog.json at {sha[:7]}")
            bad += 1
    if bad:
        return 1
    print(f"commit {sha}\n")
    for e in listed:
        print(f"{e['id']}  {e['label']}  {e['rows']:,} rows  "
              f"{e['bytes']:,} bytes  sha256 {e['sha256']}")
        for base in bases:
            print(f"  {base}/{e['id']}.parquet")
    if args.rust:
        print()
        for name, base in zip(("REPO", "CDN", "FASTLY"), bases):
            print(f'const {name}: &str = "{base}";')
        print(f"\npub const PACKS: [Pack; {len(listed)}] = [")
        for e in listed:
            print(f'    Pack {{\n        id: "{e["id"]}",\n'
                  f'        source: "{e["from"]}",\n'
                  f'        target: "{e["to"]}",\n'
                  f'        entries: {e["rows"]:_},\n'
                  f'        bytes: {e["bytes"]:_},\n    }},')
        print("];")
    return 0


if __name__ == "__main__":
    sys.exit(main())
