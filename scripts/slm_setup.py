#!/usr/bin/env python3
from __future__ import annotations

"""Zxyphorz AI — SLM (Small Local Model) Setup

Adds an optional *Advanced* mode powered by a local GGUF model (llama.cpp).
Basic mode stays fully functional with zero extra deps.

Commands:
  python scripts/slm_setup.py recommend
  python scripts/slm_setup.py download <key>
  python scripts/slm_setup.py activate <key>
  python scripts/slm_setup.py status
  python scripts/slm_setup.py bench   (optional; needs llama-cpp-python)

What this script writes:
  data/models/<model>.gguf
  data/models/slm_config.json  (consumed by backend)

Why GGUF?
- llama.cpp requires GGUF model files.
"""

import argparse
import hashlib
import json
import os
import platform
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ModelSpec:
    key: str
    name: str
    repo_id: str
    filename: str
    chat_format: str
    params_hint: str
    license_hint: str
    notes: str

    def url(self) -> str:
        return f"https://huggingface.co/{self.repo_id}/resolve/main/{self.filename}?download=true"


RECOMMENDED: List[ModelSpec] = [
    ModelSpec(
        key="qwen2_5_0_5b_q4",
        name="Qwen2.5 0.5B Instruct (GGUF, Q4_K_M)",
        repo_id="Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        filename="qwen2.5-0.5b-instruct-q4_k_m.gguf",
        chat_format="chatml",
        params_hint="~0.49B params (very fast)",
        license_hint="See model card (Qwen)",
        notes="Best speed/quality for CPU + multilingual.",
    ),
    ModelSpec(
        key="tinyllama_1_1b_q4",
        name="TinyLlama 1.1B Chat v1.0 (GGUF, Q4_K_M)",
        repo_id="TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
        filename="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        chat_format="llama-2",
        params_hint="~1.1B params (still light)",
        license_hint="See model card (TinyLlama/TheBloke)",
        notes="More chatty; slightly slower than Qwen 0.5B.",
    ),
    ModelSpec(
        key="phi2_q4",
        name="Phi-2 (GGUF, Q4_K_M)",
        repo_id="TheBloke/phi-2-GGUF",
        filename="phi-2.Q4_K_M.gguf",
        chat_format="chatml",
        params_hint="~2.7B params (heavier but stronger)",
        license_hint="Microsoft Research License (check restrictions)",
        notes="Better reasoning/coding but heavier CPU load.",
    ),
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def models_dir() -> Path:
    return repo_root() / 'data' / 'models'


def cfg_path() -> Path:
    return models_dir() / 'slm_config.json'


def ensure_dirs() -> None:
    models_dir().mkdir(parents=True, exist_ok=True)


def get_model(key: str) -> Optional[ModelSpec]:
    k = (key or '').strip().lower()
    for m in RECOMMENDED:
        if m.key.lower() == k:
            return m
    return None


def load_cfg() -> Dict[str, Any]:
    if not cfg_path().exists():
        return {}
    try:
        return json.loads(cfg_path().read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_cfg(cfg: Dict[str, Any]) -> None:
    ensure_dirs()
    cfg_path().write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _ua_headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    hdrs = {
        'User-Agent': 'ZxyphorzAI-SLM-Setup/1.0',
        'Accept': '*/*',
    }
    if extra:
        hdrs.update(extra)
    return hdrs


def download(url: str, out: Path, *, resume: bool = True, chunk: int = 256 * 1024) -> None:
    """Download a file with basic resume support (Range requests)."""
    ensure_dirs()
    tmp = out.with_suffix(out.suffix + '.part')
    done = 0
    headers: Dict[str, str] = {}
    if resume and tmp.exists():
        done = tmp.stat().st_size
        if done > 0:
            headers['Range'] = f'bytes={done}-'

    req = urllib.request.Request(url, headers=_ua_headers(headers), method='GET')
    t0 = time.perf_counter()

    with urllib.request.urlopen(req, timeout=60) as resp:
        total = None
        try:
            cl = resp.headers.get('Content-Length')
            if cl is not None:
                total = int(cl)
                if 'Range' in headers:
                    total += done  # remaining + previous
        except Exception:
            total = None

        mode = 'ab' if done > 0 else 'wb'
        with open(tmp, mode) as f:
            last = 0.0
            while True:
                data = resp.read(chunk)
                if not data:
                    break
                f.write(data)
                done += len(data)

                now = time.perf_counter()
                if now - last > 0.4:
                    last = now
                    dt = max(now - t0, 1e-6)
                    mbps = (done / dt) / (1024 * 1024)
                    if total:
                        pct = (done / max(total, 1)) * 100.0
                        print(f"\rDownloading… {pct:6.2f}% • {mbps:.2f} MB/s", end='', flush=True)
                    else:
                        print(f"\rDownloading… {done/1024/1024:.1f} MB • {mbps:.2f} MB/s", end='', flush=True)

    print('\nDownload finished.')
    tmp.replace(out)


def cmd_recommend() -> int:
    print('\nRecommended small GGUF models:\n')
    for m in RECOMMENDED:
        print(f"- {m.key}: {m.name}")
        print(f"  params: {m.params_hint}")
        print(f"  license: {m.license_hint}")
        print(f"  chat_format: {m.chat_format}")
        print(f"  url: {m.url()}")
        print(f"  notes: {m.notes}\n")
    print('Tip: Start with qwen2_5_0_5b_q4 for low latency on CPU.')
    return 0


def cmd_download(key: str, force: bool) -> int:
    m = get_model(key)
    if not m:
        print('Unknown key. Run: python scripts/slm_setup.py recommend')
        return 2

    out = models_dir() / m.filename
    if out.exists() and not force:
        print(f'Already exists: {out}')
        print('Use --force to re-download.')
        return 0

    print(f"\nDownloading: {m.name}")
    print(f"To: {out}")
    try:
        download(m.url(), out, resume=True)
    except urllib.error.HTTPError as e:
        print(f"HTTPError {e.code}: {e.reason}")
        return 2
    except Exception as e:
        print(f"{type(e).__name__}: {e}")
        return 2

    # Sidecar hash helps debugging (even if no official checksum)
    try:
        print('Computing sha256… (this can take a while)')
        h = sha256(out)
        (out.with_suffix(out.suffix + '.sha256')).write_text(h, encoding='utf-8')
        print('sha256:', h)
    except Exception as e:
        print(f'Hash skipped: {type(e).__name__}: {e}')

    print('Done.')
    return 0


def cmd_activate(key: str, n_ctx: int, n_threads: int, n_batch: int, max_tokens: int) -> int:
    m = get_model(key)
    if not m:
        print('Unknown key.')
        return 2

    mp = models_dir() / m.filename
    if not mp.exists():
        print('Model file missing. Download first.')
        return 2

    cfg = {
        'enabled': True,
        'key': m.key,
        'display_name': m.name,
        'model_path': str(mp),
        'chat_format': m.chat_format,
        'n_ctx': int(n_ctx),
        'n_threads': int(n_threads),
        'n_batch': int(n_batch),
        'max_tokens': int(max_tokens),
        'temperature': 0.2,
        'top_p': 0.9,
        'repeat_penalty': 1.1,
    }
    save_cfg(cfg)

    print('\nActivated Advanced mode config:')
    print('  config ->', cfg_path())
    print('Next: pip install -r requirements-advanced.txt')
    print('Then: python -m backend')
    print('In UI: set Mode = Advanced')
    return 0


def cmd_disable() -> int:
    cfg = load_cfg()
    if not cfg:
        print('Nothing to disable.')
        return 0
    cfg['enabled'] = False
    save_cfg(cfg)
    print('Advanced mode disabled (Basic only).')
    return 0


def _try_import_llama() -> Tuple[Optional[Any], Optional[str]]:
    try:
        from llama_cpp import Llama  # type: ignore
        return Llama, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def cmd_bench() -> int:
    cfg = load_cfg()
    if not cfg or not cfg.get('enabled'):
        print('No enabled model. Activate first.')
        return 2

    mp = Path(str(cfg.get('model_path') or ''))
    if not mp.exists():
        print('Model file missing:', mp)
        return 2

    Llama, err = _try_import_llama()
    if err:
        print('llama-cpp-python not installed. Install requirements-advanced.txt')
        print('Error:', err)
        return 2

    n_ctx = int(cfg.get('n_ctx') or 2048)
    n_threads = int(cfg.get('n_threads') or max(os.cpu_count() or 4, 4))
    n_batch = int(cfg.get('n_batch') or 256)
    chat_format = str(cfg.get('chat_format') or 'chatml')

    print('\nBenchmarking (quick)…')
    print('model:', mp)
    print('n_threads:', n_threads, 'n_batch:', n_batch, 'n_ctx:', n_ctx, 'chat_format:', chat_format)

    t0 = time.perf_counter()
    try:
        llm = Llama(
            model_path=str(mp),
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_batch=n_batch,
            chat_format=chat_format,
            verbose=False,
        )
        out = llm.create_chat_completion(
            messages=[
                {'role': 'system', 'content': 'You are a concise assistant.'},
                {'role': 'user', 'content': 'Write 5 short bullet tips for learning Python.'},
            ],
            max_tokens=192,
            temperature=0.2,
            top_p=0.9,
            stream=False,
        )
        usage = out.get('usage') or {}
        gen = int(usage.get('completion_tokens') or 0)
        dt = max(time.perf_counter() - t0, 1e-6)
        tps = gen / dt if gen else 0.0
        print(f"\nSpeed: {tps:.2f} tokens/sec (gen_tokens={gen}, time={dt:.2f}s)")
        cfg['last_bench'] = {
            'tokens_per_sec': tps,
            'gen_tokens': gen,
            'seconds': dt,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'platform': {
                'system': platform.system(),
                'release': platform.release(),
                'machine': platform.machine(),
                'python': sys.version.splitlines()[0],
            },
        }
        save_cfg(cfg)
        return 0
    except Exception as e:
        print(f"{type(e).__name__}: {e}")
        return 2


def cmd_status() -> int:
    ensure_dirs()
    cfg = load_cfg()
    print('\n=== Zxyphorz AI SLM Status ===')
    print('models_dir:', models_dir())
    print('config:', cfg_path())

    if not cfg:
        print('No active config yet. Use recommend/download/activate.')
        return 0

    for k, v in cfg.items():
        print(f"- {k}: {v}")

    mp = Path(str(cfg.get('model_path') or ''))
    if mp.exists():
        print(f"Model file: OK ({mp.stat().st_size/1024/1024:.1f} MB)")
    else:
        print('Model file: MISSING')
        return 2

    Llama, err = _try_import_llama()
    if err:
        print('llama-cpp-python: not installed -> Advanced mode will fall back to Basic.')
    else:
        print('llama-cpp-python: installed -> Advanced mode should run.')
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Zxyphorz AI SLM setup helper.')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('recommend')
    sub.add_parser('status')

    dl = sub.add_parser('download')
    dl.add_argument('key')
    dl.add_argument('--force', action='store_true')

    act = sub.add_parser('activate')
    act.add_argument('key')
    act.add_argument('--n-ctx', type=int, default=2048)
    act.add_argument('--n-threads', type=int, default=max(os.cpu_count() or 4, 4))
    act.add_argument('--n-batch', type=int, default=256)
    act.add_argument('--max-tokens', type=int, default=384)

    sub.add_parser('disable')
    sub.add_parser('bench')
    return p


def main(argv: Optional[List[str]] = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == 'recommend':
        return cmd_recommend()
    if a.cmd == 'status':
        return cmd_status()
    if a.cmd == 'download':
        return cmd_download(a.key, bool(a.force))
    if a.cmd == 'activate':
        return cmd_activate(a.key, a.n_ctx, a.n_threads, a.n_batch, a.max_tokens)
    if a.cmd == 'disable':
        return cmd_disable()
    if a.cmd == 'bench':
        return cmd_bench()
    print('Unknown command')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())