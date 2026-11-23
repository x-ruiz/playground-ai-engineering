"""AgentRunner protocol and zero-shell least-privilege AgyCliRunner implementation."""

from __future__ import annotations

import datetime
import importlib.util
import json
import logging
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from yt_to_obsidian.config import AppConfig, resolve_agy_binary, resolve_skill_dir
from yt_to_obsidian.parser import TranscriptDocument

logger = logging.getLogger("yt_to_obsidian.runner")

_EXCLUDED_VAULT_DIRS = frozenset({"misc", ".obsidian", ".git", "staging"})
_ALIAS_BLOCK_RE = re.compile(r"^aliases:\s*\n((?:\s+-\s+.+\n?)+)", re.MULTILINE)
_ALIAS_INLINE_RE = re.compile(r"^aliases:\s*\[([^\]]+)\]", re.MULTILINE)


class RunnerError(RuntimeError):
    """Raised when the headless agent runner fails to produce a valid note."""


@dataclass(frozen=True)
class RunRequest:
    transcript: TranscriptDocument
    output_dir: Path
    vault_path: Path
    dry_run: bool = False
    model_override: str | None = None
    effort_override: str | None = None


@dataclass(frozen=True)
class RunResult:
    status: str
    recommended_category: str
    note_title: str
    output_path: Path
    tags: list[str]
    aliases: list[str] = field(default_factory=list)
    existing_wikilinks: list[str] = field(default_factory=list)
    overlapping_notes: list[str] = field(default_factory=list)
    validation_passed: bool = False
    summary: str = ""
    duration_seconds: float = 0.0
    attempts: int = 1
    raw_stdout: str = ""
    raw_stderr: str = ""


class AgentRunner(Protocol):
    """Abstract interface allowing drop-in swap between CLI and future SDK runners."""

    def run(self, request: RunRequest) -> RunResult: ...


def _extract_aliases_from_note(note_path: Path) -> list[str]:
    try:
        head = note_path.read_text(encoding="utf-8", errors="ignore")[:1024]
    except OSError:
        return []
    if not head.startswith("---"):
        return []
    end_idx = head.find("\n---", 3)
    if end_idx == -1:
        return []
    fm = head[3:end_idx]
    inline = _ALIAS_INLINE_RE.search(fm)
    if inline:
        return [a.strip().strip("'\"") for a in inline.group(1).split(",") if a.strip()]
    block = _ALIAS_BLOCK_RE.search(fm)
    if block:
        aliases: list[str] = []
        for line in block.group(1).splitlines():
            cleaned = re.sub(r"^\s*-\s+", "", line).strip().strip("'\"")
            if cleaned:
                aliases.append(cleaned)
        return aliases
    return []


def scan_vault_inventory(vault_path: Path) -> list[str]:
    """Read-only scan of existing Obsidian note titles (and aliases) for wikilink discovery."""
    if not vault_path.is_dir():
        return []

    notes: list[str] = []
    for path in sorted(vault_path.rglob("*.md")):
        rel_parts = path.relative_to(vault_path).parts
        if any(part in _EXCLUDED_VAULT_DIRS or part.startswith(".") for part in rel_parts[:-1]):
            continue
        if path.name.lower() == "readme.md":
            continue
        aliases = _extract_aliases_from_note(path)
        if aliases:
            notes.append(f"{path.stem} (aliases: {', '.join(aliases)})")
        else:
            notes.append(path.stem)
    return notes


def load_note_validator(skill_dir: Path) -> Any:
    """Dynamically load `validate_note` from the skill's bundled validator script."""
    script_path = skill_dir / "scripts" / "validate_note.py"
    if not script_path.is_file():
        raise RunnerError(f"Skill validator script not found: {script_path}")

    module_name = "obsidian_youtube_note_validator"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RunnerError(f"Could not load validator module from: {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.validate_note


def _parse_agy_json_output(stdout: str) -> dict[str, Any]:
    """Parse structured JSON payload from `agy -p --output-format json` stdout."""
    text = stdout.strip()
    if not text:
        raise RunnerError("agy CLI produced empty stdout.")

    # Handle any stray leading non-JSON log lines before the final JSON object
    envelope: dict[str, Any] | None = None
    try:
        envelope = json.loads(text)
    except json.JSONDecodeError:
        for line in reversed(text.splitlines()):
            line_stripped = line.strip()
            if line_stripped.startswith("{") and line_stripped.endswith("}"):
                try:
                    envelope = json.loads(line_stripped)
                    break
                except json.JSONDecodeError:
                    continue

    if not isinstance(envelope, dict):
        raise RunnerError(f"Could not parse JSON envelope from agy output: {text[:400]!r}")

    denied = envelope.get("denied_actions")
    if denied and not envelope.get("structured_output") and not envelope.get("response"):
        raise RunnerError(f"agy CLI denied required actions in headless mode: {denied}")

    structured = envelope.get("structured_output")
    if isinstance(structured, dict):
        return structured

    response = envelope.get("response")
    if isinstance(response, str) and response.strip():
        # Try direct parse or extract last JSON object from response string
        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}\s*$", response, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    pass

    raise RunnerError(
        f"agy JSON output did not contain a valid structured_output payload: {text[:400]!r}"
    )


