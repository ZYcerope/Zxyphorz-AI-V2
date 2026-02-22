from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


def safe_read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default
    except Exception:
        return default


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def slugify(text: str, limit: int = 60) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-]", "", text)
    text = re.sub(r"\s+", "-", text).strip("-")
    return text[:limit] if text else "item"


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def getenv_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def stable_hash_tokens(tokens: Sequence[str]) -> int:
    """A stable-ish integer hash for token sequences (for caching).

    We avoid Python's built-in hash() since it is randomized per-process.
    """
    h = 2166136261  # FNV-1a basis
    for t in tokens:
        for ch in t:
            h ^= ord(ch)
            h *= 16777619
            h &= 0xFFFFFFFF
        h ^= 0xFF
        h *= 16777619
        h &= 0xFFFFFFFF
    return int(h)


@dataclass(frozen=True)
class Timer:
    start: float

    @staticmethod
    def start_now() -> "Timer":
        return Timer(start=time.perf_counter())

    def ms(self) -> int:
        return int((time.perf_counter() - self.start) * 1000)
