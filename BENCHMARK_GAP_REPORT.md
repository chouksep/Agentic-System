# Benchmark Tier 1 Gap Analysis Report

**Date**: 2026-05-02  
**Status**: Critical gaps identified  
**Severity**: HIGH — Benchmarks don't match actual wiki schema  

## Executive Summary

Running Tier 1 benchmarks against real wiki data revealed **critical gaps** between:
1. What the benchmarks expect (schema-wise)
2. What the actual wiki pages contain
3. What the schema document specifies

**All 15 wiki pages fail parameter correctness tests** due to schema mismatches.

---

## Gap 1: Field Names Mismatch

### ❌ Problem
The benchmarks expect `title` field in frontmatter, but wiki pages use `name`.

**Benchmark expects:**
```yaml
frontmatter:
  title: "OpenAI"
  type: "company"
  confidence: "high"
```

**Actual wiki uses:**
```yaml
name: OpenAI
type: company
founded: 2015
hq: "San Francisco, California, U.S."
funding_stage: growth
funding_total: "$13B+ (Microsoft investment); $6.6B share sale (Oct 2025)"
employees: 4500
last_updated: 2025-01-31
sources: []
```

### Impact
- ❌ All 15 wiki pages fail `frontmatter_title_required` test
- ❌ Parameter correctness benchmark score: **0%** (should be ~95%+)

### Source
- **Benchmark definition**: `benchmarks/parameter-correctness/test_cases.json` (line 56)
- **Actual schema**: `schema/wiki_schema.md` (line 28-36) specifies `name` field

### Fix Required
Update all test cases to check for `name` instead of `title`.

---

## Gap 2: Confidence Not in Frontmatter

### ❌ Problem
Benchmarks expect `confidence` field in YAML frontmatter, but schema specifies it goes in HTML comments within sections.

**Benchmark expects:**
```yaml
frontmatter:
  confidence: "high"
```

**Actual schema specifies:**
```markdown
## Pricing
<!-- confidence: high | source_count: 3 -->
```

### Impact
- ❌ All 15 wiki pages fail `frontmatter_confidence_required` test  
- ❌ Cannot measure confidence calibration without parsing section comments
- ❌ Cost efficiency benchmark can't validate confidence metadata

### Source
- **Benchmark definition**: `benchmarks/parameter-correctness/test_cases.json` (lines 70, 102, etc.)
- **Actual schema**: `schema/wiki_schema.md` (section 5, line 202)

### Fix Required
1. Redesign confidence validation to parse inline HTML comments
2. Create separate benchmark for confidence calibration (currently in Tier 2 list)

---

## Gap 3: Entity-Specific Frontmatter Fields Missing

### ❌ Problem
Different entity types require different frontmatter fields per schema, but benchmarks don't validate these.

**Schema specifies:**

| Entity Type | Required Fields | Current Benchmark | Gap |
|---|---|---|---|
| Company | `name`, `type`, `founded`, `hq`, `funding_stage`, `funding_total`, `employees`, `last_updated` | Only checks `type` | Missing 7 fields |
| Product | `name`, `type`, `company`, `category`, `pricing_model`, `last_updated` | Only checks `type` | Missing 5 fields |
| Person | `name`, `type`, `role`, `company`, `last_updated` | Only checks `type` | Missing 4 fields |
| Trend | `name`, `type`, `category`, `maturity`, `last_updated` | Only checks `type` | Missing 4 fields |

### Impact
- ❌ Benchmarks don't validate entity-specific required fields
- ❌ Can't detect if required fields like `founding_year`, `role`, `category` are missing
- ❌ No validation of `last_updated` date format
- ❌ Can't validate enumerated values (e.g., `funding_stage` must be one of: seed|series-a|series-b|series-c|growth|public|acquired|unknown)

### Source
- **Actual schema**: `schema/wiki_schema.md` (lines 23-67 for company template)
- **Benchmarks**: Only generic tests, no entity-specific validation

### Fix Required
1. Create entity-specific test cases for each type
2. Validate required fields per entity type
3. Validate enumerated field values

---

## Gap 4: Confidence Levels In Test Cases Mismatch

### ❌ Problem  
Test case for `frontmatter_confidence_high` (and medium/low) expect to find a `confidence` field, which doesn't exist in actual wiki pages.

**Test ID**: `frontmatter_confidence_high`, `frontmatter_confidence_medium`, `frontmatter_confidence_low`

### Impact
- ❌ 3 test cases will always fail on real wiki data
- ❌ Can't measure whether agent assigns appropriate confidence levels
- ❌ Confidence calibration benchmark (Tier 2) needs redesign

