"""The languages packs join: mareader2's code, English name and script."""

from __future__ import annotations

import re

# ISO 639-1 codes, except mareader2's "jp" for Japanese.
LANGUAGES = {
    "en": ("English", r"[A-Za-z]"),
    "my": ("Burmese", r"[\u1000-\u109f\ua9e0-\ua9ff\uaa60-\uaa7f]"),
    "jp": ("Japanese", r"[\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff]"),
    "zh": ("Chinese", r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]"),
    "ko": ("Korean", r"[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]"),
    "th": ("Thai", r"[\u0e00-\u0e7f]"),
    "fr": ("French", r"[A-Za-zÀ-ÿ]"),
    "es": ("Spanish", r"[A-Za-zÀ-ÿ]"),
    "de": ("German", r"[A-Za-zÀ-ÿß]"),
}


def name(code: str) -> str:
    return LANGUAGES[code][0]


def script(code: str) -> re.Pattern[str]:
    """What a word in `code` contains at least one of."""
    return re.compile(LANGUAGES[code][1])
