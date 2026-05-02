# Parameter Correctness Benchmark

**Adapted from:** Berkeley Function-Calling Leaderboard (BFCL)  
**Focus:** Tool parameter validation and consistency  
**Status:** ✅ Tier 1.2 Complete

## Overview

This benchmark validates that the ci-wiki agent generates tool parameters in the correct format and with valid values. It tests:

- **Path Format**: Pages are created in correct directory (e.g., `companies/`, `products/`)
- **Slug Format**: Page slugs follow kebab-case convention with no spaces
- **Frontmatter Fields**: Required YAML fields (title, type, confidence) are present
- **Valid Values**: Types and confidence levels are from allowed sets
- **Cross-References**: Wiki links use correct `[[type:slug]]` syntax
- **Consistency**: Path directory matches entity type, title relates to slug
- **Update Behavior**: Type and path don't change on update

## Test Cases (23 total)

### Critical Tests (60% weight)
These tests **must pass** for overall success:

| Test ID | Category | What it Tests |
|---------|----------|---------------|
| `path_format_company` | Path Format | Company pages in `companies/` |
| `path_format_product` | Path Format | Product pages in `products/` |
| `path_format_person` | Path Format | Person pages in `people/` |
| `path_format_trend` | Path Format | Trend pages in `trends/` |
| `path_slug_kebab_case` | Slug Format | Kebab-case conversion |
| `path_avoid_spaces` | Slug Format | No spaces in paths |
| `frontmatter_title_required` | Frontmatter | Title field present |
| `frontmatter_type_required` | Frontmatter | Type field with valid value |
| `frontmatter_confidence_required` | Frontmatter | Confidence field present |
| `frontmatter_no_invalid_types` | Validation | Type is one of: company, product, person, trend |
| `frontmatter_no_invalid_confidence` | Validation | Confidence is one of: high, medium, low |
| `content_not_empty` | Content Quality | Minimum 50 characters |
| `update_preserves_type` | Update Behavior | Type unchanged on update |
| `update_preserves_path` | Update Behavior | Path unchanged on update |
| `path_matches_type` | Consistency | Directory matches type |

### Non-Critical Tests (40% weight)

| Test ID | Category | What it Tests |
|---------|----------|---------------|
| `frontmatter_confidence_high` | Confidence | Correctly assigns "high" |
| `frontmatter_confidence_medium` | Confidence | Correctly assigns "medium" |
| `frontmatter_confidence_low` | Confidence | Correctly assigns "low" |
| `crossref_syntax_correct` | Content | `[[type:slug]]` syntax |
| `crossref_valid_types` | Content | Cross-ref types are valid |
| `markdown_formatting` | Content | Valid Markdown syntax |
| `no_hallucinated_fields` | Validation | No extra frontmatter fields |
| `title_matches_path_slug` | Consistency | Title related to slug |

## Running the Benchmark

### Single Page Evaluation

```python
from benchmarks.parameter_correctness import ParameterCorrectnessEvaluator

evaluator = ParameterCorrectnessEvaluator("test_cases.json")

page_data = {
    "path": "companies/openai",
    "frontmatter": {
        "title": "OpenAI",
        "type": "company",
        "confidence": "high",
    },
    "content": "OpenAI is an AI research company founded in 2015..."
}

result = evaluator.evaluate_page(page_data, "path_format_company")
print(f"Test: {result.test_name}")
print(f"Passed: {result.passed}")
print(f"Score: {result.score:.1f}%")
```

### Batch Evaluation (Leaderboard)

```python
pages = [
    {
        "test_id": "path_format_company",
        "path": "companies/openai",
        "frontmatter": {...},
        "content": "..."
    },
    {
        "test_id": "path_format_product",
        "path": "products/chatgpt",
        "frontmatter": {...},
        "content": "..."
    },
    # ... more pages
]

score = evaluator.evaluate_batch(pages)
print(f"Model: {score.model_name}")
print(f"Total Score: {score.total_score:.1f}%")
print(f"Tests Passed: {score.tests_passed}/{score.tests_total}")
print(f"Pass Rate: {score.pass_rate:.1f}%")
```

