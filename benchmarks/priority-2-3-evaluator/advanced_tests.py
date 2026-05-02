"""Advanced evaluator for Priority 2 and 3 tests."""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Set
from pathlib import Path

from ..._common.parsers import (
    ConfidenceCommentParser,
    ConfidenceComment,
    SourceListParser,
    CrossReferenceParser,
)


@dataclass
class AdvancedTestResult:
    """Result of an advanced test."""
    test_id: str
    test_name: str
    passed: bool
    priority: str  # priority_2 or priority_3
    score: float
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class Priority2Evaluator:
    """Evaluate Priority 2 tests: Confidence comments and sources validation."""

    def evaluate_confidence_comments(self, page_data: Dict[str, Any]) -> AdvancedTestResult:
        """Evaluate confidence comment syntax and presence."""
        errors = []
        warnings = []

        content = page_data.get("content", "")
        frontmatter = page_data.get("frontmatter", {})
        entity_type = frontmatter.get("type", "")

        # Extract and validate confidence comments
        comments = ConfidenceCommentParser.extract_confidence_comments(content)

        if not comments:
            warnings.append("No confidence comments found in page")

        valid, comment_errors = ConfidenceCommentParser.validate_confidence_comments(comments)
        errors.extend(comment_errors)

        return AdvancedTestResult(
            test_id="confidence_comment_syntax",
            test_name="Confidence Comment Syntax",
            passed=len(errors) == 0,
            priority="priority_2",
            score=100.0 if len(errors) == 0 else max(0, 100 - len(errors) * 20),
            errors=errors,
            warnings=warnings,
        )

    def evaluate_section_confidence(self, page_data: Dict[str, Any]) -> AdvancedTestResult:
        """Evaluate that critical sections have confidence comments."""
        errors = []
        warnings = []

        content = page_data.get("content", "")
        frontmatter = page_data.get("frontmatter", {})
        entity_type = frontmatter.get("type", "")

        # Check required sections have confidence
        valid, section_errors = ConfidenceCommentParser.validate_section_confidence(
            entity_type, content
        )
        errors.extend(section_errors)

        if not errors:
            # Warn if other sections also have confidence (good practice)
            all_comments = ConfidenceCommentParser.extract_confidence_comments(content)
            if len(all_comments) > 2:
                warnings.append(f"Found {len(all_comments)} confidence comments (expected 1-2)")

        return AdvancedTestResult(
            test_id="confidence_section_presence",
            test_name="Section Confidence Presence",
            passed=len(errors) == 0,
            priority="priority_2",
            score=100.0 if len(errors) == 0 else max(0, 100 - len(errors) * 25),
            errors=errors,
            warnings=warnings,
        )

    def evaluate_sources_validation(self, page_data: Dict[str, Any]) -> AdvancedTestResult:
        """Evaluate sources list validity."""
        errors = []
        warnings = []

        frontmatter = page_data.get("frontmatter", {})
        sources_str = frontmatter.get("sources", "")

        # Extract sources
        sources = SourceListParser.extract_sources(sources_str)

        if not sources:
            warnings.append("No sources found (sources list is empty)")

        # Validate sources
        valid, source_errors = SourceListParser.validate_sources(sources)
        errors.extend(source_errors)

        return AdvancedTestResult(
            test_id="sources_validation",
            test_name="Sources Validation",
            passed=len(errors) == 0,
            priority="priority_2",
            score=100.0 if len(errors) == 0 else max(0, 100 - len(errors) * 15),
            errors=errors,
            warnings=warnings,
        )

    def evaluate_all_priority_2(self, page_data: Dict[str, Any]) -> List[AdvancedTestResult]:
        """Run all Priority 2 tests."""
        return [
            self.evaluate_confidence_comments(page_data),
            self.evaluate_section_confidence(page_data),
            self.evaluate_sources_validation(page_data),
        ]


