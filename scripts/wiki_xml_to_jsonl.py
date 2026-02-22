from __future__ import annotations

import bz2
import gzip
import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Iterable, Optional, Tuple


def _open_maybe_compressed(path: Path) -> IO[bytes]:
    name = path.name.lower()
    if name.endswith(".bz2"):
        return bz2.open(path, "rb")
    if name.endswith(".gz"):
        return gzip.open(path, "rb")
    return open(path, "rb")


def _wiki_domain(lang: str) -> str:
    if lang == "en":
        return "en.wikipedia.org"
    if lang == "id":
        return "id.wikipedia.org"
    if lang == "es":
        return "es.wikipedia.org"
    if lang == "fr":
        return "fr.wikipedia.org"
    if lang == "pt":
        return "pt.wikipedia.org"
    if lang == "zh":
        return "zh.wikipedia.org"
    if lang == "ja":
        return "ja.wikipedia.org"
    # fallback
    return f"{lang}.wikipedia.org"


def _clean_wikitext(text: str) -> str:
    """A pragmatic cleaner for Wikipedia wikitext (not perfect, but robust).

    We remove:
    - HTML tags and refs
    - Templates {{...}} (best-effort, iterative)
    - Tables {| ... |}
    - Links [[A|B]] -> B, [[A]] -> A
    - Categories/files and common markup
    """
    t = text or ""
    t = html.unescape(t)

    # Remove comments
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)

    # Remove ref tags
    t = re.sub(r"<ref[^>/]*/\s*>", " ", t, flags=re.I)
    t = re.sub(r"<ref.*?>.*?</ref>", " ", t, flags=re.S | re.I)

    # Remove other HTML tags
    t = re.sub(r"<[^>]+>", " ", t)

    # Remove tables
    t = re.sub(r"\{\|.*?\|\}", " ", t, flags=re.S)

    # Remove templates {{...}} iteratively to handle shallow nesting
    for _ in range(12):
        new = re.sub(r"\{\{[^{}]*\}\}", " ", t)
        if new == t:
            break
        t = new

    # File / Image links
    t = re.sub(r"\[\[(File|Image):[^\]]+\]\]", " ", t, flags=re.I)

    # Categories
    t = re.sub(r"\[\[Category:[^\]]+\]\]", " ", t, flags=re.I)

    # Links [[A|B]] -> B ; [[A]] -> A
    t = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", t)
    t = re.sub(r"\[\[([^\]]+)\]\]", r"\1", t)

    # Headings == ==
    t = re.sub(r"={2,}\s*(.*?)\s*={2,}", r"\1", t)

    # URLs / external links [http://.. label]
    t = re.sub(r"\[https?://[^\s\]]+\s*([^\]]*)\]", r"\1", t)

    # Remove remaining brackets/braces
    t = t.replace("[", " ").replace("]", " ").replace("{", " ").replace("}", " ")

    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def build_jsonl_from_wikipedia_dump(
    dump_path: Path,
    out_path: Path,
    lang: str,
    source_title: str,
    max_pages: int = 25000,
    min_chars: int = 240,
) -> int:
    """Stream-parse a Wikipedia XML dump and write a clean JSONL dataset.

    Notes:
    - This is intentionally simple and pure Python (no external parsers).
    - It processes only main namespace (ns=0) pages and skips redirects.
    - For huge dumps, consider lowering max_pages.
    """
    count = 0
    domain = _wiki_domain(lang)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with _open_maybe_compressed(dump_path) as f, open(out_path, "w", encoding="utf-8") as out:
        # iterparse is incremental; we look for <page> end events.
        ctx = ET.iterparse(f, events=("end",))
        for event, elem in ctx:
            if not elem.tag.endswith("page"):
                continue

            ns = elem.findtext("./{*}ns") or "0"
            title = elem.findtext("./{*}title") or ""
            redirect = elem.find("./{*}redirect") is not None

            if ns != "0" or redirect:
                elem.clear()
                continue

            text = elem.findtext("./{*}revision/{*}text") or ""
            cleaned = _clean_wikitext(text)
            if len(cleaned) < min_chars:
                elem.clear()
                continue

            url_title = title.replace(" ", "_")
            url = f"https://{domain}/wiki/{url_title}"

            obj = {
                "title": title,
                "lang": lang,
                "source": source_title,
                "url": url,
                "text": cleaned,
            }
            out.write(json.dumps(obj, ensure_ascii=False) + "\n")

            count += 1
            if count >= max_pages:
                break

            # Important to free memory
            elem.clear()

    return count
