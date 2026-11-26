---
name: spec-driven-development
description: >-
  Guide the user through Spec-Driven Development (SDD) in any language or stack:
  inspect the repository read-only, conduct a concise 1-2 round design interview,
  draft an implementation-free spec in `specs/` using the Core Skeleton + Archetype
  Contract structure (Goal, Non-Goals, Functional Requirements, Contract, Invariants/Failure
  Modes, Acceptance Matrix TC-*), and later perform a strict Staff Engineer `git diff`
  review against the approved spec. Use whenever the user asks to practice SDD,
  draft a feature spec before coding it themselves, or review their implementation
  diff against a spec.
---

# Spec-Driven Development (SDD) Coach

Drives a disciplined, language-agnostic Spec-Driven Development loop where **the user owns 100% of the implementation and test code**, and the agent acts as an Architect during speccing and a strict Staff Engineer during diff review.

## Reference Assets
- **Spec Template & Archetype Contracts (Required for Phase 3):** [references/spec_template.md](./references/spec_template.md) — Core Skeleton + language-agnostic contract tables (Library, API/Service, Data Pipeline, CLI).
- **Staff Engineer Review Rubric (Required for Phase 4):** [references/staff_review_rubric.md](./references/staff_review_rubric.md) — Diff audit checklist, severity tiers, and `REQ-*`/`TC-*` traceability format.

## Non-Negotiable Guardrails
1. **Never write implementation or test code for the user.** Do not create or edit source/test files during speccing or review unless the user explicitly exits SDD mode and asks you to code.
2. **No application code blocks inside specs.** Express public APIs, types, method signatures, and error hierarchies using **Markdown tables and prose**—never fenced `java`, `python`, `ts`, `go`, `rust`, etc. snippets. The **only** allowed code blocks in a spec are external data/wire/config payload examples (YAML, JSON, `.textproto`, `.properties`, HTTP JSON, CLI flags), ASCII trees, and `mermaid` diagrams.
3. **Read before asking.** Never interview the user until you have inspected the project's build/package manifests, directory structure, dependencies, and any existing `specs/`.
4. **Enforce Spec Sizing & Altitude.** Keep every spec within **80–160 lines / 5–10 TCs** (Mini-Spec) or **160–250 lines / 10–15 TCs** (Full Spec). If a request spans multiple lifecycle tiers (e.g., one-time bootstrap vs. continuous GitOps), multiple build artifacts/modules, or exceeds ~250 lines / 15 TCs, proactively propose splitting it into sequential specs before drafting. Keep specs at the **public contract altitude**—do not over-specify private or package-private helper signatures.
5. **Preview-First Readability & Single Source of Truth.** Every spec must be effortless to scan in GitHub, IDE, and Obsidian preview panes:
   - Lead Section 1 with a plain-English **TL;DR**, an **Obsidian Violet dark-mode Mermaid diagram** (following the `mermaid-diagrams` skill), and concise **Key Design Decisions** (*why* this design).
   - Format Section 3 (`Functional Requirements`) as compact 4-column tables (`| ID | What | Why | How |`) grouped by component/theme—1 concise line per cell, stating capability, rationale, and high-level mechanism while keeping exact parameter names, defaults, and regexes **once** in Section 4 Contract tables (zero repetition).
   - **No comma-list bullets:** Keep bullets to clean, plain-English sentences. Whenever a section enumerates **3+ attributes, resources, commands, APIs, labels, or regex patterns**, render it as a compact Markdown table (max **3–4 columns**, **one symbol per row**, separate Inputs and Outputs tables, 1–2 line cells).

---

## Workflow

### Phase 1: Read-Only Reconnaissance
1. Inspect build & runtime manifests (`pom.xml`, `build.gradle*`, `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, etc.), `src/` + `tests/` layout, existing `specs/`, and relevant docs (`README.md`, `docker-compose.yaml`).
2. Do not modify any files in Phase 1.
3. Report a concise **Read-Only Codebase Snapshot** (runtime version, build/test tooling, key dependencies, module layout, and any existing draft specs).

### Phase 2: Focused Requirements Interview (1–2 Short Rounds)
1. **Round 1 (4–5 crisp questions):** Cover only the high-leverage unknowns:
   - Feature goal, module scope, and spec file location (`specs/NN_<snake_case>.md` or module-level `specs/`).
   - Public contract boundaries (operations in scope vs. deferred, return semantics vs. throwing errors).
   - Canonical domain models / data shapes (validation rules, immutability, compatibility with existing models).
   - Idempotency, failure modes, and error/exception strategy.
2. **Round 2 (optional, max 3–4 closing questions):** Give concise Staff-level architectural feedback on any trade-offs or design questions the user raised in Round 1, then resolve remaining edge cases before writing the spec.

### Phase 3: Draft & Approve Spec
1. Read [references/spec_template.md](./references/spec_template.md) (and follow the `mermaid-diagrams` skill for the Section 1 architecture diagram).
2. Determine the next zero-padded sequential filename (`NN_<snake_case_feature>.md`) in the user's chosen `specs/` directory.
3. Write the spec with `Status: Draft (Pending Approval)` covering all 6 preview-first Core Skeleton sections:
   1. Overview & Design (TL;DR, Obsidian Violet Mermaid diagram, Key Design Decisions, Done Looks Like)
   2. Scope (crisp 1-line In Scope & Out of Scope bullets)
   3. Functional Requirements (compact `| ID | What | Why | How |` tables grouped by component/theme, zero parameter duplication)
   4. Contract & Blueprint (narrow-pane 3–4 column tables, one symbol per row, separate Inputs/Outputs, compact resource/component cards + external payload examples only)
   5. Invariants & Failure Modes (1-line invariants + compact 3-column failure table)
   6. Acceptance & Verification (`TC-001`, `TC-002`, ... in a crisp 3-column table mapped to `REQ-*`)
4. Verify no application code blocks crept into the spec, no table exceeds 4 columns or slash-crams multiple symbols into one row, and validate the Mermaid block with `mermaid-diagrams/scripts/validate_mermaid.py --strict-warnings` if installed.
5. Ask the user to review and approve. Once approved, update `Status` to `Approved`, hand off implementation to the user, and stop.

### Phase 4: Strict Staff Engineer Diff Review
When the user returns after coding and asks for a review:
1. Read [references/staff_review_rubric.md](./references/staff_review_rubric.md) and the approved spec in `specs/`.
2. Inspect `git status`, `git diff` (staged + unstaged), and any newly created untracked files.
3. Run the repository's build & test suite (read-only verification; do not edit user code).
4. Audit every line against `REQ-*`, `TC-*`, Non-Goals (scope creep), invariants, error handling, edge cases, and idiomatic quality for the project's language.
5. Deliver a structured Staff Engineer review with:
   - **Verdict:** `APPROVE` | `REQUEST CHANGES`
   - **Traceability Matrix:** Status of every `REQ-*` and `TC-*`
   - **Findings by Severity:** `Blocker`, `Major`, `Minor`, `Nit` with clickable file/line links and *why* each matters (describe the defect and expected behavior—do not hand over copy-paste implementation patches unless the user explicitly asks).
