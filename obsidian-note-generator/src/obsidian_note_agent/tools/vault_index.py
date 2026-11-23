"""Read-only vault + staging indexer for wikilinks, live tag tree, and overlap detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_EXCLUDED_DIRS = frozenset({"misc", ".obsidian", ".git"})
_BLOCK_LIST_RE = re.compile(r"^{key}:\s*\n((?:\s+-\s+.+\n?)+)", re.MULTILINE)
_INLINE_LIST_RE = re.compile(r"^{key}:\s*\[([^\]]+)\]", re.MULTILINE)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "for", "of", "to", "in", "on", "with", "vs",
        "what", "how", "why", "is", "are", "you", "your", "need", "know", "about",
        "guide", "overview", "introduction", "intro", "documentation", "docs",
        "tutorial", "course", "crash", "explained", "building", "using", "modern",
    }
)


@dataclass(frozen=True)
class IndexedNote:
    title: str
    rel_path: str
    category: str
    location: str  # "vault" or "staging"
    aliases: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class OverlapCandidate:
    title: str
    rel_path: str
    category: str
    location: str
    score: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class VaultSnapshot:
    notes: tuple[IndexedNote, ...]
    live_tags: tuple[str, ...]

    def format_inventory(
        self,
        *,
        query_text: str = "",
        rank_threshold: int = 150,
        top_k: int = 40,
    ) -> list[str]:
        """Return compact `Title [staging] (aliases: ...)` lines, top-K ranked above threshold."""
        selected = list(self.notes)
        if len(selected) > rank_threshold and query_text.strip():
            query_tokens = _tokenize(query_text)
            scored = sorted(
                selected,
                key=lambda n: (_note_overlap_score(n, query_tokens)[0], n.title.lower()),
                reverse=True,
            )
            selected = scored[:top_k]

        lines: list[str] = []
        for note in selected:
            parts = [note.title]
            if note.location == "staging":
                parts.append("[staged]")
            if note.aliases:
                parts.append(f"(aliases: {', '.join(note.aliases)})")
            lines.append(" ".join(parts))
        return lines

    def find_likely_overlaps(
        self,
        *,
        title: str,
        headings: list[str] | None = None,
        top_n: int = 3,
        min_score: float = 0.28,
    ) -> list[OverlapCandidate]:
        """Deterministically rank existing production and staged notes that may overlap."""
        query_parts = [title, *(headings or [])[:10]]
        query_tokens = _tokenize(" ".join(query_parts))
        title_tokens = _tokenize(title)
        if not query_tokens:
            return []

        candidates: list[OverlapCandidate] = []
        for note in self.notes:
            # Give extra weight to direct title-to-title/alias matches
            score_all, terms_all = _note_overlap_score(note, query_tokens)
            score_title, terms_title = _note_overlap_score(note, title_tokens)
            score = max(score_title, score_all * 0.85)
            matched = terms_title if score_title >= score_all * 0.85 else terms_all
            if score >= min_score and matched:
                candidates.append(
                    OverlapCandidate(
                        title=note.title,
                        rel_path=note.rel_path,
                        category=note.category,
                        location=note.location,
                        score=round(score, 3),
                        matched_terms=tuple(sorted(matched)),
                    )
                )

        candidates.sort(key=lambda c: (c.score, c.location == "vault", c.title), reverse=True)
        return candidates[:top_n]


def _tokenize(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if len(t) >= 2 and t not in _STOPWORDS}


def _note_overlap_score(note: IndexedNote, query_tokens: set[str]) -> tuple[float, set[str]]:
    if not query_tokens:
        return 0.0, set()
    note_tokens = _tokenize(" ".join([note.title, *note.aliases]))
    if not note_tokens:
        return 0.0, set()
    shared = note_tokens & query_tokens
    if not shared:
        return 0.0, set()
    # Dice-like coverage favoring complete match of the shorter note title
    coverage_note = len(shared) / len(note_tokens)
    coverage_query = len(shared) / len(query_tokens)
    score = 0.65 * coverage_note + 0.35 * coverage_query
    return score, shared


def _extract_yaml_list(frontmatter: str, key: str) -> list[str]:
    inline_re = re.compile(_INLINE_LIST_RE.pattern.format(key=re.escape(key)), re.MULTILINE)
    inline = inline_re.search(frontmatter)
    if inline:
        return [item.strip().strip("'\"") for item in inline.group(1).split(",") if item.strip()]

    block_re = re.compile(_BLOCK_LIST_RE.pattern.format(key=re.escape(key)), re.MULTILINE)
    block = block_re.search(frontmatter)
    if block:
        items: list[str] = []
        for line in block.group(1).splitlines():
            cleaned = re.sub(r"^\s*-\s+", "", line).strip().strip("'\"")
            if cleaned:
                items.append(cleaned)
        return items
    return []


def _extract_frontmatter_metadata(note_path: Path) -> tuple[list[str], list[str]]:
    try:
        head = note_path.read_text(encoding="utf-8", errors="ignore")[:2048]
    except OSError:
        return [], []
    if not head.startswith("---"):
        return [], []
    end_idx = head.find("\n---", 3)
    if end_idx == -1:
        return [], []
    fm = head[3:end_idx]
    aliases = _extract_yaml_list(fm, "aliases")
    tags = _extract_yaml_list(fm, "tags")
    return aliases, tags


def scan_vault_state(vault_path: Path, *, staging_dir: Path | None = None) -> VaultSnapshot:
    """Read-only scan of production vault notes + staged notes for inventory, tags, and overlap."""
    resolved_vault = vault_path.expanduser().resolve()
    if not resolved_vault.is_dir():
        return VaultSnapshot(notes=(), live_tags=())

    resolved_staging = (
        staging_dir.expanduser().resolve()
        if staging_dir is not None
        else (resolved_vault / "staging").resolve()
    )

    notes: list[IndexedNote] = []
    hierarchical_tags: set[str] = set()

    for path in sorted(resolved_vault.rglob("*.md")):
        try:
            rel = path.relative_to(resolved_vault)
        except ValueError:
            continue
        rel_parts = rel.parts
        if any(part in _EXCLUDED_DIRS or part.startswith(".") for part in rel_parts[:-1]):
            continue
        if path.name.lower() == "readme.md":
            continue
        # Skip existing update draft files so they aren't treated as standalone target notes
        if path.stem.endswith(" (Update)"):
            continue

        is_staged = path.resolve().is_relative_to(resolved_staging)
        location = "staging" if is_staged else "vault"

        if is_staged:
            try:
                staged_rel = path.resolve().relative_to(resolved_staging).parts
                category = staged_rel[0] if len(staged_rel) >= 2 else ""
            except ValueError:
                category = ""
        else:
            category = rel_parts[0] if len(rel_parts) >= 2 else ""

        # Skip category hub MOC files (e.g. Software Engineering/Software Engineering.md)
        if category and path.stem == category:
            continue

        aliases, tags = _extract_frontmatter_metadata(path)
        for tag in tags:
            cleaned = tag.lstrip("#").strip()
            # Only surface hierarchical tags (pillar/domain[/topic]) in the reusable tag tree
            if "/" in cleaned:
                hierarchical_tags.add(cleaned)

        notes.append(
            IndexedNote(
                title=path.stem,
                rel_path=rel.as_posix(),
                category=category,
                location=location,
                aliases=tuple(aliases),
                tags=tuple(tags),
            )
        )

    return VaultSnapshot(notes=tuple(notes), live_tags=tuple(sorted(hierarchical_tags)))
