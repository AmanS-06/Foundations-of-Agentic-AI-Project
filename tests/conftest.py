"""Shared test setup: every test reads the sample data in tests/fixtures, never real data."""

import os
import tempfile
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

# Must be set before zeroplate.config is imported anywhere.
os.environ["ZEROPLATE_RAW_DIR"] = str(FIXTURES / "raw")
os.environ["ZEROPLATE_LLM_MODE"] = "deterministic"
os.environ["ZEROPLATE_OUTPUTS_DIR"] = tempfile.mkdtemp(prefix="zeroplate_test_outputs_")
os.environ["ZEROPLATE_MEMORY_DB"] = os.path.join(os.environ["ZEROPLATE_OUTPUTS_DIR"], "memory.db")
os.environ["ZEROPLATE_USE_MCP"] = "0"  # in-process by default; test_mcp starts real servers itself


@pytest.fixture(scope="session")
def hub():
    """In-process hub: the same tool functions without starting server processes (fast)."""
    from zeroplate.mcp_client.hub import MCPHub

    with MCPHub(use_mcp=False) as h:
        yield h


@pytest.fixture
def ctx(hub, tmp_path):
    from zeroplate.agents.base import AgentContext
    from zeroplate.llm.client import LLM
    from zeroplate.memory.long_term import Memory
    from zeroplate.rag.retriever import KnowledgeBase

    return AgentContext(
        hub=hub,
        llm=LLM("deterministic"),
        kb=KnowledgeBase(FIXTURES / "kb"),
        memory=Memory(tmp_path / "memory.db"),
    )
