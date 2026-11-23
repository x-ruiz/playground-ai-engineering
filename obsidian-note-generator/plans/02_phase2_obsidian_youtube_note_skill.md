# Phase 2 Implementation Plan: Author & Validate `obsidian-youtube-note` Skill

> **Parent Plan:** [01_yt_to_obsidian_pipeline.md](./01_yt_to_obsidian_pipeline.md)  
> **Phase 1 Audit Input:** [phase1_vault_style_audit.md](../docs/phase1_vault_style_audit.md)

---

## 1. Objective & Scope

Author, install, and validate the standalone Antigravity Skill **`obsidian-youtube-note`** that transforms a YouTube transcript file into an evergreen, publication-grade Obsidian reference note aligned with `../obsidian-notes` and staged for human review at `staging/<Recommended Category>/<Note Title>.md`.

Phase 2 is complete when the skill is version-controlled in this repo, symlinked into Antigravity's global discovery path (`~/.gemini/config/skills/obsidian-youtube-note`), and verified end-to-end via headless `agy -p` against a realistic transcript fixture into a dry-run output directory — passing both automated structural validation and manual voice/formatting review.

*(Python watcher daemon, queue worker, SQLite ledger, and `AgyCliRunner` remain scoped to Phase 3.)*

---

## 2. Locked-In Decisions Carrying Into Phase 2

All conventions from [phase1_vault_style_audit.md](../docs/phase1_vault_style_audit.md) plus user confirmations:

| Area | Locked-In Rule |
| :--- | :--- |
| **YAML Frontmatter** | Include `tags` (required), `aliases` (optional, for acronyms/alternate names), and provenance metadata: `source`, `source-type: youtube`, `created: YYYY-MM-DD`, plus optional `channel` / `url` when present in the transcript |
| **Tag Taxonomy** | Exclusively **hierarchical `kebab-case` tags** (`<category-slug>/<focus-area-slug>` + optional `/<subtopic-slug>`) in YAML `tags:` list format; zero inline `#tags`; no legacy flat tags |
| **Category Classification** | Exactly one of the 6 Mastery Framework categories: `Cloud Infrastructure`, `Data Processing`, `Information Security`, `Software Engineering`, `System Resiliency`, `AI Engineering` |
| **Output Path** | `<staging_root>/<Recommended Category>/<Note Title>.md` (defaults to `<vault_path>/staging/<Recommended Category>/<Note Title>.md`; overridable for dry-run validation) |
| **Note Title & Filename** | Clean **Title Case** concept noun phrase (`Protocol Buffers.md`); strip `_transcript`, underscores, and clickbait suffixes (`Crash Course`, `Full Guide`, `Explained in 10 Minutes`) |
| **Heading Style** | Never repeat the filename as an `# H1` title; open directly with a 1–3 sentence definition or `> [!IMPORTANT]` mental-model callout; use `##` top-level sections and `###` subsections |
| **Persona & Voice** | Evergreen engineering reference for a Data Platform Engineer (L3 → Senior): zero video-recap narration ("In this video..."), dense under-the-hood mechanics, concrete code/tables, optional Mermaid diagrams, explicit trade-offs & "When Not to Use" |
| **Vault Hygiene** | No raw HTML `<mark>` tags, no dangling `- [ ]` checkboxes (which trigger `obsidian-tasks-plugin` hub queries), no `obsidian://open` URIs, no triple-backtick inline spans |
| **`.base` Compatibility** | Staging under `staging/<Category>/` keeps unreviewed notes out of `<Category>.base` (`file.inFolder("<Category>")`) until human promotion |
| **Git Safety** | Skill must **never** run `git commit`, `git push`, or modify existing vault notes outside the target staging path |

---

## 3. Target Files to Create in Phase 2

```text
<repo-root>/
├── README.md
├── scripts/
│   └── install_skill.py                               # Cross-platform (macOS + Linux) symlink installer for all skills
└── obsidian-youtube-note/                             # Skill root directory (named after the skill)
    ├── SKILL.md                                       # Concise workflow & progressive-disclosure links
    ├── references/
    │   └── vault_conventions.md                       # Complete Mastery Framework, tag slugs, frontmatter, style & anti-pattern rules
    ├── examples/
    │   └── golden_notes.md                            # Annotated excerpts from Builder Pattern, Enums, Factory Method, IoC, Spring
    ├── resources/
    │   └── output_schema.json                         # JSON schema for `agy -p --output-format json --json-schema`
    ├── scripts/
    │   └── validate_note.py                           # Stdlib-only validator for generated note frontmatter, tags & hygiene
    ├── docs/
    │   └── phase1_vault_style_audit.md
    ├── plans/
    │   ├── 01_yt_to_obsidian_pipeline.md
    │   └── 02_phase2_obsidian_youtube_note_skill.md   # This plan
    └── tests/
        └── fixtures/
            └── Protocol_Buffers_Crash_Course_transcript
```

