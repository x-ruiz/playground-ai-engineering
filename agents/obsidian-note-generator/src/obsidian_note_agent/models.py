"""Resilient Gemini LLM wrapper with exponential backoff retries and fallback models."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from google.adk.models.google_llm import Gemini
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from google.genai.errors import APIError
from pydantic import Field

from obsidian_note_agent.config import AppConfig

logger = logging.getLogger("obsidian_note_agent.models")

_RETRYABLE_ERROR_CODES = frozenset({"429", "500", "503", "504", "UNAVAILABLE", "RESOURCE_EXHAUSTED"})


def _is_retryable_exception(exc: Exception, retry_status_codes: set[int]) -> bool:
    code = getattr(exc, "code", None)
    if isinstance(code, int) and code in retry_status_codes:
        return True
    status = str(getattr(exc, "status", "") or "").upper()
    if status in _RETRYABLE_ERROR_CODES:
        return True
    if isinstance(exc, APIError):
        msg = str(exc).upper()
        if any(token in msg for token in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
            return True
    return False


def _is_retryable_response(resp: LlmResponse, retry_status_codes: set[int]) -> bool:
    if not resp.error_code:
        return False
    code_str = str(resp.error_code).strip().upper()
    if code_str in _RETRYABLE_ERROR_CODES:
        return True
    return code_str.isdigit() and int(code_str) in retry_status_codes


class ResilientGemini(Gemini):
    """ADK Gemini model supporting HTTP exponential backoff retries and ordered fallback models."""

    fallback_models: list[str] = Field(default_factory=list)
    retry_status_codes: list[int] = Field(default_factory=lambda: [429, 500, 503, 504])

    def _candidate_models(self, primary: str) -> list[str]:
        ordered: list[str] = []
        for name in [primary, *self.fallback_models]:
            cleaned = name.strip()
            if cleaned and cleaned not in ordered:
                ordered.append(cleaned)
        return ordered

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        primary = llm_request.model or self.model
        candidates = self._candidate_models(primary)
        retry_codes = set(self.retry_status_codes)

        for idx, candidate in enumerate(candidates):
            has_next = idx < len(candidates) - 1
            next_model = candidates[idx + 1] if has_next else None

            config_copy = llm_request.config.model_copy(deep=True) if llm_request.config else None
            attempt_request = llm_request.model_copy(
                update={"model": candidate, "config": config_copy}
            )

            yielded_any = False
            fallback_triggered = False
            try:
                async for resp in super().generate_content_async(attempt_request, stream=stream):
                    if (
                        not yielded_any
                        and has_next
                        and _is_retryable_response(resp, retry_codes)
                    ):
                        logger.warning(
                            "Model '%s' returned transient error (%s: %s); falling back to '%s'",
                            candidate,
                            resp.error_code,
                            resp.error_message,
                            next_model,
                        )
                        fallback_triggered = True
                        break
                    yielded_any = True
                    yield resp
            except Exception as exc:
                if (
                    not yielded_any
                    and has_next
                    and _is_retryable_exception(exc, retry_codes)
                ):
                    logger.warning(
                        "Model '%s' failed with transient error (%s); falling back to '%s'",
                        candidate,
                        exc,
                        next_model,
                    )
                    continue
                raise

            if not fallback_triggered:
                return


def build_resilient_model(
    config: AppConfig,
    *,
    model_override: str | None = None,
) -> ResilientGemini:
    """Construct a ResilientGemini configured from AppConfig.agent retry & fallback settings."""
    primary = (model_override or config.agent.model).strip()
    retry_cfg = config.agent.retry
    retry_options = types.HttpRetryOptions(
        attempts=retry_cfg.attempts,
        initial_delay=retry_cfg.initial_delay,
        max_delay=retry_cfg.max_delay,
        exp_base=retry_cfg.exp_base,
        jitter=retry_cfg.jitter,
        http_status_codes=list(retry_cfg.http_status_codes),
    )
    return ResilientGemini(
        model=primary,
        retry_options=retry_options,
        fallback_models=list(config.agent.fallback_models),
        retry_status_codes=list(retry_cfg.http_status_codes),
    )
