"""Guarded read-only vault inspection and validated staging writer tools for ADK."""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from obsidian_note_agent.config import AppConfig, resolve_skill_dir
from obsidian_note_agent.state import StateStore

_MD_HEADING_RE = re.compile(r"^#{1,4}\s+(.+)$", re.MULTILINE)
_MAX_READ_CHARS = 16_000


@dataclass
class ToolRuntimeContext:
    config: AppConfig
    dry_run: bool = False
    output_dir: Path | None = None
    force: bool = False

    @property
    def effective_output_dir(self) -> Path:
        if self.output_dir is not None:
            return self.output_dir.expanduser().resolve()
        return self.config.staging_path


def load_validator_module() -> Any:
    """Load the bundled stdlib validate_note.py module from the unified skill directory."""
    skill_dir = resolve_skill_dir()
    if skill_dir is None:
        raise RuntimeError("Could not locate obsidian-note-generator skill directory.")
    script_path = skill_dir / "scripts" / "validate_note.py"
    if not script_path.is_file():
        raise RuntimeError(f"Validator script missing: {script_path}")

    module_name = "obsidian_note_generator_validator"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load validator module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def read_vault_note_impl(ctx: ToolRuntimeContext, target_path: str) -> dict[str, Any]:
    """Read an existing production or staged note inside vault_path strictly read-only."""
    vault_root = ctx.config.vault.path.expanduser().resolve()
    clean_rel = target_path.strip().lstrip("/")
    if not clean_rel or ".." in Path(clean_rel).parts:
        return {"status": "error", "error": f"Invalid vault-relative target_path: {target_path!r}"}

    candidate = (vault_root / clean_rel).resolve()
    if not candidate.is_relative_to(vault_root):
        return {
            "status": "error",
            "error": f"Security guard: target_path ({target_path}) escapes vault root.",
        }
    if not candidate.is_file():
        return {"status": "error", "error": f"Note not found at {clean_rel}."}

    text = candidate.read_text(encoding="utf-8", errors="ignore")
    headings = [m.group(1).strip() for m in _MD_HEADING_RE.finditer(text)]
    truncated = len(text) > _MAX_READ_CHARS
    return {
        "status": "ok",
        "target_path": candidate.relative_to(vault_root).as_posix(),
        "title": candidate.stem,
        "headings": headings,
        "truncated": truncated,
        "content": text[:_MAX_READ_CHARS],
    }


def stage_obsidian_note_impl(
    ctx: ToolRuntimeContext,
    *,
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
    """Write a new note or update draft strictly inside staging/<Category>/ and validate it."""
    validator = load_validator_module()
    valid_categories: tuple[str, ...] = validator.VALID_CATEGORIES

    clean_category = category.strip()
    if clean_category not in valid_categories:
        return {
            "status": "validation_failed",
            "validation_passed": False,
            "errors": [
                f"Invalid category {clean_category!r}. Must be one of: {', '.join(valid_categories)}."
            ],
            "warnings": [],
        }

    clean_action = note_action.strip().lower() or "create"
    if clean_action not in ("create", "update"):
        return {
            "status": "validation_failed",
            "validation_passed": False,
            "errors": [f"Invalid note_action {clean_action!r}. Must be 'create' or 'update'."],
            "warnings": [],
        }

    clean_title = note_title.strip()
    if clean_title.endswith(".md"):
        clean_title = clean_title[:-3].strip()
    if (
        not clean_title
        or "/" in clean_title
        or "\\" in clean_title
        or ".." in clean_title
        or "\x00" in clean_title
    ):
        return {
            "status": "validation_failed",
            "validation_passed": False,
            "errors": [f"Invalid note_title {note_title!r}; must be a plain Title Case filename stem."],
            "warnings": [],
        }

    if clean_action == "update" and not clean_title.endswith(" (Update)"):
        clean_title = f"{clean_title} (Update)"

    output_dir = ctx.effective_output_dir
    dest_dir = (output_dir / clean_category).resolve()
    dest_path = (dest_dir / f"{clean_title}.md").resolve()

    if not dest_path.is_relative_to(output_dir):
        return {
            "status": "validation_failed",
            "validation_passed": False,
            "errors": [f"Security guard: destination ({dest_path}) escapes staging output_dir."],
            "warnings": [],
        }

    dest_dir.mkdir(parents=True, exist_ok=True)
    normalized_content = markdown_content.rstrip() + "\n"
    dest_path.write_text(normalized_content, encoding="utf-8")

    report = validator.validate_note(
        dest_path,
        check_category_dir=True,
        strict_warnings=ctx.config.agent.strict_validation_warnings,
        expected_source_type=source_type.strip().lower() or None,
        expected_note_action=clean_action,
    )

    if not report.valid:
        # Remove invalid draft so staging/ stays clean if the agent stops
        dest_path.unlink(missing_ok=True)
        return {
            "status": "validation_failed",
            "validation_passed": False,
            "errors": report.errors,
            "warnings": report.warnings,
            "hint": "Fix every listed error and warning, then call stage_obsidian_note again.",
        }

    tags = [str(t) for t in report.frontmatter.get("tags", [])]
    resolved_source_title = source_title.strip() or str(report.frontmatter.get("source", clean_title))
    resolved_target_note = target_note.strip() or (
        str(report.frontmatter.get("target-note", "")) if clean_action == "update" else None
    )

    if not ctx.dry_run and content_sha256.strip():
        with StateStore(ctx.config.state.db_path) as store:
            store.record_completed(
                canonical_url=source_url.strip() or None,
                content_sha256=content_sha256.strip(),
                source_type=source_type.strip().lower(),
                note_action=clean_action,
                target_note=resolved_target_note or None,
                source_title=resolved_source_title,
                recommended_category=clean_category,
                note_title=clean_title,
                output_note_path=dest_path,
                tags=tags,
            )

    return {
        "status": "staged",
        "validation_passed": True,
        "note_action": clean_action,
        "target_note": resolved_target_note or None,
        "category": clean_category,
        "note_title": clean_title,
        "output_path": str(dest_path),
        "tags": tags,
        "dry_run": ctx.dry_run,
    }