class AgyCliRunner:
    """Headless `agy -p` runner operating with zero shell permissions (`--mode accept-edits`)."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def _build_prompt(
        self,
        *,
        transcript_file: Path,
        request: RunRequest,
        vault_notes: list[str],
        today_iso: str,
        retry_feedback: str | None = None,
    ) -> str:
        inventory_block = (
            "\n".join(f"- {entry}" for entry in vault_notes)
            if vault_notes
            else "(no existing notes found)"
        )
        parts = [
            f"Use the {self.config.runner.skill_name} skill to convert the YouTube transcript at "
            f"{transcript_file} (fallback_title: \"{request.transcript.fallback_title}\") "
            "into a staged Obsidian note.",
            f"Use vault_path={request.vault_path} strictly READ-ONLY for context; "
            "do NOT create, edit, or delete any file inside vault_path outside output_dir, "
            "and NEVER run git commands.",
            f"Write the generated note ONLY inside output_dir={request.output_dir} at "
            "<output_dir>/<Recommended Category>/<Note Title>.md.",
            f"Today's date for frontmatter `created` is {today_iso}.",
            "Pre-scanned read-only inventory of existing notes in obsidian-notes for [[Wikilinks]] "
            f"and overlap detection:\n{inventory_block}",
            "Do NOT execute any Bash/shell commands (use only built-in file reading and writing "
            "tools; the caller executes validate_note.py --strict-warnings deterministically after "
            "you finish).",
            "Return the final JSON result matching output_schema.json.",
        ]
        if retry_feedback:
            parts.append(
                "PREVIOUS ATTEMPT FAILED VALIDATION. Fix every issue below and rewrite the note:\n"
                f"{retry_feedback}"
            )
        return "\n\n".join(parts)

    def _build_command(
        self,
        *,
        agy_bin: Path,
        prompt: str,
        vault_path: Path,
        output_dir: Path,
        temp_transcript_dir: Path,
        schema_path: Path,
        model: str | None,
        effort: str | None,
    ) -> list[str]:
        cmd = [
            str(agy_bin),
            "-p",
            prompt,
            "--add-dir",
            str(vault_path),
            "--add-dir",
            str(output_dir),
            "--add-dir",
            str(temp_transcript_dir),
            "--mode",
            "accept-edits",
            "--output-format",
            "json",
            "--json-schema",
            str(schema_path),
            "--print-timeout",
            f"{self.config.runner.timeout_seconds}s",
        ]
        if model:
            cmd.extend(["--model", model])
        if effort:
            cmd.extend(["--effort", effort])
        return cmd

    def run(self, request: RunRequest) -> RunResult:
        agy_bin = resolve_agy_binary(self.config)
        if agy_bin is None:
            raise RunnerError("Could not locate executable 'agy' binary.")

        skill_dir = resolve_skill_dir(self.config)
        if skill_dir is None:
            raise RunnerError(f"Could not locate skill directory for '{self.config.runner.skill_name}'.")

        schema_path = skill_dir / "resources" / "output_schema.json"
        if not schema_path.is_file():
            raise RunnerError(f"Missing skill output schema: {schema_path}")

        validate_note = load_note_validator(skill_dir)

        output_dir = request.output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        vault_path = request.vault_path.expanduser().resolve()
        vault_notes = scan_vault_inventory(vault_path)
        today_iso = datetime.date.today().isoformat()

        model = request.model_override or self.config.runner.model
        effort = request.effort_override or self.config.runner.effort
        max_attempts = 1 + self.config.runner.max_retries

        last_error: str = "Unknown runner failure"
        retry_feedback: str | None = None
        started_at = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="yt-to-obsidian-input-") as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str).resolve()
            normalized_file = tmp_dir / request.transcript.source_path.name
            normalized_file.write_text(request.transcript.render_for_agent(), encoding="utf-8")

            for attempt in range(1, max_attempts + 1):
                prompt = self._build_prompt(
                    transcript_file=normalized_file,
                    request=request,
                    vault_notes=vault_notes,
                    today_iso=today_iso,
                    retry_feedback=retry_feedback,
                )
                cmd = self._build_command(
                    agy_bin=agy_bin,
                    prompt=prompt,
                    vault_path=vault_path,
                    output_dir=output_dir,
                    temp_transcript_dir=tmp_dir,
                    schema_path=schema_path,
                    model=model,
                    effort=effort,
                )
                logger.info(
                    "Invoking agy CLI (attempt %d/%d) for '%s'",
                    attempt,
                    max_attempts,
                    request.transcript.fallback_title,
                )
                try:
                    proc = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=self.config.runner.timeout_seconds + 30,
                        check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    last_error = f"agy CLI timed out after {self.config.runner.timeout_seconds}s"
                    logger.warning("%s (attempt %d/%d)", last_error, attempt, max_attempts)
                    retry_feedback = None
                    if attempt == max_attempts:
                        raise RunnerError(last_error) from exc
                    continue

                if proc.returncode != 0:
                    last_error = (
                        f"agy CLI exited with code {proc.returncode}: "
                        f"{(proc.stderr or proc.stdout).strip()[:500]}"
                    )
                    logger.warning("%s (attempt %d/%d)", last_error, attempt, max_attempts)
                    retry_feedback = None
                    if attempt == max_attempts:
                        raise RunnerError(last_error)
                    continue

                try:
                    payload = _parse_agy_json_output(proc.stdout)
                except RunnerError as exc:
                    last_error = str(exc)
                    logger.warning("%s (attempt %d/%d)", last_error, attempt, max_attempts)
                    retry_feedback = None
                    if attempt == max_attempts:
                        raise
                    continue

                if payload.get("status") != "created":
                    last_error = f"Agent reported status={payload.get('status')!r}: {payload.get('summary', '')}"
                    logger.warning("%s (attempt %d/%d)", last_error, attempt, max_attempts)
                    retry_feedback = last_error
                    if attempt == max_attempts:
                        raise RunnerError(last_error)
                    continue

                raw_output_path = payload.get("output_path")
                if not isinstance(raw_output_path, str) or not raw_output_path.strip():
                    last_error = "Agent response missing valid 'output_path'."
                    if attempt == max_attempts:
                        raise RunnerError(last_error)
                    retry_feedback = last_error
                    continue

                output_path = Path(raw_output_path).expanduser().resolve()
                if not output_path.is_relative_to(output_dir):
                    raise RunnerError(
                        f"Security guard: agent output_path ({output_path}) is outside "
                        f"configured output_dir ({output_dir})."
                    )

                report = validate_note(
                    output_path,
                    check_category_dir=True,
                    strict_warnings=self.config.runner.strict_validation_warnings,
                )
                if not report.valid:
                    issues = [*(f"ERROR: {e}" for e in report.errors), *(f"WARN: {w}" for w in report.warnings)]
                    last_error = "Generated note failed validate_note.py:\n" + "\n".join(issues)
                    logger.warning("%s (attempt %d/%d)", last_error, attempt, max_attempts)
                    retry_feedback = "\n".join(issues)
                    if attempt == max_attempts:
                        raise RunnerError(last_error)
                    continue

                duration = time.monotonic() - started_at
                return RunResult(
                    status="created",
                    recommended_category=str(payload["recommended_category"]),
                    note_title=str(payload["note_title"]),
                    output_path=output_path,
                    tags=[str(t) for t in payload.get("tags", [])],
                    aliases=[str(a) for a in payload.get("aliases", [])],
                    existing_wikilinks=[str(w) for w in payload.get("existing_wikilinks", [])],
                    overlapping_notes=[str(o) for o in payload.get("overlapping_notes", [])],
                    validation_passed=True,
                    summary=str(payload.get("summary", "")),
                    duration_seconds=round(duration, 2),
                    attempts=attempt,
                    raw_stdout=proc.stdout,
                    raw_stderr=proc.stderr,
                )

        raise RunnerError(last_error)
