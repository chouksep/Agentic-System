"""ToolComp-style evaluation for ci-wiki agent tool composition."""

import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class ToolCall:
    """Representation of a tool call made by the agent."""
    tool: str
    params: Dict[str, Any]
    step: int


@dataclass
class EvaluationResult:
    """Result of evaluating a single test case."""
    test_id: str
    passed: bool
    tool_invocation_score: float
    parameter_score: float
    abstention_score: float
    sequencing_score: float
    total_score: float
    feedback: List[str]


class ToolCompEvaluator:
    """Evaluator for tool composition benchmarks."""

    def __init__(self, test_prompts_path: str):
        """Initialize evaluator with test prompts."""
        with open(test_prompts_path) as f:
            self.test_data = json.load(f)
        self.test_cases = self.test_data["test_cases"]
        self.rubric = self.test_data["evaluation_rubric"]

    def evaluate_test_case(
        self,
        test_id: str,
        agent_tool_calls: List[ToolCall],
        agent_abstained: bool,
    ) -> EvaluationResult:
        """Evaluate a single test case."""
        test_case = next((tc for tc in self.test_cases if tc["id"] == test_id), None)
        if not test_case:
            raise ValueError(f"Test case {test_id} not found")

        feedback = []
        scores = {
            "tool_invocation": self._evaluate_tool_invocation(
                agent_tool_calls, test_case, feedback
            ),
            "parameter": self._evaluate_parameters(
                agent_tool_calls, test_case, feedback
            ),
            "abstention": self._evaluate_abstention(
                agent_abstained, test_case, feedback
            ),
            "sequencing": self._evaluate_sequencing(
                agent_tool_calls, test_case, feedback
            ),
        }

        total_score = (
            scores["tool_invocation"] * 0.4
            + scores["parameter"] * 0.4
            + scores["abstention"] * 0.1
            + scores["sequencing"] * 0.1
        )

        return EvaluationResult(
            test_id=test_id,
            passed=total_score >= 80,  # 80% threshold
            tool_invocation_score=scores["tool_invocation"],
            parameter_score=scores["parameter"],
            abstention_score=scores["abstention"],
            sequencing_score=scores["sequencing"],
            total_score=total_score,
            feedback=feedback,
        )

    def _evaluate_tool_invocation(
        self, agent_calls: List[ToolCall], test_case: Dict, feedback: List[str]
    ) -> float:
        """Evaluate if correct tools were called."""
        expected_calls = test_case.get("expected_tool_calls", [])

        if not expected_calls:
            # Should have abstained
            if not agent_calls:
                return 100.0
            feedback.append("Expected no tool calls, but agent made some")
            return 0.0

        if len(agent_calls) != len(expected_calls):
            feedback.append(
                f"Expected {len(expected_calls)} tool calls, got {len(agent_calls)}"
            )

        correct = 0
        for i, expected in enumerate(expected_calls):
            if i < len(agent_calls):
                if agent_calls[i].tool == expected["tool"]:
                    correct += 1
                else:
                    feedback.append(
                        f"Step {i+1}: Expected {expected['tool']}, got {agent_calls[i].tool}"
                    )

        if expected_calls:
            return (correct / len(expected_calls)) * 100
        return 0.0

    def _evaluate_parameters(
        self, agent_calls: List[ToolCall], test_case: Dict, feedback: List[str]
    ) -> float:
        """Evaluate if tool parameters are correct."""
        expected_calls = test_case.get("expected_tool_calls", [])
        critical_params = test_case.get("critical_params", [])

        if not expected_calls:
            return 100.0

        correct = 0
        total = 0

        for i, expected in enumerate(expected_calls):
            if i < len(agent_calls):
                agent_params = agent_calls[i].params
                expected_params = expected.get("params", {})

                # Check critical parameters first
                for param in critical_params:
                    total += 1
                    if self._check_parameter(
                        param, agent_params, expected_params
                    ):
                        correct += 1
                    else:
                        feedback.append(
                            f"Step {i+1}: Parameter '{param}' mismatch"
                        )

                # Check other parameters
                for key in expected_params:
                    if key not in critical_params:
                        total += 1
                        if self._check_parameter(
                            key, agent_params, expected_params
                        ):
                            correct += 1

        if total > 0:
            return (correct / total) * 100
        return 100.0

    def _check_parameter(
        self, key: str, agent_params: Dict, expected_params: Dict
    ) -> bool:
        """Check if a parameter matches expected value."""
        if key not in agent_params:
            return False
        if key not in expected_params:
            return True
        return agent_params[key] == expected_params[key]

    def _evaluate_abstention(
        self, agent_abstained: bool, test_case: Dict, feedback: List[str]
    ) -> float:
        """Evaluate if agent correctly decided to abstain."""
        should_abstain = test_case.get("should_abstain", False)

        if should_abstain and agent_abstained:
            return 100.0
        elif not should_abstain and not agent_abstained:
            return 100.0
        elif should_abstain and not agent_abstained:
            feedback.append("Agent should have abstained but made tool calls")
            return 0.0
        else:
            feedback.append("Agent abstained but should have made tool calls")
            return 0.0

    def _evaluate_sequencing(
        self, agent_calls: List[ToolCall], test_case: Dict, feedback: List[str]
    ) -> float:
        """Evaluate if tool calls are in optimal sequence."""
        expected_calls = test_case.get("expected_tool_calls", [])

        if not expected_calls:
            return 100.0

        # Check if sequences match
        if len(agent_calls) == len(expected_calls):
            # Perfect sequence
            tools_match = all(
                agent_calls[i].tool == expected_calls[i]["tool"]
                for i in range(len(expected_calls))
            )
            if tools_match:
                return 100.0
            else:
                feedback.append("Tool sequence is suboptimal")
                return 50.0
        else:
            feedback.append("Tool sequence length mismatch")
            return 0.0

    def evaluate_batch(
        self, test_results: List[Dict]
    ) -> Dict[str, Any]:
        """Evaluate multiple test results and generate summary."""
        results = []
        for test_result in test_results:
            result = self.evaluate_test_case(
                test_result["test_id"],
                [
                    ToolCall(
                        tool=tc["tool"],
                        params=tc.get("params", {}),
                        step=i,
                    )
                    for i, tc in enumerate(test_result.get("tool_calls", []))
                ],
                test_result.get("abstained", False),
            )
            results.append(result)

        passed = sum(1 for r in results if r.passed)
        total = len(results)
        avg_score = sum(r.total_score for r in results) / total if results else 0

        return {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": (passed / total * 100) if total > 0 else 0,
            "average_score": avg_score,
            "results": [
                {
                    "test_id": r.test_id,
                    "passed": r.passed,
                    "score": r.total_score,
                    "feedback": r.feedback,
                }
                for r in results
            ],
        }


if __name__ == "__main__":
    # Example usage
    evaluator = ToolCompEvaluator("test_prompts.json")
    print("ToolComp Evaluator loaded successfully")
    print(f"Total test cases: {len(evaluator.test_cases)}")
