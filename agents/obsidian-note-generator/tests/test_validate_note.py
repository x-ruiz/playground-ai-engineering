"""Tests for unified validate_note.py (create, update drafts, concise composable tags) and installer."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_validator():
    script_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "obsidian-note-generator"
        / "scripts"
        / "validate_note.py"
    )
    spec = importlib.util.spec_from_file_location("unified_validate_note", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["unified_validate_note"] = module
    spec.loader.exec_module(module)
    return module


def test_validate_create_documentation_note_passes(tmp_path: Path) -> None:
    validator = _load_validator()
    note = tmp_path / "Data Processing" / "Managed Service for Apache Spark.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        """---
tags:
  - data-processing/frameworks/spark
  - cloud-infrastructure/services/gcp
aliases:
  - Dataproc Serverless
source: "Google Cloud Managed Service for Apache Spark Documentation"
source-type: documentation
vendor: "Google Cloud"
url: "https://cloud.google.com/products/managed-service-for-apache-spark"
created: 2026-11-23
---
Fully managed execution platform for Apache Spark batch, streaming, and interactive workloads.

## Execution Modes
- Serverless batches autoscale compute per job.
""",
        encoding="utf-8",
    )

    report = validator.validate_note(
        note, strict_warnings=True, expected_source_type="documentation", expected_note_action="create"
    )
    assert report.valid is True
    assert report.errors == []
    assert report.warnings == []


def test_validate_update_draft_passes_and_enforces_metadata(tmp_path: Path) -> None:
    validator = _load_validator()
    good = tmp_path / "AI Engineering" / "Modern AI Architecture (Update).md"
    good.parent.mkdir(parents=True)
    good.write_text(
        """---
note-action: update
target-note: "[[Modern AI Architecture]]"
target-path: "AI Engineering/Modern AI Architecture.md"
tags:
  - ai-engineering/agents/harness
source: "Building Production AI Agent Harnesses"
source-type: article
author: "Databricks Engineering Blog"
published: 2026-04-15
url: "https://www.databricks.com/blog/ai-harness"
created: 2026-11-23
---
> [!NOTE]
> **Draft Modification for [[Modern AI Architecture]]**

## Proposed New Section: `## Eval Gates`
Run golden eval suites in CI before deploying prompt changes.
""",
        encoding="utf-8",
    )
    report = validator.validate_note(
        good, strict_warnings=True, expected_source_type="article", expected_note_action="update"
    )
    assert report.valid is True
    assert report.errors == []
    assert report.warnings == []

    # Missing (Update) suffix and missing target-note must fail
    bad = tmp_path / "AI Engineering" / "Modern AI Architecture.md"
    bad.write_text(
        "---\nnote-action: update\ntags:\n  - ai-engineering/agents/harness\n"
        "source: \"Test\"\nsource-type: article\ncreated: 2026-11-23\n---\nBody.\n",
        encoding="utf-8",
    )
    bad_report = validator.validate_note(bad, strict_warnings=True, expected_note_action="update")
    assert bad_report.valid is False
    assert any("(Update).md" in e for e in bad_report.errors)
    assert any("target-note" in e for e in bad_report.errors)
    assert any("target-path" in e for e in bad_report.errors)


def test_validate_rejects_redundant_parent_child_and_verbose_tags(tmp_path: Path) -> None:
    validator = _load_validator()
    note = tmp_path / "AI Engineering" / "Tag Test.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        """---
tags:
  - ai-engineering/agents
  - ai-engineering/agents/mcp
  - ai-engineering/agent-deployment-and-development
source: "Example"
source-type: article
created: 2026-11-23
---
In this article, we cover MCP.
""",
        encoding="utf-8",
    )

    report = validator.validate_note(note, strict_warnings=True)
    assert report.valid is False
    assert any("Redundant parent/child" in e for e in report.errors)
    assert any("-and-" in w for w in report.warnings)
    assert any("recap/meta phrasing" in w for w in report.warnings)


def test_install_skill_discovers_consolidated_skill() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    installer_path = repo_root / "skills" / "install_skills.py"
    spec = importlib.util.spec_from_file_location("repo_install_skills", installer_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["repo_install_skills"] = module
    spec.loader.exec_module(module)

    discovered = {p.name: p for p in module.discover_skills(repo_root / "skills")}
    assert "obsidian-note-generator" in discovered
    assert "obsidian-youtube-note" not in discovered
    assert "obsidian-article-note" not in discovered
    assert "obsidian-docs-note" not in discovered
