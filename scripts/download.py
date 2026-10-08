#!/usr/bin/env python3
"""Download Wiktionary JSONL dumps from kaikki.org.

kaikki.org publishes, for every language of Wiktionary, one JSONL file where
each line is a single dictionary entry (word + POS + senses with English
glosses, sounds, etymology, ...) extracted from the *English* Wiktionary.

Because the definitions of every language are written in English, these files
are ready-made "English <-> X" bilingual dictionaries:

    Japanese word + English gloss  ->  eng-jp dictionary
    French   word + English gloss  ->  eng-fr dictionary
    Burmese  word + English gloss  ->  eng-mm dictionary  (Myanmar)

Usage:
    python scripts/download.py                # download all configured datasets
    python scripts/download.py Japanese       # download only one
    python scripts/download.py --outdir data/raw
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

KAICKI_URL = (
    "https://kaikki.org/dictionary/{lang}/words/"
    "kaikki.org-dictionary-{lang}-words.jsonl"
)

#: language name on kaikki.org  ->  local filename
DEFAULT_LANGS = {
    "Japanese": "Japanese.jsonl",
    "French": "French.jsonl",
    "Burmese": "Burmese.jsonl",  # the Myanmar language is "Burmese" on Wiktionary
}

CHUNK = 1 << 20  # 1 MiB


def remote_size(url: str) -> int | None:
    try:
        r = requests.head(url, timeout=30, allow_redirects=True)
        r.raise_for_status()
        return int(r.headers.get("Content-Length", 0)) or None
    except Exception:
        return None


def download(lang: str, outdir: Path, filename: str | None = None) -> Path:
    url = KAICKI_URL.format(lang=lang.replace(" ", "%20"))
    dest = outdir / (filename or f"{lang}.jsonl")
    outdir.mkdir(parents=True, exist_ok=True)

    total = remote_size(url)
    existing = dest.stat().st_size if dest.exists() else 0

    # Resume support: the server honours Range requests.
    headers = {}
    if existing and total and existing < total:
        headers["Range"] = f"bytes={existing}-"
        mode = "ab"
        print(f"[{lang}] resuming {dest.name} from {existing/1e6:.1f} MB")
    elif existing and total and existing >= total:
        print(f"[{lang}] {dest.name} already complete ({existing/1e6:.1f} MB)")
        return dest
    else:
        mode = "wb"
        existing = 0

    with requests.get(url, headers=headers, stream=True, timeout=60) as r:
        if r.status_code == 416:  # range not satisfiable -> already done
            print(f"[{lang}] {dest.name} already complete")
            return dest
        r.raise_for_status()
        done = existing
        last_log = time.time()
        with open(dest, mode) as fh:
            for chunk in r.iter_content(chunk_size=CHUNK):
                if not chunk:
                    continue
                fh.write(chunk)
                done += len(chunk)
                now = time.time()
                if now - last_log > 5:
                    if total:
                        pct = done / total * 100
                        print(f"[{lang}] {done/1e6:8.1f} / {total/1e6:.1f} MB  ({pct:5.1f}%)", flush=True)
                    else:
                        print(f"[{lang}] {done/1e6:8.1f} MB", flush=True)
                    last_log = now

    print(f"[{lang}] done -> {dest} ({dest.stat().st_size/1e6:.1f} MB)")
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("langs", nargs="*", help="languages to download (default: all)")
    ap.add_argument("--outdir", default="data/raw", help="output directory")
    args = ap.parse_args()

    langs = args.langs or list(DEFAULT_LANGS)
    unknown = [l for l in langs if l not in DEFAULT_LANGS]
    if unknown:
        print(f"note: languages not in the default set: {unknown} "
              f"(any Wiktionary language name works)")

    outdir = Path(args.outdir)
    for lang in langs:
        try:
            download(lang, outdir, DEFAULT_LANGS.get(lang))
        except Exception as exc:  # keep going with the remaining languages
            print(f"[{lang}] FAILED: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
