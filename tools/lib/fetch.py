"""Resumable downloads that remember where each file came from."""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

CHUNK = 1 << 20
AGENT = "wikidict-builder (+https://github.com/codewiththiha/wikidict)"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def receipt(dest: Path) -> dict:
    """What `fetch` recorded about `dest`: url, bytes, sha256, dates."""
    side = dest.with_name(dest.name + ".json")
    return json.loads(side.read_text()) if side.exists() else {}


def fetch(url: str, dest: Path) -> dict:
    """`url` saved at `dest` unless already whole there; its receipt.

    A partial `.part` file is resumed. The receipt sits beside the file as
    `<name>.json` and is what packs cite as their source.
    """
    known = receipt(dest)
    if dest.exists() and known.get("url") == url:
        return known
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    if have:
        request.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(request, timeout=60) as response:
        if have and response.status != 206:
            have = 0
        total = have + int(response.headers.get("Content-Length") or 0)
        modified = response.headers.get("Last-Modified")
        with open(part, "ab" if have else "wb") as fh:
            done = have
            for block in iter(lambda: response.read(CHUNK), b""):
                fh.write(block)
                done += len(block)
                if total:
                    print(f"\r  {dest.name}: {done * 100 // total}%",
                          end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    part.replace(dest)
    made = {
        "url": url,
        "bytes": dest.stat().st_size,
        "sha256": _sha256(dest),
        "fetched": datetime.now(timezone.utc).date().isoformat(),
    }
    if modified:
        made["modified"] = parsedate_to_datetime(modified).date().isoformat()
    dest.with_name(dest.name + ".json").write_text(json.dumps(made, indent=2))
    return made
