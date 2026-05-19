"""Faithful port of BFCL's AST checker for the ci-wiki agent.

Source: https://github.com/ShishirPatil/gorilla
Paper: The Berkeley Function Calling Leaderboard (BFCL): From Tool Use to
       Agentic Evaluation of Large Language Models (Patil et al., ICML 2025)

This module implements the EXACT same algorithm as BFCL's `ast_checker.py`:
- simple_function_checker
- multiple_function_checker
- parallel_function_checker_no_order
- type_checker, string_checker, list_checker, dict_checker, list_dict_checker
- standardize_string (lowercase, strip punctuation)

The only adaptation: the function descriptions and test cases use the ci-wiki
tool schemas (read_wiki_page, write_wiki_page, search_wiki, list_wiki_pages,
flag_contradiction) instead of generic Python functions.
"""
from __future__ import annotations

import re
from typing import Any


PYTHON_TYPE_MAPPING = {
    "string": str,
    "integer": int,
    "float": float,
    "boolean": bool,
    "array": list,
    "tuple": list,
    "dict": dict,
    "any": str,
}

PYTHON_NESTED_TYPE_CHECK_LIST = ["array", "tuple"]


def standardize_string(input_string: str) -> str:
    """Identical to BFCL: lowercase, strip space/punctuation, normalize quotes."""
    regex_string = r"[ \,\.\/\-\_\*\^]"
    return re.sub(regex_string, "", input_string).lower().replace("'", '"')


def get_possible_answer_type(possible_answer: list):
    for answer in possible_answer:
        if answer != "":
            return type(answer)
    return None


def type_checker(
    param: str,
    value: Any,
    possible_answer: list,
    expected_type_description: str,
    expected_type_converted,
    nested_type_converted,
):
    """Identical to BFCL type_checker."""
    result = {
        "valid": True,
        "error": [],
        "is_variable": False,
        "error_type": "type_error:simple",
    }

    is_variable = False
    possible_answer_type = get_possible_answer_type(possible_answer)
    if possible_answer_type is not None:
        if possible_answer_type != expected_type_converted:
            is_variable = True

    if type(value) == expected_type_converted:
        if nested_type_converted is None:
            result["is_variable"] = is_variable
            return result
        else:
            for possible_answer_item in possible_answer:
                flag = True
                if type(possible_answer_item) == list:
                    for value_item in value:
                        checker_result = type_checker(
                            param,
                            value_item,
                            possible_answer_item,
                            str(nested_type_converted),
                            nested_type_converted,
                            None,
                        )
                        if not checker_result["valid"]:
                            flag = False
                            break
                if flag:
                    return {"valid": True, "error": [], "is_variable": is_variable}

            result["valid"] = False
            result["error"] = [
                f"Nested type checking failed for parameter {repr(param)}. "
                f"Expected outer type {expected_type_description} with inner type "
                f"{str(nested_type_converted)}. Parameter value: {repr(value)}."
            ]
            result["error_type"] = "type_error:nested"

    possible_answer_type = get_possible_answer_type(possible_answer)
    if possible_answer_type is not None:
        if type(value) == possible_answer_type:
            result["is_variable"] = True
            return result

    result["valid"] = False
    result["error"].append(
        f"Incorrect type for parameter {repr(param)}. "
        f"Expected type {expected_type_description}, got {type(value).__name__}. "
        f"Parameter value: {repr(value)}."
    )
    result["error_type"] = "type_error:simple"
    return result


def string_checker(param: str, model_output: str, possible_answer: list):
    """Identical to BFCL string_checker."""
    standardize_possible_answer = []
    standardize_model_output = standardize_string(model_output)
    for i in range(len(possible_answer)):
        if type(possible_answer[i]) == str:
            standardize_possible_answer.append(standardize_string(possible_answer[i]))

    if standardize_model_output not in standardize_possible_answer:
        return {
            "valid": False,
            "error": [
                f"Invalid value for parameter {repr(param)}: {repr(model_output)}. "
                f"Expected one of {possible_answer}. Case insensitive."
            ],
            "error_type": "value_error:string",
        }
    return {"valid": True, "error": []}


