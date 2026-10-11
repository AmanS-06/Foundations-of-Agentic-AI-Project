"""One way for agents to ask the language model, in four modes.

    deterministic  no model at all: the agent's own rule-based answer (tests, "deterministic policy")
    ollama         ask the local model live (Ollama), validate the answer, fall back on failure
    record         like ollama, and save every answer to data/recordings/answers.json
    replay         look the answer up in the recording (the demo: fast, offline, repeatable)

Every answer that feeds logic is parsed into a Pydantic schema. If the model's output does not
fit, it is retried once and then replaced by the agent's deterministic fallback, so a bad model
answer can never crash the workflow (output-validation guardrail). The result always says where
the answer came from, and the UI shows it.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from zeroplate import config

MODES = ("deterministic", "ollama", "record", "replay")


@dataclass
class LLMResult:
    value: Any  # a schema instance, or text
    source: str  # "model", "replay" or "deterministic"
    note: str = ""  # why a fallback was used, if it was
    agreement: float = 1.0  # self-consistency: share of samples that agreed


def extract_json(text: str) -> str:
    """The first {...} block in a model answer (models sometimes add prose or code fences)."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else text


class LLM:
    def __init__(
        self,
        mode: str = config.LLM_MODE,
        model: str = config.OLLAMA_MODEL,
        recordings: Path = config.RECORDINGS_DIR / "answers.json",
    ) -> None:
        if mode not in MODES:
            raise ValueError(f"LLM mode must be one of {MODES}, not {mode!r}")
        self.mode, self.model, self.path = mode, model, Path(recordings)
        self._lock = threading.Lock()
        self._recorded: dict[str, str] = {}
        if self.path.exists():
            self._recorded = json.loads(self.path.read_text(encoding="utf-8"))
        self._client = None

    # ---------------------------------------------------------------- public
    def ask(
        self,
        task: str,
        prompt: str,
        fallback: Callable[[], Any],
        schema: type[BaseModel] | None = None,
        system: str = "",
        sample: int = 0,
        temperature: float = 0.0,
    ) -> LLMResult:
        """Answer `prompt`. `task` names the call site (e.g. "critic.feedback")."""
        if self.mode == "deterministic":
            return LLMResult(fallback(), "deterministic")
        key = self._key(task, prompt, system, sample)
        if self.mode == "replay":
            if key not in self._recorded:
                return LLMResult(fallback(), "deterministic", "no recorded answer")
            try:
                return LLMResult(self._parse(self._recorded[key], schema), "replay")
            except (ValidationError, ValueError) as exc:
                return LLMResult(fallback(), "deterministic", f"recording invalid: {exc}")
        return self._ask_live(task, prompt, fallback, schema, system, key, temperature)

    def ask_majority(
        self,
        task: str,
        prompt: str,
        fallback: Callable[[], BaseModel],
        schema: type[BaseModel],
        system: str = "",
        n: int = 3,
    ) -> LLMResult:
        """Self-consistency: sample the model n times and keep the most common answer."""
        if self.mode == "deterministic":
            return LLMResult(fallback(), "deterministic")
        results = [
            self.ask(task, prompt, fallback, schema, system, sample=i, temperature=0.7)
            for i in range(n)
        ]
        votes = Counter(r.value.model_dump_json() for r in results)
        winner, count = votes.most_common(1)[0]
        first = next(r for r in results if r.value.model_dump_json() == winner)
        return LLMResult(first.value, first.source, first.note, agreement=count / n)

    # ---------------------------------------------------------------- internals
    def _key(self, task: str, prompt: str, system: str, sample: int) -> str:
        raw = f"{self.model}|{task}|{sample}|{system}|{prompt}"
        return f"{task}#{sample}#" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _ask_live(self, task, prompt, fallback, schema, system, key, temperature) -> LLMResult:
        last_error = ""
        for _ in range(2):  # one retry
            try:
                raw = self._chat(prompt, schema, system, temperature)
                value = self._parse(raw, schema)
            except (ValidationError, ValueError) as exc:
                last_error = f"invalid answer: {str(exc)[:200]}"
                continue
            except Exception as exc:  # noqa: BLE001 - model offline, timeout, ...
                return LLMResult(fallback(), "deterministic", f"model unavailable: {exc}")
            if self.mode == "record":
                self._save(key, raw)
            return LLMResult(value, "model")
        return LLMResult(fallback(), "deterministic", last_error)

    def _chat(self, prompt: str, schema, system: str, temperature: float) -> str:
        import ollama  # imported lazily so tests never need the package to reach a server

        if self._client is None:
            self._client = ollama.Client(host=config.OLLAMA_HOST, timeout=config.LLM_TIMEOUT_S)
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        response = self._client.chat(
            model=self.model,
            messages=messages,
            format=schema.model_json_schema() if schema else None,
            options={"temperature": temperature},
        )
        return response.message.content

    @staticmethod
    def _parse(raw: str, schema: type[BaseModel] | None):
        if schema is None:
            text = raw.strip()
            if not text:
                raise ValueError("empty answer")
            return text
        return schema.model_validate_json(extract_json(raw))

    def _save(self, key: str, raw: str) -> None:
        with self._lock:
            self._recorded[key] = raw
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._recorded, indent=1, sort_keys=True), "utf-8")