### Source
- **Benchmarks**: `parameter-correctness/test_cases.json` (lines 68-90)

### Fix Required
Parse inline `<!-- confidence: X | source_count: N -->` comments instead of frontmatter field.

---

## Gap 5: Cross-Reference Validation Incomplete

### ⚠️ Problem
Benchmarks check for cross-reference syntax `[[type:slug]]` but don't validate:
1. Target page exists
2. Slug is correctly formatted
3. No broken references

**Test ID**: `crossref_syntax_correct`, `crossref_valid_types`

### Current Validation
- ✅ Syntax `[[type:slug]]` present
- ✅ Type is one of: company, product, person, trend

### Missing Validation
- ❌ Target slug exists in wiki
- ❌ Slug is in kebab-case
- ❌ Referenced entity actually exists
- ❌ No circular references
- ❌ Uniqueness (no duplicate references to same page)

### Impact
- ⚠️ Could have broken references without detection
- ⚠️ Search index doesn't warn about dead links
- ⚠️ Query results may reference non-existent pages

### Fix Required
Add reference resolution checks (low priority - informational only).

---

## Gap 6: Slug Validation Doesn't Check Directory-Type Consistency

### ⚠️ Problem
Test `path_matches_type` checks that directory matches type, but actual implementation only validates via `path_slug_kebab_case`.

**Test case**: `path_matches_type` (test ID) — says it validates but the implementation is incomplete.

### Current Validation
- ✅ Path is in format `type/slug`
- ✅ Slug is kebab-case

### Missing Validation
- ❌ Directory name matches type (companies→company, products→product, etc.)
- ❌ Enforced in evaluator code

### Fix Required
Complete implementation of directory-type consistency check.

---

## Gap 7: No Validation of last_updated Field Format

### ⚠️ Problem
Schema specifies `last_updated: YYYY-MM-DD` but benchmarks don't validate date format.

**Impact**:
- ⚠️ Could have invalid dates (e.g., "2025-13-45")
- ⚠️ Staleness detection (lint) may fail
- ⚠️ Can't sort pages by recency

### Fix Required
Add date format validation to frontmatter checks.

---

## Gap 8: Sources List Not Validated

### ⚠️ Problem
Schema specifies `sources: []` list in frontmatter for tracking source URIs, but benchmarks don't validate:
- List format (must be YAML array)
- Valid URIs
- No duplicates

### Fix Required
Add sources validation test (low priority).

---

## Test Results Summary

| Benchmark | Status | Issues Found |
|---|---|---|
| **Parameter Correctness** | ❌ FAIL | 15/15 pages fail due to field name mismatch |
| **ToolComp** | ⚠️ UNTESTED | Test prompts use wrong field names (`title` vs `name`) |
| **Cost Efficiency** | ✅ PASS | Works correctly, parses existing logs |

---

## Tier 1 Test Results (Actual)

```
Parameter Correctness Benchmark Results
======================================================================

⚠️ companies/anthropic:              0/2 (0%)
   ❌ Missing title (should be checking 'name')
   ❌ Invalid confidence (not in frontmatter)

⚠️ companies/google-deepmind:        0/2 (0%)
⚠️ companies/openai:                 0/2 (0%)
⚠️ people/dario-amodei:              0/2 (0%)
⚠️ people/daniela-amodei:            0/2 (0%)
⚠️ people/demis-hassabis:            0/2 (0%)
⚠️ people/elon-musk:                 0/2 (0%)
⚠️ people/greg-brockman:             0/2 (0%)
⚠️ people/ilya-sutskever:            0/2 (0%)
⚠️ people/sam-altman:                0/2 (0%)
⚠️ people/mustafa-suleyman:          0/2 (0%)
⚠️ products/chatgpt:                 0/2 (0%)
⚠️ products/claude:                  0/2 (0%)
⚠️ products/gemini:                  0/2 (0%)
⚠️ trends/generative-ai-rise:        0/2 (0%)

======================================================================
OVERALL: 0/30 tests passed (0%)
```

---

## Root Cause Analysis

The benchmarks were designed based on **idealized schema** (from `schema/wiki_schema.md`) rather than **actual wiki page structure**.

**Timeline of mismatch:**
1. `schema/wiki_schema.md` created with specification (title, type, confidence in frontmatter)
2. Benchmarks built to test against that spec
3. Actual wiki pages created with different field names (`name` vs `title`)
4. Confidence stored differently (comments vs frontmatter)
5. Benchmarks never validated against real data ← **Gap found**

---

## Recommendations & Fix Plan

