"""Shared dataclasses for the runner package."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentRecord:
    """One agent execution against one BfclCase.

    `calls` is in BFCL's prediction shape: list of {func_name: {param: value}}.
    `error` is set only when the agent loop raised — calls is [] in that case.
    """
    calls: list[dict] = field(default_factory=list)
    tokens_used: int = 0
    latency_seconds: float = 0.0
    cost_usd: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "calls": self.calls,
            "tokens_used": self.tokens_used,
            "latency_seconds": self.latency_seconds,
            "cost_usd": self.cost_usd,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentRecord":
        return cls(
            calls=data.get("calls", []),
            tokens_used=int(data.get("tokens_used", 0)),
            latency_seconds=float(data.get("latency_seconds", 0.0)),
            cost_usd=float(data.get("cost_usd", 0.0)),
            error=data.get("error"),
        )


@dataclass
class ModelResult:
    """Per-model aggregate after evaluation."""
    model_id: str
    per_case: list[dict] = field(default_factory=list)  # from evaluator results.json
    accuracy: float = 0.0
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    agent_errors: int = 0


@dataclass
class MultiModelResults:
    run_id: str
    models: list[ModelResult] = field(default_factory=list)
    cases_evaluated: int = 0
    partial: bool = False
    reason: str | None = None
