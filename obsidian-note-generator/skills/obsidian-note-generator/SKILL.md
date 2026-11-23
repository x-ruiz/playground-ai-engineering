---
name: obsidian-note-generator
description: >-
  Convert a YouTube URL/transcript, technical article/engineering blog URL, or official
  technical/product documentation URL (or pasted text) into an evergreen, Mastery
  Framework-aligned Obsidian reference note—or a staged Update Draft when an overlapping
  note already exists—under `staging/<Category>/`.
---

# Obsidian Note Generator

Produces high-signal evergreen engineering notes (or targeted Update Drafts) for `obsidian-notes`.

## Reference Assets
- **Vault Conventions (Required):** [references/vault_conventions.md](./references/vault_conventions.md) — categories, concise composable tags, `create`/`update` schemas, voice, and hygiene ban list.
- **Compact Exemplars (Load if needed):** [references/exemplars.md](./references/exemplars.md) — minimal `create` and `update` draft templates.
- **Validator:** [scripts/validate_note.py](./scripts/validate_note.py) — deterministic frontmatter, tag, and hygiene checker.

## Source Profiles

| `source-type` | Provenance Keys | Extraction Emphasis |
| :--- | :--- | :--- |
| `youtube` | `source`, `channel` *(opt)*, `url` *(opt)* | Strip spoken filler & timestamps; distill mental model, under-the-hood mechanics, code, and trade-offs. |
| `article` | `source`, `author` *(opt)*, `published` *(opt)*, `url` | Extract thesis, design rationale, benchmarks, and pitfalls; separate durable engineering patterns from vendor hype. |
| `documentation` | `source`, `vendor` *(opt)*, `url` | Strip marketing CTAs; capture architectural positioning, execution modes, CLI/API primitives, limits, IAM/cost drivers, and alternatives. |

## Workflow

1. **Ingest & Context (1 call when using ADK):**
   - Call `ingest_url(url)` (or `ingest_pasted_text(...)` if paywalled/pasted). It returns cleaned content, provenance metadata, suggested `source_type`, the live vault tag tree (`vault_tags`), existing note inventory (`vault_notes`), and deterministic `likely_overlap_notes`.
   - If `status == "duplicate"`, report the existing staged/completed run and stop unless the user asked to force reprocessing.
   - If running interactively outside ADK, fetch the URL/text and inspect `obsidian-notes` read-only.
2. **Decide `create` vs. `update`:**
   - Only if `likely_overlap_notes` (or `vault_notes`) shows a genuine topic match, call `read_vault_note(target_path)` to inspect existing headings and coverage.
   - **Substantial overlap** (same core concept or new angle belonging inside an existing note) → choose `note-action: update` targeting that existing note. Draft **only net-new content** with explicit merge placement (`Add under ## ...`, `New section: ## ...`). Never duplicate what the target note already explains.
   - **Distinct concept** → choose `note-action: create` and reference related existing notes via `[[Wikilinks]]`.
3. **Classify Category & Concise Composable Tags:**
   - Pick **1** canonical category from [references/vault_conventions.md](./references/vault_conventions.md).
   - Pick **1–3** hierarchical tags (`<pillar>/<domain>[/<topic>]`, max 3 levels). **Check `vault_tags` first and extend existing branches** rather than inventing parallel tags. Never emit parent + child pairs together, flat 1-level tags, or `-and-` filler.
4. **Stage & Validate:**
   - Call `stage_obsidian_note(...)` (or write `<output_dir>/<Category>/<Title>.md` for `create`, `<output_dir>/<Category>/<Existing Title> (Update).md` for `update` and run `validate_note.py --strict-warnings`).
   - If validation reports any errors or warnings, fix every item and re-stage until `validation_passed: true`.
   - **Safety:** Never edit or delete existing notes outside `staging/`, and never run `git` commands.
5. **Report:** Return a concise summary: action (`create` or `update`), staged file path, target note (if update), category, tags, and wikilinks.
