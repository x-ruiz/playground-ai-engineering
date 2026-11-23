"""Cross-platform configuration loading, path resolution, and runtime checks."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

DEFAULT_AGY_FALLBACK_PATHS: tuple[Path, ...] = (
    Path("/opt/homebrew/bin/agy"),
    Path("/usr/local/bin/agy"),
    Path.home() / ".local" / "bin" / "agy",
)


def skill_project_root() -> Path:
    """Return the `obsidian-youtube-note/` directory containing pyproject.toml and SKILL.md."""
    candidates: list[Path] = [
        *Path(__file__).resolve().parents[:4],
        Path(sys.prefix).resolve().parent,
        Path.cwd().resolve(),
        (Path.cwd() / "obsidian-youtube-note").resolve(),
        Path.home() / ".gemini" / "config" / "skills" / "obsidian-youtube-note",
    ]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if (resolved / "SKILL.md").is_file():
            return resolved
    return Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    """Return the parent multi-skill repository root."""
    return skill_project_root().parent


def expand_and_resolve(raw: str | Path, *, base_dir: Path) -> Path:
    """Expand env vars and `~`, resolving relative paths against `base_dir`."""
    expanded = os.path.expandvars(str(raw))
    path = Path(expanded).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


class WatchConfig(BaseModel):
    path: Path = Field(default=Path("~/Downloads"))
    recursive: bool = False
    allowed_extensions: list[str] = Field(default_factory=lambda: [".txt", ".md", ".srt", ".vtt"])
    debounce_ms: int = Field(default=500, ge=50, le=30_000)
    stability_checks: int = Field(default=2, ge=1, le=20)
    stability_timeout_seconds: float = Field(default=15.0, gt=0.0, le=300.0)

    @field_validator("allowed_extensions")
    @classmethod
    def _normalize_extensions(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for ext in value:
            cleaned = ext.strip().lower()
            if not cleaned:
                continue
            if not cleaned.startswith("."):
                cleaned = f".{cleaned}"
            normalized.append(cleaned)
        return normalized


class VaultConfig(BaseModel):
    path: Path = Field(default=Path("../../obsidian-notes"))
    staging_dir: Path = Field(default=Path("staging"))


class StateConfig(BaseModel):
    db_path: Path = Field(default=Path("~/.local/state/yt-to-obsidian/state.db"))
    log_file: Path = Field(default=Path("~/.local/state/yt-to-obsidian/logs/yt-to-obsidian.log"))
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def _uppercase_level(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value


class PostProcessConfig(BaseModel):
    action: Literal["keep", "move"] = "keep"
    archive_dir: Path = Field(default=Path("~/Downloads/processed-transcripts"))


class RunnerConfig(BaseModel):
    backend: Literal["agy-cli"] = "agy-cli"
    agy_binary: Path | None = None
    skill_name: str = "obsidian-youtube-note"
    skill_dir: Path | None = None
    model: str | None = None
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None
    timeout_seconds: int = Field(default=300, ge=15, le=3600)
    max_retries: int = Field(default=1, ge=0, le=5)
    strict_validation_warnings: bool = True


class NotificationConfig(BaseModel):
    enabled: bool = True


class AppConfig(BaseModel):
    watch: WatchConfig = Field(default_factory=WatchConfig)
    vault: VaultConfig = Field(default_factory=VaultConfig)
    state: StateConfig = Field(default_factory=StateConfig)
    post_process: PostProcessConfig = Field(default_factory=PostProcessConfig)
    runner: RunnerConfig = Field(default_factory=RunnerConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)

    @property
    def staging_path(self) -> Path:
        if self.vault.staging_dir.is_absolute():
            return self.vault.staging_dir
        return (self.vault.path / self.vault.staging_dir).resolve()

    def resolve_all_paths(self, *, base_dir: Path) -> AppConfig:
        """Return a copy with all filesystem paths expanded and resolved."""
        data = self.model_dump()
        data["watch"]["path"] = expand_and_resolve(self.watch.path, base_dir=base_dir)
        data["vault"]["path"] = expand_and_resolve(self.vault.path, base_dir=base_dir)
        if self.vault.staging_dir.is_absolute() or str(self.vault.staging_dir).startswith("~"):
            data["vault"]["staging_dir"] = expand_and_resolve(
                self.vault.staging_dir, base_dir=base_dir
            )
        data["state"]["db_path"] = expand_and_resolve(self.state.db_path, base_dir=base_dir)
        data["state"]["log_file"] = expand_and_resolve(self.state.log_file, base_dir=base_dir)
        data["post_process"]["archive_dir"] = expand_and_resolve(
            self.post_process.archive_dir, base_dir=base_dir
        )
        if self.runner.agy_binary is not None:
            data["runner"]["agy_binary"] = expand_and_resolve(
                self.runner.agy_binary, base_dir=base_dir
            )
        if self.runner.skill_dir is not None:
            data["runner"]["skill_dir"] = expand_and_resolve(
                self.runner.skill_dir, base_dir=base_dir
            )
        return AppConfig.model_validate(data)


def discover_config_file(explicit_path: Path | None = None) -> Path | None:
    """Locate the active config file using the standard lookup precedence."""
    if explicit_path is not None:
        resolved = explicit_path.expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Config file not found: {resolved}")
        return resolved

    env_path = os.environ.get("YT_TO_OBSIDIAN_CONFIG")
    if env_path:
        resolved = Path(env_path).expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(
                f"Config file referenced by YT_TO_OBSIDIAN_CONFIG not found: {resolved}"
            )
        return resolved

    candidates = (
        Path.cwd() / "config.yaml",
        skill_project_root() / "config.yaml",
        Path.home() / ".config" / "yt-to-obsidian" / "config.yaml",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def load_config(config_path: Path | None = None) -> tuple[AppConfig, Path | None]:
    """Load, validate, and resolve paths for AppConfig."""
    found = discover_config_file(config_path)
    if found is None:
        base_dir = skill_project_root()
        return AppConfig().resolve_all_paths(base_dir=base_dir), None

    raw_text = found.read_text(encoding="utf-8")
    loaded = yaml.safe_load(raw_text)
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {found}")

    config = AppConfig.model_validate(loaded).resolve_all_paths(base_dir=found.parent)
    return config, found


def resolve_agy_binary(config: AppConfig) -> Path | None:
    """Locate the `agy` CLI executable via explicit config, PATH, or standard install paths."""
    if config.runner.agy_binary is not None:
        candidate = config.runner.agy_binary
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
        return None

    from_path = shutil.which("agy")
    if from_path:
        return Path(from_path).resolve()

    for fallback in DEFAULT_AGY_FALLBACK_PATHS:
        expanded = fallback.expanduser()
        if expanded.is_file() and os.access(expanded, os.X_OK):
            return expanded.resolve()
    return None


def resolve_skill_dir(config: AppConfig) -> Path | None:
    """Resolve the skill directory containing SKILL.md, output_schema.json, and validate_note.py."""
    candidates: list[Path] = []
    if config.runner.skill_dir is not None:
        candidates.append(config.runner.skill_dir)
    else:
        candidates.append(skill_project_root())
        candidates.append(Path.home() / ".gemini" / "config" / "skills" / config.runner.skill_name)

    for candidate in candidates:
        if (candidate / "SKILL.md").is_file():
            return candidate.resolve()
    return None


@dataclass(frozen=True)
class EnvCheckResult:
    name: str
    status: Literal["ok", "warn", "fail"]
    detail: str


def validate_runtime_environment(config: AppConfig) -> list[EnvCheckResult]:
    """Run diagnostic checks against configured directories, `agy`, and skill assets."""
    checks: list[EnvCheckResult] = []

    # Watch directory
    if config.watch.path.is_dir():
        checks.append(EnvCheckResult("watch.path", "ok", str(config.watch.path)))
    else:
        checks.append(
            EnvCheckResult("watch.path", "fail", f"Directory does not exist: {config.watch.path}")
        )

    # Vault directory
    if config.vault.path.is_dir():
        if (config.vault.path / "README.md").is_file():
            checks.append(EnvCheckResult("vault.path", "ok", str(config.vault.path)))
        else:
            checks.append(
                EnvCheckResult(
                    "vault.path",
                    "warn",
                    f"Directory exists but README.md not found: {config.vault.path}",
                )
            )
    else:
        checks.append(
            EnvCheckResult("vault.path", "fail", f"Vault directory does not exist: {config.vault.path}")
        )

    # agy binary
    agy_bin = resolve_agy_binary(config)
    if agy_bin is not None:
        checks.append(EnvCheckResult("runner.agy_binary", "ok", str(agy_bin)))
    else:
        checks.append(
            EnvCheckResult(
                "runner.agy_binary",
                "fail",
                "Could not find executable 'agy' on PATH or standard locations.",
            )
        )

    # Skill directory and assets
    skill_dir = resolve_skill_dir(config)
    if skill_dir is None:
        checks.append(
            EnvCheckResult(
                "runner.skill_dir",
                "fail",
                f"Skill '{config.runner.skill_name}' not found (missing SKILL.md).",
            )
        )
    else:
        missing_assets = [
            rel
            for rel in (
                "SKILL.md",
                "references/vault_conventions.md",
                "resources/output_schema.json",
                "scripts/validate_note.py",
            )
            if not (skill_dir / rel).is_file()
        ]
        if missing_assets:
            checks.append(
                EnvCheckResult(
                    "runner.skill_dir",
                    "fail",
                    f"Missing skill assets under {skill_dir}: {', '.join(missing_assets)}",
                )
            )
        else:
            checks.append(EnvCheckResult("runner.skill_dir", "ok", str(skill_dir)))

    # Global skill symlink discovery check
    global_skill = Path.home() / ".gemini" / "config" / "skills" / config.runner.skill_name
    if (global_skill / "SKILL.md").is_file():
        checks.append(
            EnvCheckResult("global_skill_install", "ok", f"{global_skill} -> {global_skill.resolve()}")
        )
    else:
        checks.append(
            EnvCheckResult(
                "global_skill_install",
                "warn",
                f"Not installed at {global_skill}. Run 'yt-to-obsidian install-skill'.",
            )
        )

    # Post-process archive directory check
    if config.post_process.action == "move":
        if config.post_process.archive_dir.is_dir():
            checks.append(
                EnvCheckResult("post_process.archive_dir", "ok", str(config.post_process.archive_dir))
            )
        else:
            checks.append(
                EnvCheckResult(
                    "post_process.archive_dir",
                    "warn",
                    f"Will be created on first move: {config.post_process.archive_dir}",
                )
            )

    return checks
