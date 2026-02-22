from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .base import Tool, ToolResult


class KnowledgePacksTool(Tool):
    name = "knowledge_packs"
    description = "Manage offline knowledge packs (list / status / how-to)."
    examples = "packs list / packs status / packs howto"

    def __init__(self, packs_dir: Path):
        self.packs_dir = packs_dir
        self.manifest_path = packs_dir / "manifest.json"
        self.raw_dir = packs_dir / "raw"
        self.processed_dir = packs_dir / "processed"

    def match(self, user_text: str) -> bool:
        t = user_text.strip().lower()
        return t.startswith("packs") or t.startswith("knowledge packs") or t.startswith("knowledge_packs")

    def run(self, user_text: str, session_id: str) -> ToolResult:
        t = user_text.strip().lower()
        cmd = "list"
        if "status" in t:
            cmd = "status"
        if "how" in t or "help" in t:
            cmd = "howto"

        if cmd == "howto":
            msg = (
                "To add large real-world knowledge (offline, no external AI APIs):\n\n"
                "1) List packs\n"
                "   - `python scripts/packs.py list`\n"
                "2) Download a pack (example ~343MB)\n"
                "   - `python scripts/packs.py download wikipedia_simple_en_343mb`\n"
                "3) Build a clean searchable dataset (JSONL)\n"
                "   - `python scripts/packs.py build wikipedia_simple_en_343mb --max-pages 25000`\n\n"
                "After that, Zxyphorz AI automatically loads `data/knowledge_packs/processed/*.jsonl`."
            )
            return ToolResult(True, msg, {"tool": self.name, "mode": "howto"})

        packs = self._load_manifest_packs()

        if cmd == "status":
            lines: List[str] = ["Knowledge pack status:"]
            for p in packs:
                pid = p.get("id", "?")
                downloads = p.get("downloads") or []
                raw_ok = False
                if downloads:
                    fname = downloads[0].get("filename")
                    raw_ok = bool(fname and (self.raw_dir / pid / fname).exists())
                processed_ok = (self.processed_dir / f"{pid}.jsonl").exists()
                lines.append(f"- **{pid}** — raw={'yes' if raw_ok else 'no'} | processed={'yes' if processed_ok else 'no'}")
            return ToolResult(True, "\n".join(lines), {"tool": self.name, "mode": "status"})

        # list
        lines = ["Available knowledge packs:"]
        for p in packs:
            pid = p.get("id", "?")
            title = p.get("title", "")
            lang = p.get("lang", "")
            desc = p.get("description", "")
            lines.append(f"- **{pid}** ({lang}) — {title}")
            if desc:
                lines.append(f"  - {desc}")
        lines.append("")
        lines.append("Tip: run `packs howto` for install instructions.")
        return ToolResult(True, "\n".join(lines), {"tool": self.name, "mode": "list"})

    def _load_manifest_packs(self) -> List[Dict[str, Any]]:
        if not self.manifest_path.exists():
            return []
        try:
            obj = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return list(obj.get("packs") or [])
        except Exception:
            return []
