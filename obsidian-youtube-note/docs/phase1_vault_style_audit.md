# Phase 1: Vault Style Audit (`obsidian-notes`)

**Audit Scope:** Full inspection of all 24 Markdown notes, `README.md`, `misc/bases/Software Engineering.base`, and `.obsidian/` configuration in `../obsidian-notes` (exceeding the initial 4–6 note sample because the vault is compact enough to audit exhaustively).

**Key Surprise Caught by Full Audit:** Two candidate notes named in the original plan (`Data Processing/NoSQL.md` and `Cloud Infrastructure/Cloud Infrastructure.md`) are currently 0-byte placeholder stubs, and `Spring Beans.md` lives inside a subfolder (`Software Engineering/Spring/Spring Beans.md`). Auditing the full vault surfaced the vault's strongest style exemplars (`Builder Pattern.md`, `Enums.md`, `Factory Method Pattern.md`, `Inversion of Control.md`, `Spring.md`, `Spring Boot.md`, and `Spring Beans.md`).

---

## 1. Vault Structure & Inventory

| Path | Role | Status / Notes |
| :--- | :--- | :--- |
| `README.md` | Mastery Framework hub | Defines the 6 categories, Focus Areas table, Leadership Lens table, Reading List |
| `Cloud Infrastructure/` | Category folder | Contains `Cloud Infrastructure.md` (0-byte stub) |
| `Data Processing/` | Category folder | Contains `NoSQL.md` (0-byte stub), `SQL.md` (0-byte stub) |
| `Software Engineering/` | Active category folder (20 notes) | Hub `Software Engineering.md`, 6 direct notes, plus subfolders `Language/Java/` (4 notes) and `Spring/` (9 notes) |
| `Information Security/`, `System Resiliency/`, `AI Engineering/` | Planned category folders | Not yet created in vault (referenced in `README.md`) |
| `misc/` | Non-note assets | Ignored via `.obsidian/app.json` (`"userIgnoreFilters": ["misc/"]`); holds `bases/`, `Excalidraw/`, `images/`, `copilot/` |

### Relevant Obsidian Settings & Plugins
- **`.obsidian/app.json`**: `"alwaysUpdateLinks": true`, `"userIgnoreFilters": ["misc/"]`. Moving promoted notes from `staging/<Category>/` into `<Category>/` inside Obsidian will automatically update links.
- **Core Plugins Enabled**: `bases`, `properties`, `templates`, `backlink`, `outgoing-link`, `tag-pane`, `outline`, `graph`, `sync`.
- **Community Plugins Enabled**: `code-styler`, `obsidian-excalidraw-plugin`, `obsidian-tasks-plugin`, `table-editor-obsidian`, `file-explorer-plus`, `obsidian-icon-folder`, `colored-tags`, `obsidian-git`, `highlightr-plugin`, `dataview`.

---

## 2. Obsidian Bases (`.base`) Compatibility

`misc/bases/Software Engineering.base` defines two table views:

```yaml
views:
  - type: table
    name: Table
    filters:
      and:
        - file.inFolder("Software Engineering")
        - file.name != "Software Engineering"
  - type: table
    name: Software Engineering
    filters:
      and:
        - file.inFolder("Software Engineering")
        - file.name != "Software Engineering"
```

### Implications for the Pipeline
1. **Folder-driven inclusion, no mandatory custom Base columns**: Notes automatically appear in `<Category>.base` solely by living inside `<Category>/` (including nested subfolders) and having a filename different from the category hub name.
2. **Clean staging isolation**: Writing generated notes to `staging/<Recommended Category>/<Note Title>.md` guarantees they stay out of production `.base` views until human review and drag-and-drop promotion.
3. **Registered property types (`.obsidian/types.json`)**: Only standard Obsidian properties (`aliases`, `cssclasses`, `tags`) and Obsidian Tasks (`TQ_*`) keys are registered vault-wide. Category-hub-only fields (`category`, `last-studied`) appear solely on `Software Engineering.md`, never on individual topic notes.

---

## 3. YAML Frontmatter & Tag Taxonomy

### Observed Frontmatter Patterns
- **Every non-empty topic note** starts with YAML frontmatter containing `tags:` as a YAML list.
- **Zero inline `#tags`** exist anywhere in note bodies — tags live exclusively in YAML frontmatter without leading `#`.
- **`aliases:`** is used selectively for common acronyms/abbreviations (e.g., `Inversion of Control.md` → `aliases: [IoC]`; `Software Engineering.md` → `aliases: [SE, SWE]`).
- **Date format** (observed on `Software Engineering.md`): ISO `YYYY-MM-DD` (`last-studied: 2026-03-15`).

### Tag Evolution Discovered (Legacy Flat vs. Current Hierarchical)
Auditing all notes plus `.obsidian/plugins/colored-tags/data.json` revealed two distinct tagging generations:

1. **Legacy flat tags** (earlier `Spring/` notes):
   ```yaml
   tags:
     - frameworks
     - spring-frameworks
     - spring
     - software-engineering
   ```
