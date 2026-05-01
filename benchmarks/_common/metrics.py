"""Common metrics for benchmark evaluation."""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class ToolCallMetric:
    """Metrics for evaluating tool calls."""
    total_calls: int
    correct_calls: int
    abstained_correctly: int  # When tool wasn't called but should have been skipped
    incorrect_params: int
    tool_sequence_errors: int

    @property
    def invocation_accuracy(self) -> float:
        """Percentage of correct tool invocations."""
        if self.total_calls == 0:
            return 0.0
        return (self.correct_calls / self.total_calls) * 100

    @property
    def parameter_correctness(self) -> float:
        """Percentage of correct tool parameters."""
        if self.total_calls == 0:
            return 0.0
        return ((self.total_calls - self.incorrect_params) / self.total_calls) * 100

    @property
    def sequence_quality(self) -> float:
        """Percentage of correct tool calling sequences."""
        if self.total_calls == 0:
            return 0.0
        return ((self.total_calls - self.tool_sequence_errors) / self.total_calls) * 100


@dataclass
class FactExtractionMetric:
    """Metrics for fact extraction accuracy."""
    total_facts: int
    correct_facts: int
    hallucinated_facts: int
    missing_facts: int

    @property
    def precision(self) -> float:
        """Percentage of extracted facts that are correct."""
        if self.total_facts == 0:
            return 0.0
        return (self.correct_facts / self.total_facts) * 100

    @property
    def hallucination_rate(self) -> float:
        """Percentage of facts that are hallucinated."""
        if self.total_facts == 0:
            return 0.0
        return (self.hallucinated_facts / self.total_facts) * 100


@dataclass
class ConfidenceCalibration:
    """Metrics for confidence score calibration."""
    high_confidence_facts: int
    high_confidence_correct: int
    medium_confidence_facts: int
    medium_confidence_correct: int
    low_confidence_facts: int
    low_confidence_correct: int

    @property
    def high_confidence_precision(self) -> float:
        """Accuracy of high confidence facts."""
        if self.high_confidence_facts == 0:
            return 0.0
        return (self.high_confidence_correct / self.high_confidence_facts) * 100

    @property
    def medium_confidence_precision(self) -> float:
        """Accuracy of medium confidence facts."""
        if self.medium_confidence_facts == 0:
            return 0.0
        return (self.medium_confidence_correct / self.medium_confidence_facts) * 100

    @property
    def low_confidence_precision(self) -> float:
        """Accuracy of low confidence facts."""
        if self.low_confidence_facts == 0:
            return 0.0
        return (self.low_confidence_correct / self.low_confidence_facts) * 100

    @property
    def is_calibrated(self) -> bool:
        """Check if confidence scores match actual accuracy."""
        high = self.high_confidence_precision
        medium = self.medium_confidence_precision
        low = self.low_confidence_precision
        # Confidence should be monotonically decreasing
        return high >= medium >= low


def calculate_f1(precision: float, recall: float) -> float:
    """Calculate F1 score from precision and recall."""
    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)


def calculate_accuracy(correct: int, total: int) -> float:
    """Calculate accuracy percentage."""
    if total == 0:
        return 0.0
    return (correct / total) * 100
