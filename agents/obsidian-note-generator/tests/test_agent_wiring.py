"""Tests verifying Google ADK root_agent, SkillToolset, retry_options, and fallback models."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import patch

import pytest
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.skill_toolset import SkillToolset
from google.genai import types
from google.genai.errors import APIError

from obsidian_note_agent import root_agent
from obsidian_note_agent.agent import build_agent
from obsidian_note_agent.config import AppConfig
from obsidian_note_agent.models import ResilientGemini, build_resilient_model


def test_root_agent_loads_skill_toolset_resilient_model_and_tools(tmp_path: Path) -> None:
    cfg = AppConfig.model_validate(
        {
            "vault": {"path": str(tmp_path / "vault")},
            "state": {"db_path": str(tmp_path / "state.db")},
            "agent": {
                "model": "gemini-2.5-flash",
                "fallback_models": ["gemini-2.5-flash-lite", "gemini-2.5-pro"],
                "retry": {"attempts": 5, "initial_delay": 1.5, "http_status_codes": [429, 503]},
            },
        }
    )
    agent = build_agent(cfg, dry_run=True, output_dir=tmp_path / "preview")

    assert agent.name == "obsidian_note_agent"
    assert isinstance(agent.model, ResilientGemini)
    assert agent.model.model == "gemini-2.5-flash"
    assert agent.model.fallback_models == ["gemini-2.5-flash-lite", "gemini-2.5-pro"]
    assert agent.model.retry_options is not None
    assert agent.model.retry_options.attempts == 5
    assert agent.model.retry_options.initial_delay == 1.5
    assert agent.model.retry_options.http_status_codes == [429, 503]
    assert root_agent.name == "obsidian_note_agent"

    toolsets = [t for t in agent.tools if isinstance(t, SkillToolset)]
    assert len(toolsets) == 1

    callable_names = {getattr(t, "__name__", "") for t in agent.tools if callable(t)}
    assert {
        "ingest_url",
        "ingest_pasted_text",
        "read_vault_note",
        "stage_obsidian_note",
        "list_recent_notes",
    }.issubset(callable_names)


def test_resilient_gemini_falls_back_on_503_exception_and_error_response() -> None:
    cfg = AppConfig.model_validate(
        {
            "agent": {
                "model": "gemini-2.5-flash",
                "fallback_models": ["gemini-2.5-flash-lite", "gemini-2.5-pro"],
            }
        }
    )
    model = build_resilient_model(cfg)
    seen_models: list[str] = []

    async def fake_super_generate(
        _self: ResilientGemini, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        assert llm_request.model is not None
        seen_models.append(llm_request.model)
        if llm_request.model == "gemini-2.5-flash":
            raise APIError(503, {"error": {"code": 503, "status": "UNAVAILABLE", "message": "busy"}})
        if llm_request.model == "gemini-2.5-flash-lite":
            yield LlmResponse(error_code="UNAVAILABLE", error_message="503 UNAVAILABLE")
            return
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part.from_text(text="ok from pro")])
        )

    async def _run() -> list[LlmResponse]:
        req = LlmRequest(model="gemini-2.5-flash", contents=[])
        results: list[LlmResponse] = []
        with patch(
            "google.adk.models.google_llm.Gemini.generate_content_async",
            new=fake_super_generate,
        ):
            async for item in model.generate_content_async(req):
                results.append(item)
        return results

    outputs = asyncio.run(_run())
    assert seen_models == ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]
    assert len(outputs) == 1
    assert outputs[0].content is not None
    assert outputs[0].content.parts is not None
    assert outputs[0].content.parts[0].text == "ok from pro"


def test_resilient_gemini_does_not_fallback_on_non_retryable_400() -> None:
    cfg = AppConfig.model_validate(
        {
            "agent": {
                "model": "gemini-2.5-flash",
                "fallback_models": ["gemini-2.5-pro"],
            }
        }
    )
    model = build_resilient_model(cfg)
    seen_models: list[str] = []

    async def fake_super_generate(
        _self: ResilientGemini, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        assert llm_request.model is not None
        seen_models.append(llm_request.model)
        raise APIError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "bad"}})
        yield  # pragma: no cover

    async def _run() -> None:
        req = LlmRequest(model="gemini-2.5-flash", contents=[])
        with patch(
            "google.adk.models.google_llm.Gemini.generate_content_async",
            new=fake_super_generate,
        ):
            async for _ in model.generate_content_async(req):
                pass

    with pytest.raises(APIError):
        asyncio.run(_run())
    assert seen_models == ["gemini-2.5-flash"]
