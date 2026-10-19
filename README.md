<div align="center">

# ZeroPlate

**A cross-domain agentic AI planner for the college canteen**<br>
Five agents, three departments, one goal: *cook what will be eaten.*

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.65-FF4B4B?logo=streamlit&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1.2-1C3C3C)
![MCP](https://img.shields.io/badge/MCP-1.30-6E56CF)
![Ollama](https://img.shields.io/badge/Ollama-Mistral-000000?logo=ollama&logoColor=white)
![Tests](https://img.shields.io/badge/tests-230%20passing-34d399)

CA-3 proof of concept for *Foundations of Agentic AI*, SIT Pune · Anhad Mahajan and Aman Saxena<br>
All data in this project is synthetic.

</div>

---

## The problem

A college canteen cooks before it knows who will come. Three offices each hold part of the answer, but nobody combines them:

| Department | Knows | MCP server |
|---|---|---|
| **Education** (academic office) | exam days, holidays, fests, expected attendance | `edu_server` |
| **Supply** (canteen store) | stock, recipes, leftovers, suppliers | `supply_server` |
| **Finance** (accounts) | the daily budget and the cost of a plan | `finance_server` |

ZeroPlate's agents ask all three, then decide how much of each dish to cook: as little waste as possible, no shortages, within budget and FSSAI food-safety rules.

## Final submission

Everything submitted for CA-3 is in [`Final submission/`](Final%20submission/):

| | File |
|---|---|
| Presentation | [PDF](Final%20submission/ZeroPlate_CA3_presentation.pdf) (viewable on GitHub) · [PPTX](Final%20submission/ZeroPlate_CA3_presentation.pptx) (download) |
| Problem statement and domain | [PDF](Final%20submission/ZeroPlate_problem_statement_and_domain.pdf) |

### Complete architecture

![ZeroPlate end-to-end architecture](Final%20submission/ZeroPlate_architecture_diagram.png)

<details>
<summary><b>1. LangGraph: state, nodes and edges</b></summary>

![LangGraph state, nodes and edges](Final%20submission/ZeroPlate_architecture_1_langgraph.png)
</details>

<details>
<summary><b>2. Orchestration layer: agent and tool calls</b></summary>

![Orchestration layer](Final%20submission/ZeroPlate_architecture_2_orchestration.png)
</details>

<details>
<summary><b>3. MCP layer: host, client and servers</b></summary>

![MCP host, client and servers](Final%20submission/ZeroPlate_architecture_3_mcp.png)
</details>

<details>
<summary><b>4. RAG: knowledge-base retrieval</b></summary>

![RAG connection and implementation](Final%20submission/ZeroPlate_architecture_4_rag.png)
</details>

## How it works

The agents run **sequentially** in one LangGraph graph, with a reflection loop: the Critic can send a plan back to the Executor at most twice, then hands the decision to a person.

```mermaid
flowchart LR
    UI([Streamlit UI]):::ui --> P[Planner]:::agent
    P --> R[Research]:::agent
    R --> E[Executor]:::agent
    E --> C{Critic}:::critic
    C -- approve --> A[Business Automation]:::agent
    C -- "revise (max 2)" --> E
    C -- escalate --> H([Canteen manager]):::human
    A --> D([Prep sheet + purchase orders]):::ui

    classDef ui fill:#0f172a,stroke:#7dd3fc,color:#e6edf3
    classDef agent fill:#064e3b,stroke:#34d399,color:#ecfdf5
    classDef critic fill:#422006,stroke:#fbbf24,color:#fef3c7
    classDef human fill:#4c0519,stroke:#fb7185,color:#ffe4e6
```

| Agent | Job |
|---|---|
| **Planner** | Breaks the goal into tasks (the language model does the decomposition) |
| **Research** | Reads the calendar, attendance, menu and leftovers; searches the knowledge base; recalls past runs; reads the manager's note after an injection check |
| **Executor** | ReAct loop: forecasts demand (median of three methods), scores Tree-of-Thought branches (+0/5/10/15%) by expected utility, then costs the plan |
| **Critic** | Checks six rules (C1 event-aware range, C2 forecast band, C4 budget, C5 dietary fairness, C6 fact check, C9 FSSAI leftover safety); approves, revises or escalates |
| **Business Automation** | The only agent with write tools: raises purchase orders, writes the prep sheet, saves a lesson to memory |

### Tools over MCP

The ZeroPlate app is the **MCP host**. Inside it, the **MCP client** (`MCPHub`) keeps one session per server over stdio and checks every call against a per-agent allowlist.

```mermaid
flowchart LR
    subgraph HOST["MCP host: ZeroPlate app"]
        direction TB
        AG[Agents]:::agent --> AL{Allowlist}:::critic
        AL --> CL[MCP client<br/>MCPHub, 3 sessions]:::client
        AG -.-> KB[(Knowledge base<br/>Chroma + BM25)]:::local
        AG -.-> MEM[(Memory<br/>SQLite)]:::local
        AG -.-> LLM[Mistral via Ollama<br/>record / replay]:::local
    end
    CL -- stdio --> EDU[Education server]:::server
    CL -- stdio --> SUP[Supply server]:::server
    CL -- stdio --> FIN[Finance server]:::server

    classDef agent fill:#064e3b,stroke:#34d399,color:#ecfdf5
    classDef critic fill:#422006,stroke:#fbbf24,color:#fef3c7
    classDef client fill:#1e1b4b,stroke:#a5b4fc,color:#e0e7ff
    classDef server fill:#0c4a6e,stroke:#7dd3fc,color:#e0f2fe
    classDef local fill:#1f2937,stroke:#94a3b8,color:#e5e7eb
    style HOST fill:#0a0e13,stroke:#334155,color:#e6edf3
```

### Retrieval (RAG)

```mermaid
flowchart LR
    Q[Query]:::q --> S[Semantic search<br/>TF-IDF in ChromaDB]:::step
    Q --> B[Keyword search<br/>BM25]:::step
    S --> F{Reciprocal<br/>rank fusion}:::fuse
    B --> F
    F --> T[Top 3 chunks<br/>with citations]:::out
    K[(data/kb/*.md<br/>39 chunks)]:::kb -.-> S
    K -.-> B

    classDef q fill:#0f172a,stroke:#7dd3fc,color:#e6edf3
    classDef step fill:#064e3b,stroke:#34d399,color:#ecfdf5
    classDef fuse fill:#422006,stroke:#fbbf24,color:#fef3c7
    classDef out fill:#1e1b4b,stroke:#a5b4fc,color:#e0e7ff
    classDef kb fill:#1f2937,stroke:#94a3b8,color:#e5e7eb
```

- **Memory:** short-term memory is the LangGraph state of a run; long-term memory is a SQLite store of past runs.
- **Language model:** Mistral through Ollama does real work in three places: planning, reading the manager's note, and writing the Critic's feedback. Its answers are recorded once and replayed in the demo. Every number comes from a tool, and the Critic fact-checks every number the model writes.
- **Guardrails:** prompt-injection check on the manager's note, tool allowlist (least privilege), C6 fact check, C9 FSSAI rule.

## Results (simulation on synthetic data)

| | |
|---|---|
| Benchmark scenarios passing | **6 / 6** |
| Food waste vs the old habit | **−41.1%** |
| Unmet demand vs the old habit | **−68.9%** |
| Forecast error (MAPE) | **13%** |

The last three rows come from a 30-day backtest on a held-out dataset (a different seed and different demand multipliers). The old habit is the canteen cooking last week's sales plus 15%.

## Getting started

**Setup** (Windows, Python 3.11)

```bash
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\check_env.py
```

**Run**

```bash
.venv\Scripts\streamlit run app.py
```

Pick a scenario in the sidebar and press **Run the agents**. Scenario **S1 (college fest)** shows the whole loop: the Critic rejects the plan for unsafe leftovers, then for going over budget, and approves the third attempt.

**Optional: record the local model's answers**

```bash
ollama pull mistral
.venv\Scripts\python scripts\record_answers.py
```

The app replays `data/recordings/answers.json` by default. To call the model live, choose `ollama` under *Advanced* in the sidebar.

**Tests and evaluation**

```bash
.venv\Scripts\python -m pytest -q
set PYTHONPATH=src
.venv\Scripts\python -m zeroplate.eval.run_eval --mcp
```

## Project layout

```
app.py                     Streamlit interface
Final submission/          deck, problem statement, architecture diagrams
src/zeroplate/
  agents/                  the five agents
  graph.py                 LangGraph orchestration
  mcp_servers/             Education, Supply and Finance MCP servers
  mcp_client/              MCP client (hub) and tool allowlist
  domain/                  forecast, stocking calculation, costing
  guardrails/              injection check, fact check, FSSAI rule, Critic rules
  llm/                     model client: deterministic / ollama / record / replay
  rag/  memory/            knowledge-base search, long-term memory
  eval/                    scenarios and evaluation harness
data/                      synthetic dataset, held-out dataset, knowledge base, recordings
tests/                     tests and sample fixture data
```
