# Obsidian Vault Conventions (`obsidian-notes`)

Compact specification for generating `create` notes and `update` drafts staged under `obsidian-notes/staging/<Category>/`.

## 1. Categories & Concise Composable Tags

Assign **1** exact category folder and **1–3** hierarchical kebab-case tags (`<pillar>/<domain>[/<topic>]`, 2–3 levels).
- **Reuse-first:** Always inspect the live vault tag tree first and extend existing prefixes (`ai-engineering/agents` → `ai-engineering/agents/mcp`).
- **Concise:** 1–2 short words per segment (<= 22 chars), no `-and-` conjunctions, no `#` prefix, no flat 1-level tags, and **no parent + child duplicates** on the same note.

| Category Folder | Level-1 Pillar | Concise Level-2 Domains | Example Level-3 Extensions |
| :--- | :--- | :--- | :--- |
| `AI Engineering` | `ai-engineering` | `agents`, `models`, `ml-pipelines`, `mlops`, `safety` | `agents/mcp`, `agents/rag`, `agents/memory`, `agents/harness`, `models/evals` |
| `Data Processing` | `data-processing` | `pipelines`, `frameworks`, `storage`, `streaming`, `quality` | `frameworks/spark`, `storage/iceberg`, `streaming/kafka`, `pipelines/dbt` |
| `Cloud Infrastructure` | `cloud-infrastructure` | `architecture`, `iac`, `containers`, `networking`, `services` | `containers/k8s`, `iac/terraform`, `services/gcp` |
| `Information Security` | `information-security` | `appsec`, `auth`, `crypto`, `threats`, `compliance` | `auth/oauth2`, `crypto/tls`, `threats/prompt-injection` |
| `Software Engineering` | `software-engineering` | `principles`, `patterns`, `frameworks`, `languages`, `testing`, `cicd` | `patterns/creational`, `languages/java`, `frameworks/spring`, `frameworks/protobuf` |
| `System Resiliency` | `system-resiliency` | `observability`, `fault-tolerance`, `chaos`, `incidents`, `dr` | `fault-tolerance/circuit-breakers`, `observability/otel` |

## 2. YAML Frontmatter Schemas

### New Note (`note-action: create`, default)
Filename: `<Category>/<Clean Title Case Concept>.md` (strip `_transcript`, underscores, clickbait like `Crash Course` / `Explained`).
```yaml
---
tags:
  - ai-engineering/agents/harness
aliases:
  - Agent Harness
source: "Building Production AI Agent Harnesses"
source-type: article
author: "Databricks Engineering Blog"
published: 2026-04-15
url: "https://www.databricks.com/blog/ai-harness"
created: 2026-11-23
---
```

### Update Draft (`note-action: update`)
Filename: `<Category>/<Existing Note Title> (Update).md` (never modify existing notes in place).
```yaml
---
note-action: update
target-note: "[[Modern AI Architecture]]"
target-path: "AI Engineering/Modern AI Architecture.md"
tags:
  - ai-engineering/agents/harness
source: "Building Production AI Agent Harnesses"
source-type: article
author: "Databricks Engineering Blog"
url: "https://www.databricks.com/blog/ai-harness"
created: 2026-11-23
---
```

### Field Rules
- **Required:** `tags` (1–3 concise hierarchical tags), `source` (quoted title), `source-type` (`youtube` | `article` | `documentation`), `created` (`YYYY-MM-DD`).
- **Required on `note-action: update`:** `target-note` (`"[[Exact Note Title]]"`), `target-path` (vault-relative `.md` path).
- **Optional (omit if unknown — never fabricate):** `aliases`, `channel` (YouTube), `author` & `published` (`YYYY-MM-DD`, articles), `vendor` (docs), `url`.
- **Forbidden:** Hub-only keys `category` and `last-studied`.

## 3. Structure, Voice & Wikilinks
- **Audience:** Data Platform Engineer (L3 → Senior track: JVM/Java, distributed data, lakehouses, cloud/AI systems).
- **No duplicate H1:** Never repeat the filename as `# Title`. Open directly with a crisp 1–3 sentence definition bolding the mental model, or an `> [!IMPORTANT]` / `> [!NOTE]` callout.
- **Hierarchy:** `##` major sections, `###` subsections. Include core mechanics, concrete fenced code/CLI blocks (`// GOOD` vs `// BAD` where helpful), comparison tables (`Senior Note` column), optional high-signal Mermaid (quote labels with special chars: `id["Label (Detail)"]`), and explicit trade-offs / `## When Not to Use`.
- **Update Draft body:** Open with a `> [!NOTE]` naming `[[Target Note]]` + why to merge, followed by `## Proposed Frontmatter Additions` (if any) and ready-to-paste `## Proposed Additions to ...` / `## Proposed New Section: ...` containing **only net-new content**.
- **Evergreen voice:** Zero recap/meta phrasing (*"In this video..."*, *"The speaker..."*, *"In this article..."*, *"The author argues..."*, *"This blog post..."*, *"This page describes..."*, *"In this documentation..."*, *"Click here to get started..."*) and zero vendor hype.
- **Wikilinks:** Prefer existing vault notes (`[[SQL]]`, `[[NoSQL]]`, `[[Interface]]`, etc.); limit forward-looking ("red") links to 2–5 foundational concepts.

## 4. Strict Hygiene Ban List
- No inline `#tags` in prose
- No `<mark>` HTML
- No `- [ ]` task checkboxes
- No `obsidian://open` URIs
- No inline triple-backticks (use single backticks)
- No `**bold**` inside fenced code blocks
- No edits outside `staging/` and no `git` commands
