#!/usr/bin/env python3
"""Validate Mermaid diagrams against the Obsidian Violet theme and Staff-grade hygiene rules.

Stdlib-only (Python 3.11+) so the skill remains portable standalone, in Antigravity,
in Claude Code, or inside ADK toolsets.

Supports:
  - Markdown files containing one or more ```mermaid fenced blocks
  - Raw .mmd diagram files
  - Standard input (`-`)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APPROVED_PALETTE: frozenset[str] = frozenset(
    {
        # Obsidian Blacks & Charcoal Surfaces
        "#09090B",
        "#0F0F14",
        "#111116",
        "#16141F",
        "#18181B",
        "#1E1B2E",
        "#27272A",
        # Graphite Greys & High-Contrast Typography
        "#3F3F46",
        "#52525B",
        "#6B7280",
        "#71717A",
        "#A1A1AA",
        "#D4D4D8",
        "#E4E4E7",
        "#F4F4F5",
        # Imperial Violet, Vivid Purple, Lavender & Orchid
        "#2E1065",
        "#3B0764",
        "#4C1D95",
        "#6D28D9",
        "#7C3AED",
        "#8B5CF6",
        "#9333EA",
        "#A855F7",
        "#C084FC",
        "#C4B5FD",
        "#D8B4FE",
        "#E879F9",
        "#EDE9FE",
        "#F5F3FF",
        "#FAF5FF",
    }
)

DARK_CANVAS_SURFACES: frozenset[str] = frozenset(
    {
        "#09090B",
        "#0F0F14",
        "#111116",
        "#16141F",
        "#18181B",
    }
)

UNIVERSAL_DIAGRAM_TYPES: tuple[str, ...] = (
    "flowchart",
    "sequenceDiagram",
    "stateDiagram-v2",
    "erDiagram",
    "classDiagram",
)

LEGACY_OR_FRAGILE_TYPES: tuple[str, ...] = (
    "graph",
    "stateDiagram",
    "architecture-beta",
    "block-beta",
    "c4Context",
    "c4Container",
    "c4Component",
    "c4Dynamic",
    "c4Deployment",
    "zenuml",
    "mindmap",
    "timeline",
    "sankey-beta",
    "xychart-beta",
)

RESERVED_NODE_IDS: frozenset[str] = frozenset(
    {
        "end",
        "subgraph",
        "class",
        "style",
        "click",
        "default",
        "graph",
        "flowchart",
        "linkStyle",
        "classDef",
        "direction",
    }
)

MAX_FLOWCHART_NODES = 22
MAX_LABEL_LINES = 4
MAX_LABEL_CHARS = 160
MIN_EDGES_FOR_LABEL_RATIO = 6
MIN_LABELED_EDGE_RATIO = 0.40

INIT_BLOCK_RE = re.compile(r"%%\{\s*init\s*:(.*?)\}%%", re.DOTALL)
HEX_COLOR_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")
RAW_HTML_RE = re.compile(r"<\s*/?\s*(br|b|i|u|strong|em|small|span|div|font|p|code|hr)\b[^>]*>", re.IGNORECASE)
SUBGRAPH_RE = re.compile(r"^\s*subgraph\s+(.+?)\s*$")
EXPLICIT_SUBGRAPH_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_-]*\s*\[\s*"[^"]+"\s*\]$')
CLASSDEF_RE = re.compile(r"^\s*classDef\s+([A-Za-z_][A-Za-z0-9_-]*)\s+(.+)$")
CLASS_ASSIGN_RE = re.compile(r"^\s*class\s+([A-Za-z0-9_,\s-]+?)\s+([A-Za-z_][A-Za-z0-9_-]*)\s*$")
INLINE_CLASS_RE = re.compile(r":::[A-Za-z_][A-Za-z0-9_-]*")

# Matches flowchart node declarations with quoted labels or unquoted labels
FLOWCHART_NODE_DECL_RE = re.compile(
    r"""
    (?<![A-Za-z0-9_-])
    (?P<id>[A-Za-z_][A-Za-z0-9_-]*)
    (?P<open>\(\[|\[\(|\[\[|\(\(|\{\{|\(|\[|\{)
    (?P<body>.*?)
    (?P<close>\]\)|\)\]|\]\]|\)\)|\}\}|\)|\]|\})
    """,
    re.VERBOSE,
)

FLOWCHART_EDGE_RE = re.compile(
    r"""
    (?P<arrow><-->|==>|-.->|-->|---|-\.-|===|--o|--x|o--o|x--x)
    (?:\s*\|(?P<pipe_label>[^|]+)\|)?
    """,
    re.VERBOSE,
)

FLOWCHART_INLINE_EDGE_LABEL_RE = re.compile(r"--\s+\"?.+?\"?\s+-->|==\s+\"?.+?\"?\s+==>|-\.\s+\"?.+?\"?\s+\.->")

SEQ_BLOCK_OPEN_RE = re.compile(r"^\s*(alt|opt|loop|par|critical|break|rect|box)\b")
SEQ_MESSAGE_RE = re.compile(r"^\s*[A-Za-z0-9_.\"-]+\s*(->>|-->>|->|-->|-x|--x|-\)|--\))\s*[+-]?[A-Za-z0-9_.\"-]+\s*:")


@dataclass
class DiagramBlock:
    index: int
    start_line: int
    content: str


@dataclass
class BlockReport:
    block_index: int
    start_line: int
    diagram_type: str = "unknown"
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def extract_mermaid_blocks(text: str, *, is_markdown: bool) -> list[DiagramBlock]:
    """Extract ```mermaid blocks from Markdown or treat full text as one diagram."""
    if not is_markdown:
        stripped = text.strip()
        return [DiagramBlock(index=1, start_line=1, content=stripped)] if stripped else []

    blocks: list[DiagramBlock] = []
    lines = text.splitlines()
    in_mermaid = False
    fence_char = ""
    fence_len = 0
    buf: list[str] = []
    start_line = 0

    for lineno, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if not in_mermaid:
            match = re.match(r"^(`{3,}|~{3,})\s*mermaid\b.*$", stripped, re.IGNORECASE)
            if match:
                in_mermaid = True
                fence_token = match.group(1)
                fence_char = fence_token[0]
                fence_len = len(fence_token)
                buf = []
                start_line = lineno + 1
        else:
            close_re = re.compile(rf"^{re.escape(fence_char)}{{{fence_len},}}\s*$")
            if close_re.match(stripped):
                blocks.append(
                    DiagramBlock(
                        index=len(blocks) + 1,
                        start_line=start_line,
                        content="\n".join(buf).strip(),
                    )
                )
                in_mermaid = False
                buf = []
            else:
                buf.append(line)

    if in_mermaid:
        blocks.append(
            DiagramBlock(
                index=len(blocks) + 1,
                start_line=start_line,
                content="\n".join(buf).strip(),
            )
        )
    return blocks


