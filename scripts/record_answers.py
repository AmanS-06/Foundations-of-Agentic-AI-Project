"""Record the local model's answers once, so the demo can replay them (fast, offline, repeatable).

Needs Ollama running with the model pulled (same model on both laptops so recordings match):
    ollama pull mistral
    .venv\\Scripts\\python scripts\\record_answers.py

It runs every benchmark scenario with the language model in "record" mode. Each model answer
is validated against its schema and saved to data/recordings/answers.json, keyed by the call
site and a hash of the prompt. In "replay" mode (the app's default) the same prompt finds the
same answer. Re-run this script whenever the prompts or the dataset change.
"""

from __future__ import annotations

import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from zeroplate import config
from zeroplate.agents.base import AgentContext
from zeroplate.eval.scenarios import SCENARIOS
from zeroplate.graph import run_plan
from zeroplate.llm.client import LLM
from zeroplate.mcp_client.hub import MCPHub
from zeroplate.memory.long_term import Memory
from zeroplate.rag.retriever import KnowledgeBase


def ollama_ready() -> str:
    """Empty string if Ollama answers and has the model; otherwise what is wrong."""
    try:
        import ollama

        names = [m.model for m in ollama.Client(host=config.OLLAMA_HOST).list().models]
    except Exception as exc:  # noqa: BLE001 - any failure means Ollama is not usable
        return f"cannot reach Ollama at {config.OLLAMA_HOST} ({exc}). Is it installed and running?"
    if not any(n.split(":")[0] == config.OLLAMA_MODEL for n in names):
        return f"model '{config.OLLAMA_MODEL}' not found. Run: ollama pull {config.OLLAMA_MODEL}"
    return ""


def main() -> int:
    problem = ollama_ready()
    if problem:
        print(f"Cannot record: {problem}")
        return 1
    llm = LLM("record")
    print(
        f"Recording {config.OLLAMA_MODEL} answers for {len(SCENARIOS)} scenarios (data: {config.RAW_DIR})"
    )
    with MCPHub(use_mcp=False) as hub:
        # a fresh memory, so recordings do not depend on earlier runs
        memory = Memory(Path(tempfile.mkdtemp()) / "memory.db")
        ctx = AgentContext(hub, llm, KnowledgeBase(config.KB_DIR), memory)
        for sc in SCENARIOS:
            state = run_plan(ctx, **sc.options)
            sources = Counter(
                s.tool.split(":", 1)[1]
                for s in state["trace"]
                if s.tool and s.tool.startswith("llm:")
            )
            print(f"  {sc.id} {sc.name:<32} {state['status']:<10} model answers: {dict(sources)}")
    saved = json.loads(llm.path.read_text(encoding="utf-8")) if llm.path.exists() else {}
    print(f"\n{len(saved)} answers saved to {llm.path}")
    print("Commit that file; the app replays it by default (ZEROPLATE_LLM_MODE=replay).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