---

## 4. Detailed Component Design

### 4.1 `skills/obsidian-youtube-note/SKILL.md`
Follow Antigravity's progressive-disclosure best practices (`name` and third-person `description` frontmatter, concise procedural steps, relative links into `references/`, `examples/`, `resources/`, and `scripts/`):

- **Frontmatter**:
  - `name: obsidian-youtube-note`
  - `description`: Third-person trigger description covering both headless pipeline runs (`agy -p`) and interactive usage ("Use this skill when converting a YouTube transcript file or pasted transcript into a structured Obsidian note for the Mastery Framework vault (`obsidian-notes`)...").
- **Inputs expected in the prompt**:
  - `transcript_path` (or inline transcript text)
  - `fallback_title` (derived from filename, e.g., `Protocol Buffers Crash Course`)
  - `vault_path` (path to `obsidian-notes`, read-only except for the staging output directory)
  - `output_dir` (defaults to `<vault_path>/staging`; overridden to a temp folder during `--dry-run`)
- **6-Step Execution Workflow**:
  1. **Load Conventions & Exemplars**: Read [vault_conventions.md](../references/vault_conventions.md) and consult [golden_notes.md](../examples/golden_notes.md) for structural patterns and tone.
  2. **Analyze Transcript**: Read the full transcript, extract any header metadata (video title, channel, URL), strip timestamp noise mentally, derive a clean evergreen Title Case concept name, and identify key mental models, mechanics, code examples, trade-offs, and senior/architectural implications.
  3. **Inspect Vault Context (Read-Only)**: Scan existing note filenames in `<vault_path>` (excluding `misc/`, `.obsidian/`, `.git/`, and `staging/`) to:
     - Discover valid `[[Wikilinks]]` to existing notes (and check for duplicate/overlapping notes to flag in warnings).
     - Confirm exact category naming against `README.md` if needed.
  4. **Classify & Tag**: Select the single best Mastery Framework category and 1–3 canonical hierarchical `kebab-case` tags from `references/vault_conventions.md`.
  5. **Draft & Write Staged Note**: Write `<output_dir>/<Recommended Category>/<Note Title>.md` (creating parent directories if needed) adhering strictly to the frontmatter schema, heading rules, code/diagram guidelines, and hygiene rules. Never overwrite an existing note in production folders; never run git commands.
  6. **Validate & Return Structured Summary**: Run `python3 ./scripts/validate_note.py "<output_note_path>"` (resolving relative to the skill directory) to verify frontmatter, hierarchical tags, filename, and Markdown hygiene; fix any reported violations before completing. Return a concise final response conforming to `resources/output_schema.json`.

### 4.2 `skills/obsidian-youtube-note/references/vault_conventions.md`
The authoritative playbook distilled directly from [phase1_vault_style_audit.md](../docs/phase1_vault_style_audit.md):

1. **Mastery Framework Categories & Canonical Hierarchical Tag Table**:
   - All 6 category folders and their exact canonical `<category-slug>/<focus-area-slug>` mappings:
     - `Cloud Infrastructure` (`cloud-infrastructure/...`)
     - `Data Processing` (`data-processing/...`)
     - `Information Security` (`information-security/...`)
     - `Software Engineering` (`software-engineering/...`)
     - `System Resiliency` (`system-resiliency/...`)
     - `AI Engineering` (`ai-engineering/...`)
   - Tie-breaker guidance for cross-cutting topics (e.g., Protocol Buffers serialization mechanics & RPC contracts → `Software Engineering` or `Data Processing` depending on whether the transcript emphasizes service APIs/code-gen vs. data pipelines/storage schemas; Kafka/Spark/databases → `Data Processing`; Spring/design patterns/languages → `Software Engineering`).
   - Rules for adding optional 3rd-level `<subtopic-slug>` tags (e.g., `software-engineering/languages/java`, `software-engineering/design-patterns/creational-patterns`, `data-processing/data-quality-and-transformation/serialization`).