def _detect_diagram_type(lines: list[str]) -> tuple[str, int]:
    """Return (diagram_type_token, 0-based line index) after skipping init/comments."""
    in_init = False
    for idx, raw in enumerate(lines):
        s = raw.strip()
        if not s:
            continue
        if in_init:
            if "}%%" in s:
                in_init = False
            continue
        if s.startswith("%%{"):
            if "}%%" not in s:
                in_init = True
            continue
        if s.startswith("%%"):
            continue
        first_token = s.split()[0]
        return first_token, idx
    return "unknown", -1


def _validate_init_and_palette(
    block: DiagramBlock,
    report: BlockReport,
    *,
    allow_custom_colors: bool,
) -> None:
    match = INIT_BLOCK_RE.search(block.content)
    if not match:
        report.add_error(
            "Missing %%{init: ...}%% theme header. Use the Obsidian Violet base themeVariables "
            "from references/theme_system.md."
        )
    else:
        raw_json = match.group(1).strip()
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            report.add_error(
                f"Invalid JSON in %%{{init}}%% directive ({exc.msg}). Use strict double-quoted JSON."
            )
            parsed = None

        if isinstance(parsed, dict):
            theme = parsed.get("theme")
            if theme != "base":
                report.add_error(
                    f'%%{{init}}%% must set "theme": "base" (found {theme!r}) for Obsidian Violet dark-mode theming.'
                )
            theme_css = parsed.get("themeCSS")
            if not isinstance(theme_css, str) or "background-color" not in theme_css.lower():
                report.add_error(
                    '%%{init}%% must set "themeCSS": "svg { background-color: #09090B !important; border-radius: 8px; }" '
                    "so the diagram never renders on a white background."
                )
            elif re.search(r"background-color\s*:\s*(white|#fff(fff)?)\b", theme_css, re.IGNORECASE):
                report.add_error("themeCSS must use a dark obsidian canvas background, never white.")

            theme_vars = parsed.get("themeVariables")
            if not isinstance(theme_vars, dict) or not theme_vars:
                report.add_error('%%{init}%% is missing a populated "themeVariables" object.')
            else:
                if theme_vars.get("darkMode") is not True:
                    report.add_error(
                        'themeVariables must set "darkMode": true so Mermaid derives dark-mode fills instead of light/white defaults.'
                    )
                bg = str(theme_vars.get("background", "")).upper()
                if bg not in DARK_CANVAS_SURFACES:
                    report.add_error(
                        f'themeVariables "background" must be an Obsidian dark surface '
                        f"({', '.join(sorted(DARK_CANVAS_SURFACES))}); found {theme_vars.get('background')!r}."
                    )
                if "mainBkg" not in theme_vars:
                    report.add_warning(
                        'themeVariables should set "mainBkg": "#18181B" so ER/class/state boxes never fall back to light fills.'
                    )
                if "textColor" not in theme_vars:
                    report.add_warning(
                        'themeVariables should set "textColor": "#F4F4F5" for high-contrast dark-mode typography.'
                    )
                if report.diagram_type in ("flowchart", "stateDiagram-v2", "erDiagram", "classDiagram"):
                    if "edgeLabelBackground" not in theme_vars:
                        report.add_warning(
                            'themeVariables should set "edgeLabelBackground": "#18181B" for crisp dark edge-label pills.'
                        )

    if not allow_custom_colors:
        found_hex = {h.upper() for h in HEX_COLOR_RE.findall(block.content)}
        off_palette = sorted(found_hex - APPROVED_PALETTE)
        if off_palette:
            report.add_error(
                f"Off-palette hex color(s) detected: {', '.join(off_palette)}. "
                "Restrict colors to the Obsidian Violet purple/black/grey palette (references/theme_system.md)."
            )