### Priority 1: Critical (Required for Tier 1 validity)

**1.1: Fix Parameter Correctness Test Cases**
- [ ] Change `title` → `name` in all test cases
- [ ] Remove frontmatter `confidence` checks
- [ ] Add inline comment confidence parsing
- **Impact**: Fix 0% → ~95% pass rate
- **Effort**: 2-3 hours

**1.2: Fix ToolComp Test Prompts**
- [ ] Update expected_tool_calls to use `name` field
- [ ] Remove confidence from frontmatter examples
- **Impact**: Ensures evaluator works correctly
- **Effort**: 1-2 hours

**1.3: Add Entity-Specific Field Validation**
- [ ] Create company-specific test cases (validate founded, hq, etc.)
- [ ] Create product-specific test cases (validate company, category, etc.)
- [ ] Create person-specific test cases (validate role, company, etc.)
- [ ] Create trend-specific test cases (validate category, maturity, etc.)
- **Impact**: Detect missing required fields
- **Effort**: 3-4 hours

### Priority 2: High (Improves benchmark quality)

**2.1: Implement Confidence Comment Parser**
- [ ] Extract `<!-- confidence: X -->` from section comments
- [ ] Create separate confidence calibration test
- [ ] Validate high/medium/low levels
- **Impact**: Enable confidence measurement
- **Effort**: 2-3 hours

**2.2: Add Field Value Validation**
- [ ] Validate `funding_stage` enum (seed|series-a|...|unknown)
- [ ] Validate `pricing_model` enum
- [ ] Validate `category` enum
- [ ] Validate `maturity` enum
- **Impact**: Catch invalid enumeration values
- **Effort**: 1-2 hours

**2.3: Add Date Format Validation**
- [ ] Validate `last_updated` is YYYY-MM-DD format
- [ ] Check dates are not in future
- **Impact**: Ensure staleness detection works
- **Effort**: 1 hour

### Priority 3: Medium (Optional improvements)

**3.1: Add Reference Resolution**
- [ ] Check cross-referenced pages exist
- [ ] Validate slug format in references
- [ ] Detect broken links
- **Impact**: Better link integrity
- **Effort**: 2-3 hours

**3.2: Add Sources Validation**
- [ ] Validate sources field is proper YAML array
- [ ] Check for valid URIs
- [ ] Detect duplicates
- **Impact**: Better source tracking
- **Effort**: 1-2 hours

---

## Updated Timeline

**Phase 1: Critical Fixes (Priority 1)**
- **Duration**: 6-9 hours
- **Deliverable**: Fixed Tier 1 benchmarks that pass real data
- **Target**: All 15 wiki pages pass parameter correctness tests

**Phase 2: Quality Improvements (Priority 2)**
- **Duration**: 4-6 hours
- **Deliverable**: Enhanced validation for all fields
- **Target**: Confidence measurement, enum validation, date validation

**Phase 3: Integration (Priority 3)**
- **Duration**: 3-5 hours
- **Deliverable**: Reference resolution, sources validation
- **Target**: Complete link integrity checking

---

## Impact on Other Tiers

### Tier 2 Benchmarks (Affected)
- **Confidence Calibration**: Currently planned to measure `frontmatter.confidence` — **needs redesign** to parse comments
- **Literature Discovery**: Validates entity extraction — **mostly unaffected**
- **Reasoning Quality**: Validates tool sequencing — **mostly unaffected**

### Tier 3 Benchmarks (Affected)
- **Wiki vs RAG Comparison**: Uses benchmark data — **will work once fixed**
- **Hallucination Detection**: Measures fact accuracy — **mostly unaffected**
- **Domain Accuracy**: Fact correctness — **mostly unaffected**

---

## Conclusion

Tier 1 benchmarks are **functionally correct** but **not calibrated** to the actual wiki schema. This is a **gap in validation**, not a bug in the evaluation logic.

**Status**: ⚠️ Tier 1 currently shows 0% pass rate due to schema mismatch, not system problems.

**Next Action**: Execute Priority 1 fixes to calibrate benchmarks to real data. Estimated 6-9 hours of work required.

---

## Files to Modify

```
benchmarks/
├── parameter-correctness/
│   ├── test_cases.json          ← Fix field names, add entity-specific tests
│   └── leaderboard.py           ← Add confidence comment parser
├── toolcomp-eval/
│   ├── test_prompts.json        ← Fix field names in expected_tool_calls
│   └── evaluate.py              ← May need minor tweaks
└── _common/
    └── metrics.py               ← Add confidence parser utility
```

**Estimated effort**: 6-9 hours for complete Priority 1 fix.
