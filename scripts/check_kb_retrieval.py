"""Can a plain keyword search find the right section of the knowledge base for each of the 15 questions?

This is a baseline, not the project's retriever. It splits the four knowledge-base documents into one
chunk per "##" section, scores every chunk against a question with BM25 (a standard keyword-matching
score), and asks where the section that should answer the question lands in the ranking.

  hit@1   the right section is ranked first
  hit@3   the right section is among the top three (the measure the project reports)
  MRR     the average of 1 / (rank of the right section); 1.0 means always first

For the questions that need two documents, "all needed in top 5" asks whether every required section
is within the top five results.

A keyword search only matches words. It cannot know that "fridge" and "refrigerated" mean the same,
so some misses are expected. They are the cases that a search by meaning (embeddings) should win.
The retriever Aman builds should score at least as well as this.

Run:  .venv\\Scripts\\python scripts\\check_kb_retrieval.py
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[1]
HEADING = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
STOPWORDS = frozenset(
    {
        # plain English words that say nothing about which section answers a question
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "does", "for", "from",
        "has", "have", "how", "i", "if", "in", "is", "it", "its", "of", "on", "or", "our", "so",
        "than", "that", "the", "their", "them", "then", "there", "these", "they", "this", "to",
        "us", "was", "we", "what", "when", "which", "who", "will", "with", "would", "you", "your",
    }
)  # fmt: skip
MIN_STEM_LENGTH = 3  # never cut a word down to fewer letters than this
SUFFIXES = ("ing", "ed", "es", "s")  # a deliberately plain stemmer: "reheated" and "reheating" meet


@dataclass(frozen=True)
class Chunk:
    """One '##' section of one knowledge-base file."""

    source: str  # file name, e.g. food_safety_fssai.md
    section: str  # the heading text
    text: str


@dataclass
class Result:
    """Where the right section(s) landed for one question."""

    question: str
    expected: tuple[str, str]
    rank: int  # 1 = best; position of the expected section in the ranking
    top: list[tuple[str, str]]  # the three best-ranked sections
    also: dict[tuple[str, str], int] = field(default_factory=dict)  # rank of each extra section

    @property
    def all_needed_in_top5(self) -> bool:
        return self.rank <= 5 and all(r <= 5 for r in self.also.values())


def stem(word: str) -> str:
    """Strip one common ending, keeping at least MIN_STEM_LENGTH letters."""
    for suffix in SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= MIN_STEM_LENGTH:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list[str]:
    """Lower-case words and numbers, without stop words, each with one ending stripped."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [stem(w) for w in words if w not in STOPWORDS]


def load_chunks(kb_dir: Path) -> list[Chunk]:
    """One chunk per '##' section, in file order. The heading is part of the chunk's text."""
    chunks = []
    for path in sorted(kb_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        starts = [m for m in HEADING.finditer(text)]
        for i, m in enumerate(starts):
            end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
            chunks.append(Chunk(path.name, m.group(1), m.group(1) + "\n" + text[m.end() : end]))
    return chunks


def evaluate(kb_dir: Path, questions_path: Path) -> list[Result]:
    """Rank every chunk for every question and record where the expected sections land."""
    chunks = load_chunks(kb_dir)
    if not chunks:
        raise ValueError(f"no '##' sections found in {kb_dir}")
    keys = [(c.source, c.section) for c in chunks]
    bm25 = BM25Okapi([tokenize(c.text) for c in chunks])
    questions = json.loads(questions_path.read_text(encoding="utf-8"))

    results = []
    for q in questions:
        scores = bm25.get_scores(tokenize(q["question"]))
        order = sorted(range(len(chunks)), key=lambda i: (-scores[i], i))  # ties keep file order
        position = {keys[i]: rank for rank, i in enumerate(order, start=1)}
        expected = (q["expected_source"], q["expected_section"])
        extras = {
            (e["expected_source"], e["expected_section"]): _rank_of(
                position, q["question"], e["expected_source"], e["expected_section"]
            )
            for e in q.get("also_needs", [])
        }
        rank = _rank_of(position, q["question"], *expected)
        results.append(Result(q["question"], expected, rank, [keys[i] for i in order[:3]], extras))
    return results


def _rank_of(position: dict[tuple[str, str], int], question: str, source: str, section: str) -> int:
    """Where one section landed in the ranking; a clear error if the section does not exist."""
    if (source, section) not in position:
        raise KeyError(f"{source}: no section called {section!r} (question: {question})")
    return position[(source, section)]


def summarise(results: list[Result]) -> dict[str, float]:
    """hit@1, hit@3, MRR and the multi-document measure, over all questions."""
    n = len(results)
    multi = [r for r in results if r.also]
    return {
        "questions": n,
        "hit@1": sum(r.rank <= 1 for r in results) / n,
        "hit@3": sum(r.rank <= 3 for r in results) / n,
        "mrr": sum(1 / r.rank for r in results) / n,
        "multi_questions": len(multi),
        "multi_all_in_top5": (
            sum(r.all_needed_in_top5 for r in multi) / len(multi) if multi else 0.0
        ),
    }


def render(results: list[Result]) -> str:
    """A table of every question, then the summary."""
    lines = [f"{'#':>2}  {'rank':>4}  {'section the question should find':<56}  question"]
    for i, r in enumerate(results, start=1):
        mark = " " if r.rank <= 3 else "*"
        lines.append(f"{i:>2}  {r.rank:>3}{mark}  {r.expected[1][:56]:<56}  {r.question[:70]}")
    misses = [r for r in results if r.rank > 3]
    if misses:
        lines.append("\n* = not in the top 3. What was ranked first to third instead:")
        for r in misses:
            lines.append(f"  - {r.question[:75]}")
            lines += [f"      {s} :: {t[:60]}" for s, t in r.top]
    s = summarise(results)
    lines += [
        "",
        f"questions            {s['questions']}",
        f"hit@1                {s['hit@1']:.1%}",
        f"hit@3                {s['hit@3']:.1%}",
        f"MRR                  {s['mrr']:.3f}",
        (
            f"two-document questions: all needed sections in the top 5 for "
            f"{s['multi_all_in_top5']:.0%} of {s['multi_questions']}"
        ),
    ]
    return "\n".join(lines)


def main() -> None:
    """Command line entry point."""
    parser = argparse.ArgumentParser(description="Keyword-search baseline for the knowledge base.")
    parser.add_argument("--kb", type=Path, default=ROOT / "data" / "kb")
    parser.add_argument(
        "--questions", type=Path, default=ROOT / "data" / "kb" / "eval_questions.json"
    )
    args = parser.parse_args()
    print(render(evaluate(args.kb, args.questions)))


if __name__ == "__main__":
    main()
