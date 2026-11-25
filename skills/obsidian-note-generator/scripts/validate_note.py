#!/usr/bin/env python3
"""Validate generated Obsidian notes and update drafts against Mastery Framework conventions.

Stdlib-only (Python 3.11+) so the skill remains portable standalone or inside ADK.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_CATEGORIES: tuple[str, ...] = (
    "Cloud Infrastructure",
    "Data Processing",
    "Information Security",
    "Software Engineering",
    "System Resiliency",
    "AI Engineering",
)

VALID_CATEGORY_SLUGS: tuple[str, ...] = (
    "cloud-infrastructure",
    "data-processing",
    "information-security",
    "software-engineering",
    "system-resiliency",
    "ai-engineering",
)

VALID_SOURCE_TYPES: tuple[str, ...] = (
    "youtube",
    "article",
    "documentation",
)

VALID_NOTE_ACTIONS: tuple[str, ...] = (
    "create",
    "update",
)

MAX_TAG_DEPTH = 3
MAX_TAG_SEGMENT_LEN = 22

HIERARCHICAL_TAG_RE = re.compile(
    r"^(" + "|".join(VALID_CATEGORY_SLUGS) + r")/[a-z0-9-]+(/[a-z0-9-]+)*$"
)
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WIKILINK_RE = re.compile(r"^\[\[[^\[\]]+\]\]$")
INLINE_TAG_RE = re.compile(r"(?<!\S)#[a-z][a-z0-9_/-]+")
TASK_CHECKBOX_RE = re.compile(r"^\s*[-*+]\s+\[\s\]\s+")
INLINE_TRIPLE_BACKTICK_RE = re.compile(r"```[^`\n]+```")
CODE_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE_SPAN_RE = re.compile(r"`[^`\n]+`")
RECAP_PHRASING_RE = re.compile(
    r"\b(in this video|the speaker|the presenter|the host explains|"
    r"this video covers|this crash course covers|welcome to this video|"
    r"in this article|this blog post|the author argues|the author explains|"
    r"this post explores|in this documentation|this documentation covers|"
    r"this page describes|click here to get started)\b",
    re.IGNORECASE,
)
CLICKBAIT_FILENAME_RE = re.compile(
    r"\b(crash course|full course|full tutorial|explained in \d+)\b",
    re.IGNORECASE,
)
DISALLOWED_HUB_KEYS = frozenset({"category", "last-studied"})


@dataclass
class ValidationReport:
    path: str
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    frontmatter: dict[str, Any] = field(default_factory=dict)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _parse_simple_yaml(yaml_text: str) -> tuple[dict[str, Any], list[str]]:
    """Parse standard Obsidian YAML frontmatter without external dependencies."""
    data: dict[str, Any] = {}
    errors: list[str] = []
    current_list_key: str | None = None

    for lineno, raw_line in enumerate(yaml_text.splitlines(), start=2):
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if re.match(r"^\s*-\s+", line):
            if current_list_key is None:
                errors.append(f"YAML line {lineno}: list item without parent key: {stripped!r}")
                continue
            item_raw = re.sub(r"^\s*-\s+", "", line, count=1).strip()
            if not item_raw:
                errors.append(f"YAML line {lineno}: empty list item under '{current_list_key}'")
                continue
            if not isinstance(data.get(current_list_key), list):
                data[current_list_key] = []
            data[current_list_key].append(_strip_quotes(item_raw))
            continue

        if ":" not in line or line[0].isspace():
            errors.append(f"YAML line {lineno}: unexpected syntax: {raw_line!r}")
            continue

        key, raw_val = line.split(":", 1)
        key = key.strip()
        val = raw_val.strip()

        if not key:
            errors.append(f"YAML line {lineno}: empty key")
            continue

        if val == "":
            data[key] = []
            current_list_key = key
        elif val.startswith("[") and val.endswith("]") and not val.startswith("[["):
            inner = val[1:-1].strip()
            items = [_strip_quotes(part) for part in inner.split(",") if part.strip()]
            data[key] = items
            current_list_key = None
        else:
            if val.lower() in ("null", "~"):
                data[key] = None
            else:
                data[key] = _strip_quotes(val)
            current_list_key = None

    return data, errors


def _extract_frontmatter(text: str) -> tuple[str | None, str, list[str]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text, ["Missing YAML frontmatter opening '---' on line 1."]

    end_idx: int | None = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break

    if end_idx is None:
        return None, "", ["Unclosed YAML frontmatter: missing closing '---'."]

    fm_text = "\n".join(lines[1:end_idx])
    body_text = "\n".join(lines[end_idx + 1 :])
    return fm_text, body_text, []


def _validate_tags(tags: Any, report: ValidationReport) -> None:
    if not isinstance(tags, list) or len(tags) == 0:
        report.add_error("Frontmatter 'tags' must be a non-empty YAML list.")
        return

    valid_tags: list[str] = []
    for tag in tags:
        if not isinstance(tag, str) or not tag:
            report.add_error(f"Invalid empty/non-string tag: {tag!r}")
            continue
        if tag.startswith("#"):
            report.add_error(f"YAML tag must not start with '#': '{tag}'.")
            continue
        if not HIERARCHICAL_TAG_RE.match(tag):
            report.add_error(
                f"Tag '{tag}' is not a valid hierarchical kebab-case tag "
                "('<pillar>/<domain>[/<topic>]')."
            )
            continue

        segments = tag.split("/")
        if len(segments) > MAX_TAG_DEPTH:
            report.add_error(
                f"Tag '{tag}' has {len(segments)} levels; keep composable tags to 2-{MAX_TAG_DEPTH} levels."
            )
            continue

        # Conciseness checks on Level-2 / Level-3 segments
        for seg in segments[1:]:
            if "-and-" in seg:
                report.add_warning(
                    f"Tag '{tag}' contains verbose '-and-' filler in segment '{seg}'; "
                    "use a concise composable noun."
                )
            elif len(seg) > MAX_TAG_SEGMENT_LEN:
                report.add_warning(
                    f"Tag '{tag}' segment '{seg}' exceeds {MAX_TAG_SEGMENT_LEN} chars; "
                    "keep segments concise and composable."
                )

        valid_tags.append(tag)

    # Check redundant parent + child pairs (e.g. ai-engineering/agents + ai-engineering/agents/mcp)
    tag_set = set(valid_tags)
    for tag in valid_tags:
        parts = tag.split("/")
        for depth in range(2, len(parts)):
            ancestor = "/".join(parts[:depth])
            if ancestor in tag_set:
                report.add_error(
                    f"Redundant parent/child tags '{ancestor}' and '{tag}'; "
                    "keep only the more specific tag (Obsidian matches parent hierarchies automatically)."
                )

    if len(tags) > 3:
        report.add_warning(f"Note has {len(tags)} tags; prefer 1-3 concise composable tags.")


def validate_note(
    note_path: Path,
    *,
    check_category_dir: bool = True,
    strict_warnings: bool = False,
    expected_source_type: str | None = None,
    expected_note_action: str | None = None,
) -> ValidationReport:
    report = ValidationReport(path=str(note_path))

    if not note_path.exists():
        report.add_error(f"File does not exist: {note_path}")
        return report
    if not note_path.is_file():
        report.add_error(f"Path is not a regular file: {note_path}")
        return report

    # 1. Filename & parent directory checks
    if note_path.suffix != ".md":
        report.add_error(f"Filename must end with '.md', got '{note_path.name}'.")

    stem = note_path.stem
    if "_transcript" in stem.lower():
        report.add_error(f"Filename still contains '_transcript': '{note_path.name}'.")
    if "_" in stem:
        report.add_error(f"Filename should use spaces, not underscores: '{note_path.name}'.")
    if CLICKBAIT_FILENAME_RE.search(stem):
        report.add_warning(
            f"Filename '{note_path.name}' appears to retain tutorial/clickbait suffix; "
            "prefer a clean concept title."
        )

    if check_category_dir:
        parent_name = note_path.parent.name
        if parent_name not in VALID_CATEGORIES:
            report.add_error(
                f"Parent directory '{parent_name}' is not a valid Mastery Framework category. "
                f"Expected one of: {', '.join(VALID_CATEGORIES)}."
            )

    # 2. Read UTF-8 content
    try:
        raw_text = note_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        report.add_error(f"File is not valid UTF-8: {exc}")
        return report

    if not raw_text.strip():
        report.add_error("Note file is empty.")
        return report

    # 3. Frontmatter extraction & parsing
    fm_text, body_text, fm_extract_errors = _extract_frontmatter(raw_text)
    for err in fm_extract_errors:
        report.add_error(err)
    if fm_text is None:
        return report

    fm, yaml_errors = _parse_simple_yaml(fm_text)
    report.frontmatter = fm
    for err in yaml_errors:
        report.add_error(err)

    # 4. Validate frontmatter keys & types
    for forbidden in DISALLOWED_HUB_KEYS:
        if forbidden in fm:
            report.add_error(
                f"Frontmatter must not include hub-only key '{forbidden}' on topic notes."
            )

    # note-action (defaults to 'create' if omitted)
    note_action = fm.get("note-action", "create")
    if expected_note_action is not None:
        if note_action != expected_note_action:
            report.add_error(
                f"Frontmatter 'note-action' must be '{expected_note_action}', got {note_action!r}."
            )
    elif note_action not in VALID_NOTE_ACTIONS:
        report.add_error(
            f"Frontmatter 'note-action' must be one of {', '.join(VALID_NOTE_ACTIONS)}, "
            f"got {note_action!r}."
        )

    if note_action == "update":
        if not stem.endswith(" (Update)"):
            report.add_error(
                f"Update draft filename must end with ' (Update).md', got '{note_path.name}'."
            )
        target_note = fm.get("target-note")
        if not isinstance(target_note, str) or not WIKILINK_RE.match(target_note.strip()):
            report.add_error(
                f"Update draft requires 'target-note' as a wikilink (e.g. '[[Existing Note]]'), got {target_note!r}."
            )
        target_path = fm.get("target-path")
        if not isinstance(target_path, str) or not target_path.strip().endswith(".md"):
            report.add_error(
                f"Update draft requires vault-relative 'target-path' ending in '.md', got {target_path!r}."
            )

    # tags
    _validate_tags(fm.get("tags"), report)

    # source
    source = fm.get("source")
    if not isinstance(source, str) or not source.strip():
        report.add_error("Frontmatter 'source' must be a non-empty string.")

    # source-type
    source_type = fm.get("source-type")
    if expected_source_type is not None:
        if source_type != expected_source_type:
            report.add_error(
                f"Frontmatter 'source-type' must be '{expected_source_type}', got {source_type!r}."
            )
    elif source_type not in VALID_SOURCE_TYPES:
        report.add_error(
            f"Frontmatter 'source-type' must be one of {', '.join(VALID_SOURCE_TYPES)}, "
            f"got {source_type!r}."
        )

    # created
    created = fm.get("created")
    if not isinstance(created, str) or not ISO_DATE_RE.match(created):
        report.add_error(
            f"Frontmatter 'created' must be an ISO YYYY-MM-DD date, got {created!r}."
        )
    else:
        try:
            datetime.date.fromisoformat(created)
        except ValueError:
            report.add_error(f"Frontmatter 'created' is not a valid calendar date: '{created}'.")

    # optional aliases
    if "aliases" in fm:
        aliases = fm["aliases"]
        if not isinstance(aliases, list) or not aliases or any(
            not isinstance(a, str) or not a.strip() for a in aliases
        ):
            report.add_error(
                "Frontmatter 'aliases', when present, must be a non-empty list of strings."
            )

    # optional provenance strings
    for opt_key in ("channel", "url", "author", "vendor"):
        if opt_key in fm:
            val = fm[opt_key]
            if not isinstance(val, str) or not val.strip():
                report.add_error(
                    f"Optional frontmatter '{opt_key}' must be non-empty when present (omit if unknown)."
                )

    # optional published date (ISO YYYY-MM-DD)
    if "published" in fm:
        published = fm["published"]
        if not isinstance(published, str) or not ISO_DATE_RE.match(published):
            report.add_error(
                f"Optional frontmatter 'published' must be an ISO YYYY-MM-DD date, got {published!r}."
            )
        else:
            try:
                datetime.date.fromisoformat(published)
            except ValueError:
                report.add_error(
                    f"Optional frontmatter 'published' is not a valid calendar date: '{published}'."
                )

    # 5. Body hygiene checks
    body_lines = body_text.splitlines()
    non_empty_body = [line for line in body_lines if line.strip()]
    if not non_empty_body:
        report.add_error("Note body is empty.")
        return report

    first_line = non_empty_body[0].strip()
    if first_line.startswith("# "):
        h1_title = first_line[2:].strip()
        if h1_title.lower() == stem.lower():
            report.add_error(
                f"Body starts with duplicate H1 matching filename: '{first_line}'. "
                "Start directly with a definition paragraph or callout."
            )
        else:
            report.add_warning(
                f"Body starts with an H1 heading ('{first_line}'); prefer opening with a "
                "concise summary paragraph or callout and using '##' for major sections."
            )

    in_fence = False
    fence_char = ""
    fence_len = 0
    frontmatter_line_offset = len(raw_text.splitlines()) - len(body_lines)

    for rel_idx, line in enumerate(body_lines, start=1):
        abs_lineno = frontmatter_line_offset + rel_idx
        fence_match = CODE_FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
                fence_len = len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_len and line.strip() == marker:
                in_fence = False
                fence_char = ""
                fence_len = 0
            continue

        if in_fence:
            continue

        if INLINE_TRIPLE_BACKTICK_RE.search(line):
            report.add_error(
                f"Line {abs_lineno}: inline triple-backtick span found; use single backticks."
            )

        prose = INLINE_CODE_SPAN_RE.sub("", line)

        if "<mark" in prose.lower():
            report.add_error(f"Line {abs_lineno}: raw HTML '<mark>' tag is disallowed.")

        if "obsidian://open" in prose.lower():
            report.add_error(
                f"Line {abs_lineno}: 'obsidian://open' URI found; use [[Wikilinks]] instead."
            )

        if TASK_CHECKBOX_RE.match(prose):
            report.add_error(
                f"Line {abs_lineno}: dangling task checkbox '- [ ]' leaks into Obsidian Tasks queries."
            )

        if not re.match(r"^\s*#{1,6}\s+", prose):
            prose_no_links = re.sub(r"\[\[[^\]]+\]\]", "", prose)
            prose_no_links = re.sub(r"https?://\S+", "", prose_no_links)
            prose_no_links = re.sub(r"\[[^\]]*\]\([^)]+\)", "", prose_no_links)
            tag_match = INLINE_TAG_RE.search(prose_no_links)
            if tag_match:
                report.add_error(
                    f"Line {abs_lineno}: inline tag '{tag_match.group(0)}' found; "
                    "keep all tags in YAML frontmatter."
                )

        recap_match = RECAP_PHRASING_RE.search(prose)
        if recap_match:
            report.add_warning(
                f"Line {abs_lineno}: recap/meta phrasing detected ('{recap_match.group(0)}'); "
                "rewrite in evergreen technical reference voice."
            )

    if in_fence:
        report.add_error("Unclosed fenced code block detected.")

    if strict_warnings and report.warnings:
        report.valid = False

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a generated Obsidian note or update draft against Mastery Framework conventions."
    )
    parser.add_argument("note_path", type=Path, help="Path to the generated .md note.")
    parser.add_argument(
        "--no-check-category-dir",
        action="store_true",
        help="Skip verifying that the parent folder matches one of the 6 Mastery Framework categories.",
    )
    parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Treat warnings (e.g., recap phrasing or verbose tag segments) as validation failures.",
    )
    parser.add_argument(
        "--source-type",
        choices=VALID_SOURCE_TYPES,
        default=None,
        help="Require a specific frontmatter source-type (youtube, article, or documentation).",
    )
    parser.add_argument(
        "--note-action",
        choices=VALID_NOTE_ACTIONS,
        default=None,
        help="Require a specific frontmatter note-action (create or update).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit validation report as JSON.",
    )
    args = parser.parse_args(argv)

    report = validate_note(
        args.note_path,
        check_category_dir=not args.no_check_category_dir,
        strict_warnings=args.strict_warnings,
        expected_source_type=args.source_type,
        expected_note_action=args.note_action,
    )

    if args.as_json:
        print(
            json.dumps(
                {
                    "path": report.path,
                    "valid": report.valid,
                    "errors": report.errors,
                    "warnings": report.warnings,
                    "frontmatter": report.frontmatter,
                },
                indent=2,
            )
        )
    else:
        status = "PASS" if report.valid else "FAIL"
        print(f"[{status}] {report.path}")
        for err in report.errors:
            print(f"  ERROR: {err}")
        for warn in report.warnings:
            print(f"  WARN:  {warn}")

    return 0 if report.valid else 1


if __name__ == "__main__":
    sys.exit(main())
