# ZeroPlate: validation, results, limitations and future scope

Every canteen number in this document comes from synthetic data that we generated ourselves. None of it is a measurement of the SIT Pune canteen. The results show that the method behaves sensibly under our assumptions. They do not show what a real canteen would save.

The numbers were measured on 11 October 2026 on the merged project (commit `28a5f23` of `main`, plus the three pending changes named in section 8). Section 9 lists the commands that reproduce them.

## 1. What was evaluated

We ran the whole system, with the real MCP servers, the real knowledge base and the recorded model answers, in four ways.

1. Six benchmark scenarios on the main dataset, each with an automatic check of what the team should do.
2. A 30-day backtest, in which ZeroPlate plans each of the last 30 days using only earlier data, and the plan is compared with the old habit of cooking the recent same-weekday sales plus 15%. We ran it on the main dataset and on a second, held-out dataset made with a different seed and slightly different multipliers.
3. A search test of the knowledge base, with 15 questions written the way a canteen manager would ask them.
4. Guardrail probes: attacks and harmless notes sent through the manager's note box, and the same attacks sent through the whole system.

The language model is Mistral 7B run locally through Ollama. Its answers were recorded once on the merged data and are replayed in the demo, so the runs are fast and repeat exactly. Every number in a plan comes from a tool or a function, never from the model.

## 2. The six scenarios

| Scenario | What the team should do | Result | Revisions |
|---|---|---|---|
| S1 College fest and budget conflict | Reject the best plan as over budget, revise, approve within budget | Approved | 2 |
| S2 Exam week | Plan a smaller day without trouble | Approved | 0 |
| S3 Budget cut of 30% | Find that no plan fits and hand over to a human | Escalated | 1 |
| S4 Injected manager note | Flag the note, ignore it, plan as if it were not there | Approved, note flagged | 2 |
| S5 Wrong number in the summary | Catch the invented figure with the fact check and rewrite the summary | Approved | 2 |
| S6 Unsafe leftovers | Block the unsafe batches and reuse only the safe ones | Approved | 2 |

All six behave as expected, in replay mode and in the fixed-rules mode, and with the real MCP servers and with the in-process fallback. The two fallbacks give identical statuses, revisions and tool-call counts.

A scenario takes about 215 tool calls and roughly 1.5 to 2.5 seconds with the recorded answers, depending on how busy the machine is. All 42 model answers in the six scenarios come from the recording, and none falls back to the fixed rules. The scenarios cost no money to run.

### The demo story in numbers

On the demo day, 16 October 2026, a fest, accounts has set a budget of Rs 60,900. The system makes three attempts.

| Attempt | Cooks | Food cost | What the Critic found |
|---|---|---|---|
| 1 | Forecast plus 5% | Rs 58,953 | Fails the leftover rule C9: batches B1, B3 and B5 are unsafe to reuse |
| 2 | Forecast plus 5% | Rs 61,239 | Fails the budget rule C4: over by Rs 339 |
| 3 | The forecast itself (plus 0%) | Rs 58,252 | Passes every rule and is approved |

The plan reuses batches B2 and B4 and raises purchase orders worth Rs 30,255. Of the four candidate plans, the one with the best expected utility is the plus 5% plan, and it does not fit the budget. That is why the Critic has something real to reject.

## 3. Waste and shortage compared with the old habit

The old habit is what the canteen does today in our model: cook the average of the last three same-weekday sales plus 15%, and ignore the calendar. The table covers the last 30 days of history, 16 September to 15 October 2026.

| | Plates wasted | Plates unmet | Waste cost |
|---|---:|---:|---:|
| **Main dataset** | | | |
| Old habit | 7,219 | 2,359 | Rs 189,092 |
| ZeroPlate | 3,514 | 1,295 | Rs 81,118 |
| Change | **−51.3%** | −45.1% | −57.1% |
| **Held-out dataset** | | | |
| Old habit | 8,896 | 3,952 | Rs 226,596 |
| ZeroPlate | 5,242 | 1,230 | Rs 124,427 |
| Change | **−41.1%** | −68.9% | −45.1% |

The forecast error (mean absolute percentage error) is 10.9% on the main dataset and 13.0% on the held-out one.

The main dataset flatters the system, because the forecaster is built around the same kind of data. The honest figure to quote is the held-out one: **waste falls by about 41% and unmet demand by about 69%**, always as a simulation on synthetic data.

The "old habit" numbers were worked out twice, by two separate programs: the evaluation harness, and a baseline script that adds up the history directly. They agree exactly on plates wasted and plates unmet, and on the cost of the waste to the rupee, on both datasets.

## 4. Output validation

Every output of every agent is a typed record that is checked the moment it is made, so a wrong type or a missing field stops the run. On top of that the Critic checks the plan against six rules before anything is acted on.

| Rule | What it checks |
|---|---|
| C1 | Each dish is within half to one and a half times its usual quantity on days of the same type |
| C2 | The planned amount is no more than 15% above the forecast |
| C4 | The food cost fits the day's budget |
| C5 | The vegetarian and Jain dishes keep their minimum portions |
| C6 | Every number in the model's written summary matches a tool result within 1% |
| C9 | Leftover reuse follows the FSSAI rules, and cites the knowledge base |

The Critic gives one of three verdicts, approve, revise or escalate, and the verdict comes from the rules alone. The model only writes the feedback text.

