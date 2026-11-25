"""Shared async ADK runner helpers for obsidian_note_agent."""

from __future__ import annotations

from pathlib import Path

from google.adk.runners import InMemoryRunner
from google.genai import types

from obsidian_note_agent.agent import build_agent
from obsidian_note_agent.config import load_config


async def _execute_prompt(
    prompt: str,
    *,
    config_path: Path | None = None,
    env_file: Path | None = None,
    dry_run: bool = False,
    output_dir: Path | None = None,
    force: bool = False,
    model: str | None = None,
    user_id: str = "agent-user",
) -> str:
    config, _ = load_config(config_path, env_file=env_file)
    agent = build_agent(
        config,
        dry_run=dry_run,
        output_dir=output_dir,
        force=force,
        model_override=model or None,
    )
    runner = InMemoryRunner(agent=agent, app_name="obsidian_note_agent")
    try:
        session = await runner.session_service.create_session(
            app_name="obsidian_note_agent",
            user_id=user_id,
        )
        final_chunks: list[str] = []
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=prompt)]),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if getattr(part, "text", None):
                        final_chunks.append(part.text)
        return "\n".join(final_chunks).strip()
    finally:
        await runner.close()


async def run_urls_async(
    urls: list[str],
    *,
    config_path: Path | None = None,
    env_file: Path | None = None,
    dry_run: bool = False,
    output_dir: Path | None = None,
    force: bool = False,
    model: str | None = None,
    user_id: str = "cli-user",
) -> str:
    """Run obsidian_note_agent end-to-end on one or more URLs and return the final summary."""
    cleaned_urls = [u.strip() for u in urls if u and u.strip()]
    if not cleaned_urls:
        raise ValueError("At least one non-empty URL is required.")

    url_lines = "\n".join(f"- {u}" for u in cleaned_urls)
    force_clause = " Force regeneration even if already processed." if force else ""
    prompt = (
        f"Generate staged Obsidian note(s) or Update Draft(s) for the following URL(s):{force_clause}\n"
        f"{url_lines}"
    )
    return await _execute_prompt(
        prompt,
        config_path=config_path,
        env_file=env_file,
        dry_run=dry_run,
        output_dir=output_dir,
        force=force,
        model=model,
        user_id=user_id,
    )


async def run_pasted_text_async(
    *,
    text: str,
    title: str,
    source_type: str = "article",
    url: str = "",
    config_path: Path | None = None,
    env_file: Path | None = None,
    dry_run: bool = False,
    output_dir: Path | None = None,
    force: bool = False,
    model: str | None = None,
    user_id: str = "agent-user",
) -> str:
    """Run obsidian_note_agent end-to-end on pasted source text (e.g., paywalled articles)."""
    cleaned_text = text.strip()
    if not cleaned_text:
        raise ValueError("Source text cannot be empty.")

    meta_lines = [
        f"Title: {title.strip() or 'Untitled Source'}",
        f"Source type: {source_type.strip().lower() or 'article'}",
    ]
    if url.strip():
        meta_lines.append(f"URL: {url.strip()}")
    force_clause = " Force regeneration even if already processed." if force else ""

    prompt = (
        "Use `ingest_pasted_text` with the source metadata and text below, then generate and stage "
        f"an Obsidian note or Update Draft.{force_clause}\n\n"
        + "\n".join(meta_lines)
        + f"\n\nSource text:\n{cleaned_text}"
    )
    return await _execute_prompt(
        prompt,
        config_path=config_path,
        env_file=env_file,
        dry_run=dry_run,
        output_dir=output_dir,
        force=force,
        model=model,
        user_id=user_id,
    )
