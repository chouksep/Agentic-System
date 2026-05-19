"""Unit tests verifying the BFCL-faithful AST checker behaves correctly.

These tests verify that the checker:
  (1) accepts golden answers (positive cases)
  (2) rejects wrong function names
  (3) rejects missing required parameters
  (4) rejects wrong parameter types
  (5) rejects wrong parameter values
  (6) handles parallel/multiple correctly
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from ast_checker import (
    simple_function_checker,
    multiple_function_checker,
    parallel_function_checker_no_order,
    standardize_string,
)
from wiki_functions import READ_WIKI_PAGE, SEARCH_WIKI, ALL_WIKI_FUNCTIONS


def assert_pass(result, label):
    assert result["valid"], f"{label}: expected pass, got {result}"
    print(f"  PASS  {label}")


def assert_fail(result, label, expected_error_type=None):
    assert not result["valid"], f"{label}: expected fail, got pass"
    if expected_error_type:
        assert result.get("error_type") == expected_error_type, (
            f"{label}: expected error_type={expected_error_type}, "
            f"got {result.get('error_type')}"
        )
    print(f"  FAIL  {label}  [{result.get('error_type', '?')}]")


def test_standardize_string():
    print("\n[standardize_string]")
    assert standardize_string("OpenAI") == "openai"
    assert standardize_string("hello, world") == "helloworld"
    assert standardize_string("dario-amodei") == "darioamodei"
    assert standardize_string("'foo'") == '"foo"'
    print("  PASS  string standardization is identical to BFCL")


def test_simple_correct():
    print("\n[simple_function_checker: correct input]")
    result = simple_function_checker(
        READ_WIKI_PAGE,
        {"read_wiki_page": {"slug": "openai", "page_type": "company"}},
        {"read_wiki_page": {"slug": ["openai"], "page_type": ["company"]}},
    )
    assert_pass(result, "exact match")

    result = simple_function_checker(
        READ_WIKI_PAGE,
        {"read_wiki_page": {"slug": "OpenAI", "page_type": "company"}},
        {"read_wiki_page": {"slug": ["openai"], "page_type": ["company"]}},
    )
    assert_pass(result, "case-insensitive string match")


def test_simple_wrong_func_name():
    print("\n[simple_function_checker: wrong function name]")
    result = simple_function_checker(
        READ_WIKI_PAGE,
        {"write_wiki_page": {"slug": "openai", "page_type": "company"}},
        {"read_wiki_page": {"slug": ["openai"], "page_type": ["company"]}},
    )
    assert_fail(result, "wrong function name", "simple_function_checker:wrong_func_name")


def test_simple_missing_required():
    print("\n[simple_function_checker: missing required param]")
    result = simple_function_checker(
        READ_WIKI_PAGE,
        {"read_wiki_page": {"slug": "openai"}},  # missing page_type
        {"read_wiki_page": {"slug": ["openai"], "page_type": ["company"]}},
    )
    assert_fail(result, "missing page_type", "simple_function_checker:missing_required")


def test_simple_wrong_value():
    print("\n[simple_function_checker: wrong parameter value]")
    result = simple_function_checker(
        READ_WIKI_PAGE,
        {"read_wiki_page": {"slug": "openai", "page_type": "company"}},
        {"read_wiki_page": {"slug": ["anthropic"], "page_type": ["company"]}},
    )
    assert_fail(result, "wrong slug", "value_error:string")


def test_simple_wrong_type():
    print("\n[simple_function_checker: wrong parameter type]")
    result = simple_function_checker(
        SEARCH_WIKI,
        {"search_wiki": {"query": "anthropic", "top_k": "five"}},
        {"search_wiki": {"query": ["anthropic"], "top_k": ["", 5]}},
    )
    assert_fail(result, "top_k should be integer, not string")


def test_multiple_picks_correct_function():
    print("\n[multiple_function_checker]")
    funcs = ALL_WIKI_FUNCTIONS
    # Question: search for X. Correct call: search_wiki(query="x").
    correct = [{"search_wiki": {"query": "anthropic"}}]
    pa = [{"search_wiki": {"query": ["anthropic"], "top_k": ["", 5]}}]
    result = multiple_function_checker(funcs, correct, pa)
    assert_pass(result, "picks correct function from many")

    wrong = [{"list_wiki_pages": {"page_type": "company"}}]
    result = multiple_function_checker(funcs, wrong, pa)
    assert_fail(result, "wrong function chosen from many")


def test_parallel_any_order():
    print("\n[parallel_function_checker_no_order]")
    funcs = [READ_WIKI_PAGE]
    expected = [
        {"read_wiki_page": {"slug": ["openai"], "page_type": ["company"]}},
        {"read_wiki_page": {"slug": ["anthropic"], "page_type": ["company"]}},
    ]
    # Same order
    same_order = [
        {"read_wiki_page": {"slug": "openai", "page_type": "company"}},
        {"read_wiki_page": {"slug": "anthropic", "page_type": "company"}},
    ]
    assert_pass(parallel_function_checker_no_order(funcs, same_order, expected),
                "parallel: same order")

    # Reversed order
    reversed_order = list(reversed(same_order))
    assert_pass(parallel_function_checker_no_order(funcs, reversed_order, expected),
                "parallel: reversed order")

    # Missing one
    missing = same_order[:1]
    assert_fail(parallel_function_checker_no_order(funcs, missing, expected),
                "parallel: missing one call")


def main():
    print("=" * 70)
    print("BFCL AST CHECKER UNIT TESTS")
    print("=" * 70)
    test_standardize_string()
    test_simple_correct()
    test_simple_wrong_func_name()
    test_simple_missing_required()
    test_simple_wrong_value()
    test_simple_wrong_type()
    test_multiple_picks_correct_function()
    test_parallel_any_order()
    print("\n" + "=" * 70)
    print("All AST checker tests passed.")
    print("=" * 70)


if __name__ == "__main__":
    main()