2. **YAML Frontmatter Specification**:
   ```yaml
   ---
   tags:
     - software-engineering/frameworks
     - software-engineering/frameworks/protobuf
   aliases:
     - Protobuf
   source: "Protocol Buffers Crash Course"
   source-type: youtube
   channel: "Hussein Nasser"        # optional: include only when present in transcript
   url: "https://youtube.com/..."   # optional: include only when present in transcript
   created: 2026-11-23
   ---
   ```
   - Rules: omit `aliases`, `channel`, and `url` rather than leaving empty strings/nulls; always use ISO `YYYY-MM-DD` for `created`; never include `category` or `last-studied` (those belong to category hub MOC notes only).
3. **Document Structure & Section Blueprint**:
   - Opening hook (no duplicate `# <Note Title>` H1): 1–3 sentence definition or `> [!IMPORTANT]` callout.
   - Standard `##` / `###` hierarchy; `---` dividers sparingly on long deep dives.
   - Code block standards (language tags, `// GOOD` vs `// BAD`, `// Output:`, realistic backend/data-platform framing when adding clarifying snippets without inventing unverified claims).
   - Comparison tables (including `Senior Note` column for guarantees/trade-offs when helpful).
   - Mermaid diagram guidance (use `flowchart TD` / `sequenceDiagram` only when it clarifies a non-trivial lifecycle, wire format, or architectural trade-off; valid syntax with quoted special labels).
   - Trade-offs & anti-patterns section (`Notes & Pitfalls`, `When Not to Use`, or `Architectural Best Practices & Anti-Patterns`).
   - Leadership Lens / Senior Takeaway callout (`> [!TIP]`) when relevant.
4. **Wikilink & Hygiene Rules**:
   - Shortest-path `[[Note Name]]`, section `[[Note Name#Heading]]`, aliased `[[Note Name#Heading|label]]`.
   - Prefer existing vault notes; allow at most 2–5 high-value forward ("red") wikilinks for foundational concepts.
   - Strict ban list: no inline `#tags`, no `<mark>` HTML, no `- [ ]` tasks, no `obsidian://open` links, no triple-backtick inline code, no Markdown bold inside fenced code blocks, no "In this video..." phrasing.

### 4.3 `skills/obsidian-youtube-note/examples/golden_notes.md`
Curated, annotated style excerpts extracted from the 4 golden exemplars identified in Phase 1:
1. **Full Deep-Dive Pattern** — Annotated excerpt from `Builder Pattern.md` (hierarchical tag, opening definition, Key Components, data-platform Java code, Notes & Pitfalls, `> [!IMPORTANT]` callout, styled Mermaid diagram).
2. **Under-the-Hood + Senior Engineering Lens** — Annotated excerpt from `Enums.md` (`> [!IMPORTANT]` opener, bytecode/internal mechanics, progressive patterns, `Senior Note` table, Best Practices & Anti-Patterns).
3. **Concise Reference Note** — Annotated excerpt from `Factory Method Pattern.md` (tight ~50-line format for shorter/focused videos).
4. **Conceptual Contrast & Trade-Offs** — Annotated excerpts from `Inversion of Control.md` and `Spring.md` (`aliases`, comparison table, `// GOOD` vs `// BAD`, alternatives, `When Not to Use`).
5. **Annotated Synthetic YouTube-Generated Example** — One short end-to-end example showing the new YAML provenance fields (`source`, `source-type: youtube`, `created`) combined with the vault's exact body style so the agent sees the exact target output shape.

### 4.4 `skills/obsidian-youtube-note/resources/output_schema.json`
JSON Schema (compatible with `agy -p --output-format json --json-schema`) enforcing a machine-readable return payload for both Phase 2 validation and Phase 3's `AgyCliRunner`:
```json
{
  "type": "object",
  "required": [
    "status",
    "recommended_category",
    "note_title",
    "output_path",
    "tags",
    "existing_wikilinks",
    "overlapping_notes",
    "validation_passed",
    "summary"
  ],
  "properties": {
    "status": { "type": "string", "enum": ["created", "failed"] },
    "recommended_category": {
      "type": "string",
      "enum": [
        "Cloud Infrastructure",
        "Data Processing",
        "Information Security",
        "Software Engineering",
        "System Resiliency",
        "AI Engineering"
      ]
    },
    "note_title": { "type": "string" },
    "output_path": { "type": "string" },
    "tags": { "type": "array", "items": { "type": "string" }, "minItems": 1 },
    "aliases": { "type": "array", "items": { "type": "string" } },
    "existing_wikilinks": { "type": "array", "items": { "type": "string" } },
    "overlapping_notes": { "type": "array", "items": { "type": "string" } },
    "validation_passed": { "type": "boolean" },
    "summary": { "type": "string" }
  },
  "additionalProperties": false
}
```

