"""Google ADK root_agent wiring SkillToolset and deterministic ingestion/staging tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

from obsidian_note_agent.config import AppConfig, load_config, resolve_skill_dir
from obsidian_note_agent.models import build_resilient_model
from obsidian_note_agent.tools.ingest_tools import (
    ingest_pasted_text_impl,
    ingest_url_impl,
    list_recent_notes_impl,
)
from obsidian_note_agent.tools.vault_tools import (
    ToolRuntimeContext,
    read_vault_note_impl,
    stage_obsidian_note_impl,
)

_SYSTEM_INSTRUCTION = """You convert YouTube URLs, engineering articles/blogs, technical documentation URLs, or pasted text into evergreen Mastery Framework Obsidian notes (or targeted Update Drafts) staged under `obsidian-notes/staging/<Category>/`.

Follow this token-efficient workflow for every source (process multiple URLs sequentially):
1. Call `ingest_url(url)` (or `ingest_pasted_text(...)` if the user pasted text or a site is paywalled).
   - If `status == "duplicate"`, report the existing staged path and stop unless the user requested `--force` / regeneration.
   - If `status == "error"`, report the exact error cleanly and invite the user to paste the text; never fabricate content.
2. Activate the `obsidian-note-generator` skill and load `references/vault_conventions.md` (load `references/exemplars.md` only if you need a template check).
3. Decide note scope and check `likely_overlap_notes` / `vault_notes` returned by `ingest_url`:
   - Default to 1 atomic note; split into 2-4 cross-linked atomic notes (max 4 unless explicitly requested) ONLY when a source covers genuinely distinct concepts across topics/categories (no thin stubs).
   - For each note, ONLY if an existing note genuinely overlaps that topic, call `read_vault_note(target_path)` to inspect its existing headings/coverage.
   - If it substantially overlaps an existing note, choose `note_action="update"` (draft ONLY net-new additions with explicit target headings; set `note-action: update`, `target-note`, and `target-path` in frontmatter).
   - Otherwise choose `note_action="create"` and reference related existing (and sibling) notes via `[[Wikilinks]]`.
4. Reuse existing tags from `vault_tags` whenever possible and build on existing 2-3 level branches (`<pillar>/<domain>[/<topic>]`, concise segments, zero `-and-` filler, zero redundant parent+child tags, 1-3 tags total).
5. Call `stage_obsidian_note(...)` once per planned note to write and validate strictly inside staging.
   - If `validation_passed` is false, fix every reported error/warning and re-call `stage_obsidian_note(...)` (up to the retry budget).
6. Reply concisely with each staged file's action (`create` or `update`), target note (if update), staged file path, category, tags, and wikilinks.
"""


def build_agent(
    config: AppConfig | None = None,
    *,
    dry_run: bool = False,
    output_dir: Path | None = None,
    force: bool = False,
    model_override: str | None = None,
) -> LlmAgent:
    """Create a configured ADK LlmAgent with SkillToolset and bound deterministic tools."""
    resolved_config = config if config is not None else load_config()[0]
    ctx = ToolRuntimeContext(
        config=resolved_config,
        dry_run=dry_run,
        output_dir=output_dir,
        force=force,
    )

    def ingest_url(url: str, force: bool = False) -> dict[str, Any]:
        """Fetch and clean a YouTube, article, or documentation URL with vault tags, inventory, and overlap hints.

        Args:
            url: Public HTTP/HTTPS URL (YouTube video, technical article/blog, or documentation page).
            force: Set True to bypass SQLite URL/content-hash deduplication and reprocess.
        """
        return ingest_url_impl(ctx, url=url, force=force)

    def ingest_pasted_text(
        text: str,
        title: str,
        source_type: str = "article",
        url: str = "",
        author: str = "",
        channel: str = "",
        vendor: str = "",
        published: str = "",
        force: bool = False,
    ) -> dict[str, Any]:
        """Ingest user-pasted transcript, article, or documentation text (e.g., paywalled pages).

        Args:
            text: Raw source text pasted by the user.
            title: Clean source title.
            source_type: One of 'youtube', 'article', or 'documentation'.
            url: Optional canonical source URL.
            author: Optional article author or blog publication name.
            channel: Optional YouTube channel name.
            vendor: Optional documentation vendor or project name.
            published: Optional publication date in ISO YYYY-MM-DD format.
            force: Set True to bypass content-hash deduplication.
        """
        return ingest_pasted_text_impl(
            ctx,
            text=text,
            title=title,
            source_type=source_type,
            url=url,
            author=author,
            channel=channel,
            vendor=vendor,
            published=published,
            force=force,
        )

    def read_vault_note(target_path: str) -> dict[str, Any]:
        """Read an existing vault or staged note strictly read-only to check overlap before drafting an update.

        Args:
            target_path: Vault-relative path to the `.md` note (as returned in likely_overlap_notes).
        """
        return read_vault_note_impl(ctx, target_path=target_path)

    def stage_obsidian_note(
        category: str,
        note_title: str,
        markdown_content: str,
        source_type: str,
        note_action: str = "create",
        target_note: str = "",
        source_url: str = "",
        source_title: str = "",
        content_sha256: str = "",
    ) -> dict[str, Any]:
        """Write a new Obsidian note or Update Draft inside staging/<Category>/ and run strict validation.

        Args:
            category: Exact Mastery Framework category folder (e.g., 'AI Engineering', 'Data Processing').
            note_title: Clean Title Case concept title (or existing target note title when note_action='update').
            markdown_content: Complete Markdown document starting with valid YAML frontmatter.
            source_type: One of 'youtube', 'article', or 'documentation'.
            note_action: 'create' for a new note, or 'update' for a staged Update Draft targeting an existing note.
            target_note: Wikilink to the existing note (e.g., '[[Modern AI Architecture]]') when note_action='update'.
            source_url: Canonical source URL from ingest_url (for SQLite history).
            source_title: Original source title from ingest_url (for SQLite history).
            content_sha256: SHA-256 content hash from ingest_url (for SQLite deduplication).
        """
        return stage_obsidian_note_impl(
            ctx,
            category=category,
            note_title=note_title,
            markdown_content=markdown_content,
            source_type=source_type,
            note_action=note_action,
            target_note=target_note,
            source_url=source_url,
            source_title=source_title,
            content_sha256=content_sha256,
        )

    def list_recent_notes(limit: int = 15) -> dict[str, Any]:
        """List recent generated notes and update drafts recorded in the SQLite ledger.

        Args:
            limit: Maximum number of recent entries to return (1-100).
        """
        return list_recent_notes_impl(ctx, limit=limit)

    skill_dir = resolve_skill_dir()
    if skill_dir is None:
        raise RuntimeError(
            "Unified skill directory not found (expected skills/obsidian-note-generator/SKILL.md)."
        )

    obsidian_skill = load_skill_from_dir(skill_dir)
    skill_tools = SkillToolset(skills=[obsidian_skill])

    model = build_resilient_model(resolved_config, model_override=model_override)
    return LlmAgent(
        name="obsidian_note_agent",
        model=model,
        description=(
            "Generates evergreen Mastery Framework Obsidian notes or targeted Update Drafts "
            "from YouTube, article, and technical documentation URLs."
        ),
        instruction=_SYSTEM_INSTRUCTION,
        tools=[
            skill_tools,
            ingest_url,
            ingest_pasted_text,
            read_vault_note,
            stage_obsidian_note,
            list_recent_notes,
        ],
    )


root_agent = build_agent()
