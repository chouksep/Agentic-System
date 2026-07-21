# ci-wiki Benchmarking — Results

**Report date:** 2026-07-21
**Basis:** clean-slate rebuild with the LLM-verified QA-corpus filter enabled. All prior run artifacts + cached agent records were deleted before the numbers below were generated.

---

## 1. Executive summary

| Test pool | claude-sonnet-4-5 | claude-sonnet-4-6 |
|---|---|---|
| 27 verified cases (fixtures + synthesized + verified TriviaQA slice) | **88.9% (24/27)** | **85.2% (23/27)** |

- **First observed model disagreement**: `tqa_36055_elon-musk` — Sonnet 4.5 emits the expected single call; Sonnet 4.6 over-explores and emits two (`elon-musk/person` + an extra `tesla/company`), which the strict AST checker penalizes. See Section 6 for the raw predictions.
- Per-category (Sonnet 4.5): `irrelevance` 7/7 · `parallel` 2/2 · `simple` 7/8 · `multiple` 8/10 · `triviaqa-simple` 1/1.
- Two-model spend: **$0.43**. Sonnet 4.6 costs ~24% more and runs ~19% slower for slightly lower accuracy on this workload.
- Alignment audit passes 28/28: the underlying BFCL / T-Eval / ToolComp evaluator ports are algorithmically faithful.

**Two important changes since the previous report:**
1. **LLM-verified QA-corpus filter is now live**. `benchmarks/runner/datasets/llm_verifier.py` adds a second-stage filter (Claude Haiku 4.5) on top of the naive `EntityIndex.match()` first pass. TriviaQA numbers: examined 138,384 rows, kept only **2 candidates** post-verifier (verifier dropped **36 false positives** like "Jean Claude Killy" and "Gemini zodiac"). One survived dedup and became the disagreement-revealing case above.
2. **Sonnet 4.5 vs 4.6 are now distinguishable** on this pool, whereas the previous 26-case fixture-only run had them tied. The delta is one case, so still weak signal — but this is the *first* trustworthy case in this benchmark that surfaces a real behavioral difference.

---

## 2. What ships in the runner (Phase 1 + verifier)

`benchmarks/runner/` — the live-LLM benchmark harness delivered in this branch:

- **`agent.py`** — `AgentRunner` + record-only `TraceDispatcher`. Captures parameter shapes without executing real wiki I/O during BFCL eval.
- **`cache.py`** — sha256-keyed atomic disk cache with schema invalidation. Windows-MAX_PATH-safe filename length (16 hex chars).
- **`comparator.py`** — multi-model orchestration with hard `--max-cost` ceiling.
- **`report.py`** — markdown + JSON summary with per-model diff table.
- **`datasets/`** — loaders: `fixtures.py`, `synthesizer.py`, `entity_questions.py` (nq_open), `triviaqa.py`, plus the new **`llm_verifier.py`** (Claude Haiku 4.5 secondary filter with per-entity descriptions).
- **`__main__.py`** — argparse CLI. Default `--datasets fixtures,synthesized` for cheap runs; add `entity_questions,triviaqa` to enable the verified QA-corpus slice.
- **58 unit + integration tests** covering agent loop, cache atomicity + schema invalidation, comparator cost ceiling, report rendering, CLI wiring, per-loader verifier behavior, and a MockLLMClient end-to-end test.

Alignment audit (`benchmarks/ALIGNMENT_AUDIT.py`): **28/28 = 100%** across BFCL 9/9, T-Eval 6/6, ToolComp 10/10, runtime env probes 3/3.

---

## 3. Live-agent results — full detail

Run: `python -m benchmarks.runner --benchmark bfcl --models claude-sonnet-4-5,claude-sonnet-4-6 --datasets fixtures,synthesized,entity_questions,triviaqa --n-samples 30 --seed 0 --max-cost 1.5`

### 3.1 Case pool (27 cases after dedup)

| Source | # cases | Notes |
|---|---|---|
| `fixtures` (hand-curated) | 12 | 7 simple, 3 multiple, 2 parallel |
| `synthesized` (via `Synthesizer`) | 14 | 7 multiple (padded with distractors) + 7 irrelevance (off-topic Qs, expect abstention) |
| `entity_questions` (nq_open, verifier-filtered) | 0 | 0 candidates survived the verifier — verifier is strict on ambiguous entity mentions |
| `triviaqa` (verifier-filtered) | 1 | 138,384 rows examined; 38 hit EntityIndex; verifier dropped 36; 2 kept; 1 survived pool dedup |
| **Total** | **27** | |

### 3.2 Per-model, per-category accuracy

| Category | Sonnet 4.5 | Sonnet 4.6 |
|---|---|---|
| irrelevance | 7/7 = 100.0% | 7/7 = 100.0% |
| parallel | 2/2 = 100.0% | 2/2 = 100.0% |
| simple | **7/8 = 87.5%** | 6/8 = 75.0% |
| multiple | 8/10 = 80.0% | 8/10 = 80.0% |
| **Overall** | **24/27 = 88.9%** | **23/27 = 85.2%** |

### 3.3 Cost, tokens, latency

