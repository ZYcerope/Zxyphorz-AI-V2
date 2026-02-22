from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    """Central config.

    The goal is to avoid "mystery globals" and keep all app paths consistent.
    """

    repo_root: Path
    frontend_dir: Path

    # Knowledge
    knowledge_base_dir: Path
    knowledge_packs_dir: Path
    knowledge_packs_raw_dir: Path
    knowledge_packs_processed_dir: Path
    profile_dir: Path
    seed_facts_path: Path

    # Storage
    storage_dir: Path
    sqlite_path: Path

    @staticmethod
    def from_repo_root(repo_root: Path) -> "AppConfig":
        frontend_dir = repo_root / "frontend"

        # Knowledge base (small, curated docs)
        kb_dir = repo_root / "data" / "knowledge_base"
        kb_dir.mkdir(parents=True, exist_ok=True)

        # Knowledge packs (large, downloaded datasets)
        packs_dir = repo_root / "data" / "knowledge_packs"
        packs_raw_dir = packs_dir / "raw"
        packs_processed_dir = packs_dir / "processed"
        packs_raw_dir.mkdir(parents=True, exist_ok=True)
        packs_processed_dir.mkdir(parents=True, exist_ok=True)

        # Profile / seed memory
        profile_dir = repo_root / "data" / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        seed_facts_path = profile_dir / "seed_facts.json"

        # Storage (SQLite)
        storage_dir = repo_root / "data" / "storage"
        storage_dir.mkdir(parents=True, exist_ok=True)
        sqlite_path = storage_dir / "zxyphorz.sqlite3"

        return AppConfig(
            repo_root=repo_root,
            frontend_dir=frontend_dir,
            knowledge_base_dir=kb_dir,
            knowledge_packs_dir=packs_dir,
            knowledge_packs_raw_dir=packs_raw_dir,
            knowledge_packs_processed_dir=packs_processed_dir,
            profile_dir=profile_dir,
            seed_facts_path=seed_facts_path,
            storage_dir=storage_dir,
            sqlite_path=sqlite_path,
        )
