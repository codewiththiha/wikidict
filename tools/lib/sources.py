"""The repository's layout and its list of packs, sources.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path

from lib import langs

ROOT = Path(__file__).resolve().parents[2]
PACKS = ROOT / "packs"
RAW = ROOT / "raw"
CATALOG = ROOT / "catalog.json"
README = ROOT / "README.md"
NEEDED = ("id", "from", "to", "name", "converter", "licence", "homepage",
          "downloads")


def packs() -> list[dict]:
    """Every pack in sources.toml, checked for the keys a build needs."""
    with open(ROOT / "sources.toml", "rb") as fh:
        listed = tomllib.load(fh).get("pack", [])
    ids = set()
    for pack in listed:
        missing = [k for k in NEEDED if k not in pack]
        if missing:
            raise SystemExit(f"sources.toml: {pack.get('id')} lacks {missing}")
        if pack["id"] in ids:
            raise SystemExit(f"sources.toml: {pack['id']} is listed twice")
        for side in (pack["from"], pack["to"]):
            if side not in langs.LANGUAGES:
                raise SystemExit(f"sources.toml: add {side} to lib/langs.py")
        ids.add(pack["id"])
    return listed


def path(pack: dict) -> Path:
    return PACKS / f"{pack['id']}.parquet"
