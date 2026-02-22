# Knowledge Packs (Offline "Real World" Data)

This folder is for **large, clean, offline knowledge** that you download and process locally.

Why?
- You asked for real-world knowledge without using any external AI APIs.
- The repo stays lightweight, but you can download 300MB+ of curated data with one command.

## Quick start

1) List packs
```bash
python scripts/packs.py list
```

2) Download a pack (example: ~343MB)
```bash
python scripts/packs.py download wikipedia_simple_en_343mb
```

3) Build a clean searchable dataset (JSONL) for Zxyphorz AI
```bash
python scripts/packs.py build wikipedia_simple_en_343mb --max-pages 25000
```

After building, Zxyphorz AI automatically loads:
- `data/knowledge_base/*.md` (small docs)
- `data/knowledge_packs/processed/*.jsonl` (your packs)

## Notes on licensing
Wikipedia content is licensed under CC BY-SA / GFDL. Keep the license and attribution
if you redistribute processed datasets.