def _validate_html_hygiene(block: DiagramBlock, report: BlockReport) -> None:
    for rel_lineno, line in enumerate(block.content.splitlines()):
        stripped = line.strip()
        if stripped.startswith("%%"):
            continue
        for match in RAW_HTML_RE.finditer(line):
            abs_line = block.start_line + rel_lineno
            report.add_error(
                f"Line {abs_line}: Raw HTML tag {match.group(0)!r} found. "
                'Use plain text with "\\n" inside double-quoted labels for cross-renderer portability.'
            )


def _validate_flowchart(block: DiagramBlock, report: BlockReport) -> None:
    lines = block.content.splitlines()
    subgraph_depth = 0
    class_defs: set[str] = set()
    has_class_assignment = False
    node_ids: set[str] = set()
    edge_count = 0
    labeled_edge_count = 0

    for rel_lineno, raw in enumerate(lines):
        abs_line = block.start_line + rel_lineno
        stripped = raw.strip()
        if not stripped or stripped.startswith("%%"):
            continue

        # Skip directive lines
        if stripped.startswith(("flowchart ", "direction ", "style ", "linkStyle ", "click ")):
            continue

        m_classdef = CLASSDEF_RE.match(stripped)
        if m_classdef:
            class_defs.add(m_classdef.group(1))
            continue

        m_class = CLASS_ASSIGN_RE.match(stripped)
        if m_class:
            has_class_assignment = True
            continue

        if INLINE_CLASS_RE.search(stripped):
            has_class_assignment = True

        m_sub = SUBGRAPH_RE.match(stripped)
        if m_sub:
            subgraph_depth += 1
            header = m_sub.group(1).strip()
            if not EXPLICIT_SUBGRAPH_RE.match(header):
                report.add_error(
                    f"Line {abs_line}: Subgraph {header!r} must use explicit ID + quoted title "
                    '(e.g., subgraph DataPlane["2. Data Plane"]).'
                )
            continue

        if stripped == "end":
            subgraph_depth -= 1
            if subgraph_depth < 0:
                report.add_error(f"Line {abs_line}: Unmatched 'end' with no open subgraph.")
            continue

        # Count edges & check edge label coverage
        if FLOWCHART_EDGE_RE.search(stripped):
            edges_on_line = list(FLOWCHART_EDGE_RE.finditer(stripped))
            edge_count += len(edges_on_line)
            has_inline_label = bool(FLOWCHART_INLINE_EDGE_LABEL_RE.search(stripped))
            for edge_m in edges_on_line:
                pipe_label = edge_m.group("pipe_label")
                if pipe_label is not None or has_inline_label:
                    labeled_edge_count += 1
                    if pipe_label is not None:
                        trimmed = pipe_label.strip()
                        if not (trimmed.startswith('"') and trimmed.endswith('"')):
                            if any(ch in trimmed for ch in "(){}[]/:<>"):
                                report.add_warning(
                                    f"Line {abs_line}: Quote edge label |{trimmed}| because it contains punctuation."
                                )
            # Don't parse node declarations inside pure edge lines unless nodes are declared inline
            # Fall through to check inline node declarations too.

        # Check node declarations
        # Strip edge labels |...| before matching node brackets
        cleaned_for_nodes = re.sub(r"\|[^|]*\|", " ", stripped)
        for node_m in FLOWCHART_NODE_DECL_RE.finditer(cleaned_for_nodes):
            nid = node_m.group("id")
            body = node_m.group("body").strip()

            if nid in RESERVED_NODE_IDS:
                report.add_error(
                    f"Line {abs_line}: Reserved Mermaid keyword {nid!r} used as node ID."
                )
            node_ids.add(nid)

            is_quoted = len(body) >= 2 and body[0] == '"' and body[-1] == '"'
            if not is_quoted:
                if any(ch in body for ch in "(){}[]/:<>@&"):
                    report.add_error(
                        f"Line {abs_line}: Unquoted label for node {nid!r} contains risky characters ({body!r}). "
                        f'Wrap label in double quotes: {nid}["..."].'
                    )
            else:
                inner = body[1:-1]
                label_lines = inner.split("\\n")
                if len(label_lines) > MAX_LABEL_LINES:
                    report.add_warning(
                        f"Line {abs_line}: Node {nid!r} has {len(label_lines)} lines (max {MAX_LABEL_LINES}). "
                        "Keep node labels scannable."
                    )
                if len(inner) > MAX_LABEL_CHARS:
                    report.add_warning(
                        f"Line {abs_line}: Node {nid!r} label is {len(inner)} chars (max {MAX_LABEL_CHARS}). "
                        "Distill to Name + Mechanism + key Invariant."
                    )

    if subgraph_depth > 0:
        report.add_error(f"Unclosed subgraph block(s): missing {subgraph_depth} 'end' statement(s).")

    if not class_defs:
        report.add_error(
            "Flowchart is missing Obsidian Violet semantic classDef definitions "
            "(core, service, store, external, async, guard)."
        )
    elif not has_class_assignment:
        report.add_warning("classDef styles are defined but no nodes are assigned to any class.")

    if len(node_ids) > MAX_FLOWCHART_NODES:
        report.add_warning(
            f"Flowchart has {len(node_ids)} nodes (recommended <= {MAX_FLOWCHART_NODES}). "
            "Consider splitting into 2 complementary views for Senior-Staff readability."
        )

    if edge_count >= MIN_EDGES_FOR_LABEL_RATIO:
        ratio = labeled_edge_count / edge_count
        if ratio < MIN_LABELED_EDGE_RATIO:
            report.add_warning(
                f"Only {labeled_edge_count}/{edge_count} edges ({ratio:.0%}) carry annotations. "
                "Add protocol, payload, or delivery semantics to key edges."
            )

    report.metrics = {
        "nodes": len(node_ids),
        "edges": edge_count,
        "labeled_edges": labeled_edge_count,
        "class_defs": sorted(class_defs),
    }


