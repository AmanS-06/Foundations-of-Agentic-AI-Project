"""Knowledge-base search: ingestion, chunking, embeddings, vector index, hybrid retrieval.

Ingestion pipeline (runs in well under a second at start-up):
1. Load every Markdown file in the knowledge-base folder.
2. Chunk by heading: each "# / ## heading" section becomes one chunk, so a chunk is one
   self-contained rule and a citation can name its section.
3. Embed each chunk as a TF-IDF vector (computed locally, no model download, works offline).
4. Index the vectors in ChromaDB, which uses an HNSW graph for approximate nearest-neighbour
   search with cosine similarity.

Search is hybrid: the same query is ranked by vector similarity (meaning-ish, via shared
weighted terms) and by BM25 (exact keyword relevance), and the two rankings are merged with
reciprocal rank fusion (RRF): score = sum over rankings of 1 / (60 + rank).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import chromadb
import numpy as np
from chromadb.config import Settings
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer

from zeroplate.schemas import Citation

RRF_K = 60  # standard RRF constant: damps the influence of any single ranking
CANDIDATES = 10  # how many results each ranking contributes before fusion
TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Chunk:
    source: str  # file name
    section: str  # heading
    text: str


def chunk_markdown(path: Path) -> list[Chunk]:
    """Split a Markdown file into one chunk per heading section (empty sections skipped)."""
    chunks, heading, body = [], path.stem, []

    def flush() -> None:
        text = " ".join(line.strip() for line in body if line.strip())
        if text:
            chunks.append(Chunk(path.name, heading, text))

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            flush()
            heading, body = line.lstrip("#").strip(), []
        else:
            body.append(line)
    flush()
    return chunks


STOP = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    ]
)
SUFFIXES = ("ing", "ed", "es", "s")


def stem(word: str) -> str:
    """Very light stemming so word forms match: reheated / reheating -> reheat."""
    for suffix in SUFFIXES:
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list[str]:
    """Lower-case words, stop words removed, lightly stemmed (used by both rankings)."""
    return [stem(w) for w in TOKEN.findall(text.lower()) if w not in STOP]


class KnowledgeBase:
    """Hybrid (vector + BM25) search over the Markdown files in `kb_dir`."""

    def __init__(self, kb_dir: Path) -> None:
        self.chunks: list[Chunk] = [
            c for path in sorted(Path(kb_dir).glob("*.md")) for c in chunk_markdown(path)
        ]
        if not self.chunks:
            self._vectorizer = None
            return
        texts = [f"{c.section}. {c.text}" for c in self.chunks]
        self._vectorizer = TfidfVectorizer(
            tokenizer=tokenize,
            token_pattern=None,
            lowercase=False,
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        matrix = self._vectorizer.fit_transform(texts).toarray()
        client = chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
        self._collection = client.create_collection(
            f"kb-{uuid.uuid4().hex[:8]}",
            embedding_function=None,
            metadata={"hnsw:space": "cosine"},
        )
        self._collection.add(
            ids=[str(i) for i in range(len(texts))], embeddings=matrix.tolist(), documents=texts
        )
        self._bm25 = BM25Okapi([tokenize(t) for t in texts])

    def __len__(self) -> int:
        return len(self.chunks)

    def _vector_ranking(self, query: str) -> list[int]:
        vec = self._vectorizer.transform([query]).toarray()[0]
        if not np.any(vec):  # no known words: vector search has nothing to go on
            return []
        res = self._collection.query(
            query_embeddings=[vec.tolist()], n_results=min(CANDIDATES, len(self.chunks))
        )
        return [int(i) for i in res["ids"][0]]

    def _bm25_ranking(self, query: str) -> list[int]:
        scores = self._bm25.get_scores(tokenize(query))
        order = np.argsort(-scores)[:CANDIDATES]
        return [int(i) for i in order if scores[i] > 0]

    def search(self, query: str, k: int = 3) -> list[Citation]:
        """Top-k chunks for `query`, fused from the vector and BM25 rankings."""
        if not self.chunks:
            return []
        fused: dict[int, float] = {}
        for ranking in (self._vector_ranking(query), self._bm25_ranking(query)):
            for rank, idx in enumerate(ranking, start=1):
                fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank)
        best = sorted(fused, key=fused.get, reverse=True)[:k]
        return [
            Citation(
                source=self.chunks[i].source,
                section=self.chunks[i].section,
                text=self.chunks[i].text,
                score=round(fused[i], 4),
            )
            for i in best
        ]
