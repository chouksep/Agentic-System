"""Anthropic SDK wrapper with agentic tool loop and rate limiting."""
from __future__ import annotations

import anthropic

from ci_wiki.config import Config
from ci_wiki.llm.tools import ToolCall, ToolDispatcher
from ci_wiki.utils.ratelimit import RateLimiter

_ESTIMATE_TOKENS_PER_WORD = 1.3


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text.split()) * _ESTIMATE_TOKENS_PER_WORD))


class LLMClient:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self._rate_limiter = RateLimiter(
            rpm=config.rate_limit_rpm,
            tpm=config.rate_limit_tpm,
        )

    def complete(
        self,
        system: str | list[dict],
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
        use_thinking: bool = False,
    ) -> anthropic.types.Message:
        """Single-turn completion (no tool loop)."""
        max_tokens = max_tokens or self._config.max_tokens
        estimated = _estimate_tokens(str(messages))
        self._rate_limiter.acquire_request(estimated_tokens=estimated)

        kwargs: dict = {
            "model": self._config.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        # System prompt: support both string and list (for prompt caching)
        if isinstance(system, list):
            kwargs["system"] = system
        else:
            # Wrap in cache-enabled block
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        if tools:
            kwargs["tools"] = tools

        if use_thinking:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": 5000}

        response = self._client.messages.create(**kwargs)
        actual_tokens = response.usage.input_tokens + response.usage.output_tokens
        self._rate_limiter.record_actual_tokens(estimated, actual_tokens)
        return response

    def complete_with_tools(
        self,
        system: str | list[dict],
        initial_user_message: str,
        tools: list[dict],
        dispatcher: ToolDispatcher,
        max_iterations: int = 10,
        use_thinking: bool = False,
    ) -> tuple[str, int]:
        """Run the agentic tool loop until end_turn or max_iterations.

        Returns:
            (final_text, total_tokens_used)
        """
        messages: list[dict] = [{"role": "user", "content": initial_user_message}]
        total_tokens = 0
        final_text = ""

        for iteration in range(max_iterations):
            response = self.complete(
                system=system,
                messages=messages,
                tools=tools,
                use_thinking=use_thinking,
            )
            total_tokens += response.usage.input_tokens + response.usage.output_tokens

            # Collect assistant message content
            assistant_content = []
            tool_calls: list[ToolCall] = []

            for block in response.content:
                assistant_content.append(block)
                if block.type == "tool_use":
                    tool_calls.append(ToolCall(block))
                elif block.type == "text":
                    final_text = block.text

            # Append assistant turn
            messages.append({"role": "assistant", "content": assistant_content})

            if response.stop_reason == "end_turn" or not tool_calls:
                break

            # Execute tool calls and build tool_result messages
            tool_results = []
            for tc in tool_calls:
                result_text = dispatcher.dispatch(tc)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": result_text,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        return final_text, total_tokens

    def stream_complete(
        self,
        system: str | list[dict],
        messages: list[dict],
    ) -> str:
        """Stream a response to stdout and return the full text."""
        import sys
        estimated = _estimate_tokens(str(messages))
        self._rate_limiter.acquire_request(estimated_tokens=estimated)

        if isinstance(system, str):
            system_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        else:
            system_blocks = system

        full_text = ""
        with self._client.messages.stream(
            model=self._config.model,
            max_tokens=self._config.max_tokens,
            system=system_blocks,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                sys.stdout.write(text)
                sys.stdout.flush()
                full_text += text
        sys.stdout.write("\n")
        return full_text