def _validate_sequence(block: DiagramBlock, report: BlockReport) -> None:
    lines = block.content.splitlines()
    depth = 0
    has_autonumber = False
    message_count = 0

    for rel_lineno, raw in enumerate(lines):
        abs_line = block.start_line + rel_lineno
        stripped = raw.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        if stripped == "autonumber":
            has_autonumber = True
            continue
        if SEQ_BLOCK_OPEN_RE.match(stripped):
            depth += 1
            continue
        if stripped == "end":
            depth -= 1
            if depth < 0:
                report.add_error(f"Line {abs_line}: Unmatched 'end' in sequenceDiagram.")
            continue
        if SEQ_MESSAGE_RE.match(stripped):
            message_count += 1

    if depth > 0:
        report.add_error(f"Unclosed sequence block(s): missing {depth} 'end' statement(s).")
    if message_count >= 6 and not has_autonumber:
        report.add_warning(
            f"sequenceDiagram has {message_count} messages without 'autonumber'. "
            "Add 'autonumber' for easier Staff-review referencing."
        )

    report.metrics = {"messages": message_count, "autonumber": has_autonumber}


def validate_block(block: DiagramBlock, *, allow_custom_colors: bool = False) -> BlockReport:
    report = BlockReport(block_index=block.index, start_line=block.start_line)
    if not block.content.strip():
        report.add_error("Empty Mermaid diagram block.")
        return report

    lines = block.content.splitlines()
    dtype, _ = _detect_diagram_type(lines)
    report.diagram_type = dtype

    if dtype == "unknown":
        report.add_error("Could not detect Mermaid diagram type declaration.")
        return report

    if dtype in LEGACY_OR_FRAGILE_TYPES:
        if dtype == "graph":
            report.add_warning("Legacy 'graph' syntax detected; prefer 'flowchart TB' or 'flowchart LR'.")
        elif dtype == "stateDiagram":
            report.add_warning("Legacy 'stateDiagram' detected; prefer 'stateDiagram-v2'.")
        else:
            report.add_warning(
                f"Diagram type {dtype!r} may not render consistently across GitHub, Obsidian, and Antigravity. "
                f"Prefer universal types: {', '.join(UNIVERSAL_DIAGRAM_TYPES)}."
            )
    elif dtype not in UNIVERSAL_DIAGRAM_TYPES:
        report.add_warning(f"Unrecognized or non-standard diagram type: {dtype!r}.")

    _validate_init_and_palette(block, report, allow_custom_colors=allow_custom_colors)
    _validate_html_hygiene(block, report)

    if dtype in ("flowchart", "graph"):
        _validate_flowchart(block, report)
    elif dtype == "sequenceDiagram":
        _validate_sequence(block, report)

    return report


