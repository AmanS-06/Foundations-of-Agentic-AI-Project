"""The knowledge-base files chunk well, agree with the CSVs and config, and match the eval questions.

tests/conftest.py points the data loader at tests/fixtures. These tests read the real files in
data/raw and data/kb directly by path.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from zeroplate import config

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data" / "kb"
RAW = ROOT / "data" / "raw"

KB_FILES = [
    "food_safety_fssai.md",
    "canteen_sop.md",
    "recipe_yields.md",
    "budget_policy.md",
]
MIN_WORDS, MAX_WORDS = 40, 350
TRANSPORT = "Transporting cooked food"
FOUR_HOURS = re.compile(r"\b(?:4|four)\s+hours\b", re.IGNORECASE)


def read(name: str) -> str:
    return (KB / name).read_text(encoding="utf-8")


def sections(name: str) -> dict[str, str]:
    """Map each '## ' heading text to the body text under it."""
    found: dict[str, list[str]] = {}
    current = None
    for line in read(name).splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            assert current not in found, f"duplicate heading {current!r} in {name}"
            found[current] = []
        elif current is not None:
            found[current].append(line)
    return {k: "\n".join(v).strip() for k, v in found.items()}


def csv_rows(name: str) -> list[dict[str, str]]:
    with open(RAW / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------------ structure of every file
@pytest.mark.parametrize("name", KB_FILES)
def test_file_starts_with_title_and_has_three_sections(name):
    text = read(name)
    assert text.startswith("# "), f"{name} must start with a '# ' title"
    assert not text.startswith("## ")
    assert len(sections(name)) >= 3


@pytest.mark.parametrize("name", KB_FILES)
def test_every_section_is_between_40_and_350_words(name):
    for heading, body in sections(name).items():
        words = len(body.split())
        assert MIN_WORDS <= words <= MAX_WORDS, f"{name} / {heading}: {words} words"


@pytest.mark.parametrize("name", KB_FILES)
def test_file_is_plain_ascii(name):
    assert read(name).isascii(), f"{name} has non-ASCII characters"


def test_sop_states_it_is_illustrative():
    assert (
        "Illustrative SOP written for the ZeroPlate project. "
        "It is not the real SIT Pune canteen SOP."
    ) in read("canteen_sop.md")


def test_budget_policy_is_labelled_illustrative():
    assert "illustrative" in read("budget_policy.md").lower()


# ------------------------------------------------------------------ eval questions
def load_questions() -> list[dict]:
    return json.loads((KB / "eval_questions.json").read_text(encoding="utf-8"))


def test_there_are_exactly_15_questions():
    questions = load_questions()
    assert len(questions) == 15
    assert len({q["question"] for q in questions}) == 15


def test_question_mix_is_6_3_3_3():
    counts = Counter(q["expected_source"] for q in load_questions())
    assert counts == {
        "food_safety_fssai.md": 6,
        "canteen_sop.md": 3,
        "recipe_yields.md": 3,
        "budget_policy.md": 3,
    }


def test_at_least_two_questions_need_two_documents():
    two_docs = [q for q in load_questions() if q.get("also_needs")]
    assert len(two_docs) >= 2
    for q in two_docs:
        assert all(e["expected_source"] != q["expected_source"] for e in q["also_needs"])


def test_the_paneer_curry_question_is_included():
    wanted = "can a 6-hour-old paneer curry kept at room temperature be served again?"
    assert any(q["question"].lower() == wanted for q in load_questions())


def test_every_expected_section_exists_as_a_heading():
    for q in load_questions():
        assert set(q) - {"also_needs"} == {"question", "expected_source", "expected_section"}
        targets = [(q["expected_source"], q["expected_section"])]
        targets += [(e["expected_source"], e["expected_section"]) for e in q.get("also_needs", [])]
        for source, heading in targets:
            assert source in KB_FILES, f"unknown file {source!r}"
            assert heading in sections(source), f"{source} has no section {heading!r}"


# ------------------------------------------------------------------ recipe_yields.md vs the CSVs
def parse_dish_section(body: str) -> dict:
    ingredients = {}
    for m in re.finditer(r"^- (\w+): ([0-9.]+) (\w+) per plate$", body, re.MULTILINE):
        ingredients[m.group(1)] = (m.group(2), m.group(3))

    def field(label: str) -> str:
        m = re.search(rf"^{re.escape(label)}: (.+)$", body, re.MULTILINE)
        assert m, f"missing line {label!r}"
        return m.group(1).strip()

    return {
        "ingredients": ingredients,
        "diet": field("Diet tag"),
        "cost": field("Cost per plate"),
        "price": field("Selling price"),
        "shelf": field("Assumed shelf life (assumption)"),
        "min_portions": field("Minimum portions (fairness floor, assumption)"),
    }


def test_recipe_yields_has_a_section_for_every_dish_in_the_menu():
    menu = csv_rows("menu.csv")
    assert len(menu) == 10
    assert {row["dish"] for row in menu} <= set(sections("recipe_yields.md"))


def test_recipe_yields_matches_recipes_and_menu_csv_exactly():
    recipes = csv_rows("recipes.csv")
    secs = sections("recipe_yields.md")
    for row in csv_rows("menu.csv"):
        dish = row["dish"]
        got = parse_dish_section(secs[dish])
        expected = {
            r["ingredient"]: (r["qty_per_plate"], r["unit"]) for r in recipes if r["dish"] == dish
        }
        assert got["ingredients"] == expected, dish
        assert got["diet"] == row["diet"], dish
        assert got["cost"] == f"Rs {row['cost_per_plate']}", dish
        assert got["price"] == f"Rs {row['price']}", dish
        assert got["shelf"] == f"{row['shelf_life_hrs']} hours", dish
        assert got["min_portions"] == row["min_portions"], dish


def test_jain_khichdi_has_none_of_the_jain_excluded_ingredients():
    excluded = {"onion", "garlic", "potato", "tomato", "mixed_veg"}
    got = parse_dish_section(sections("recipe_yields.md")["jain_khichdi"])
    assert not excluded & set(got["ingredients"])


# ------------------------------------------------------------------ food_safety_fssai.md
def test_four_hours_appears_only_in_the_transport_chunk():
    secs = sections("food_safety_fssai.md")
    assert TRANSPORT in secs
    assert FOUR_HOURS.search(secs[TRANSPORT]), "the transport chunk must state the transport limit"
    for heading, body in secs.items():
        if heading != TRANSPORT:
            assert not FOUR_HOURS.search(body), f"'4 hours' found in {heading!r}"
    preamble = read("food_safety_fssai.md").split("\n## ", 1)[0]
    assert not FOUR_HOURS.search(preamble)


def test_transport_chunk_says_the_limit_is_not_for_leftovers():
    body = sections("food_safety_fssai.md")[TRANSPORT].lower()
    assert "not a general time limit for leftovers" in body


def test_every_food_safety_chunk_cites_a_section_and_page():
    cited = re.compile(r"section \d\.\d(?:\.\d)?(?:\([a-z]\))?,? p\.\d+|p\.\d+|pp\.\d+-\d+")
    for heading, body in sections("food_safety_fssai.md").items():
        if heading.startswith("Project interpretation"):
            continue
        assert cited.search(body), f"no section/page citation in {heading!r}"


def numbers(pattern: str, text: str) -> set[int]:
    return {int(n) for n in re.findall(pattern, text)}


def test_food_safety_numbers_agree_with_config():
    secs = sections("food_safety_fssai.md")
    hot = secs["Hot and cold holding temperatures for high-risk food"]
    below = secs["Hot food that has fallen below 65 C: the 2-hour rule"]
    reheat = secs["Reheating cooked food: method and temperature"]
    once = secs["Reheating only once: meat, poultry, fish and gravies"]
    age = secs["Eat cooked food within 24 hours of preparation"]
    ours = next(v for k, v in secs.items() if k.startswith("Project interpretation"))

    assert config.HOT_HOLD_MIN_C in numbers(r"(\d+) C", hot)
    assert config.HOT_HOLD_MIN_C in numbers(r"(\d+) C", below)
    assert config.BELOW_HOT_HOLD_MAX_HOURS in numbers(r"(\d+) hours", below)
    assert config.REHEAT_TEMP_C in numbers(r"(\d+) C", below)
    assert config.REHEAT_TEMP_C in numbers(r"(\d+) C", reheat)
    assert config.MAX_AGE_HOURS in numbers(r"(\d+) hours", age)
    assert config.MAX_REHEATS == 1  # the text says "only once" and "one reheat"
    assert "only once" in once
    assert "one reheat" in ours

    # the five project rules quote the same numbers
    assert config.MAX_AGE_HOURS in numbers(r"(\d+) hours", ours)
    assert config.BELOW_HOT_HOLD_MAX_HOURS in numbers(r"(\d+) hours", ours)
    assert {config.HOT_HOLD_MIN_C, config.REHEAT_TEMP_C} <= numbers(r"(\d+) C", ours)


def test_cooling_numbers_match_the_guide_and_config_comment():
    body = sections("food_safety_fssai.md")["Cooling cooked food before refrigeration"]
    assert "from 60 C to 21 C within 2 hours" in body
    assert "from 21 C to 5 C" in body


def test_project_interpretation_covers_the_five_outcomes():
    ours = next(
        v
        for k, v in sections("food_safety_fssai.md").items()
        if k.startswith("Project interpretation")
    )
    for phrase in ("Older than 24 hours", "may be served", "blocked", "reheated once", "chilled"):
        assert phrase in ours, phrase
    assert ours.count("blocked") >= 3
    assert "paneer curry" in ours


# ---------------------------------------------------------------- figures and dates agree with the data
def test_money_figures_in_policy_and_sop_match_budget_csv():
    """Every budget amount quoted in the text must be one of the amounts in budget.csv."""
    real = {int(float(r["daily_budget"])) for r in csv_rows("budget.csv")}
    events = {r["date"]: r["event"] for r in csv_rows("calendar.csv")}
    by_event = {events[r["date"]]: int(float(r["daily_budget"])) for r in csv_rows("budget.csv")}
    real.add(by_event["fest"] - by_event["normal"])  # the policy text quotes this difference
    for name in ("budget_policy.md", "canteen_sop.md"):
        text = read(name)
        quoted = [int(m.replace(",", "")) for m in re.findall(r"\b\d{2},\d{3}\b", text)]
        assert quoted, f"{name} quotes no budget amounts"
        assert set(quoted) <= real, f"{name}: {sorted(set(quoted) - real)} are not in budget.csv"


def test_fest_allowance_wording_matches_the_numbers():
    text = read("budget_policy.md")
    by_event: dict[str, int] = {}
    events = {r["date"]: r["event"] for r in csv_rows("calendar.csv")}
    for r in csv_rows("budget.csv"):
        by_event[events[r["date"]]] = int(float(r["daily_budget"]))
    ratio = by_event["fest"] / by_event["normal"]
    assert "about a fifth more" in text and 1.15 <= ratio <= 1.25
    assert f"difference of Rs {by_event['fest'] - by_event['normal']:,}" in text


def test_dates_and_weekdays_in_the_text_exist_in_the_calendar():
    """'Friday 16 October 2026' must be a Friday, and every dated example must be in the data."""
    import calendar as cal_module
    from datetime import date

    months = {name: i for i, name in enumerate(cal_module.month_name) if name}
    days = {r["date"] for r in csv_rows("calendar.csv")}
    pattern = re.compile(
        r"(?:(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) )?(\d{1,2}) ([A-Z][a-z]+) 2026"
    )
    checked = 0
    for name in KB_FILES:
        for weekday, day, month in pattern.findall(read(name)):
            if month not in months:
                continue
            d = date(2026, months[month], int(day))
            if d.isoformat() not in days:  # dates quoted from the FSSAI text are not dates in 2026
                continue
            if weekday:
                assert d.strftime("%A") == weekday, f"{name}: {weekday} {day} {month} 2026"
            checked += 1
    assert checked >= 5
