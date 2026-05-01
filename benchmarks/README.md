# Benchmarking Suite for ci-wiki

This directory contains benchmarking tools and evaluation frameworks for the ci-wiki agentic system, adapted from recent research papers on agentic systems (2024-2026).

## Overview

The benchmarking suite evaluates the ci-wiki agent across multiple dimensions:
- **Tool Composition**: Can the agent correctly compose multiple tool calls?
- **Parameter Correctness**: Are tool parameters in the correct format?
- **Cost Efficiency**: What is the token cost per unit of work?
- **Reasoning Quality**: How well does the agent reason about tool choices?
- **Confidence Calibration**: Do confidence scores match actual accuracy?

## Directory Structure

```
benchmarks/
├── _common/
│   ├── metrics.py          # Common evaluation metrics
│   └── __init__.py
├── toolcomp-eval/          # Tier 1.1: Tool Composition Evaluation
│   ├── test_prompts.json   # 12+ ToolComp-style test cases
│   ├── evaluate.py         # Evaluation engine
│   └── README.md
├── parameter-correctness/  # Tier 1.2: Parameter Correctness Benchmark
│   ├── test_cases.json     # BFCL-style test cases
│   ├── leaderboard.py      # Scoring harness
│   └── README.md
├── cost-efficiency/        # Tier 1.3: Cost Analysis
│   ├── analyze_costs.py    # Token cost analyzer
│   ├── reports/
│   └── README.md
└── README.md               # This file
```

## Quick Start

### 1. Tool Composition Benchmark (Tier 1.1)

**What it tests**: Whether the agent correctly identifies and calls the appropriate tools in sequence.

```bash
cd benchmarks/toolcomp-eval
python evaluate.py
```

**Key metrics**:
- Invocation Accuracy: % of correct tool calls
- Parameter Correctness: % of correct tool parameters
- Abstention Accuracy: % of correct abstention decisions
- Sequence Quality: % of optimal tool calling sequences

**Test cases**: 12 test cases covering:
- Single-tool invocations
- Multi-step tool compositions
- Abstention scenarios
- Edge cases and error handling

### 2. Parameter Correctness Benchmark (Tier 1.2)

**What it tests**: Whether generated tool parameters follow the correct format and constraints.

```bash
cd benchmarks/parameter-correctness
python leaderboard.py
```

**Key metrics**:
- Page path format correctness (e.g., `companies/openai`)
- YAML frontmatter field presence and validity
- Cross-reference syntax correctness (`[[type:slug]]`)
- Confidence score level validation (high/medium/low)

**Test approach**: Leaderboard-style automated scoring against golden answers.

### 3. Cost Efficiency Benchmark (Tier 1.3)

**What it tests**: Token usage and cost per operation across different scenarios.

```bash
cd benchmarks/cost-efficiency
python analyze_costs.py
```

**Key metrics**:
- Total tokens used
- Estimated cost in USD
- Tokens per page created/updated
- Tokens per query
- Error rate and efficiency

**Data source**: Parses existing `wiki/log.md` for operational data.

## Benchmark Details

### Paper References

1. **ToolComp** - Benchmarking Tool Composition in Agent Systems
   - Focus: Evaluating agent ability to compose dependent tool calls
   - Relevance: Direct application to ci-wiki's read/search/write tools

2. **Berkeley Function-Calling Leaderboard (BFCL)**
   - Focus: Standardized function calling evaluation
   - Relevance: Validates parameter correctness

3. **T-Eval** - Reasoning Metric for Tool Call Trajectories
   - Focus: Quality of agent decision-making
   - Implementation: See reasoning-quality/ (future work)

4. **AutoResearchBench** - Complex Literature Discovery
   - Focus: Entity extraction and fact synthesis
   - Implementation: See literature-discovery/ (future work)

5. **Beyond Accuracy** - Multi-Dimensional Framework (2026)
   - Focus: Cost-efficiency, safety, multi-dimensional success
   - Implementation: Cost-efficiency/ addresses cost dimension

## Running All Benchmarks

```bash
# Run all Tier 1 benchmarks
make benchmark

# Or manually:
cd toolcomp-eval && python evaluate.py
cd ../parameter-correctness && python leaderboard.py
cd ../cost-efficiency && python analyze_costs.py
```

## Interpreting Results

### Tool Composition Scores

| Score | Interpretation |
|-------|-----------------|
| 90-100% | Excellent: Agent reliably composes correct tool sequences |
| 80-90% | Good: Minor issues with parameter or sequencing |
| 70-80% | Fair: Some tool call or sequencing errors |
| <70% | Poor: Significant issues with tool composition |

### Parameter Correctness Scores

| Score | Interpretation |
|-------|-----------------|
| 95-100% | Excellent: Parameters consistently correct |
| 85-95% | Good: Minor parameter format issues |
| 75-85% | Fair: Multiple parameter errors |
| <75% | Poor: Fundamental parameter misunderstanding |

### Cost Efficiency Baselines

(Based on initial ci-wiki runs):
- Cost per ingest: ~50-100K tokens
- Cost per query: ~20-30K tokens
- Cost per page: ~5-10K tokens
- Estimated monthly cost: <$5 (based on current usage)

## Future Benchmarks (Tier 2 & 3)

### Tier 2 (Medium Effort)
- **Reasoning Quality**: Measure agent decision-making logic
- **Confidence Calibration**: Verify confidence scores match accuracy
- **Literature Discovery**: Entity extraction and synthesis quality

### Tier 3 (Long-term)
- **Wiki vs. RAG Comparison**: Empirical validation of architecture choice
- **Hallucination Detection**: Measure and reduce LLM hallucinations
- **Domain Accuracy**: Competitive intelligence fact accuracy

## Contributing New Benchmarks

To add a new benchmark:

1. Create a new directory: `benchmarks/my-new-benchmark/`
2. Add test data: `my-new-benchmark/test_data.json`
3. Add evaluation logic: `my-new-benchmark/evaluate.py`
4. Update this README with:
   - Description of what the benchmark tests
   - How to run it
   - Key metrics
   - Interpretation guide

## Integration with CI/CD

Benchmarks can be integrated into GitHub Actions for continuous monitoring:

```yaml
- name: Run Benchmarks
  run: |
    cd benchmarks
    python toolcomp-eval/evaluate.py
    python cost-efficiency/analyze_costs.py
```

## Questions?

See the main [README.md](../README.md) for more information about the ci-wiki system.

## References

- [Agentic Frameworks for Reasoning Tasks](https://arxiv.org/html/2604.16646v1)
- [AutoResearchBench](https://arxiv.org/html/2604.25256v1)
- [Beyond Accuracy Framework](https://arxiv.org/html/2511.14136v1)
- [Berkeley Function-Calling Leaderboard](https://labs.scale.com/leaderboard/tool_use_enterprise)
- [Evaluation and Benchmarking of LLM Agents Survey](https://arxiv.org/html/2507.21504v1)