| Metric | Sonnet 4.5 | Sonnet 4.6 | 4.6 vs 4.5 |
|---|---|---|---|
| Total cost | $0.191 | $0.237 | +24.4% |
| Total tokens | 48,616 | 53,972 | +11.0% |
| Latency p50 | 4.85 s | 5.78 s | +19.2% |
| Latency p95 | ~10 s | ~11 s | +10% |
| Agent errors | 0 | 0 | — |

Two-model total: **$0.428** for 27 cases × 2 models = 54 (model, case) pairs. Effective ~$0.0079/pair.

Plus verifier cost: **~$0.01** for the 38 entity-index candidates from TriviaQA (Haiku 4.5, ~50-token prompts). Verifier cost is a one-time expense per corpus per verifier version — subsequent runs at the same cache state pay nothing.

---

## 4. Model comparison — first observed real difference

Sonnet 4.5 and Sonnet 4.6 diverged on **1 case** in this run:

| case_id | Sonnet 4.5 | Sonnet 4.6 |
|---|---|---|
| `tqa_36055_elon-musk` | ✓ valid | ✗ `wrong_count` |

**The case:** *"What car company was founded by Elon Musk?"*
**Expected call:** `read_wiki_page(slug=elon-musk, page_type=person)` — single call.

- **Sonnet 4.5 emitted:** exactly one call: `read_wiki_page(elon-musk, person)` ✓
- **Sonnet 4.6 emitted:** two calls: `read_wiki_page(elon-musk, person)` **plus** `read_wiki_page(tesla, company)` — the second call is the actual *answer* entity (Tesla is a car company Musk founded). Semantically arguably *better* behavior, but the BFCL AST checker treats this as `wrong_count` because the fixture expects exactly one call.

**Reading:** Sonnet 4.6 tends toward more thorough / exploratory tool use. On this specific question that thoroughness gets penalized under BFCL's strict counting; on questions where the fixture allows multiple calls (parallel category), both models score identically. Whether "over-exploration" is a real quality issue depends on your definition — for a benchmark that scores exact counts, it costs a point.

At n=27, this one-case delta translates to 88.9% vs 85.2%. Statistical significance at this sample size is weak — both readings sit inside a ~10-percentage-point 95% CI. Larger sample would tell you whether Sonnet 4.6 systematically over-explores or if this was a single-case artifact.

---

## 5. Alignment audit (evaluator ports vs paper)

`python benchmarks/ALIGNMENT_AUDIT.py`

| Suite | Score |
|---|---|
| BFCL (Patil et al., ICML 2025) | 9/9 |
| T-Eval (Chen et al., ACL 2024, arXiv:2312.14033) | 6/6 |
| ToolComp (Nath et al., arXiv:2501.01290) | 10/10 |
| Runtime environment probes | 3/3 |
| **Overall** | **28/28 (100%)** |

---

## 6. Failing cases — root cause on each

| Case | Category | Fails on | Root cause |
|---|---|---|---|
| `simple_flag_contradiction` | simple | both | Agent emitted `description="The pages list different founding years for Anthropic"` — semantically identical to expected but BFCL uses case-insensitive **exact-string match**. Fixture-level fix documented (loosen expected list). |
| `simple_flag_contradiction__multi` | multiple (synthesized) | both (different error for each model) | Same underlying issue — Sonnet 4.5 fails on string match, Sonnet 4.6 fails on `wrong_count` (emitted extra exploratory call). |
| `multiple_pick_search` | multiple | both | Over-generation — model emits >1 tool call when fixture expects exactly one. |
| `tqa_36055_elon-musk` | simple (from TriviaQA) | **Sonnet 4.6 only** | See Section 4. Sonnet 4.6 emits two exploratory calls; Sonnet 4.5 emits the expected single call. |

**Fixture-level fix targets** (deferable):
- Loosen the `flag_contradiction` `possible_answer[]` to accept common paraphrases → +2 pass on both models → Sonnet 4.5 → 26/27, Sonnet 4.6 → 25/27.
- Update `multiple_pick_search` / `tqa_36055_elon-musk` to accept multiple-call variants → +1 or +2 pass depending on how far we loosen.

---

## 7. Verifier behavior — TriviaQA + NQ-Open

The verifier is a targeted secondary filter on top of `EntityIndex.match()`. For each candidate row where the naive whole-word slug match hits, we ask Claude Haiku 4.5:

> *Target entity: "Claude" (product) — Anthropic's AI assistant / large language model product.*
> *Question: "The Claude Francois song 'Comme d'habitude' was a hit in English for Frank Sinatra."*
> *Is this question about the target entity above, or about a different entity that happens to share the same or similar name?*

Answer: **NO** → dropped from the pool.

**Live-run stats from this session:**

| Source | Rows examined | EntityIndex hits (candidates) | Verifier kept | Verifier dropped |
|---|---|---|---|---|
| nq_open | streaming | few (loader logged 0 kept post-dedup) | 0 | all |
| triviaqa | 138,384 | 38 | **2** | **36** |

Precision on the 2 kept TriviaQA cases: **1/1 in the survivor's ground truth is genuinely correct** (the surviving case is a real question about Elon Musk, appropriately mapped to `read_wiki_page(elon-musk, person)`).

