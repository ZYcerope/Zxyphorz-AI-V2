from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "data" / "knowledge_packs" / "manifest.json"
RAW_DIR = REPO_ROOT / "data" / "knowledge_packs" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "knowledge_packs" / "processed"


def load_manifest() -> Dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Missing manifest: {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def find_pack(man: Dict[str, Any], pack_id: str) -> Dict[str, Any]:
    for p in man.get("packs", []):
        if p.get("id") == pack_id:
            return p
    raise KeyError(f"Unknown pack id: {pack_id}")


def _fmt_bytes(n: Optional[int]) -> str:
    if n is None:
        return "unknown"
    x = float(n)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if x < 1024.0:
            return f"{x:.1f} {unit}"
        x /= 1024.0
    return f"{x:.1f} PB"


def list_packs(man: Dict[str, Any]) -> None:
    print("Available knowledge packs:")
    for p in man.get("packs", []):
        pid = p.get("id")
        title = p.get("title")
        lang = p.get("lang")
        size = None
        downloads = p.get("downloads") or []
        if downloads:
            size = downloads[0].get("approx_size_bytes")
        print(f"- {pid} | {title} | lang={lang} | size≈{_fmt_bytes(size)}")


def _http_download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    # Resume if possible
    existing = tmp.stat().st_size if tmp.exists() else 0
    headers = {"User-Agent": "ZxyphorzAI/1.0 (offline knowledge pack downloader)"}
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"

    req = Request(url, headers=headers)
    with urlopen(req) as resp:
        total = resp.headers.get("Content-Length")
        total_size = int(total) + existing if total else None

        mode = "ab" if existing > 0 else "wb"
        start = time.time()
        last_print = 0.0
        downloaded = existing

        with open(tmp, mode) as f:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)

                now = time.time()
                if now - last_print > 0.4:
                    last_print = now
                    if total_size:
                        pct = downloaded / total_size * 100.0
                        print(f"  {dest.name}: {pct:5.1f}% ({_fmt_bytes(downloaded)}/{_fmt_bytes(total_size)})", end="\r")
                    else:
                        print(f"  {dest.name}: {_fmt_bytes(downloaded)}", end="\r")

        elapsed = max(0.001, time.time() - start)
        speed = downloaded / elapsed
        print(" " * 120, end="\r")
        print(f"  Done: {dest.name} ({_fmt_bytes(downloaded)}) at {_fmt_bytes(int(speed))}/s")

    tmp.rename(dest)


def download_pack(man: Dict[str, Any], pack_id: str) -> None:
    pack = find_pack(man, pack_id)
    downloads = pack.get("downloads") or []
    if not downloads:
        print("No downloads specified for this pack.")
        return

    out_dir = RAW_DIR / pack_id
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading pack: {pack_id}")
    for d in downloads:
        url = d["url"]
        fname = d["filename"]
        dest = out_dir / fname
        if dest.exists() and dest.stat().st_size > 0:
            print(f"- Skipping existing file: {dest.name}")
            continue
        print(f"- {url}")
        _http_download(url, dest)


def build_pack(pack_id: str, max_pages: int, min_chars: int) -> None:
    # We keep build code in a separate module to keep this CLI small.
    from wiki_xml_to_jsonl import build_jsonl_from_wikipedia_dump

    man = load_manifest()
    pack = find_pack(man, pack_id)

    downloads = pack.get("downloads") or []
    if not downloads:
        raise ValueError("Pack has no downloads.")

    lang = str(pack.get("lang") or "en").strip().lower()
    source_title = str(pack.get("title") or pack_id)

    raw_file = RAW_DIR / pack_id / downloads[0]["filename"]
    if not raw_file.exists():
        raise FileNotFoundError(f"Raw file not found. Download first: {raw_file}")

    out = PROCESSED_DIR / f"{pack_id}.jsonl"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Building processed JSONL: {out}")
    print(f"- input: {raw_file.name}")
    print(f"- lang: {lang}")
    print(f"- max_pages: {max_pages}")
    print(f"- min_chars: {min_chars}")

    count = build_jsonl_from_wikipedia_dump(
        dump_path=raw_file,
        out_path=out,
        lang=lang,
        source_title=source_title,
        max_pages=max_pages,
        min_chars=min_chars,
    )
    print(f"Built {count} documents into: {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Zxyphorz AI knowledge pack manager (offline).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub_list = sub.add_parser("list", help="List available packs.")
    sub_dl = sub.add_parser("download", help="Download a pack.")
    sub_dl.add_argument("pack_id", type=str)

    sub_build = sub.add_parser("build", help="Build processed JSONL for a pack (clean + searchable).")
    sub_build.add_argument("pack_id", type=str)
    sub_build.add_argument("--max-pages", type=int, default=25000)
    sub_build.add_argument("--min-chars", type=int, default=240)

    args = parser.parse_args()
    man = load_manifest()

    if args.cmd == "list":
        list_packs(man)
        return

    if args.cmd == "download":
        download_pack(man, args.pack_id)
        return

    if args.cmd == "build":
        build_pack(args.pack_id, max_pages=args.max_pages, min_chars=args.min_chars)
        return


if __name__ == "__main__":
    main()
