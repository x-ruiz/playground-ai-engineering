---
name: obsidian-youtube-note
description: >-
  Convert a YouTube transcript file or pasted transcript into an evergreen,
  structured Obsidian reference note aligned with the Mastery Framework vault
  (obsidian-notes) and stage it for human review under staging/<Category>/<Title>.md.
  Use this skill whenever processing a downloaded YouTube transcript (via headless
  `agy -p` pipeline or interactive chat) into an Obsidian note.
---

# Obsidian YouTube Note Generator

Transforms a raw YouTube transcript into an evergreen engineering reference note matching the conventions, voice, frontmatter schema, hierarchical tags, and wikilink graph of `obsidian-notes`.

## Reference Assets

Read these before writing the note:
- **Vault Conventions (Required):** [references/vault_conventions.md](./references/vault_conventions.md) — Mastery Framework categories, canonical hierarchical `kebab-case` tags, frontmatter provenance schema, heading/code/Mermaid standards, voice rules, and hygiene ban list.
- **Golden Exemplars:** [examples/golden_notes.md](./examples/golden_notes.md) — Annotated style excerpts from `obsidian-notes` plus a target YouTube-generated example.
- **Validator Script:** [scripts/validate_note.py](./scripts/validate_note.py) — Deterministic stdlib-only checker for frontmatter, hierarchical tags, filename, and Markdown hygiene.
- **Output Schema:** [resources/output_schema.json](./resources/output_schema.json) — JSON contract for headless `agy -p` runs.

---

## Inputs

The calling prompt provides:
- `transcript_path` (or inline transcript text)
- `fallback_title` (derived from the transcript filename, e.g., `Protocol Buffers Crash Course`)
- `vault_path` (path to `obsidian-notes`, used read-only for wikilink discovery and overlap checks)
- `output_dir` (defaults to `<vault_path>/staging`; may be overridden to a preview directory for dry runs)

---

## Workflow

### Step 1: Load Vault Conventions & Exemplars
1. Read [references/vault_conventions.md](./references/vault_conventions.md) in full.
2. Read [examples/golden_notes.md](./examples/golden_notes.md) to calibrate density, tone, code comments, tables, and callouts.

### Step 2: Analyze the Transcript
1. Read the full transcript file at `transcript_path`.
2. Extract header metadata if explicitly present (video title, channel name, URL). Never invent a channel or URL.
3. Strip timestamp noise mentally and distill the core engineering concepts:
   - What problem it solves and its core mental model
   - Under-the-hood mechanics, architecture, or wire/runtime behavior
   - Concrete code examples, schemas, commands, or comparisons from the transcript
   - Trade-offs, pitfalls, failure modes, alternatives, and "When Not to Use" criteria
4. Derive a clean **Title Case** concept name for the note filename (e.g., `Protocol Buffers Crash Course` → `Protocol Buffers`), removing `_transcript`, underscores, and tutorial fluff (`Crash Course`, `Full Tutorial`, `Explained`).

### Step 3: Inspect Vault Context (Read-Only)
1. Discover existing `.md` note filenames inside `<vault_path>` (excluding `misc/`, `.obsidian/`, `.git/`, and `staging/`):
   - If the calling prompt already supplies the vault note inventory, use it directly.
   - Otherwise, use built-in read-only file/search tools (or read-only research delegation) rather than shell commands so headless `--mode accept-edits` runs never hit shell permission denials.
2. Identify:
   - Existing notes that can be organically referenced via `[[Wikilinks]]`.
   - Any existing notes that closely overlap with the new topic (record them in `overlapping_notes` in the final output; **never** edit or overwrite existing vault notes).

### Step 4: Classify Category & Hierarchical Tags
1. Choose the **single best** Mastery Framework category from the 6 canonical categories in [references/vault_conventions.md](./references/vault_conventions.md).
2. Choose **1–3 hierarchical `kebab-case` tags** (`<category-slug>/<focus-area-slug>` + optional `/<subtopic-slug>`). Never emit legacy flat tags or duplicate parent tags.

### Step 5: Draft & Write the Staged Note
Write the note to:
```text
<output_dir>/<Recommended Category>/<Note Title>.md
```
(Create `<output_dir>/<Recommended Category>/` if it does not already exist.)

Ensure the note adheres strictly to every rule in [references/vault_conventions.md](./references/vault_conventions.md):
- Valid YAML frontmatter with `tags`, optional `aliases`, `source`, `source-type: youtube`, optional `channel`/`url` (only when present in transcript), and `created` (today's `YYYY-MM-DD`).
- No duplicate `# <Note Title>` H1 heading — open directly with a 1–3 sentence definition or `> [!IMPORTANT]` callout.
- Evergreen engineering reference voice (zero "In this video..." or "The speaker..." narration).
- Consistent `##` / `###` hierarchy, concrete fenced code blocks, Markdown comparison tables where helpful, optional high-signal Mermaid diagram, and explicit trade-offs / "When Not to Use".
- Zero inline `#tags`, zero `<mark>` HTML, zero `- [ ]` checkboxes, zero `obsidian://open` URIs, zero triple-backtick inline code spans.
- **Safety:** Never modify any file inside `<vault_path>` outside `<output_dir>`, and never run `git commit` or `git push`.

### Step 6: Validate & Return Structured Result
1. **If shell commands are permitted** (interactive sessions or runs with shell access), run the bundled validator script against the written note:
   ```bash
   python3 <skill_dir>/scripts/validate_note.py "<output_note_path>" --strict-warnings
   ```
   Fix any reported errors or warnings and re-run until exit status is `0`.
2. **If running in zero-shell headless mode (`--mode accept-edits`)** where shell commands are disabled (and the caller executes `validate_note.py` externally), perform a strict manual verification of every rule in [references/vault_conventions.md](./references/vault_conventions.md) (YAML frontmatter keys/types, hierarchical `kebab-case` tags, ISO `created` date, no duplicate H1, no inline `#tags`/`<mark>`/`- [ ]`/`obsidian://open`, no video-recap phrasing, balanced code fences).
3. Return the final summary conforming to [resources/output_schema.json](./resources/output_schema.json) (when `--json-schema` is active, output valid JSON matching that schema; in interactive chat, provide a concise summary with the output path, category, tags, and wikilinks).
