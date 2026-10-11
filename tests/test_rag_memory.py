"""Knowledge-base search (chunking, hybrid retrieval) and long-term memory."""

from pathlib import Path

import pytest

from zeroplate.memory.long_term import Memory
from zeroplate.rag.retriever import KnowledgeBase, chunk_markdown, stem

KB = Path(__file__).parent / "fixtures" / "kb"


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase(KB)


def test_chunks_follow_headings():
    sections = [c.section for c in chunk_markdown(KB / "food_safety.md")]
    assert sections == [
        "Food safety (test fixture)",
        "Hot holding",
        "Reheating gravies and meat",
        "Cooling and storage",
    ]


def test_light_stemming():
    assert stem("reheated") == stem("reheating") == "reheat"


@pytest.mark.parametrize(
    "query, section",
    [
        ("reheat biryani twice", "Reheating gravies and meat"),
        ("hot food below 65 degrees", "Hot holding"),
        ("daily budget exceeded", "Daily food budget"),
        ("jain dishes always available", "Fairness"),
        ("cooling cooked food to 5 C", "Cooling and storage"),
    ],
)
def test_retrieval_hit_at_3(kb, query, section):
    assert section in [c.section for c in kb.search(query, k=3)]


def test_citations_name_their_source(kb):
    top = kb.search("reheat once", k=1)[0]
    assert top.source == "food_safety.md" and top.score > 0


def test_nonsense_query_returns_nothing(kb):
    assert kb.search("xyzzy plugh") == []


def test_empty_knowledge_base(tmp_path):
    assert KnowledgeBase(tmp_path).search("anything") == []


def test_memory_recalls_same_kind_of_day(tmp_path):
    m = Memory(tmp_path / "m.db")
    m.save_run("r1", "2026-08-21", "fest", "approved", 0.05, 30000, 1, "fest: budget tight")
    m.save_run("r2", "2026-09-28", "exam", "approved", 0.05, 16000, 0, "exam: quiet")
    assert [r["lesson"] for r in m.similar("fest")] == ["fest: budget tight"]
    assert m.count() == 2
