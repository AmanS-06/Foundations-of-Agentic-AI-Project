"""The keyword-search baseline for the knowledge base ranks and scores correctly.

The ranking logic is checked on a toy knowledge base that can be reasoned about by hand. The real
knowledge base is then held to a floor, so that an edit which makes it much harder to search fails
a test instead of going unnoticed.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data" / "kb"
QUESTIONS = KB / "eval_questions.json"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses look their own module up by name
    spec.loader.exec_module(module)
    return module


check = _load("check_kb_retrieval")

# ---------------------------------------------------------------- a toy knowledge base
TOY_A = "# A\n\n## Cats\nCats purr and chase mice.\n\n## Dogs\nDogs bark and fetch sticks.\n"
TOY_B = "# B\n\n## Rice\nRice grows in flooded fields.\n"
TOY_QUESTIONS = [
    {"question": "Which animal barks?", "expected_source": "a.md", "expected_section": "Dogs"},
    {
        "question": "Where does rice grow",
        "expected_source": "b.md",
        "expected_section": "Rice",
        "also_needs": [{"expected_source": "a.md", "expected_section": "Cats"}],
    },
    {"question": "zzz qqq", "expected_source": "a.md", "expected_section": "Dogs"},
]


@pytest.fixture()
def toy(tmp_path):
    (tmp_path / "a.md").write_text(TOY_A, encoding="utf-8")
    (tmp_path / "b.md").write_text(TOY_B, encoding="utf-8")
    questions = tmp_path / "q.json"
    questions.write_text(json.dumps(TOY_QUESTIONS), encoding="utf-8")
    return tmp_path, questions


def test_each_section_is_one_chunk_in_file_order(toy):
    chunks = check.load_chunks(toy[0])
    assert [(c.source, c.section) for c in chunks] == [
        ("a.md", "Cats"),
        ("a.md", "Dogs"),
        ("b.md", "Rice"),
    ]
    assert (
        "purr" in chunks[0].text and "bark" not in chunks[0].text
    )  # the text stops at the next heading


def test_the_obvious_section_is_ranked_first(toy):
    results = check.evaluate(*toy)
    assert results[0].rank == 1 and results[0].top[0] == ("a.md", "Dogs")
    assert results[1].rank == 1 and results[1].top[0] == ("b.md", "Rice")


def test_a_question_with_no_matching_word_falls_back_to_file_order(toy):
    """With every score tied at zero, the sections keep their file order: Cats, Dogs, Rice."""
    third = check.evaluate(*toy)[2]
    assert third.rank == 2  # Dogs comes second in file order


def test_extra_sections_for_two_document_questions_are_ranked_too(toy):
    second = check.evaluate(*toy)[1]
    assert second.also == {("a.md", "Cats"): 2}
    assert second.all_needed_in_top5


def test_summary_numbers_for_the_toy_questions(toy):
    s = check.summarise(check.evaluate(*toy))
    assert s["questions"] == 3
    assert s["hit@1"] == pytest.approx(2 / 3)
    assert s["hit@3"] == 1.0
    assert s["mrr"] == pytest.approx((1 + 1 + 1 / 2) / 3)
    assert s["multi_questions"] == 1 and s["multi_all_in_top5"] == 1.0


def test_a_section_that_does_not_exist_is_reported_clearly(toy):
    folder, _ = toy
    bad = folder / "bad.json"
    bad.write_text(
        json.dumps([{"question": "q", "expected_source": "a.md", "expected_section": "Birds"}]),
        encoding="utf-8",
    )
    with pytest.raises(KeyError, match="no section called 'Birds'"):
        check.evaluate(folder, bad)


def test_an_empty_knowledge_base_is_an_error(tmp_path):
    (tmp_path / "q.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="no '##' sections"):
        check.evaluate(tmp_path, tmp_path / "q.json")


def test_the_table_marks_questions_that_missed_the_top_three():
    miss = check.Result(
        "q", ("a.md", "X"), rank=4, top=[("a.md", "A"), ("a.md", "B"), ("a.md", "C")]
    )
    hit = check.Result("q2", ("a.md", "Y"), rank=2, top=[("a.md", "A")])
    text = check.render([miss, hit])
    assert "4*" in text and "not in the top 3" in text
    assert re.search(r"hit@3\s+50\.0%", text)  # one of the two questions is in the top three


# ---------------------------------------------------------------- words
def test_stop_words_are_dropped_and_endings_are_stripped():
    assert check.tokenize("The cooked food is reheated") == ["cook", "food", "reheat"]
    assert check.tokenize("reheating") == check.tokenize("reheated") == ["reheat"]


def test_the_stemmer_never_cuts_a_word_below_three_letters():
    # short words are left alone, not cut down to a stub
    assert check.stem("is") == "is"
    assert check.stem("gas") == "gas"
    assert check.stem("bus") == "bus"
    assert check.stem("ring") == "ring"  # "ing" would leave only "r"
    # words long enough lose one ending
    assert check.stem("ties") == "tie"
    assert check.stem("reheated") == "reheat"
    assert check.stem("fields") == "field"


def test_numbers_are_kept_as_words():
    assert "65" in check.tokenize("hold at 65 C") and "c" in check.tokenize("hold at 65 C")


# ---------------------------------------------------------------- the real knowledge base
def test_every_real_section_is_a_chunk():
    chunks = check.load_chunks(KB)
    assert len(chunks) == 35  # 11 food safety + 8 SOP + 11 recipes + 5 budget
    assert {c.source for c in chunks} == {
        "food_safety_fssai.md",
        "canteen_sop.md",
        "recipe_yields.md",
        "budget_policy.md",
    }


def test_all_15_questions_point_at_real_sections():
    """evaluate() raises if a question names a section that does not exist."""
    assert len(check.evaluate(KB, QUESTIONS)) == 15


def test_evaluation_is_repeatable():
    first = [(r.rank, r.top) for r in check.evaluate(KB, QUESTIONS)]
    second = [(r.rank, r.top) for r in check.evaluate(KB, QUESTIONS)]
    assert first == second


def test_keyword_baseline_stays_above_its_floor():
    """On 11 Oct the plain keyword search found the right section in the top 3 for 10 of 15.

    This floor (9 of 15) fails if an edit makes the documents much harder to search. It is a
    baseline for the project's own retriever, which should do at least as well.
    """
    s = check.summarise(check.evaluate(KB, QUESTIONS))
    assert s["hit@3"] >= 9 / 15
    assert s["mrr"] >= 0.6


def test_questions_about_recipes_and_budget_are_found_first_time():
    """The questions that name a dish or a budget figure use the documents' own words."""
    by_question = {r.question: r.rank for r in check.evaluate(KB, QUESTIONS)}
    for text, rank in by_question.items():
        if "chicken biryani" in text or "veg sandwich" in text or "normal Monday" in text:
            assert rank == 1, text