def list_checker(param: str, model_output: list, possible_answer: list):
    """Identical to BFCL list_checker."""
    if model_output in possible_answer:
        return {"valid": True, "error": []}
    standardize_possible_answer = []
    for ans in possible_answer:
        if type(ans) == list:
            inner = []
            for v in ans:
                inner.append(standardize_string(v) if isinstance(v, str) else v)
            standardize_possible_answer.append(inner)
    standardize_model = [
        standardize_string(v) if isinstance(v, str) else v for v in model_output
    ]
    if standardize_model in standardize_possible_answer:
        return {"valid": True, "error": []}
    return {
        "valid": False,
        "error": [
            f"Invalid value for parameter {repr(param)}: {repr(model_output)}. "
            f"Expected one of {possible_answer}."
        ],
        "error_type": "value_error:list",
    }


def dict_checker(param: str, model_output: dict, possible_answers: list):
    """Identical to BFCL dict_checker."""
    for i in range(len(possible_answers)):
        result = {"valid": False, "error": [], "error_type": "dict_checker:unclear"}
        flag = True
        possible_answer = possible_answers[i]

        for key, value in model_output.items():
            if key not in possible_answer:
                result["valid"] = False
                result["error"].append(f"Unexpected dict key parameter: '{key}'.")
                result["error_type"] = "value_error:dict_key"
                flag = False
                break

            standardize_value = standardize_string(value) if isinstance(value, str) else value
            standardize_possible_answer = []
            for j in range(len(possible_answer[key])):
                if isinstance(possible_answer[key][j], str):
                    standardize_possible_answer.append(
                        standardize_string(possible_answer[key][j])
                    )
                else:
                    standardize_possible_answer.append(possible_answer[key][j])

            if standardize_value not in standardize_possible_answer:
                result["valid"] = False
                result["error"].append(
                    f"Invalid value for parameter {repr(key)}: {repr(value)}. "
                    f"Expected one of {standardize_possible_answer}."
                )
                result["error_type"] = "value_error:dict_value"
                flag = False
                break

        for key, value in possible_answer.items():
            if key not in model_output and "" not in value:
                result["valid"] = False
                result["error"].append(f"Missing dict key parameter: '{key}'.")
                result["error_type"] = "value_error:dict_key"
                flag = False
                break

        if flag:
            return {"valid": True, "error": []}

    return result


def convert_func_name(function_name: str, model_name: str = "default"):
    """Simplified port (no underscore_to_dot model mapping for ci-wiki)."""
    return function_name


def find_description(func_descriptions, name):
    if isinstance(func_descriptions, list):
        for f in func_descriptions:
            if f["name"] == name:
                return f
        return None
    return func_descriptions


def simple_function_checker(
    func_description: dict,
    model_output: dict,
    possible_answer: dict,
    model_name: str = "default",
):
    """Identical to BFCL simple_function_checker (Python language path)."""
    possible_answer = list(possible_answer.values())[0]
    func_name = func_description["name"]
    param_details = func_description["parameters"]["properties"]
    required_params = func_description["parameters"]["required"]

    result = {"valid": True, "error": [], "error_type": "simple_function_checker:unclear"}
    func_name = convert_func_name(func_name, model_name)

    if func_name not in model_output:
        result["valid"] = False
        result["error"].append(
            f"Function name {repr(func_name)} not found in model output."
        )
        result["error_type"] = "simple_function_checker:wrong_func_name"
        return result

    model_params = model_output[func_name]

    for param in required_params:
        if param not in model_params:
            result["valid"] = False
            result["error"].append(f"Missing required parameter: {repr(param)}.")
            result["error_type"] = "simple_function_checker:missing_required"
            return result

    for param, value in model_params.items():
        if param not in param_details or param not in possible_answer:
            result["valid"] = False
            result["error"].append(f"Unexpected parameter: {repr(param)}.")
            result["error_type"] = "simple_function_checker:unexpected_param"
            return result

        full_param_details = param_details[param]
        expected_type_description = full_param_details["type"]
        nested_type_converted = None

        expected_type_converted = PYTHON_TYPE_MAPPING[expected_type_description]
        if expected_type_description in PYTHON_NESTED_TYPE_CHECK_LIST:
            nested_type = param_details[param]["items"]["type"]
            nested_type_converted = PYTHON_TYPE_MAPPING[nested_type]

        if expected_type_description == "tuple" and isinstance(value, tuple):
            value = list(value)
        if expected_type_description == "float" and isinstance(value, int):
            value = float(value)

        type_check_result = type_checker(
            param,
            value,
            possible_answer[param],
            expected_type_description,
            expected_type_converted,
            nested_type_converted,
        )
        is_variable = type_check_result["is_variable"]
        if not type_check_result["valid"]:
            return type_check_result

        if not is_variable:
            if expected_type_converted == dict:
                r = dict_checker(param, value, possible_answer[param])
                if not r["valid"]:
                    return r
                continue
            elif expected_type_converted == list and nested_type_converted == dict:
                r = dict_checker(param, value, possible_answer[param])
                if not r["valid"]:
                    return r
                continue
            elif expected_type_converted == str:
                r = string_checker(param, value, possible_answer[param])
                if not r["valid"]:
                    return r
                continue
            elif expected_type_converted == list:
                r = list_checker(param, value, possible_answer[param])
                if not r["valid"]:
                    return r
                continue

        if value not in possible_answer[param]:
            result["valid"] = False
            result["error"].append(
                f"Invalid value for parameter {repr(param)}: {repr(value)}. "
                f"Expected one of {possible_answer[param]}."
            )
            result["error_type"] = "value_error:others"
            return result

    for param in possible_answer:
        if param not in model_params and "" not in possible_answer[param]:
            result["valid"] = False
            result["error"].append(
                f"Optional parameter {repr(param)} not provided and not marked as optional."
            )
            result["error_type"] = "simple_function_checker:missing_optional"
            return result

    return result


