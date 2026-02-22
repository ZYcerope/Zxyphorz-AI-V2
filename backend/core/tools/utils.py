from __future__ import annotations

import re
from typing import Optional, Tuple


def strip_prefix(text: str, *prefixes: str) -> Optional[str]:
    t = text.strip()
    for p in prefixes:
        if t.lower().startswith(p.lower()):
            return t[len(p):].strip()
    return None


def looks_like_math(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    # Must contain at least one digit and only allowed math-ish chars
    if not re.search(r"\d", t):
        return False
    return bool(re.fullmatch(r"[0-9\s\+\-\*\/\%\(\)\.^]+", t))
