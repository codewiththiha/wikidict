#!/usr/bin/env python3
"""Download a pack's sources and convert them into packs/<id>.parquet.

  python3 tools/build.py cedict-en-zh          # one pack
  python3 tools/build.py --all                 # every pack in sources.toml
  python3 tools/build.py --raw /tmp/raw wiktionary-en-de

Packs sharing a converter and its downloads are built in one pass. Raw
downloads stay in raw/ (git-ignored) so a rebuild doesn't fetch again.
The catalog and the README table are rewritten afterwards.
"""

from __future__ import annotations

import argparse
import importlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import catalog, pack, sources  # noqa: E402
from lib.fetch import fetch  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="pack ids from sources.toml")
    ap.add_argument("--all", action="store_true", help="build every pack")
    ap.add_argument("--raw", type=Path, default=sources.RAW,
                    help="where downloads are kept (default: raw/)")
    args = ap.parse_args()
    listed = {p["id"]: p for p in sources.packs()}
    ids = list(listed) if args.all else args.ids
    unknown = [i for i in ids if i not in listed]
    if not ids or unknown:
        ap.error(f"name packs from sources.toml: {', '.join(listed)}")

    groups: dict[tuple, list[dict]] = {}
    for i in ids:
        p = listed[i]
        key = (p["converter"], tuple(d["url"] for d in p["downloads"]))
        groups.setdefault(key, []).append(p)

    for (converter, _), packs in groups.items():
        started = time.time()
        files, receipts = {}, []
        for d in packs[0]["downloads"]:
            dest = args.raw / d["file"]
            receipts.append(fetch(d["url"], dest))
            files[d["file"]] = dest
        module = importlib.import_module(f"convert.{converter}")
        built = module.convert(files, packs)
        for p in packs:
            rows, info = built[p["id"]]
            meta = {
                "id": p["id"], "from": p["from"], "to": p["to"],
                "name": p["name"], "licence": p["licence"],
                "homepage": p["homepage"], "version": info["version"],
                "downloads": [{k: r[k] for k in ("url", "sha256", "bytes")}
                              for r in receipts],
            }
            kept = pack.write(rows, sources.path(p), meta)
            size = sources.path(p).stat().st_size / 1e6
            print(f"{p['id']}: {kept:,} rows, {size:.1f} MB "
                  f"({info['version']}, {time.time() - started:.0f}s)")
    catalog.write()


if __name__ == "__main__":
    main()