def multiple_function_checker(
    func_descriptions: list,
    model_output: list,
    possible_answer: list,
    model_name: str = "default",
):
    """Identical to BFCL multiple_function_checker.

    Used for `multiple` category: exactly one function should be called, chosen
    correctly from several available functions.
    """
    if len(model_output) != 1:
        return {
            "valid": False,
            "error": ["Wrong number of functions."],
            "error_type": "multiple_function_checker:wrong_count",
        }
    func_name = list(possible_answer[0].keys())[0]
    func_description = find_description(func_descriptions, func_name)
    return simple_function_checker(
        func_description, model_output[0], possible_answer[0], model_name
    )


def parallel_function_checker_no_order(
    func_descriptions: list,
    model_output: list,
    possible_answers: list,
    model_name: str = "default",
):
    """Identical to BFCL parallel_function_checker_no_order.

    Used for `parallel` category: multiple function calls in any order.
    """
    if len(model_output) != len(possible_answers):
        return {
            "valid": False,
            "error": ["Wrong number of functions."],
            "error_type": "parallel_function_checker_no_order:wrong_count",
        }

    matched_indices = []
    for i in range(len(possible_answers)):
        func_name_expected = list(possible_answers[i].keys())[0]
        func_description = find_description(func_descriptions, func_name_expected)

        matched_index = -1
        all_errors = []
        for j in range(len(model_output)):
            if j in matched_indices:
                continue
            r = simple_function_checker(
                func_description, model_output[j], possible_answers[i], model_name
            )
            if r["valid"]:
                matched_index = j
                break
            else:
                all_errors.append(r)
        if matched_index == -1:
            return {
                "valid": False,
                "error": [
                    f"Cannot find a match for expected call to "
                    f"{repr(func_name_expected)}."
                ],
                "error_type": "parallel_function_checker_no_order:no_match",
                "details": all_errors,
            }
        matched_indices.append(matched_index)

    return {"valid": True, "error": []}


def ast_checker(
    func_description,
    model_output,
    possible_answer,
    test_category: str,
    model_name: str = "default",
):
    """Top-level dispatcher matching BFCL's ast_checker signature."""
    if "parallel" in test_category:
        return parallel_function_checker_no_order(
            func_description, model_output, possible_answer, model_name
        )
    elif "multiple" in test_category:
        return multiple_function_checker(
            func_description, model_output, possible_answer, model_name
        )
    else:
        if len(model_output) != 1:
            return {
                "valid": False,
                "error": ["Wrong number of functions."],
                "error_type": "simple_function_checker:wrong_count",
            }
        return simple_function_checker(
            func_description[0] if isinstance(func_description, list) else func_description,
            model_output[0],
            possible_answer[0],
            model_name,
        )