**Verifier fail-mode is closed:** on any API error the verifier returns `False` (drop the case). Rather have false negatives than false positives.

**One caveat:** we did not benchmark verifier precision against a hand-labeled gold set. The 36-drop / 2-keep ratio matches the expected pattern (broad-domain corpora are dominated by false positives for our short slug names), but a formal precision measurement would require hand-labeling ~50 candidates. Deferred.

---

## 8. Cost analysis + projections

Observed unit economics:

| Line item | Cost |
|---|---|
| Agent call (per model, per case) | ~$0.0079 |
| Verifier call (Haiku 4.5, one candidate) | ~$0.0002 |
| Sonnet 4.6 premium over Sonnet 4.5 | +24% cost, +19% latency |

**Projections for larger, well-curated runs:**

| Configuration | Cases (post-verifier) | Est. run cost |
|---|---|---|
| Single model, fixtures + synthesized only | 26 | ~$0.20 |
| Two-model comparison, fixtures + synthesized only | 26 × 2 | ~$0.41 |
| Two-model + full QA-corpus verified, ~100 cases | 100 × 2 | ~$1.60 (agent) + ~$0.10 (verifier warmup) |

Cache re-hits are $0. Verifier results could be cached too (they're pure `(entity_key, question) → bool` mappings) — not yet wired but a straightforward addition.

---

## 9. Known limitations rolled up

**Fixed since last report** ✓
- ~~`EntityIndex.match()` over-matches on broad corpora — QA-corpus loaders produce nonsensical ground truth.~~ → Resolved by `llm_verifier.py` two-stage filter.

**Still open** (code-review items, not blockers):
- `--no-cache` argparse flag declared but not wired.
- `Comparator.run_evaluation_phase` uses `subprocess.run(check=True)` — a single evaluator failure aborts the whole multi-model run.
- Verifier cache not implemented — every run re-verifies from scratch (~$0.01 per run, so low-priority).
- Per-category accuracy computed here but not surfaced in the auto-generated `report.md`.

**Design limitations (not defects)**:
- BFCL scores string parameters by case-insensitive **exact** match (documented paper limitation). Semantically-correct verbose descriptions fail. Fixture-level fix is possible; upstream fix requires touching the AST checker (would break alignment audit).
- The verifier is fail-closed — an API outage silently drops all candidates. For long-lived batch runs, could add retry-with-backoff and surface a metric.

---

## 10. Reproducibility

All numbers in Sections 3-7 come from a clean-slate rebuild on `main` (`benchmarks/runner/results/20260721T174555Z/`). Prior artifacts and caches were deleted before running.

Full reproduction:

```powershell
$env:PYTHONIOENCODING = "utf-8"

# clean slate
Remove-Item -Recurse -Force benchmarks/runner/results, benchmarks/runner/cache
Remove-Item benchmarks/alignment_report.json, benchmarks/BENCHMARK_RESULTS.md,
    benchmarks/bfcl-faithful/results.json,
    benchmarks/teval-faithful/results.json,
    benchmarks/cost-efficiency/report.json

# regenerate audit + fixture-based evaluators
python benchmarks/ALIGNMENT_AUDIT.py
python benchmarks/bfcl-faithful/evaluate.py --self-test
python benchmarks/teval-faithful/evaluate.py
python benchmarks/cost-efficiency/analyze_costs.py

# clean live run (both models, verified QA-corpus, fixtures + synthesized)
python -m benchmarks.runner --benchmark bfcl `
    --models claude-sonnet-4-5,claude-sonnet-4-6 `
    --datasets fixtures,synthesized,entity_questions,triviaqa `
    --n-samples 30 --seed 0 --max-cost 1.5
```

Run artifacts land under `benchmarks/runner/results/<UTC-timestamp>/`. `benchmarks/runner/{results,cache}/` are `.gitignore`'d.

---

## 11. Recommended next steps

Ordered by expected impact:

1. **Loosen the `flag_contradiction` fixture** to accept common paraphrases → Sonnet 4.5 → 26/27 = 96.3%, Sonnet 4.6 → 25/27 = 92.6%. One-line change; no code impact.
2. **Author 50-100 additional hand-curated BFCL cases** across categories, especially targeting the difference between "single-call" and "exploratory multi-call" behavior that Sonnet 4.6 exhibits — the only reliable way to distinguish 4.5 vs 4.6 statistically.
3. **Cache verifier decisions** (`(question, entity_key) → bool`) alongside the agent cache. Low-effort; makes verifier free on re-runs.
4. **Address code-review Important items:** wire `--no-cache`; guard the evaluator subprocess.
5. **Phase 2: T-Eval live generator.** Architecture reserves space (`agent.py` already captures full trajectory metadata); a trajectory-emitter mode + T-Eval-format adapter would light up the T-Eval side.
6. **Statistical robustness at n≥100:** either grow the fixture set (path 2) or explore recent benchmarks (BFCL v3, τ-bench, MetaTool) that ship n≥100 out of the box.

Phase 3 (ToolComp live judging) remains out of scope per the shipped spec.