**The leftover rule, checked against the knowledge base.** The knowledge base says which of the five leftover batches may be served again: B2 (chilled, never reheated) and B4 (still held hot) may, and B1 (left at room temperature), B3 (already reheated once) and B5 (older than 24 hours) may not. We checked the system against that list directly, not against the code's own function. In every scenario on the fest day, the batches reused are exactly B2 and B4, and never B1, B3 or B5.

**The note scanner and what stands behind it.** The scanner is a simple filter of keywords and large numbers. We probed it with harmless notes and with variations of the attack.

| | Result |
|---|---|
| Harmless notes flagged by mistake | 3 of 7 (any number above 300, such as "1200 students", and the words "skip" with "budget review") |
| Attack variations flagged | 5 of 11 |
| Attack variations missed | 6 of 11 (extra spaces, a slightly different wording, letters spread apart, an order phrased as a policy) |

The scanner is a first line of defence and it has gaps, as any keyword filter does. What matters is whether a missed attack can change the outcome. We sent each missed attack through the whole system. In every case the plan and the leftover choices were identical to the run without the note, so no unsafe batch was reused. The Critic's rules, the allowlist and the limits on what a note may change are what actually hold. A harmless note that asks for 20% more tea did change the plan, as it should.

## 5. Finding the right passage in the knowledge base

We measured how often the right section is among the first three results, and how high it is ranked on average (mean reciprocal rank, where 1.0 means always first).

| Retriever | First place | Top three | Mean reciprocal rank |
|---|---:|---:|---:|
| Plain keyword search (BM25) | 66.7% | 66.7% | 0.701 |
| ZeroPlate's retriever (TF-IDF vectors and BM25, merged) | 53.3% | 73.3% | 0.619 |

Both find the right section in the top three for about two questions in three. The questions that both miss use different words from the documents: "serving counter" against "displayed", "fridge" against "refrigerated". Both of ZeroPlate's rankings count words, so merging them adds little. A search by meaning, with embeddings from a language model, would link such words. We did not change the questions to raise the score.

## 6. Tests

The project has 217 automatic tests on `main`, and they all pass on a fresh clone with a fresh environment built only from `requirements.txt`. The 17 environment checks also pass. With the three pending changes in section 8 there are 230 tests.

Eight of the tests run the whole system on the real data, in a fresh process each, and protect the results above: all six scenarios behave as expected, every model answer comes from the recording, only the safe batches are reused, a scenario needs no more than 260 tool calls, the real MCP servers agree with the fallback, and the held-out backtest keeps its headline result. We checked that these tests can fail by breaking the system on purpose in two ways, and both were caught.

## 7. Limitations

- All canteen data is synthetic, and the data generator, the forecaster and the old habit were all written by us. The held-out dataset reduces this problem but is still made by our generator. Real data would need a visit to the canteen.
- The model covers one canteen. The numbers for holidays and fests rest on only four days each. The academic calendar is illustrative and not SIT Pune's real one.
- The demand effects, the shelf lives, the minimum portions and the weights of 1 and 3 are our assumptions.
- The food-safety rules come from one FSSAI guide, and where the guide can be read in two ways we took the stricter reading and said so. The project is a planning aid and not a certified food-safety system.
- In the demo the model's answers are replayed, not live. They are real model output recorded earlier on the same data, but they only match the prompts that were recorded. Any change to the data or the prompts needs the answers to be recorded again.
- A small local model sometimes writes feedback that is wrong, even when the verdict is right. In the demo scenario the model's feedback tells the canteen to "reheat the chicken biryani", although a batch that has been reheated once must be thrown away. The rules decide the outcome, so the plan is safe, but the sentence is wrong and visible on screen.
- Whether a live model can be talked into something by a note that the scanner misses was not tested, because the live model runs only on one laptop with a graphics card. The tests above used the recorded answers and the fixed rules.
- The scanner flags some harmless notes and misses some attacks, as shown in section 4.
- A keyword-based search misses questions that use different words from the documents.

## 8. Changes that were pending when these numbers were measured

Three changes were made after the main branch was merged. They do not change any result above, except the tool-call count.

1. The Education server serves the academic calendar as JSON, so the agents read it in one call. Before, they asked day by day, and a scenario took 393 tool calls instead of 215 and about twice as long. All other numbers were identical before and after.
2. The eight whole-system tests.
3. This document.

## 9. How to reproduce

From the project folder, with the virtual environment, using Python 3.11:

The evaluation commands need the source folder on the Python path, and the tests do not. In PowerShell set it with `$env:PYTHONPATH = "src"`, and in Command Prompt with `set PYTHONPATH=src`.

```
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m zeroplate.eval.run_eval --mcp --llm replay --days 30
.venv\Scripts\python -m zeroplate.eval.run_eval --mcp --llm replay --days 30 --raw-dir data\heldout
.venv\Scripts\python scripts\baseline_metrics.py data/raw data/heldout --last-days 30
.venv\Scripts\python scripts\check_kb_retrieval.py
```

The evaluation writes its tables to `outputs/eval/report.md`.

## 10. Future scope

- Replace the synthetic data with real feeds from the canteen's till and the academic office, starting with a short visit for footfall, number of dishes and monthly waste.
- Add more departments as new MCP servers, for example sustainability and food donation, or nutrition and allergens, without rewriting the agents.
- Use embeddings that understand meaning for the knowledge-base search, so that a manager's own words find the right rule.
- Apply the same agents to other kinds of cafeteria, such as hostel messes, where only the servers change.
- Let canteens share surplus food with each other without a central controller.
- Test the live model against a wider set of attacks, and add a check that the feedback text agrees with the rule it describes.
- Put a person in the loop through an approval screen for the plans that the Critic escalates.
