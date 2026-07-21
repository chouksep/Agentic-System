# ci-wiki Benchmarks

This directory contains two generations of benchmarks. **Only the `*-faithful/`
ports actually implement the methodologies of their cited papers.** The earlier
directories (`parameter-correctness/`, `toolcomp-eval/`, `priority-2-3-evaluator/`)
were named after research papers but implemented wiki-schema linting instead.
They are kept for historical reference and clearly relabelled below.

## Faithful ports (use these)

| Directory | Paper | Upstream | Alignment |
|-----------|-------|----------|-----------|
| `bfcl-faithful/` | Patil et al., **BFCL**, ICML 2025 | [ShishirPatil/gorilla](https://github.com/ShishirPatil/gorilla) | 9/9 algorithmic checks pass; no model download needed |
| `teval-faithful/` | Chen et al., **T-Eval**, ACL 2024 ([2312.14033](https://arxiv.org/abs/2312.14033)) | [open-compass/T-Eval](https://github.com/open-compass/T-Eval) | 6/6 algorithmic checks pass; BERT-score evaluator runs only with `huggingface.co` access |
| `toolcomp-faithful/` | Nath et al., **ToolComp**, [2501.01290](https://arxiv.org/abs/2501.01290) | [vaskar-open-source-research/toolcomp](https://github.com/vaskar-open-source-research/toolcomp) | 10/10 algorithmic checks pass; pluggable LLM judge |

Run the alignment audit:

```bash
python benchmarks/ALIGNMENT_AUDIT.py
```

### BFCL

Faithful port of `ast_checker.py` (`simple_function_checker`,
`multiple_function_checker`, `parallel_function_checker_no_order`,
`type_checker`, `string_checker`, `dict_checker`, `list_checker`,
`list_dict_checker`, `standardize_string`). Test cases are written against the
five real ci-wiki tools (`read_wiki_page`, `write_wiki_page`, `search_wiki`,
`list_wiki_pages`, `flag_contradiction`) in BFCL's
`{function_description, possible_answer, category}` schema.

```bash
cd benchmarks/bfcl-faithful
python test_checker.py          # unit-tests the AST checker
python evaluate.py --self-test  # runs the canonical golden answers
```

### T-Eval

Faithful port of the four upstream evaluator classes:

- `InstructEvaluator` — `format_metric` + `args_em_metric`
  (= `(action_match + matched_arg_count) / (gt_arg_count + 1)`).
- `PlanningEvaluator` — BERT-score matching with the upstream defaults
  (`name_weight=0.75`, `args_weight=0.25`, `match_threshold=0.8`) on
  `all-mpnet-base-v2`, then `networkx.max_weight_matching` (Hungarian), then
  Longest-Increasing-Subsequence to count correctly-ordered nodes. Also
  supports the `permutation` strategy which needs no model.
- `ReasonRetrieveUnderstandEvaluator` — thought (cosine BERT-score), name
  (exact match), args (per-key exact-match ratio over `len(gt) + 1e-5`).
- `ReviewEvaluator` — `review_quality = 1 if pred == gt else 0`, plus
  `parse_rate`.

```bash
cd benchmarks/teval-faithful
python evaluate.py                  # full (requires huggingface.co)
python evaluate.py --skip-bertscore # permutation + instruct + review only
```

### ToolComp

Faithful port of `_extract_label`, `_score_pair`, and the upstream metrics
aggregation (`total_accuracy`, `action_plan_only_accuracy`,
`react_steps_accuracy`). The LLM judge is pluggable: pass any
`callable(prompt: str) -> str` to `evaluate_pair`.

```bash
cd benchmarks/toolcomp-faithful
python test_evaluator.py            # verifies extract / score / aggregate
```

## Live agent benchmarking (NEW)

`benchmarks/runner/` runs the ci_wiki agent end-to-end against the BFCL
evaluator, with multi-model comparison and a hard cost ceiling. The agent's
tool dispatcher is record-only during BFCL eval — no real wiki I/O occurs.

```bash
# Smoke test against the 12 committed fixtures (no HF download)
python -m benchmarks.runner \
    --benchmark bfcl \
    --models claude-sonnet-4-5 \
    --datasets fixtures \
    --n-samples 12 \
    --max-cost 0.50

# Full mid-scale run with QA-corpus expansion
python -m benchmarks.runner \
    --benchmark bfcl \
    --models claude-sonnet-4-5,claude-sonnet-4-6 \
    --datasets fixtures,entity_questions,triviaqa \
    --n-samples 250 \
    --seed 0 \
    --max-cost 15.0
```

Output:
- `benchmarks/runner/results/<run_id>/report.md` — per-model accuracy + diff table
- `benchmarks/runner/results/<run_id>/summary.json` — full structured output
- `benchmarks/runner/results/<run_id>/predictions/<model>.json` — raw BFCL predictions
- `benchmarks/runner/cache/` — per-`(model, case)` cache; re-runs with the same
  flags pay only for cache misses.

Design doc: `docs/superpowers/specs/2026-05-22-live-llm-benchmark-generator-design.md`.

## Deprecated benchmarks (do NOT use as if they implemented the named paper)

These were earlier work that borrowed names from research papers but actually
tested wiki-page schema compliance. They still pass their own internal checks
but they do **not** reproduce the methodology of the cited papers.

| Directory | What it actually tests | Reason it does *not* match its named paper |
|-----------|-----------------------|--------------------------------------------|
| `parameter-correctness/` | Wiki YAML frontmatter fields | BFCL tests function-call parameter correctness, not document schemas |
| `toolcomp-eval/` | 12 wiki-write/read prompts | ToolComp uses 485 prompts with LLM-as-judge and pairwise process supervision |
| `priority-2-3-evaluator/` | Confidence comments & duplicate cross-refs | Not from any cited paper — it's a wiki-quality linter |
| `cost-efficiency/` | Token counting from `wiki/log.md` | Inspired by *Beyond Accuracy* but only implements 1 of 6 dimensions |

## Alignment summary

```
BFCL          9/9   (100% of algorithmic checks)
T-Eval        6/6   (100% of algorithmic checks)
ToolComp     10/10  (100% of algorithmic checks)
Environment:  1/3   (2 dependencies unavailable here; declared, not faked)

OVERALL:     26/28  (93%) — see ALIGNMENT_AUDIT.py for the per-check breakdown.
```

Limitations are declared in the audit, not silently faked:

- **T-Eval BERT-score**: requires `huggingface.co` to download
  `all-mpnet-base-v2`. The upstream-supported `permutation` strategy runs
  offline and is provided as an alternative.
- **ToolComp LLM judge**: requires an API key for an actual model. The pipeline
  accepts any `callable(str) -> str` so a real judge can be plugged in without
  code changes.
