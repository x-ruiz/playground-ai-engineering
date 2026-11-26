---
name: mermaid-diagrams
description: >-
  Generate clean, high-contrast, Staff-engineer-grade Mermaid diagrams styled in an
  Obsidian Violet (purple, black, and graphite grey) theme that renders reliably across
  GitHub, Obsidian, VS Code, and Antigravity. Covers system topology (`flowchart`),
  protocol/failure flows (`sequenceDiagram`), lifecycle state machines (`stateDiagram-v2`),
  data schemas (`erDiagram`), and interface hierarchies (`classDiagram`), with a
  deterministic Python validator. Use whenever the user asks to create, redesign, theme,
  or review technical Mermaid diagrams for RFCs, design specs, READMEs, architecture docs,
  or Obsidian engineering notes.
---

# Obsidian Violet Mermaid Diagrams (Senior–Staff Grade)

Produces visually cohesive **purple, black, and grey** Mermaid diagrams that balance **immediate visual scannability** with **Senior–Staff architectural depth** (trust boundaries, protocols, delivery semantics, failure modes, and invariants).

## Reference Assets
- **Theme System & Portability Rules (Required):** [references/theme_system.md](./references/theme_system.md) — Obsidian Violet hex palette (WCAG AAA contrast), dual-canvas (light + dark mode) legibility rules, copy-ready `%%{init}%%` headers, `classDef` & subgraph styles, line semantics, and strict parser-hygiene rules.
- **Staff-Grade Exemplars (Load for the matching diagram type):** [references/staff_exemplars.md](./references/staff_exemplars.md) — Production-ready templates for `flowchart`, `sequenceDiagram`, `stateDiagram-v2`, `erDiagram`, and `classDiagram`.
- **Deterministic Validator:** [scripts/validate_mermaid.py](./scripts/validate_mermaid.py) — Stdlib-only Python linter checking theme tokens, JSON `init` syntax, balanced blocks, HTML-free labels, node density, and edge signal.

## Non-Negotiable Guardrails
1. **Strict Obsidian Violet Palette.** Use only the curated purple, black, and graphite grey tokens from [references/theme_system.md](./references/theme_system.md). Never fall back to default Mermaid yellow/pastel themes or introduce uncoordinated rainbow colors (unless the user explicitly requests semantic red/green status overrides).
2. **Dual-Canvas Legibility.** Every styled node, subgraph, and edge label pill must specify explicit dark `fill`, explicit `stroke`, and explicit high-contrast `color` so diagrams look razor-sharp on **both** light canvases (GitHub Light) and dark canvases (GitHub Dark, Obsidian, Antigravity).
3. **Portable Universal Syntax Only.** Use `flowchart TB`/`LR`, `sequenceDiagram`, `stateDiagram-v2`, `erDiagram`, or `classDiagram`. Avoid legacy `graph` and fragile beta types (`architecture-beta`, `block-beta`, `c4Context`, `zenuml`) unless explicitly requested.
4. **Zero Raw HTML & Always Quote Labels.** Never emit `<br/>`, `<b>`, `<i>`, `<span`, or `<div` inside labels. Use double-quoted labels with `\n` line breaks (`ID["Service\nTech · Invariant"]`) and explicit subgraph IDs (`subgraph ControlPlane["1. Control Plane"]`).
5. **No Spaghetti Monoliths.** Keep each flowchart to **8–18 nodes** (hard warning above 22) and **2–5 bounded subgraphs**. When a system spans orthogonal concerns (e.g., topology + retry sequence + storage schema), split into **2–3 focused complementary views** instead of one overcrowded graph.
6. **Staff Signal Over Generic Boxes.** Every node must name the concrete component + runtime/mechanism (+ load-bearing invariant/SLO when relevant). Every non-trivial edge must carry protocol/transport, contract/payload, or delivery semantics (`sync` `-->`, `hot/write path` `==>`, `async/control/telemetry` `-.->`).

---

## Workflow

### Phase 1: Ground & Select Diagram View(s)
1. If diagramming an existing codebase, spec, or RFC, inspect the actual files first—never invent services, topics, or schemas that contradict the source.
2. Choose the minimal set of complementary views that answer a Senior–Staff reviewer's core questions:
   - **System Topology / Data & Control Planes** → `flowchart TB` (default for 3+ layered tiers; renders best in narrow panes) or `flowchart LR` (linear ETL/streaming pipelines <= 4 stages).
   - **Request Lifecycle, Auth Handshake, Retries & Failure Paths** → `sequenceDiagram` with `autonumber` and explicit `alt` / `opt` / `par` / `critical` blocks.
   - **Job / Consensus / Order Lifecycle** → `stateDiagram-v2` with `[guard]` conditions and explicit retry/terminal error states.
   - **Persistence & Domain Contracts** → `erDiagram` with cardinalities, `PK`/`FK`/`UK`, and invariant comments.
   - **Module / Interface Boundaries** → `classDiagram` focusing on contracts and composition (omit trivial getters/setters).
3. Load [references/theme_system.md](./references/theme_system.md) and the matching section of [references/staff_exemplars.md](./references/staff_exemplars.md).

### Phase 2: Draft with Architectural Signal & Clean Layout
1. **Emit the exact `%%{init: ...}%%` JSON block** for the diagram type using double-quoted valid JSON (`"theme": "base"`).
2. **Structure layout topologically:**
   - Declare subgraphs in reading order (numbered `1.`, `2.`, `3.`, ... when directional) representing real **trust zones, failure domains, planes, or ownership boundaries**.
   - Declare nodes inside their subgraph using the 2–3 line Staff label pattern:
     - Line 1: Concrete component / primitive name
     - Line 2: Tech / runtime / protocol mechanism
     - Line 3 *(optional)*: Key invariant, capacity, TTL, or failure guarantee
   - Group cross-subgraph edges cleanly after subgraphs to minimize Dagre edge crossings.
3. **Apply semantic classes consistently** (`core`, `service`, `store`, `external`, `async`, `guard`) and style every subgraph (`zoneOuter`, `zoneInner`, `zoneExternal`) using the exact hex tokens in [references/theme_system.md](./references/theme_system.md).
4. **Surface reliability & security primitives explicitly**—do not hide idempotency ledgers, DLQs, circuit breakers, auth/WIF boundaries, schema validators, or read-only vs. write paths.
5. **Add a compact legend** (inline subgraph or 1-line note beneath the diagram) whenever 3+ arrow styles or non-obvious classes are used.

### Phase 3: Validate Deterministically
1. Run the bundled validator against the generated `.mmd` or `.md` file (or pipe via stdin):
   ```bash
   python3 skills/mermaid-diagrams/scripts/validate_mermaid.py --strict-warnings <path-to-file.md>
   ```
2. Fix every reported error and warning (palette drift, unquoted punctuation, raw HTML tags, unbalanced `end` blocks, oversized nodes, or unlabeled edge sprawl) and re-run until exit code is `0`.

### Phase 4: Deliver with Crisp Architectural Context
- When embedding in an RFC, spec, README, or Obsidian note, follow complex diagrams with **3–5 concise bullets** highlighting the non-obvious **invariants, failure modes, and trade-offs** (never restating box labels verbatim).
