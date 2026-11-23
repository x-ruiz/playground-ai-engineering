#!/usr/bin/env python3
"""Cross-platform (macOS + Linux) symlink manager for all Antigravity skills in this repository.

Auto-discovers every skill directory containing a `SKILL.md` file—both top-level
`<repo_root>/<skill-name>/SKILL.md` and grouped project packages under
`<repo_root>/<project>/skills/<skill-name>/SKILL.md`—and symlinks each into
`~/.gemini/config/skills/<skill-name>` so Antigravity CLI (`agy`), IDE, and
Desktop App discover all skills automatically.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_target_skills_dir() -> Path:
    return Path.home() / ".gemini" / "config" / "skills"


def discover_skills(root: Path) -> list[Path]:
    """Return sorted skill directories containing a SKILL.md file.

    Supports both top-level `<repo>/<skill>/SKILL.md` and grouped project
    packages `<repo>/<project>/skills/<skill>/SKILL.md`.
    """
    skills: list[Path] = []
    seen_names: dict[str, Path] = {}

    def _register(candidate: Path) -> None:
        if not (candidate / "SKILL.md").is_file():
            return
        if candidate.name in seen_names:
            raise ValueError(
                f"Duplicate skill name '{candidate.name}' found at "
                f"{seen_names[candidate.name]} and {candidate}"
            )
        seen_names[candidate.name] = candidate
        skills.append(candidate)

    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "SKILL.md").is_file():
            _register(child)
        nested_skills_dir = child / "skills"
        if nested_skills_dir.is_dir():
            for nested in sorted(nested_skills_dir.iterdir()):
                if nested.is_dir() and not nested.name.startswith("."):
                    _register(nested)
    return sorted(skills, key=lambda p: p.name)


def resolve_selected_skills(root: Path, requested: list[str]) -> tuple[list[Path], list[str]]:
    discovered = {p.name: p for p in discover_skills(root)}
    if not requested:
        return list(discovered.values()), []

    selected: list[Path] = []
    missing: list[str] = []
    for name in requested:
        if name in discovered:
            selected.append(discovered[name])
        else:
            missing.append(name)
    return selected, missing


def check_install(source: Path, target: Path) -> int:
    if not (source / "SKILL.md").is_file():
        print(f"[FAIL] Source skill missing SKILL.md: {source}", file=sys.stderr)
        return 1
    if not target.exists() and not target.is_symlink():
        print(f"[FAIL] {source.name}: not installed at {target}", file=sys.stderr)
        return 1
    if not target.is_symlink():
        print(f"[FAIL] {source.name}: target exists but is not a symlink ({target})", file=sys.stderr)
        return 1

    resolved = target.resolve()
    if resolved != source.resolve():
        print(
            f"[FAIL] {source.name}: symlink points to {resolved}, expected {source.resolve()}",
            file=sys.stderr,
        )
        return 1

    if not (target / "SKILL.md").is_file():
        print(f"[FAIL] {source.name}: symlink target does not expose SKILL.md", file=sys.stderr)
        return 1

    print(f"[OK] {target} -> {resolved}")
    return 0


def install_skill(source: Path, target: Path, *, force: bool = False) -> int:
    source = source.resolve()
    if not (source / "SKILL.md").is_file():
        print(f"[ERROR] Source skill directory is missing SKILL.md: {source}", file=sys.stderr)
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)

    if target.is_symlink():
        if target.exists() and target.resolve() == source:
            print(f"[OK] Already installed: {target} -> {source}")
            return 0
        if not force:
            print(
                f"[ERROR] {source.name}: existing symlink points elsewhere ({target.readlink()}). "
                "Re-run with --force to replace.",
                file=sys.stderr,
            )
            return 1
        target.unlink()
    elif target.exists():
        print(
            f"[ERROR] {source.name}: refusing to overwrite non-symlink path: {target}. "
            "Move or remove it manually first.",
            file=sys.stderr,
        )
        return 1

    target.symlink_to(source, target_is_directory=True)
    print(f"[INSTALLED] {target} -> {source}")
    return 0


def uninstall_skill(skill_name: str, target: Path) -> int:
    if target.is_symlink():
        target.unlink()
        print(f"[REMOVED] {target}")
        return 0
    if not target.exists():
        print(f"[OK] {skill_name}: not installed ({target})")
        return 0
    print(
        f"[ERROR] {skill_name}: refusing to remove non-symlink path: {target}",
        file=sys.stderr,
    )
    return 1


def list_skills(root: Path, target_dir: Path) -> int:
    skills = discover_skills(root)
    if not skills:
        print(f"No skills found under {root}")
        return 0
    for skill in skills:
        target = target_dir / skill.name
        if target.is_symlink() and target.exists() and target.resolve() == skill.resolve():
            status = "installed"
        elif target.is_symlink():
            status = f"stale symlink -> {target.readlink()}"
        elif target.exists():
            status = "conflict (non-symlink)"
        else:
            status = "not installed"
        print(f"- {skill.name} [{status}]")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install, verify, or uninstall Antigravity skills from this repository."
    )
    parser.add_argument(
        "skills",
        nargs="*",
        help="Optional skill folder names to target (defaults to all discovered skills).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=repo_root(),
        help="Repository root directory containing <skill-name>/SKILL.md folders.",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=default_target_skills_dir(),
        help="Global Antigravity skills directory (default: ~/.gemini/config/skills).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="List discovered skills and status.")
    mode.add_argument("--check", action="store_true", help="Verify installation status.")
    mode.add_argument("--uninstall", action="store_true", help="Remove installed symlinks.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing symlinks if they point elsewhere or are broken.",
    )
    args = parser.parse_args(argv)

    root = args.root.expanduser().resolve()
    target_dir = args.target_dir.expanduser()

    if args.list:
        return list_skills(root, target_dir)

    selected, missing = resolve_selected_skills(root, args.skills)
    if missing:
        print(
            f"[ERROR] Unknown skill(s) (missing <name>/SKILL.md under {root}): {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1
    if not selected:
        print(f"[ERROR] No skill directories containing SKILL.md found under {root}", file=sys.stderr)
        return 1

    exit_code = 0
    for skill_dir in selected:
        target = target_dir / skill_dir.name
        if args.check:
            rc = check_install(skill_dir, target)
        elif args.uninstall:
            rc = uninstall_skill(skill_dir.name, target)
        else:
            rc = install_skill(skill_dir, target, force=args.force)
        if rc != 0:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
