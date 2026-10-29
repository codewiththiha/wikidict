#!/usr/bin/env python3
"""Rewrite catalog.json and the README's pack table from packs/."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import catalog  # noqa: E402

if __name__ == "__main__":
    catalog.write()
    print("catalog.json and README.md are up to date")