class Priority3Evaluator:
    """Evaluate Priority 3 tests: Cross-references and advanced consistency."""

    def __init__(self, wiki_pages: Dict[str, Dict[str, Any]]):
        """Initialize with wiki pages for reference resolution."""
        self.wiki_pages = wiki_pages  # Dict of path -> page_data

    def evaluate_crossref_syntax(self, page_data: Dict[str, Any]) -> AdvancedTestResult:
        """Evaluate cross-reference syntax."""
        errors = []

        content = page_data.get("content", "")
        references = CrossReferenceParser.extract_references(content)

        # Check syntax validity
        valid, syntax_errors = CrossReferenceParser.validate_reference_syntax(references)
        errors.extend(syntax_errors)

        return AdvancedTestResult(
            test_id="crossref_syntax",
            test_name="Cross-Reference Syntax",
            passed=len(errors) == 0,
            priority="priority_3",
            score=100.0 if len(errors) == 0 else max(0, 100 - len(errors) * 20),
            errors=errors,
        )

    def evaluate_crossref_deduplication(self, page_data: Dict[str, Any]) -> AdvancedTestResult:
        """Detect duplicate cross-references."""
        errors = []

        content = page_data.get("content", "")
        references = CrossReferenceParser.extract_references(content)

        duplicates = CrossReferenceParser.detect_duplicates(references)
        errors.extend(duplicates)

        return AdvancedTestResult(
            test_id="crossref_deduplication",
            test_name="Cross-Reference Deduplication",
            passed=len(errors) == 0,
            priority="priority_3",
            score=100.0 if len(errors) == 0 else max(0, 100 - len(errors) * 10),
            errors=errors,
        )

    def evaluate_crossref_resolution(self, page_data: Dict[str, Any]) -> AdvancedTestResult:
        """Resolve cross-references and check they exist."""
        errors = []
        warnings = []

        content = page_data.get("content", "")
        references = CrossReferenceParser.extract_references(content)

        # Check if referenced pages exist
        for ref in references:
            if not ref.is_valid:
                continue  # Already caught in syntax check

            # Construct expected path
            type_dir_map = {
                "company": "companies",
                "product": "products",
                "person": "people",
                "trend": "trends",
            }
            type_dir = type_dir_map.get(ref.ref_type)
            expected_path = f"{type_dir}/{ref.ref_slug}"

            if expected_path not in self.wiki_pages:
                errors.append(
                    f"Referenced page does not exist: [[{ref.ref_type}:{ref.ref_slug}]] "
                    f"(would be at {expected_path})"
                )
            else:
                warnings.append(f"✓ {expected_path} exists")

        return AdvancedTestResult(
            test_id="crossref_resolution",
            test_name="Cross-Reference Resolution",
            passed=len(errors) == 0,
            priority="priority_3",
            score=100.0 if len(errors) == 0 else max(0, 100 - len(errors) * 15),
            errors=errors,
            warnings=warnings,
        )

    def evaluate_consistency_company_reference(
        self, page_data: Dict[str, Any]
    ) -> AdvancedTestResult:
        """Check product company field matches referenced company."""
        errors = []

        frontmatter = page_data.get("frontmatter", {})
        content = page_data.get("content", "")
        entity_type = frontmatter.get("type", "")

        if entity_type != "product":
            return AdvancedTestResult(
                test_id="consistency_company_reference",
                test_name="Company Reference Consistency",
                passed=True,
                priority="priority_3",
                score=100.0,
                errors=[],
            )

        # Get company from frontmatter
        company_slug = frontmatter.get("company", "")
        if not company_slug:
            errors.append("Product missing company field")
            return AdvancedTestResult(
                test_id="consistency_company_reference",
                test_name="Company Reference Consistency",
                passed=False,
                priority="priority_3",
                score=0.0,
                errors=errors,
            )

        # Find company references in content
        references = CrossReferenceParser.extract_references(content)
        company_refs = [r for r in references if r.ref_type == "company"]

        if not company_refs:
            errors.append(
                f"Product company field is '{company_slug}' but no company reference in content"
            )
        else:
            for ref in company_refs:
                if ref.ref_slug != company_slug:
                    errors.append(
                        f"Company reference [[{ref.ref_type}:{ref.ref_slug}]] "
                        f"doesn't match company field '{company_slug}'"
                    )

        return AdvancedTestResult(
            test_id="consistency_company_reference",
            test_name="Company Reference Consistency",
            passed=len(errors) == 0,
            priority="priority_3",
            score=100.0 if len(errors) == 0 else 0.0,
            errors=errors,
        )

    def evaluate_consistency_section_order(self, page_data: Dict[str, Any]) -> AdvancedTestResult:
        """Check sections appear in recommended order."""
        errors = []
        warnings = []

        content = page_data.get("content", "")
        frontmatter = page_data.get("frontmatter", {})
        entity_type = frontmatter.get("type", "")

        # Define expected section order per entity type
        expected_sections = {
            "company": [
                "Overview",
                "Products & Services",
                "Pricing",
                "Funding & Financials",
                "Leadership",
                "Competitive Position",
                "Recent Developments",
                "Open Questions",
                "Sources",
            ],
            "product": [
                "Overview",
                "Features",
                "Pricing",
                "Target Market",
                "Competitive Alternatives",
                "Recent Developments",
                "Sources",
            ],
            "person": [
                "Background",
                "Current Role",
                "Previous Roles",
                "Public Statements",
                "Sources",
            ],
            "trend": [
                "Summary",
                "Key Players",
                "Adoption Stage",
                "Implications",
                "Recent Developments",
                "Sources",
            ],
        }

        sections_to_check = expected_sections.get(entity_type, [])
        if not sections_to_check:
            return AdvancedTestResult(
                test_id="consistency_section_order",
                test_name="Section Order Consistency",
                passed=True,
                priority="priority_3",
                score=100.0,
                warnings=["Unknown entity type, skipping section check"],
            )

        # Find section positions
        section_positions = {}
        for section in sections_to_check:
            pattern = re.compile(rf"^##\s+{re.escape(section)}\s*$", re.MULTILINE)
            match = pattern.search(content)
            if match:
                section_positions[section] = match.start()

        # Check order
        last_pos = -1
        for section in sections_to_check:
            if section in section_positions:
                if section_positions[section] < last_pos:
                    errors.append(f"Section '{section}' appears out of order")
                last_pos = section_positions[section]
            else:
                warnings.append(f"Expected section '{section}' not found")

        return AdvancedTestResult(
            test_id="consistency_section_order",
            test_name="Section Order Consistency",
            passed=len(errors) == 0,
            priority="priority_3",
            score=100.0 if len(errors) == 0 else max(0, 100 - len(errors) * 20),
            errors=errors,
            warnings=warnings,
        )

    def evaluate_all_priority_3(self, page_data: Dict[str, Any]) -> List[AdvancedTestResult]:
        """Run all Priority 3 tests."""
        return [
            self.evaluate_crossref_syntax(page_data),
            self.evaluate_crossref_deduplication(page_data),
            self.evaluate_crossref_resolution(page_data),
            self.evaluate_consistency_company_reference(page_data),
            self.evaluate_consistency_section_order(page_data),
        ]
