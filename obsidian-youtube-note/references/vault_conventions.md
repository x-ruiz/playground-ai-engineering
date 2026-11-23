# Obsidian Vault Conventions (`obsidian-notes`)

Authoritative specification for generating notes staged for Xavier's Mastery Framework Obsidian vault (`obsidian-notes`).

---

## 1. Mastery Framework Categories & Canonical Hierarchical Tags

Every generated note MUST be assigned to **exactly one** of the 6 Mastery Framework categories below and tagged using **exclusively hierarchical `kebab-case` tags** (`<category-slug>/<focus-area-slug>` with an optional `/<subtopic-slug>`).

| Category Folder (Exact Case) | Category Slug | Canonical Focus Area Tags (`<category>/<focus-area>`) |
| :--- | :--- | :--- |
| `Cloud Infrastructure` | `cloud-infrastructure` | `cloud-infrastructure/scalable-architecture-design`<br>`cloud-infrastructure/infrastructure-as-code`<br>`cloud-infrastructure/container-orchestration`<br>`cloud-infrastructure/networking-and-load-balancing`<br>`cloud-infrastructure/cloud-services` |
| `Data Processing` | `data-processing` | `data-processing/etl-elt-pipelines`<br>`data-processing/big-data-frameworks`<br>`data-processing/databases-and-storage`<br>`data-processing/streaming-and-real-time`<br>`data-processing/data-quality-and-transformation` |
| `Information Security` | `information-security` | `information-security/secure-coding`<br>`information-security/authentication-and-authorization`<br>`information-security/encryption-and-secrets-management`<br>`information-security/threat-modeling`<br>`information-security/compliance-and-auditing` |
| `Software Engineering` | `software-engineering` | `software-engineering/design-principles`<br>`software-engineering/design-patterns`<br>`software-engineering/frameworks`<br>`software-engineering/languages`<br>`software-engineering/testing-strategies`<br>`software-engineering/cicd` |
| `System Resiliency` | `system-resiliency` | `system-resiliency/monitoring-and-observability`<br>`system-resiliency/fault-tolerance`<br>`system-resiliency/chaos-engineering`<br>`system-resiliency/incident-response`<br>`system-resiliency/disaster-recovery` |
| `AI Engineering` | `ai-engineering` | `ai-engineering/ml-pipelines`<br>`ai-engineering/model-training-and-evaluation`<br>`ai-engineering/agent-deployment-and-development`<br>`ai-engineering/mlops-and-versioning`<br>`ai-engineering/ethical-ai` |

### Tagging Rules
1. **YAML `tags:` list only** — NEVER place inline `#tags` anywhere in the note body, and NEVER prefix YAML tag values with `#`.
2. **Always hierarchical `kebab-case`** — Every tag must start with one of the 6 `<category-slug>/` prefixes above (e.g., `software-engineering/design-patterns/creational-patterns`, `software-engineering/languages/java`, `data-processing/streaming-and-real-time/kafka`).
3. **1 to 3 specific tags per note** — Because Obsidian matches nested tags hierarchically, do NOT duplicate parent tags (e.g., emit `software-engineering/languages/java`, NOT both `software-engineering` and `software-engineering/languages/java`).
4. **No legacy flat tags** — Never emit flat tags like `frameworks`, `spring`, or `software-engineering` alone.
5. **Cross-cutting tie-breakers**:
   - Serialization/RPC protocols (e.g., Protocol Buffers, gRPC): use `Software Engineering` when focused on service contracts, IDL, wire encoding, and code generation (`software-engineering/frameworks/protobuf` or `software-engineering/design-principles/serialization`); use `Data Processing` when focused on analytical lakehouse schemas, streaming pipelines, or Kafka/Avro/Parquet storage (`data-processing/data-quality-and-transformation/serialization`).
   - Databases, warehouses, lakehouses, Spark, Flink, Kafka, dbt, Airflow → `Data Processing`.
   - Kubernetes, Docker, Terraform, VPCs, load balancers, cloud-native architecture → `Cloud Infrastructure`.
   - OAuth2, JWT, TLS, IAM, KMS, OWASP → `Information Security`.
   - Retries, circuit breakers, OpenTelemetry, SLOs, post-mortems, DR → `System Resiliency`.
   - LLMs, RAG, agents, fine-tuning, evals, MLflow → `AI Engineering`.

