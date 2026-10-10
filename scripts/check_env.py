"""Check that this laptop can run ZeroPlate.

Run it with the project's virtual environment:  .venv\\Scripts\\python scripts\\check_env.py

Installing a package is not enough: Windows (for example Smart App Control) can block a
package's compiled files when they are loaded. So every check below imports the package AND
does one small real operation with it. Each line prints OK or FAIL with the reason.
"""

from __future__ import annotations

import importlib
import sys
from importlib.metadata import PackageNotFoundError, version

# package name on PyPI -> (module to import, version we pinned)
PINNED = {
    "mcp": ("mcp", "1.30.0"),
    "langgraph": ("langgraph", "1.2.14"),
    "streamlit": ("streamlit", "1.65.0"),
    "pydantic": ("pydantic", "2.14.0"),
    "chromadb": ("chromadb", "1.5.9"),
    "rank-bm25": ("rank_bm25", "0.2.2"),
    "scikit-learn": ("sklearn", "1.7.2"),
    "pandas": ("pandas", "2.3.3"),
    "numpy": ("numpy", "2.4.6"),
    "plotly": ("plotly", "7.1.0"),
    "ollama": ("ollama", "0.6.3"),
    "pytest": ("pytest", "9.1.1"),
}


def check_python() -> tuple[bool, str]:
    """Python must be 3.11 (3.14 is the default on some laptops and breaks some packages)."""
    v = sys.version_info
    return (v.major, v.minor) == (
        3,
        11,
    ), f"Python {v.major}.{v.minor}.{v.micro} at {sys.executable}"


def check_package(dist: str, module: str, pinned: str) -> tuple[bool, str]:
    """The package imports and its installed version matches the pin."""
    try:
        installed = version(dist)
    except PackageNotFoundError:
        return False, "not installed"
    try:
        importlib.import_module(module)
    except Exception as exc:  # noqa: BLE001 - blocked DLLs raise ImportError, OSError, etc.
        return False, f"installed {installed} but import failed: {type(exc).__name__}: {exc}"
    if installed != pinned:
        return False, f"version {installed}, expected {pinned}"
    return True, installed


def check_fastmcp() -> tuple[bool, str]:
    """mcp 1.x provides FastMCP; mcp 2.x removed it."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("check")

    @server.tool()
    def ping() -> str:
        return "pong"

    return True, "FastMCP server object created"


def check_numeric_stack() -> tuple[bool, str]:
    """numpy + pandas + scikit-learn compiled code actually runs."""
    import numpy as np
    import pandas as pd
    from sklearn.feature_extraction.text import TfidfVectorizer

    df = pd.DataFrame({"x": np.arange(5)})
    vec = TfidfVectorizer().fit_transform(["hot food reheated once", "budget per day"])
    return df["x"].sum() == 10 and vec.shape[0] == 2, "pandas, numpy and TF-IDF ran"


def check_chroma_offline() -> tuple[bool, str]:
    """ChromaDB works with our own embeddings, so it never downloads a model."""
    import chromadb
    from chromadb.config import Settings

    # anonymized_telemetry=False: Chroma otherwise sends usage pings over the internet
    client = chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
    col = client.create_collection("check", embedding_function=None)
    col.add(ids=["a", "b"], embeddings=[[1.0, 0.0], [0.0, 1.0]], documents=["hot", "cold"])
    hit = col.query(query_embeddings=[[0.9, 0.1]], n_results=1)["documents"][0][0]
    return hit == "hot", "in-memory vector search returned the nearest document"


def check_langgraph() -> tuple[bool, str]:
    """A two-node LangGraph graph compiles and runs."""
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph

    class S(TypedDict):
        n: int

    g = StateGraph(S)
    g.add_node("add", lambda s: {"n": s["n"] + 1})
    g.add_edge(START, "add")
    g.add_edge("add", END)
    out = g.compile().invoke({"n": 1})
    return out["n"] == 2, "graph ran"


def main() -> int:
    """Run every check, print a report, return 0 only if everything passed."""
    checks: list[tuple[str, tuple[bool, str]]] = [("python", check_python())]
    for dist, (module, pinned) in PINNED.items():
        checks.append((dist, check_package(dist, module, pinned)))
    for name, fn in [
        ("fastmcp api", check_fastmcp),
        ("numeric stack", check_numeric_stack),
        ("chroma offline", check_chroma_offline),
        ("langgraph run", check_langgraph),
    ]:
        try:
            checks.append((name, fn()))
        except Exception as exc:  # noqa: BLE001 - report any failure instead of crashing
            checks.append((name, (False, f"{type(exc).__name__}: {exc}")))

    failed = 0
    for name, (ok, detail) in checks:
        failed += not ok
        print(f"{'OK  ' if ok else 'FAIL'}  {name:<15} {detail}")
    print(f"\n{len(checks) - failed}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