def validate_text(
    text: str,
    *,
    is_markdown: bool,
    allow_custom_colors: bool = False,
) -> list[BlockReport]:
    blocks = extract_mermaid_blocks(text, is_markdown=is_markdown)
    return [validate_block(b, allow_custom_colors=allow_custom_colors) for b in blocks]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Mermaid diagrams against Obsidian Violet theme and Staff-grade hygiene rules."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Path(s) to .md or .mmd files, or '-' to read a raw Mermaid diagram from stdin.",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Force Markdown fenced-block extraction (auto-enabled for .md/.mdx files).",
    )
    parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Exit non-zero if any warnings are reported.",
    )
    parser.add_argument(
        "--allow-custom-colors",
        action="store_true",
        help="Skip strict Obsidian Violet hex palette membership check.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON validation report.",
    )
    args = parser.parse_args(argv)

    all_results: list[dict[str, Any]] = []
    overall_ok = True

    for raw_path in args.paths:
        if raw_path == "-":
            text = sys.stdin.read()
            is_md = args.markdown or ("```mermaid" in text.lower())
            label = "<stdin>"
        else:
            p = Path(raw_path)
            if not p.is_file():
                print(f"[ERROR] File not found: {p}", file=sys.stderr)
                return 1
            text = p.read_text(encoding="utf-8")
            is_md = args.markdown or p.suffix.lower() in (".md", ".markdown", ".mdx")
            label = str(p)

        reports = validate_text(
            text,
            is_markdown=is_md,
            allow_custom_colors=args.allow_custom_colors,
        )
        if not reports:
            msg = f"No Mermaid blocks found in {label}"
            if args.json:
                all_results.append({"path": label, "blocks": [], "warning": msg})
            else:
                print(f"[WARN] {msg}")
            if args.strict_warnings:
                overall_ok = False
            continue

        file_entry: dict[str, Any] = {"path": label, "blocks": []}
        for rep in reports:
            block_ok = rep.valid and (not args.strict_warnings or not rep.warnings)
            if not block_ok:
                overall_ok = False
            file_entry["blocks"].append(
                {
                    "block_index": rep.block_index,
                    "start_line": rep.start_line,
                    "diagram_type": rep.diagram_type,
                    "valid": block_ok,
                    "errors": rep.errors,
                    "warnings": rep.warnings,
                    "metrics": rep.metrics,
                }
            )
            if not args.json:
                status = "OK" if block_ok else "FAIL"
                print(
                    f"[{status}] {label} :: block #{rep.block_index} "
                    f"(line {rep.start_line}, {rep.diagram_type})"
                )
                for err in rep.errors:
                    print(f"  ERROR: {err}")
                for warn in rep.warnings:
                    print(f"  WARN:  {warn}")
        all_results.append(file_entry)

    if args.json:
        print(json.dumps({"valid": overall_ok, "files": all_results}, indent=2))

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