---

## 2. YAML Frontmatter Schema

Every generated note MUST start on line 1 with valid YAML frontmatter matching this schema:

```yaml
---
tags:
  - software-engineering/frameworks/protobuf
aliases:
  - Protobuf
source: "Protocol Buffers Crash Course"
source-type: youtube
channel: "Example Channel"
url: "https://www.youtube.com/watch?v=example"
created: 2026-11-23
---
```

### Field Rules
- **`tags`** *(required)*: Non-empty YAML list of 1–3 hierarchical `kebab-case` tags.
- **`aliases`** *(optional)*: YAML list of common acronyms or alternate names (e.g., `IoC`, `Protobuf`, `gRPC`). **Omit this key completely** if there are no meaningful aliases.
- **`source`** *(required)*: Clean video title extracted from transcript headers or derived from the fallback filename (quoted string).
- **`source-type`** *(required)*: Literal value `youtube`.
- **`channel`** *(optional)*: Channel or author name **only if explicitly present** in the transcript. Omit if unknown.
- **`url`** *(optional)*: Video URL **only if explicitly present** in the transcript. Omit if unknown.
- **`created`** *(required)*: Generation date in ISO `YYYY-MM-DD` format (use today's local date).
- **Disallowed hub-only keys**: NEVER include `category` or `last-studied` (those are reserved for category hub MOC notes like `Software Engineering.md`).

---

## 3. Staging Output Path & Filename Naming

- **Output Path**: `<output_dir>/<Recommended Category>/<Note Title>.md`
  - Default `<output_dir>` is `<vault_path>/staging`.
  - During dry-run testing, `<output_dir>` points to an isolated preview directory; NEVER write into `<vault_path>` when `<output_dir>` is outside `<vault_path>`.
- **Obsidian Bases (`.base`) Compatibility**: Category `.base` views filter by `file.inFolder("<Category>")` and `file.name != "<Category>"`. Staging notes under `staging/<Category>/` keeps unreviewed notes out of production Base tables until human promotion.
- **Note Title & Filename**:
  - Use a clean, evergreen **Title Case** concept noun phrase with spaces (e.g., `Protocol Buffers.md`, `Factory Method Pattern.md`, `Circuit Breaker Pattern.md`).
  - Strip `_transcript`, underscores (`_`), file extensions, and YouTube clickbait/format suffixes (`Crash Course`, `Full Course`, `Tutorial`, `Explained`, `in 10 Minutes`, `2026`).
  - Preserve standard technical casing for acronyms/proper nouns (`gRPC.md`, `OAuth 2.0.md`, `SQL vs NoSQL.md`).

---

## 4. Document Structure & Formatting

### Heading Rules
- **NO duplicate `# <Note Title>` H1**: Never repeat the filename as an H1 heading at the top of the note (Obsidian renders the filename as the note title).
- **Opening Hook (immediately after frontmatter)**:
  - Open with either a crisp **1–3 sentence definition** bolding the core mental model, OR an `> [!IMPORTANT]` callout summarizing the key paradigm shift (as in `Enums.md`).
- **Section Hierarchy**:
  - Use `##` for major sections and `###` for subsections so Obsidian's Outline pane remains clean and uniform.
  - Use `---` horizontal rules sparingly between major conceptual sections in longer deep dives.

### Recommended Structural Blueprint
Adapt section depth to the transcript's technical richness (concise ~50–80 lines for focused topics; deeper 100–220 lines for rich crash courses):

1. **Opening Definition / Mental Model** (1–3 sentences or `> [!IMPORTANT]` callout)
2. **Core Mechanics / Key Components / Under the Hood** — Bulleted breakdown with bold lead-ins (`- **Term:** Explanation`) or numbered execution steps.
3. **Concrete Code Examples** — Fenced code blocks with language tags (`protobuf`, `java`, `python`, `sql`, `yaml`, `bash`, etc.):
   - Preserve accurate examples from the transcript.
   - Include concise inline comments explaining *why*, `// GOOD` vs `// BAD` contrasts, and `// Output:` where illuminating.
   - When adding brief clarifying examples, realistic backend/data-platform domain names (e.g., `TableConfig`, `EventRecord`, `CatalogType`, `DataPipeline`) fit the vault's native style — never fabricate facts not supported by the domain or transcript.
4. **Comparison Tables** — Use Markdown tables for A vs. B contrasts (e.g., Protobuf vs. JSON, `@Bean` vs. Stereotypes) or guarantees tables with a `Senior Note` column where architectural nuances matter.
5. **Mermaid Diagrams (Optional, High-Signal Only)** — Include a Mermaid `flowchart TD` or `sequenceDiagram` only when it genuinely clarifies a lifecycle, wire format, or architecture trade-off. Quote node labels containing parentheses or special characters (`id["Label (Detail)"]`).
6. **Trade-offs, Pitfalls & "When Not to Use"** — Include a dedicated section such as `## Notes & Pitfalls`, `## Architectural Best Practices & Anti-Patterns`, or `## When Not to Use <Topic>`.
7. **Leadership / Senior Lens (Optional)** — When the topic touches org standards, schema evolution governance, API contracts, or team-wide engineering norms, include a concise `> [!TIP]` callout or bullet grounded in practical engineering judgment (never generic management fluff).

---

## 5. Voice & Persona Guidelines

- **Audience**: Data Platform Engineer (L3 → Senior promotion track) building Java/JVM, distributed data systems, lakehouse infrastructure, and cloud backend services.
- **Evergreen Reference Voice**:
  - Write as a durable technical reference note, **NEVER** as a video summary.
  - Forbidden phrasing: *"In this video..."*, *"The speaker explains..."*, *"The presenter shows..."*, *"This crash course covers..."*, *"At 05:30..."*.
  - Direct, dense, zero filler — focus on invariants, under-the-hood mechanics, failure modes, memory/CPU/network trade-offs, and concrete alternatives.

---

## 6. Wikilink & Hygiene Rules

### Wikilinks
- Scan `<vault_path>` (excluding `misc/`, `.obsidian/`, `.git/`, and `staging/`) before drafting to inventory existing notes and their `aliases`.
- Prefer shortest-path wikilinks to **existing notes** (`[[Inversion of Control]]`, `[[NoSQL]]`, `[[SQL]]`, `[[Interface]]`).
- Heading and aliased wikilinks are supported when pointing to specific sections (`[[Spring Beans#@Bean Annotation]]`, `[[Design Patterns#Product Class|product]]`).
- Forward-looking ("red") wikilinks are acceptable ONLY for 2–5 high-value foundational concepts that merit their own future vault notes (e.g., `[[gRPC]]`, `[[Apache Avro]]`); do not over-link minor terms.

### Strict Hygiene Ban List
- **NO inline `#tags`** in prose.
- **NO raw HTML `<mark>` tags** (reserved for manual Highlightr study passes).
- **NO dangling `- [ ]` task checkboxes** (they leak into `obsidian-tasks-plugin` queries on category hub notes).
- **NO `obsidian://open?...` URIs** (always use `[[Wikilinks]]`).
- **NO triple-backtick inline code spans** (`` ```@Bean``` `` → always single backticks `` `@Bean` ``).
- **NO Markdown bold (`**...**`) inside fenced code blocks**.
- **NO Git operations** (`git add`, `git commit`, `git push`) and **NO edits to existing notes** outside the target staged output file.
