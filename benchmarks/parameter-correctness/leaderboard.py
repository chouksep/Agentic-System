"""Leaderboard-style parameter correctness evaluator for ci-wiki."""

import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from pathlib import Path


@dataclass
class ParameterCheckResult:
    """Result of a single parameter check."""
    test_id: str
    passed: bool
    expected: Any
    actual: Any
    error_message: str = ""


@dataclass
class TestCaseResult:
    """Result of evaluating a single test case."""
    test_id: str
    test_name: str
    passed: bool
    score: float
    is_critical: bool
    checks: List[ParameterCheckResult] = field(default_factory=list)
    feedback: List[str] = field(default_factory=list)


@dataclass
class LeaderboardScore:
    """Leaderboard entry for a model/agent."""
    model_name: str
    total_score: float
    critical_score: float
    non_critical_score: float
    tests_passed: int
    tests_total: int
    pass_rate: float
    timestamp: str = ""
    detailed_results: List[TestCaseResult] = field(default_factory=list)


class ParameterCorrectnessEvaluator:
    """Evaluate parameter correctness against BFCL-style benchmark."""

    def __init__(self, test_cases_path: str):
        """Initialize evaluator with test cases."""
        with open(test_cases_path) as f:
            self.test_data = json.load(f)
        self.test_cases = {tc["id"]: tc for tc in self.test_data["test_cases"]}
        self.scoring_config = self.test_data.get(
            "scoring", self.test_data.get("test_categories_extended", {})
        )

    def evaluate_page(self, page_data: Dict[str, Any], test_id: str) -> TestCaseResult:
        """Evaluate a single page against a test case."""
        test_case = self.test_cases.get(test_id)
        if not test_case:
            raise ValueError(f"Test case {test_id} not found")

        checks = []
        feedback = []

        # Extract actual values
        actual_path = page_data.get("path", "")
        actual_frontmatter = page_data.get("frontmatter", {})
        actual_content = page_data.get("content", "")

        # Run checks based on category
        category = test_case.get("category", "")

        if category in ["path_format", "slug_format"]:
            checks.extend(
                self._check_path(
                    test_case, actual_path, actual_frontmatter, feedback
                )
            )
        elif category in ["frontmatter", "entity_specific", "validation"]:
            checks.extend(
                self._check_frontmatter(
                    test_case, actual_frontmatter, feedback
                )
            )
        elif category == "content_format":
            checks.extend(
                self._check_content_format(
                    test_case, actual_content, feedback
                )
            )
        elif category == "content_quality":
            checks.extend(
                self._check_content_quality(
                    test_case, actual_content, feedback
                )
            )
        elif category == "update_behavior":
            checks.extend(
                self._check_update_behavior(
                    test_case, page_data, feedback
                )
            )
        elif category == "consistency":
            checks.extend(
                self._check_consistency(
                    test_case, actual_path, actual_frontmatter, feedback
                )
            )

        # Calculate score
        passed = all(c.passed for c in checks) if checks else True
        score = 100.0 if passed else 0.0
        if not passed and checks:
            score = (sum(1 for c in checks if c.passed) / len(checks)) * 100

        is_critical = test_case.get("critical", False)

        return TestCaseResult(
            test_id=test_id,
            test_name=test_case.get("name", ""),
            passed=passed,
            score=score,
            is_critical=is_critical,
            checks=checks,
            feedback=feedback,
        )

    def _check_path(
        self,
        test_case: Dict,
        actual_path: str,
        frontmatter: Dict,
        feedback: List[str],
    ) -> List[ParameterCheckResult]:
        """Check path-related parameters."""
        checks = []
        expected_params = test_case.get("expected_params", {})
        expected_path = expected_params.get("path", "")
        expected_directory = expected_params.get("path_directory", "")

        # Check path directory (more flexible than exact match)
        if expected_directory:
            path_directory = actual_path.split("/")[0] if "/" in actual_path else ""
            passed = path_directory == expected_directory
            checks.append(
                ParameterCheckResult(
                    test_id=test_case["id"],
                    passed=passed,
                    expected=f"{expected_directory}/*",
                    actual=actual_path,
                    error_message="" if passed else f"Path should be in {expected_directory}/, got {actual_path}",
                )
            )
            if not passed:
                feedback.append(f"Path should be in {expected_directory}/ directory, got {actual_path}")

        # Check exact path match if specified
        if expected_path:
            passed = actual_path == expected_path
            checks.append(
                ParameterCheckResult(
                    test_id=test_case["id"],
                    passed=passed,
                    expected=expected_path,
                    actual=actual_path,
                    error_message="" if passed else f"Path mismatch: expected {expected_path}, got {actual_path}",
                )
            )
            if not passed:
                feedback.append(f"Path mismatch: expected {expected_path}, got {actual_path}")

        # Check kebab-case for slugs
        if actual_path:
            slug = actual_path.split("/")[-1] if "/" in actual_path else actual_path
            if not self._is_kebab_case(slug):
                checks.append(
                    ParameterCheckResult(
                        test_id=test_case["id"],
                        passed=False,
                        expected="kebab-case",
                        actual=slug,
                        error_message=f"Slug should be kebab-case, got: {slug}",
                    )
                )
                feedback.append(f"Slug not in kebab-case: {slug}")

        # Check no spaces in path
        if " " in actual_path:
            checks.append(
                ParameterCheckResult(
                    test_id=test_case["id"],
                    passed=False,
                    expected="no spaces",
                    actual=actual_path,
                    error_message="Path contains spaces",
                )
            )
            feedback.append("Path should not contain spaces")

        return checks

    def _check_frontmatter(
        self,
        test_case: Dict,
        frontmatter: Dict,
        feedback: List[str],
    ) -> List[ParameterCheckResult]:
        """Check frontmatter parameters."""
        checks = []
        expected = test_case.get("expected_params", {})
        valid_values = test_case.get("valid_values", [])
        invalid_values = test_case.get("invalid_values", [])

        for field_name, field_value in expected.items():
            if "." not in field_name:
                continue

            # Extract nested field (e.g., "frontmatter.type" -> "type")
            _, field = field_name.split(".", 1)
            actual_value = frontmatter.get(field)

            # Check required field exists
            if field_value == "NotEmpty":
                passed = bool(actual_value)
                checks.append(
                    ParameterCheckResult(
                        test_id=test_case["id"],
                        passed=passed,
                        expected=f"{field} required",
                        actual=actual_value,
                        error_message="" if passed else f"Field '{field}' is required but missing",
                    )
                )
                if not passed:
                    feedback.append(f"Required field '{field}' is missing")
            elif field_value == "ValidType":
                passed = actual_value in ["company", "product", "person", "trend"]
                checks.append(
                    ParameterCheckResult(
                        test_id=test_case["id"],
                        passed=passed,
                        expected="OneOf:company,product,person,trend",
                        actual=actual_value,
                        error_message="" if passed else f"Invalid type: {actual_value}",
                    )
                )
                if not passed:
                    feedback.append(f"Invalid type value: {actual_value}")
            elif field_value == "ValidEnum":
                # For enum fields, use valid_values from test case
                passed = actual_value in valid_values if valid_values else True
                checks.append(
                    ParameterCheckResult(
                        test_id=test_case["id"],
                        passed=passed,
                        expected=f"OneOf:{','.join(valid_values)}",
                        actual=actual_value,
                        error_message="" if passed else f"Invalid value: {actual_value}",
                    )
                )
                if not passed:
                    feedback.append(f"'{field}' value '{actual_value}' not in allowed values: {valid_values}")
            elif field_value.startswith("OneOf:"):
                # OneOf constraint: value must be one of the listed options
                allowed = field_value.split(":", 1)[1].split(",")
                passed = actual_value in allowed
                checks.append(
                    ParameterCheckResult(
                        test_id=test_case["id"],
                        passed=passed,
                        expected=field_value,
                        actual=actual_value,
                        error_message="" if passed else f"Invalid value: {actual_value}",
                    )
                )
                if not passed:
                    feedback.append(f"'{field}' value '{actual_value}' not in allowed set: {allowed}")
            elif field_value.startswith("DateFormat:"):
                # Date format validation
                date_format = field_value.split(":", 1)[1]
                if date_format == "YYYY-MM-DD":
                    passed = bool(re.match(r"^\d{4}-\d{2}-\d{2}$", str(actual_value)))
                    checks.append(
                        ParameterCheckResult(
                            test_id=test_case["id"],
                            passed=passed,
                            expected="YYYY-MM-DD format",
                            actual=str(actual_value),
                            error_message="" if passed else f"Invalid date format: {actual_value}",
                        )
                    )
                    if not passed:
                        feedback.append(f"Date '{actual_value}' must be in YYYY-MM-DD format")

        # Check valid values
        for field_name, field_value in expected.items():
            if "." not in field_name:
                continue
            _, field = field_name.split(".", 1)
            actual_value = frontmatter.get(field)

            if valid_values and actual_value and actual_value not in valid_values:
                # Skip if we already checked this as ValidEnum
                if field_value != "ValidEnum":
                    checks.append(
                        ParameterCheckResult(
                            test_id=test_case["id"],
                            passed=False,
                            expected=f"OneOf:{','.join(valid_values)}",
                            actual=actual_value,
                            error_message=f"Value not in allowed set: {actual_value}",
                        )
                    )
                    feedback.append(f"'{actual_value}' not in allowed values: {valid_values}")

        # Check invalid values
        for field_name, field_value in expected.items():
            if "." not in field_name:
                continue
            _, field = field_name.split(".", 1)
            actual_value = frontmatter.get(field)

            if invalid_values and actual_value in invalid_values:
                checks.append(
                    ParameterCheckResult(
                        test_id=test_case["id"],
                        passed=False,
                        expected=f"NotIn:{','.join(invalid_values)}",
                        actual=actual_value,
                        error_message=f"Value in forbidden set: {actual_value}",
                    )
                )
                feedback.append(f"'{actual_value}' is a forbidden value")

        return checks

    def _check_content_format(
        self,
        test_case: Dict,
        content: str,
        feedback: List[str],
    ) -> List[ParameterCheckResult]:
        """Check content format (Markdown, cross-references)."""
        checks = []
        expected_regex = test_case.get("expected_regex", "")
        valid_types = test_case.get("valid_crossref_types", [])

        # Check cross-reference syntax
        if expected_regex:
            matches = re.findall(expected_regex, content)
            passed = len(matches) > 0 if "[[" in test_case.get("scenario", "") else True
            checks.append(
                ParameterCheckResult(
                    test_id=test_case["id"],
                    passed=passed,
                    expected="Cross-references in [[type:slug]] format",
                    actual=f"Found {len(matches)} matching references",
                    error_message="" if passed else "No valid cross-references found",
                )
            )
            if not passed:
                feedback.append("Cross-references should use [[type:slug]] format")

        # Check cross-reference types
        if valid_types:
            crossrefs = re.findall(r"\[\[([a-z]+):([a-z-]+)\]\]", content)
            for ref_type, ref_slug in crossrefs:
                if ref_type not in valid_types:
                    checks.append(
                        ParameterCheckResult(
                            test_id=test_case["id"],
                            passed=False,
                            expected=f"OneOf:{','.join(valid_types)}",
                            actual=ref_type,
                            error_message=f"Invalid cross-reference type: {ref_type}",
                        )
                    )
                    feedback.append(f"Cross-reference type '{ref_type}' is not valid")

        return checks

    def _check_content_quality(
        self,
        test_case: Dict,
        content: str,
        feedback: List[str],
    ) -> List[ParameterCheckResult]:
        """Check content quality (not empty, sufficient length)."""
        checks = []
        min_length = test_case.get("min_length", 0)

        passed = len(content) > min_length
        checks.append(
            ParameterCheckResult(
                test_id=test_case["id"],
                passed=passed,
                expected=f">= {min_length} characters",
                actual=f"{len(content)} characters",
                error_message="" if passed else f"Content too short: {len(content)} chars",
            )
        )
        if not passed:
            feedback.append(f"Content should be at least {min_length} characters")

        return checks

    def _check_update_behavior(
        self,
        test_case: Dict,
        page_data: Dict,
        feedback: List[str],
    ) -> List[ParameterCheckResult]:
        """Check update operation behavior."""
        checks = []

        # Check type unchanged
        if "type_unchanged" in test_case.get("expected_params", {}):
            original_type = page_data.get("original_type")
            current_type = page_data.get("frontmatter", {}).get("type")
            passed = original_type == current_type
            checks.append(
                ParameterCheckResult(
                    test_id=test_case["id"],
                    passed=passed,
                    expected=f"type unchanged ({original_type})",
                    actual=current_type,
                    error_message="" if passed else f"Type changed from {original_type} to {current_type}",
                )
            )
            if not passed:
                feedback.append("Page type should not change on update")

        # Check path unchanged
        if "path_unchanged" in test_case.get("expected_params", {}):
            original_path = page_data.get("original_path")
            current_path = page_data.get("path")
            passed = original_path == current_path
            checks.append(
                ParameterCheckResult(
                    test_id=test_case["id"],
                    passed=passed,
                    expected=f"path unchanged ({original_path})",
                    actual=current_path,
                    error_message="" if passed else f"Path changed from {original_path} to {current_path}",
                )
            )
            if not passed:
                feedback.append("Page path should not change on update")

        return checks

    def _check_consistency(
        self,
        test_case: Dict,
        path: str,
        frontmatter: Dict,
        feedback: List[str],
    ) -> List[ParameterCheckResult]:
        """Check consistency between fields."""
        checks = []
        validations = test_case.get("validations", [])

        if validations:
            entity_type = frontmatter.get("type", "")
            path_dir = path.split("/")[0] if "/" in path else ""

            # Map type to directory
            type_to_dir = {
                "company": "companies",
                "product": "products",
                "person": "people",
                "trend": "trends",
            }

            expected_dir = type_to_dir.get(entity_type)
            passed = path_dir == expected_dir

            checks.append(
                ParameterCheckResult(
                    test_id=test_case["id"],
                    passed=passed,
                    expected=f"type '{entity_type}' in '{expected_dir}/' directory",
                    actual=f"Found in '{path_dir}/' directory",
                    error_message="" if passed else f"Type-directory mismatch",
                )
            )
            if not passed:
                feedback.append(f"Type '{entity_type}' should be in '{expected_dir}/' directory, not '{path_dir}/'")

        return checks

    @staticmethod
    def _is_kebab_case(s: str) -> bool:
        """Check if string is in kebab-case."""
        return bool(re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", s))

    def evaluate_batch(
        self, page_results: List[Dict[str, Any]]
    ) -> LeaderboardScore:
        """Evaluate multiple pages and return leaderboard score."""
        results = []

        for page_result in page_results:
            test_id = page_result.get("test_id")
            result = self.evaluate_page(page_result, test_id)
            results.append(result)

        # Calculate scores
        critical_results = [r for r in results if r.is_critical]
        non_critical_results = [r for r in results if not r.is_critical]

        critical_score = (
            sum(r.score for r in critical_results) / len(critical_results)
            if critical_results
            else 100.0
        )
        non_critical_score = (
            sum(r.score for r in non_critical_results) / len(non_critical_results)
            if non_critical_results
            else 100.0
        )

        # Check if critical tests must pass
        if self.scoring_config.get("critical_tests_must_pass"):
            if critical_score < 100:
                total_score = 0.0
            else:
                total_score = (
                    critical_score * self.scoring_config["critical_weight"]
                    + non_critical_score * self.scoring_config["non_critical_weight"]
                )
        else:
            total_score = (
                critical_score * self.scoring_config["critical_weight"]
                + non_critical_score * self.scoring_config["non_critical_weight"]
            )

        tests_passed = sum(1 for r in results if r.passed)
        tests_total = len(results)

        return LeaderboardScore(
            model_name="ci-wiki-agent",
            total_score=total_score,
            critical_score=critical_score,
            non_critical_score=non_critical_score,
            tests_passed=tests_passed,
            tests_total=tests_total,
            pass_rate=(tests_passed / tests_total * 100) if tests_total > 0 else 0,
            detailed_results=results,
        )


def main():
    """Example usage."""
    evaluator = ParameterCorrectnessEvaluator("test_cases.json")
    print("Parameter Correctness Evaluator loaded successfully")
    print(f"Total test cases: {len(evaluator.test_cases)}")

    # Example: evaluate a single page
    example_page = {
        "path": "companies/openai",
        "frontmatter": {
            "name": "OpenAI",
            "type": "company",
        },
        "content": "<!-- confidence: high -->\nOpenAI is an AI research company...",
    }

    result = evaluator.evaluate_page(example_page, "path_format_company")
    print(f"\nTest: {result.test_name}")
    print(f"Passed: {result.passed}")
    print(f"Score: {result.score:.1f}%")
    if result.feedback:
        print(f"Feedback: {'; '.join(result.feedback)}")


if __name__ == "__main__":
    main()
