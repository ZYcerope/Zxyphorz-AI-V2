from __future__ import annotations

"""Local SLM (Small Language Model) integration for Zxyphorz AI.

- Optional dependency: Basic mode must work without llama-cpp-python installed.
- Offline inference: load a local GGUF model (llama.cpp format).
- Low latency: stream tokens for WebSocket clients.
- Config: data/models/slm_config.json (written by scripts/slm_setup.py)
"""

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple


@dataclass(frozen=True)
class SLMSettings:
    enabled: bool
    model_path: Path
    display_name: str
    chat_format: str
    n_ctx: int
    n_threads: int
    n_batch: int
    max_tokens: int
    temperature: float
    top_p: float
    repeat_penalty: float

    @staticmethod
    def disabled() -> "SLMSettings":
        return SLMSettings(
            enabled=False,
            model_path=Path(""),
            display_name="(disabled)",
            chat_format="chatml",
            n_ctx=2048,
            n_threads=max(os.cpu_count() or 4, 4),
            n_batch=256,
            max_tokens=384,
            temperature=0.2,
            top_p=0.9,
            repeat_penalty=1.1,
        )


@dataclass
class SLMStatus:
    available: bool
    reason: str
    display_name: str
    model_path: str


def load_slm_settings(config_path: Path) -> SLMSettings:
    if not config_path.exists():
        return SLMSettings.disabled()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return SLMSettings.disabled()

    enabled = bool(raw.get("enabled"))
    mp = Path(str(raw.get("model_path") or "")).expanduser()
    return SLMSettings(
        enabled=enabled,
        model_path=mp,
        display_name=str(raw.get("display_name") or mp.name or "Local SLM"),
        chat_format=str(raw.get("chat_format") or "chatml"),
        n_ctx=int(raw.get("n_ctx") or 2048),
        n_threads=int(raw.get("n_threads") or max(os.cpu_count() or 4, 4)),
        n_batch=int(raw.get("n_batch") or 256),
        max_tokens=int(raw.get("max_tokens") or 384),
        temperature=float(raw.get("temperature") or 0.2),
        top_p=float(raw.get("top_p") or 0.9),
        repeat_penalty=float(raw.get("repeat_penalty") or 1.1),
    )


def _try_import_llama() -> Tuple[Optional[Any], Optional[str]]:
    try:
        from llama_cpp import Llama  # type: ignore
        return Llama, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


class LocalSLM:
    def __init__(self, settings: SLMSettings):
        self.settings = settings
        self._llm: Optional[Any] = None
        self._load_error: Optional[str] = None

    def status(self) -> SLMStatus:
        if not self.settings.enabled:
            return SLMStatus(False, "Disabled in config", self.settings.display_name, str(self.settings.model_path))
        if not self.settings.model_path or not self.settings.model_path.exists():
            return SLMStatus(False, "Model file not found", self.settings.display_name, str(self.settings.model_path))
        _, err = _try_import_llama()
        if err:
            return SLMStatus(False, "llama-cpp-python not installed", self.settings.display_name, str(self.settings.model_path))
        if self._load_error:
            return SLMStatus(False, f"Load error: {self._load_error}", self.settings.display_name, str(self.settings.model_path))
        return SLMStatus(True, "Ready", self.settings.display_name, str(self.settings.model_path))

    def ensure_loaded(self) -> bool:
        if self._llm is not None:
            return True
        st = self.status()
        if not st.available:
            self._load_error = st.reason
            return False

        Llama, err = _try_import_llama()
        if err:
            self._load_error = err
            return False

        try:
            self._llm = Llama(
                model_path=str(self.settings.model_path),
                n_ctx=int(self.settings.n_ctx),
                n_threads=int(self.settings.n_threads),
                n_batch=int(self.settings.n_batch),
                chat_format=str(self.settings.chat_format),
                verbose=False,
            )
            return True
        except Exception as e:
            self._load_error = f"{type(e).__name__}: {e}"
            self._llm = None
            return False

    def generate_chat(self, messages: List[Dict[str, str]], *, stop: Optional[List[str]] = None) -> Tuple[str, Dict[str, Any]]:
        if not self.ensure_loaded():
            return "", {"error": self._load_error or "SLM not available"}

        assert self._llm is not None
        t0 = time.perf_counter()
        try:
            out = self._llm.create_chat_completion(
                messages=messages,
                max_tokens=int(self.settings.max_tokens),
                temperature=float(self.settings.temperature),
                top_p=float(self.settings.top_p),
                repeat_penalty=float(self.settings.repeat_penalty),
                stop=stop,
                stream=False,
            )
            text = out["choices"][0]["message"]["content"]
            usage = out.get("usage") or {}
            dt = time.perf_counter() - t0
            meta = {
                "slm": {
                    "display_name": self.settings.display_name,
                    "model_path": str(self.settings.model_path),
                    "chat_format": self.settings.chat_format,
                },
                "usage": usage,
                "seconds": round(dt, 4),
            }
            return str(text), meta
        except Exception as e:
            return "", {"error": f"{type(e).__name__}: {e}"}

    def stream_chat(self, messages: List[Dict[str, str]], *, stop: Optional[List[str]] = None) -> Iterator[str]:
        if not self.ensure_loaded():
            yield f"[Advanced mode unavailable: {self._load_error or 'unknown'}]"
            return

        assert self._llm is not None
        try:
            for chunk in self._llm.create_chat_completion(
                messages=messages,
                max_tokens=int(self.settings.max_tokens),
                temperature=float(self.settings.temperature),
                top_p=float(self.settings.top_p),
                repeat_penalty=float(self.settings.repeat_penalty),
                stop=stop,
                stream=True,
            ):
                try:
                    choice = (chunk.get("choices") or [None])[0] or {}
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if content is None:
                        content = choice.get("text")
                    if content:
                        yield str(content)
                except Exception:
                    continue
        except Exception as e:
            yield f"\n[Streaming error: {type(e).__name__}: {e}]\n"
