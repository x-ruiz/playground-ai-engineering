"""Cross-platform configuration loading, path resolution, and runtime checks."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


def project_root() -> Path:
    """Return the `obsidian-note-generator/` project root containing pyproject.toml and skills/."""
    candidates: list[Path] = [
        *Path(__file__).resolve().parents[:4],
        Path(sys.prefix).resolve().parent,
        Path.cwd().resolve(),
        (Path.cwd() / "obsidian-note-generator").resolve(),
    ]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if (resolved / "pyproject.toml").is_file() and (resolved / "skills").is_dir():
            return resolved
    return Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    """Return the parent multi-skill repository root."""
    return project_root().parent


def expand_and_resolve(raw: str | Path, *, base_dir: Path) -> Path:
    """Expand env vars and `~`, resolving relative paths against `base_dir`."""
    expanded = os.path.expandvars(str(raw))
    path = Path(expanded).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


class VaultConfig(BaseModel):
    path: Path = Field(default=Path("../../obsidian-notes"))
    staging_dir: Path = Field(default=Path("staging"))
    inventory_rank_threshold: int = Field(default=150, ge=10, le=5000)
    inventory_top_k: int = Field(default=40, ge=5, le=200)


class StateConfig(BaseModel):
    db_path: Path = Field(default=Path("~/.local/state/obsidian-note-agent/state.db"))
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def _uppercase_level(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value


class AgentConfig(BaseModel):
    model: str = "gemini-2.5-flash"
    max_validation_retries: int = Field(default=2, ge=0, le=5)
    strict_validation_warnings: bool = True


class IngestionConfig(BaseModel):
    max_source_chars: int = Field(default=45_000, ge=2_000, le=200_000)
    http_timeout_seconds: float = Field(default=20.0, gt=1.0, le=120.0)
    enable_gemini_video_fallback: bool = False
    enable_url_context_fallback: bool = False


class AppConfig(BaseModel):
    vault: VaultConfig = Field(default_factory=VaultConfig)
    state: StateConfig = Field(default_factory=StateConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)

    @property
    def staging_path(self) -> Path:
        if self.vault.staging_dir.is_absolute():
            return self.vault.staging_dir
        return (self.vault.path / self.vault.staging_dir).resolve()

    def resolve_all_paths(self, *, base_dir: Path) -> AppConfig:
        """Return a copy with all filesystem paths expanded and resolved."""
        data = self.model_dump()
        data["vault"]["path"] = expand_and_resolve(self.vault.path, base_dir=base_dir)
        if self.vault.staging_dir.is_absolute() or str(self.vault.staging_dir).startswith("~"):
            data["vault"]["staging_dir"] = expand_and_resolve(
                self.vault.staging_dir, base_dir=base_dir
            )
        data["state"]["db_path"] = expand_and_resolve(self.state.db_path, base_dir=base_dir)
        return AppConfig.model_validate(data)


def load_project_env() -> Path | None:
    """Load `.env` from CWD or project root if present (never overrides existing env vars)."""
    for candidate in (Path.cwd() / ".env", project_root() / ".env"):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return candidate.resolve()
    return None


def discover_config_file(explicit_path: Path | None = None) -> Path | None:
    """Locate the active config file using the standard lookup precedence."""
    if explicit_path is not None:
        resolved = explicit_path.expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Config file not found: {resolved}")
        return resolved

    env_path = os.environ.get("OBSIDIAN_NOTE_AGENT_CONFIG")
    if env_path:
        resolved = Path(env_path).expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(
                f"Config file referenced by OBSIDIAN_NOTE_AGENT_CONFIG not found: {resolved}"
            )
        return resolved

    candidates = (
        Path.cwd() / "config.yaml",
        project_root() / "config.yaml",
        Path.home() / ".config" / "obsidian-note-agent" / "config.yaml",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def load_config(config_path: Path | None = None) -> tuple[AppConfig, Path | None]:
    """Load, validate, and resolve paths for AppConfig."""
    load_project_env()
    found = discover_config_file(config_path)
    if found is None:
        base_dir = project_root()
        return AppConfig().resolve_all_paths(base_dir=base_dir), None

    raw_text = found.read_text(encoding="utf-8")
    loaded = yaml.safe_load(raw_text)
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {found}")

    config = AppConfig.model_validate(loaded).resolve_all_paths(base_dir=found.parent)
    return config, found


def resolve_skill_dir() -> Path | None:
    """Resolve `skills/obsidian-note-generator/` containing SKILL.md, references/, and scripts/."""
    candidates = (
        project_root() / "skills" / "obsidian-note-generator",
        Path.home() / ".gemini" / "config" / "skills" / "obsidian-note-generator",
    )
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
    """Run diagnostic checks against configured vault, unified skill, and Gemini/Vertex auth."""
    checks: list[EnvCheckResult] = []

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

    skill_dir = resolve_skill_dir()
    if skill_dir is None:
        checks.append(
            EnvCheckResult("skill_dir", "fail", "Unified skill directory (skill/SKILL.md) not found.")
        )
    else:
        missing = [
            rel
            for rel in (
                "SKILL.md",
                "references/vault_conventions.md",
                "references/exemplars.md",
                "scripts/validate_note.py",
            )
            if not (skill_dir / rel).is_file()
        ]
        if missing:
            checks.append(
                EnvCheckResult("skill_dir", "fail", f"Missing skill assets under {skill_dir}: {', '.join(missing)}")
            )
        else:
            checks.append(EnvCheckResult("skill_dir", "ok", str(skill_dir)))

    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in ("1", "true", "yes")
    if use_vertex:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "").strip()
        if project and location:
            checks.append(
                EnvCheckResult("gemini_auth", "ok", f"Vertex AI configured (project={project}, location={location})")
            )
        else:
            checks.append(
                EnvCheckResult(
                    "gemini_auth",
                    "fail",
                    "GOOGLE_GENAI_USE_VERTEXAI=TRUE requires GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION.",
                )
            )
    elif os.environ.get("GOOGLE_API_KEY", "").strip() or os.environ.get("GEMINI_API_KEY", "").strip():
        checks.append(EnvCheckResult("gemini_auth", "ok", "Gemini API key present in environment."))
    else:
        checks.append(
            EnvCheckResult(
                "gemini_auth",
                "warn",
                "No GOOGLE_API_KEY or Vertex AI env vars set. Copy .env.example to .env before running.",
            )
        )

    global_skill = Path.home() / ".gemini" / "config" / "skills" / "obsidian-note-generator"
    if (global_skill / "SKILL.md").is_file():
        checks.append(
            EnvCheckResult("global_skill_install", "ok", f"{global_skill} -> {global_skill.resolve()}")
        )
    else:
        checks.append(
            EnvCheckResult(
                "global_skill_install",
                "warn",
                f"Optional Antigravity symlink not installed at {global_skill}. Run 'python3 scripts/install_skill.py'.",
            )
        )

    return checks