2. **Current hierarchical nested tags** (all newer notes: `Software Engineering.md`, Design Patterns, `Inversion of Control.md`, `Language/Java/*`):
   ```yaml
   tags:
     - software-engineering/design-patterns/creational-patterns
   ```
   ```yaml
   tags:
     - software-engineering/languages/java
   ```
   ```yaml
   tags:
     - software-engineering/design-principles
   ```

Because Obsidian resolves nested tags hierarchically (`#software-engineering` automatically matches `#software-engineering/languages/java`), newer notes attach only 1–2 specific nested tags rather than repeating parent category tags.

### Canonical Tag Mapping (Mastery Framework → `kebab-case` Hierarchical Slugs)
Derived from `README.md` and reconciled with the exact slugs already in `Software Engineering.md` (note `Frameworks & Languages` split into `frameworks` and `languages`, and `Build & CI/CD` shortened to `cicd`):

| Category Folder | Category Slug | Focus Area Slugs (`<category>/<focus-area>[/<subtopic>]`) |
| :--- | :--- | :--- |
| `Cloud Infrastructure` | `cloud-infrastructure` | `scalable-architecture-design`, `infrastructure-as-code`, `container-orchestration`, `networking-and-load-balancing`, `cloud-services` |
| `Data Processing` | `data-processing` | `etl-elt-pipelines`, `big-data-frameworks`, `databases-and-storage`, `streaming-and-real-time`, `data-quality-and-transformation` |
| `Information Security` | `information-security` | `secure-coding`, `authentication-and-authorization`, `encryption-and-secrets-management`, `threat-modeling`, `compliance-and-auditing` |
| `Software Engineering` | `software-engineering` | `design-principles`, `design-patterns`, `frameworks`, `languages`, `testing-strategies`, `cicd` |
| `System Resiliency` | `system-resiliency` | `monitoring-and-observability`, `fault-tolerance`, `chaos-engineering`, `incident-response`, `disaster-recovery` |
| `AI Engineering` | `ai-engineering` | `ml-pipelines`, `model-training-and-evaluation`, `agent-deployment-and-development`, `mlops-and-versioning`, `ethical-ai` |

### Proposed Frontmatter Schema for Pipeline-Generated Notes
```yaml
---
tags:
  - <category-slug>/<focus-area-slug>
  - <category-slug>/<focus-area-slug>/<optional-specific-subtopic>
aliases:
  - <Optional acronym or common alternate name>
source: "<Video title or URL if present in transcript>"
source-type: youtube
created: YYYY-MM-DD
---
```
*(Note: `aliases` omitted when not applicable; `source`/`source-type`/`created` recommended for traceability in `staging/` and easy Dataview/Bases querying — confirm preference in open decisions below.)*

---

## 4. Document Structure, Headings, Code & Visuals

### Heading Conventions
- **Never repeat the note filename as an `# H1` title**: Zero topic notes start with `# <Filename>`; Obsidian renders the filename as the note title.
- **Opening hook**: Begin immediately after frontmatter with either:
  - A crisp 1–3 sentence definition/overview bolding the core takeaway (`Factory Method Pattern.md`, `Builder Pattern.md`, `Spring Boot.md`, `Spring Beans.md`), or
  - An `> [!IMPORTANT]` mental-model callout for paradigm-defining concepts (`Enums.md`).
- **Section hierarchy**: Existing notes mix `#`/`##` and `##`/`###`. Standardizing generated notes on **`##` for top-level sections** and **`###` for subsections** (with `---` horizontal rules sparingly between major sections on longer deep dives) gives consistent Obsidian Outline navigation without competing with the note title.

### Recurring Structural Building Blocks (Golden Blueprint)
1. **Core Definition / Mental Model** (opening paragraph or `> [!IMPORTANT]` callout)
2. **Core Mechanics / Key Components / Under the Hood** (bold lead-in bullets `- **Term:** ...` or numbered execution steps)
3. **Concrete Code Examples** (fenced code blocks with language identifiers, explanatory comments, `// GOOD` vs `// BAD` contrasts, and `// Output:` annotations where helpful)
4. **Comparison Tables** (e.g., concept A vs. B, guarantees/behavior with a `Senior Note` column as in `Enums.md`, or starter/component breakdowns as in `Spring Boot.md`)
5. **Mermaid Diagrams** (optional, high-signal only — e.g., `flowchart TD` with subgraphs and `classDef` styling as in `Builder Pattern.md`, or `sequenceDiagram` for protocols/lifecycles)
6. **Trade-offs, Pitfalls & "When Not to Use"** (`Notes & Pitfalls`, `Benefits` / `Liabilities`, `When Not to Use`, or `Architectural Best Practices & Anti-Patterns`)
7. **Source Attribution** (video title, channel/URL if present in transcript — kept concise at the bottom or in frontmatter so the note reads like an evergreen reference)

