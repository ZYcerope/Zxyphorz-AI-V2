# Zxyphorz AI

A beginner friendly **multi-file** portfolio repo that runs on **localhost**.

**What it is**
- A local “AI-like” assistant named **Zxyphorz AI**
- No external AI APIs. Everything is **local + deterministic**
- Includes:
  - **Tools** (calculator, notes, todo, summaries, translator, knowledge packs)
  - **Local Knowledge Base** (search + retrieval from markdown docs you can extend)
  - **Offline Knowledge Packs** (download 300MB+ “real world” data and build a clean searchable JSONL)
  - **Conversation memory** (SQLite) + lightweight “fact extraction”
  - **Web UI** (modern minimal HTML/CSS/JS) + WebSocket streaming

> Reality check: no software can be guaranteed “bug-free on every machine”.  
> This repo is designed to run cleanly with the pinned versions below and includes tests.

## Quick Start (Windows / Mac / Linux)

### 1) Create venv & install deps
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2) Run the server
```bash
python -m backend
```
Then open:
- http://127.0.0.1:8000

## Languages (7)

Zxyphorz AI supports:
- English (`en`)
- Mandarin Chinese (`zh`)
- Japanese (`ja`)
- French (`fr`)
- Portuguese (`pt`)
- Spanish (`es`)
- Indonesian (`id`)

Set it in the UI dropdown or via:
- `/lang` (show current)
- `/lang id` (set language)

## Offline “Real World” Knowledge (300MB+)

This repo stays small, but you can add large knowledge packs locally.

### Example: download ~343MB Wikipedia (Simple English)
```bash
python scripts/packs.py list
python scripts/packs.py download wikipedia_simple_en_343mb
python scripts/packs.py build wikipedia_simple_en_343mb --max-pages 25000
```

After building, Zxyphorz AI automatically loads:
- `data/knowledge_base/*.md`
- `data/knowledge_packs/processed/*.jsonl`

## Features

### Chat + memory
- Deterministic chat engine with session memory (SQLite)
- Lightweight conversation summary
- Seed identity stored in `data/profile/seed_facts.json`

### Tools
- `/help` — show commands
- `/memory` — show saved session facts
- `/lang <code>` — set language
- `/reset` — clear current session memory
- `/export` — export chat to JSON
- Calculator: `2*(3+4)`
- Notes: “remember this …”
- Todo: “add todo: …”, “list todos”
- Summaries: “summarize: …”
- Explain: “explain: retrieval augmented generation”
- Translator: “translate to japanese: thank you”
- Knowledge packs: “packs list / packs status / packs howto”
- Code templates: “generate a fastapi project”, “create a python class …”

### Knowledge Base (RAG-lite)
- Retrieval via BM25-style scoring (pure Python)
- Multi-language tokenization (Latin + basic CJK bigrams)
- Extend docs freely in `data/knowledge_base/`

## Repo Structure
```
zxyphorz-ai/
  backend/                 # FastAPI + assistant engine
  frontend/                # Minimal modern UI
  data/
    knowledge_base/        # Small curated docs (markdown)
    knowledge_packs/       # Large offline data you download/process
    profile/               # Seed memory / identity (Created by Xceon)
    storage/               # SQLite (created at runtime)
  scripts/                 # Pack downloader + Wikipedia cleaner
  tests/                   # Smoke tests
```

## Tests
```bash
python tests/run.py
```