### 4.5 `skills/obsidian-youtube-note/scripts/validate_note.py`
A lightweight **Python 3.11+ stdlib-only** validation script (no `uv`/PyYAML prerequisite in Phase 2, keeping the skill portable even when invoked standalone outside the project venv) that parses the generated note and checks:
1. File exists, is UTF-8, and parent folder matches one of the 6 Mastery Framework categories (when `--check-category-dir` is enabled, default on).
2. Filename is `.md`, contains no `_transcript` or underscores, and starts with an uppercase character.
3. YAML frontmatter opens on line 1 (`---`) and closes cleanly (`---`).
4. Required frontmatter keys exist and conform:
   - `tags`: non-empty list; every tag matches `^(cloud-infrastructure|data-processing|information-security|software-engineering|system-resiliency|ai-engineering)/[a-z0-9-]+(/[a-z0-9-]+)*$` (enforcing hierarchical `kebab-case`, no leading `#`, no spaces/uppercase).
   - `source`: non-empty string.
   - `source-type`: equals `youtube`.
   - `created`: matches `^\d{4}-\d{2}-\d{2}$`.
   - `aliases` (if present): non-empty list of strings.
   - Disallowed hub-only keys (`category`, `last-studied`) are absent.
5. Markdown body hygiene (ignoring fenced code blocks):
   - First non-empty line is NOT `# <Note Title>` (no duplicate H1 matching filename).
   - Zero inline `#tags` (e.g., `(^|\s)#[a-z][a-z0-9/-]+`).
   - Zero `<mark` HTML tags.
   - Zero dangling `- [ ]` task checkboxes.
   - Zero `obsidian://open` URIs.
   - Balanced code fences (` ``` `).
   - Warning (non-fatal) if body contains video-recap phrases like `"in this video"` or `"the speaker"`.
6. Prints structured JSON or human-readable report and exits `0` on pass, `1` on errors.

### 4.6 Cross-Platform Skill Installer (`scripts/install_skill.py`)
A clean Python 3.11+ stdlib-only script (later imported/wrapped by Phase 3's `yt-to-obsidian install-skill` CLI command):
- Default target: `Path.home() / ".gemini" / "config" / "skills" / "obsidian-youtube-note"` (works identically on macOS and Linux).
- Creates parent directories (`~/.gemini/config/skills/`) if missing.
- Creates (or safely updates with `--force`) a symlink pointing to `<repo_root>/obsidian-youtube-note` (auto-discovering every top-level `<skill-name>/SKILL.md` in the repository).
- Supports `--check` (verifies symlink exists, resolves to repo skill, and `SKILL.md` is readable) and `--uninstall` (removes symlink only if it is a symlink, never deleting a real directory).

### 4.7 Sample Transcript Fixture (`tests/fixtures/Protocol_Buffers_Crash_Course_transcript`)
- If a real downloaded `Protocol_Buffers_Crash_Course_transcript` exists in `~/Downloads`, inspect its exact format (timestamps, headers, line wrapping) to mirror real browser-extension output faithfully; otherwise craft a realistic extensionless timestamped YouTube transcript fixture covering Protocol Buffers (`.proto` schemas, field tags, wire encoding vs JSON, schema evolution/backwards compatibility, gRPC integration, and trade-offs).
- Keep fixture clean and self-contained inside `tests/fixtures/` so both Phase 2 dry-run tests and Phase 5 `pytest` tests can reuse it.

---

## 5. Step-by-Step Execution Order

1. **Author skill reference & schema assets**:
   - Create `skills/obsidian-youtube-note/references/vault_conventions.md`
   - Create `skills/obsidian-youtube-note/examples/golden_notes.md`
   - Create `skills/obsidian-youtube-note/resources/output_schema.json`
2. **Author validation & installer scripts**:
   - Create `skills/obsidian-youtube-note/scripts/validate_note.py` (and self-test it against valid + intentionally broken synthetic notes in `/tmp`)
   - Create `scripts/install_skill.py`
3. **Author `skills/obsidian-youtube-note/SKILL.md`**:
   - Wire together the 6-step procedure, progressive-disclosure links, validator invocation, and JSON output contract.
4. **Install & verify skill discovery**:
   - Run `python3 scripts/install_skill.py` and `python3 scripts/install_skill.py --check` to verify `~/.gemini/config/skills/obsidian-youtube-note/SKILL.md` resolves cleanly.
5. **Create sample transcript fixture**:
   - Add `tests/fixtures/Protocol_Buffers_Crash_Course_transcript` (extensionless, matching the locked-in filename pattern).
6. **Run headless `agy -p` dry-run validation**:
   - Create an isolated temporary dry-run output directory (e.g., `/tmp/yt-to-obsidian-dryrun/`).
   - Invoke `agy -p` referencing the `obsidian-youtube-note` skill, passing the fixture transcript, `--add-dir ../obsidian-notes` (read-only context for wikilinks), `--add-dir /tmp/yt-to-obsidian-dryrun`, `--mode accept-edits`, `--output-format json`, `--json-schema skills/obsidian-youtube-note/resources/output_schema.json`, and `--print-timeout 300s`.
   - Confirm `../obsidian-notes` remains completely untouched (`git status` clean in `../obsidian-notes`).
7. **Inspect output & iterate**:
   - Run `validate_note.py` on the generated note.
   - Audit the generated Markdown against `Builder Pattern.md` and `Enums.md` for voice, density, frontmatter, hierarchical tags, wikilinks, code quality, Mermaid validity, and absence of video-recap fluff.
   - Refine `SKILL.md` / `vault_conventions.md` / `golden_notes.md` and re-run dry-run if any defect appears.

---

## 6. Verification & Acceptance Criteria

Phase 2 is verified and ready for Phase 3 when ALL of the following pass:

- [ ] `skills/obsidian-youtube-note/` contains `SKILL.md`, `references/vault_conventions.md`, `examples/golden_notes.md`, `resources/output_schema.json`, and `scripts/validate_note.py`.
- [ ] `python3 scripts/install_skill.py --check` exits `0` and confirms `~/.gemini/config/skills/obsidian-youtube-note` symlinks to the repository skill.
- [ ] `validate_note.py` passes on valid notes and catches every invalid case (flat tags, inline `#tags`, duplicate H1 title, missing provenance fields, `<mark>` tags, `- [ ]` checkboxes, invalid category folder).
- [ ] Headless `agy -p` dry-run against `tests/fixtures/Protocol_Buffers_Crash_Course_transcript`:
  - Activates the `obsidian-youtube-note` skill automatically.
  - Produces valid JSON matching `output_schema.json`.
  - Writes `<dry_run_dir>/<Valid Category>/<Clean Title>.md` (e.g., `Protocol Buffers.md`, not `Protocol_Buffers_Crash_Course_transcript.md`).
  - Passes `validate_note.py` with exit code `0` and zero warnings.
  - Reads `../obsidian-notes` for wikilink awareness without modifying any file in `../obsidian-notes`.
  - Matches the vault's evergreen engineering reference voice, hierarchical `kebab-case` tags, and frontmatter provenance schema.

---

## 7. Risks & Mitigations

| Risk | Mitigation |
| :--- | :--- |
| **`agy -p` doesn't discover the skill or skips `references/`** | Install symlink into `~/.gemini/config/skills/obsidian-youtube-note` AND reference the skill explicitly by name (`obsidian-youtube-note`) in the prompt; verify in the dry-run JSON/logs that `SKILL.md` and `vault_conventions.md` were read. |
| **Agent writes into `../obsidian-notes` during dry-run** | Pass an explicit `output_dir` pointing to `/tmp/yt-to-obsidian-dryrun` in the prompt and explicitly state in `SKILL.md` that `<vault_path>` is read-only when `output_dir` is outside `<vault_path>`; verify `../obsidian-notes` is untouched after the run. |
| **Agent drifts into "In this video..." summary tone** | Include explicit positive + negative voice rules in `vault_conventions.md`, provide a concrete synthetic YouTube-to-note exemplar in `golden_notes.md`, and flag recap phrases in `validate_note.py`. |
| **Cross-platform symlink differences (macOS vs Linux)** | Use `pathlib.Path.symlink_to()` with resolved absolute paths in `scripts/install_skill.py`, avoiding GNU/BSD `ln` flag incompatibilities. |