### Vault Quirks to Explicitly Avoid
- **No raw HTML `<mark>` tags**: Only used once (`Design Patterns.md`) via `highlightr-plugin` for manual highlighting; use `**bold**` or Obsidian callouts instead.
- **No dangling `- [ ]` checkboxes**: `Software Engineering.md` runs an `obsidian-tasks-plugin` query (`path includes software engineering`), so unfinished checkboxes in topic notes pollute the category task list.
- **Clean inline code & fenced blocks**: Use single backticks `` `code` `` inline (never triple backticks inline) and never place Markdown bold (`**...**`) inside fenced code blocks.
- **No `obsidian://open?...` URIs**: Body notes strictly use `[[Wikilinks]]`.

---

## 5. Voice, Persona & Domain Context

- **Target Persona**: Data Platform Engineer (L3 → Senior promotion track per `README.md` and vault context), working heavily in Java/JVM, distributed data systems, Apache Iceberg, Parquet/ORC, lakehouses, and backend infrastructure.
- **Voice & Style**:
  - **Evergreen engineering reference**, not a chronological video recap ("In this video the speaker explains..." is forbidden).
  - **Dense, direct, zero fluff**: Prioritizes under-the-hood mechanics, invariants, failure modes, performance/memory trade-offs, alternatives, and "when NOT to use" criteria.
  - **Domain-grounded examples**: Existing vault notes deliberately ground abstract patterns in data-platform constructs (`TableWriter`/`ParquetTableWriter`, `TableConfig`, `IcebergLakehouseFactory`, `CatalogType`). Generated notes should preserve the transcript's core technical examples while favoring clean, realistic backend/data-platform framing when illustrating concepts.
  - **Senior / Leadership Lens**: Where a topic raises architectural standards, schema/API compatibility, or team-wide trade-offs, include a concise `Senior Note` column or `> [!TIP]` / architectural best-practices bullet (aligned with `README.md`'s Leadership Lens and `Enums.md`).

---

## 6. Naming & Wikilink Rules

- **Filenames**: Clean **Title Case** concept noun phrases with spaces (`Protocol Buffers.md`, `Factory Method Pattern.md`, `Inversion of Control.md`). Never retain `_transcript`, underscores, or clickbait suffixes like `Crash Course` or `Full Tutorial` in the final note title.
- **Wikilink formats**:
  - Standard note link: `[[Spring Context]]`, `[[Inversion of Control]]`, `[[NoSQL]]`
  - Section link: `[[Spring Beans#@Bean Annotation]]`
  - Aliased link: `[[Design Patterns#Product Class|product]]`
- **Linking policy**:
  - Always scan `../obsidian-notes` (excluding `misc/` and `staging/`) for existing note names and `aliases` first, and prefer linking to notes that already exist.
  - Forward-looking ("red") wikilinks are acceptable in this vault (as seen with `[[Dependency Inversion Principle]]`, `[[JDBC]]`, `[[Hibernate]]`), but keep them selective (2–5 high-value foundational concepts per note at most).

---

## 7. Golden Exemplar Notes Selected for Phase 2 (`examples/golden_notes.md`)

| Exemplar Note | Why Selected |
| :--- | :--- |
| `Software Engineering/Builder Pattern.md` | Gold-standard full note: hierarchical tag, crisp summary, Key Components, data-platform Java code, Notes & Pitfalls, `> [!IMPORTANT]` callout, deep conceptual section, aliased wikilink, styled Mermaid `flowchart TD` |
| `Software Engineering/Language/Java/Enums.md` | Gold-standard deep dive: `> [!IMPORTANT]` opener, under-the-hood bytecode lowering, progressive patterns (`A/B/C`) with Iceberg/Delta examples, guarantees table with `Senior Note` column, Best Practices & Anti-Patterns |
| `Software Engineering/Factory Method Pattern.md` | Gold-standard concise note (49 lines): ideal density template for shorter/focused transcripts |
| `Software Engineering/Inversion of Control.md` + `Spring/Spring.md` | Gold-standard conceptual & trade-off exemplars: `aliases` frontmatter, comparison table, `// GOOD` vs `// BAD` code, real-world mapping, alternatives list, and `When Not to Use` section |

---

## 8. Open Decisions to Confirm Before / During Phase 2

1. **Source metadata placement**: Include lightweight provenance fields (`source`, `source-type: youtube`, `created`) in YAML frontmatter (better for Dataview/Bases filtering), or keep YAML strictly `tags` + optional `aliases` and place video source details in a `## References` footer? *(Recommendation: YAML `source` + `created` + optional `## References` link so Bases/Dataview can filter staged YouTube notes.)*
2. **Tag granularity**: Confirm standardizing all generated notes on the modern hierarchical format (`<category>/<focus-area>` + optional `/<subtopic>`) rather than the older flat Spring tag style. *(Recommendation: Hierarchical `kebab-case` only.)*
3. **Subfolder placement on staging**: Keep staging strictly two levels (`staging/<Recommended Category>/<Note Title>.md`), leaving any subfolder nesting (like `Language/Java/` or `Spring/`) to human promotion. *(Recommendation: Keep `staging/<Category>/<Title>.md` per locked-in plan.)*