## Scoring System

| Component | Weight | Formula |
|-----------|--------|---------|
| Critical Score | 60% | Avg of critical test scores |
| Non-Critical Score | 40% | Avg of non-critical test scores |
| **Total Score** | 100% | (Critical × 0.6) + (Non-Critical × 0.4) |

**Passing Threshold:** 80%  
**Critical Requirement:** All critical tests must pass (100%)

### Score Interpretation

| Score | Interpretation |
|-------|-----------------|
| 95-100% | Excellent: Consistent parameter correctness |
| 85-95% | Good: Minor formatting or validation issues |
| 75-85% | Fair: Multiple parameter errors but mostly correct structure |
| <75% | Poor: Fundamental parameter generation issues |

## Test Categories

### 1. Path Format (4 tests)
Ensures pages are created in the correct directory based on entity type.

**Valid paths:**
- Companies: `companies/openai`, `companies/anthropic`
- Products: `products/chatgpt`, `products/claude`
- People: `people/sam-altman`, `people/dario-amodei`
- Trends: `trends/generative-ai-rise`, `trends/ai-safety`

### 2. Slug Format (2 tests)
Enforces kebab-case convention for page slugs.

**Valid:** `sam-altman`, `google-deepmind`, `generative-ai-rise`  
**Invalid:** `sam altman`, `Sam-Altman`, `SamAltman`

### 3. Frontmatter (3 tests)
Validates required YAML fields are present.

**Required fields:**
```yaml
title: "Page Title"
type: "company|product|person|trend"
confidence: "high|medium|low"
```

**Optional fields:**
```yaml
description: "Brief description"
created: "2026-05-01"
updated: "2026-05-02"
```

### 4. Validation (2 tests)
Rejects invalid values for enumerated fields.

**Type values:** `company`, `product`, `person`, `trend`  
**Confidence values:** `high`, `medium`, `low`

### 5. Content Format (3 tests)
Validates Markdown syntax and cross-reference format.

**Valid cross-references:**
```markdown
This mentions [[company:openai]] and [[product:claude]].
```

**Invalid:**
```markdown
This mentions [OpenAI](openai) or [[OpenAI]] or [[COMPANY:OpenAI]].
```

### 6. Content Quality (1 test)
Ensures pages have meaningful content.

**Requirement:** Minimum 50 characters of content

### 7. Update Behavior (2 tests)
Validates that updates don't change immutable fields.

**Immutable:** `path`, `type`  
**Mutable:** `title`, `content`, `confidence`, `frontmatter` fields

### 8. Consistency (2 tests)
Validates consistency between different fields.

**Rules:**
- Type → Directory mapping (e.g., type=company → companies/)
- Title should relate to slug (e.g., "OpenAI" for slug openai)

## Integration with CI/CD

Add to GitHub Actions workflow:

```yaml
- name: Run Parameter Correctness Benchmark
  run: |
    cd benchmarks/parameter-correctness
    python leaderboard.py
    # Parse output and fail if score < 80%
```

## Example Output

```
Parameter Correctness Evaluator loaded successfully
Total test cases: 23

Model: ci-wiki-agent
Total Score: 92.3%
Critical Score: 100.0%
Non-Critical Score: 85.0%
Tests Passed: 22/23
Pass Rate: 95.7%

Failed Tests:
  - title_matches_path_slug: "OpenAI" may not relate to slug "openai"
```

## Future Enhancements

- [ ] Add regex validation for content (no obvious hallucinations)
- [ ] Check for stale content detection capability
- [ ] Validate cross-reference targets exist in wiki
- [ ] Test cross-reference uniqueness (no duplicates)
- [ ] Measure confidence score calibration accuracy

## References

- **Berkeley Function-Calling Leaderboard**: https://labs.scale.com/leaderboard/tool_use_enterprise
- **Anthropic Tool Calling Guide**: https://www.anthropic.com/engineering/writing-tools-for-agents
- **ci-wiki Schema**: `../../schema/wiki_schema.md`
