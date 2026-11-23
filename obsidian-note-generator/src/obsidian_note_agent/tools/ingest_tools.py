"""Compound URL/text ingestion and history tools minimizing ADK agent round-trips."""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import asdict
from typing import Any

from obsidian_note_agent.fetchers.classifier import canonicalize_url, classify_url
from obsidian_note_agent.fetchers.web import fetch_web
from obsidian_note_agent.fetchers.youtube import FetchedSource, FetchError, _cap_text, fetch_youtube
from obsidian_note_agent.state import StateStore
from obsidian_note_agent.tools.vault_index import scan_vault_state
from obsidian_note_agent.tools.vault_tools import ToolRuntimeContext


def _build_compound_payload(ctx: ToolRuntimeContext, fetched: FetchedSource) -> dict[str, Any]:
    """Bundle fetched source + live vault tag tree + inventory + overlap hints in one response."""
    snapshot = scan_vault_state(ctx.config.vault.path, staging_dir=ctx.config.staging_path)
    query_text = " ".join([fetched.title, *fetched.headings])
    vault_notes = snapshot.format_inventory(
        query_text=query_text,
        rank_threshold=ctx.config.vault.inventory_rank_threshold,
        top_k=ctx.config.vault.inventory_top_k,
    )
    overlaps = [
        asdict(c)
        for c in snapshot.find_likely_overlaps(
            title=fetched.title,
            headings=list(fetched.headings),
            top_n=3,
        )
    ]

    provenance: dict[str, str] = {"source": fetched.title, "source_type": fetched.source_type}
    if fetched.canonical_url:
        provenance["url"] = fetched.canonical_url
    if fetched.channel:
        provenance["channel"] = fetched.channel
    if fetched.author:
        provenance["author"] = fetched.author
    if fetched.vendor:
        provenance["vendor"] = fetched.vendor
    if fetched.published:
        provenance["published"] = fetched.published

    return {
        "status": "ok",
        "today_iso": datetime.date.today().isoformat(),
        "provenance": provenance,
        "content_sha256": fetched.content_sha256,
        "truncated": fetched.truncated,
        "extraction_method": fetched.extraction_method,
        "vault_tags": list(snapshot.live_tags),
        "vault_notes": vault_notes,
        "likely_overlap_notes": overlaps,
        "content": fetched.cleaned_text,
    }


def ingest_url_impl(ctx: ToolRuntimeContext, url: str, force: bool = False) -> dict[str, Any]:
    """Canonicalize, deduplicate, classify, fetch URL, and attach vault context in one call."""
    effective_force = force or ctx.force
    canonical = canonicalize_url(url)
    source_type = classify_url(canonical)

    if not effective_force and not ctx.dry_run:
        with StateStore(ctx.config.state.db_path) as store:
            existing = store.get_completed_by_url(canonical)
        if existing is not None:
            return {
                "status": "duplicate",
                "canonical_url": canonical,
                "existing_output_path": existing.output_note_path,
                "existing_note_action": existing.note_action,
                "existing_note_title": existing.note_title,
                "message": (
                    f"URL already processed into {existing.output_note_path}. "
                    "Pass force=True to regenerate."
                ),
            }

    ing = ctx.config.ingestion
    try:
        if source_type == "youtube":
            fetched = fetch_youtube(
                canonical,
                max_chars=ing.max_source_chars,
                timeout=ing.http_timeout_seconds,
                enable_gemini_video_fallback=ing.enable_gemini_video_fallback,
                model=ctx.config.agent.model,
            )
        else:
            fetched = fetch_web(
                canonical,
                source_type=source_type,
                max_chars=ing.max_source_chars,
                timeout=ing.http_timeout_seconds,
                enable_url_context_fallback=ing.enable_url_context_fallback,
                model=ctx.config.agent.model,
            )
    except FetchError as exc:
        return {
            "status": "error",
            "canonical_url": canonical,
            "source_type": source_type,
            "error": str(exc),
        }

    if not effective_force and not ctx.dry_run:
        with StateStore(ctx.config.state.db_path) as store:
            existing_hash = store.get_completed_by_hash(fetched.content_sha256)
        if existing_hash is not None:
            return {
                "status": "duplicate",
                "canonical_url": canonical,
                "existing_output_path": existing_hash.output_note_path,
                "existing_note_action": existing_hash.note_action,
                "existing_note_title": existing_hash.note_title,
                "message": (
                    f"Identical content already processed into {existing_hash.output_note_path}. "
                    "Pass force=True to regenerate."
                ),
            }

    return _build_compound_payload(ctx, fetched)


def ingest_pasted_text_impl(
    ctx: ToolRuntimeContext,
    *,
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
    """Ingest user-pasted transcript, article, or documentation text (e.g., paywalled sources)."""
    cleaned = text.strip()
    if not cleaned:
        return {"status": "error", "error": "Pasted text is empty."}

    norm_type = source_type.strip().lower()
    if norm_type not in ("youtube", "article", "documentation"):
        norm_type = "article"

    sha256 = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    effective_force = force or ctx.force
    if not effective_force and not ctx.dry_run:
        with StateStore(ctx.config.state.db_path) as store:
            existing = store.get_completed_by_hash(sha256)
        if existing is not None:
            return {
                "status": "duplicate",
                "existing_output_path": existing.output_note_path,
                "existing_note_title": existing.note_title,
                "message": (
                    f"Identical pasted content already processed into {existing.output_note_path}. "
                    "Pass force=True to regenerate."
                ),
            }

    bounded, truncated = _cap_text(cleaned, max_chars=ctx.config.ingestion.max_source_chars)
    fetched = FetchedSource(
        canonical_url=canonicalize_url(url) if url.strip() else "",
        source_type=norm_type,
        title=title.strip() or "Untitled Source",
        cleaned_text=bounded,
        content_sha256=sha256,
        truncated=truncated,
        channel=channel.strip() or None,
        author=author.strip() or None,
        vendor=vendor.strip() or None,
        published=published.strip() or None,
        extraction_method="pasted-text",
    )
    return _build_compound_payload(ctx, fetched)


def list_recent_notes_impl(ctx: ToolRuntimeContext, limit: int = 15) -> dict[str, Any]:
    """Return recent note generation runs from the SQLite ledger."""
    bounded_limit = max(1, min(limit, 100))
    with StateStore(ctx.config.state.db_path) as store:
        records = store.list_recent(limit=bounded_limit)
    return {
        "status": "ok",
        "count": len(records),
        "runs": [
            {
                "id": r.id,
                "updated_at": r.updated_at,
                "status": r.status,
                "source_type": r.source_type,
                "note_action": r.note_action,
                "target_note": r.target_note,
                "category": r.recommended_category,
                "note_title": r.note_title,
                "output_path": r.output_note_path,
                "tags": r.tags,
                "url": r.canonical_url,
            }
            for r in records
        ],
    }
