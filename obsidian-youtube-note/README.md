# `obsidian-youtube-note`

An Antigravity Skill and cross-platform (macOS + Linux) event-driven Python pipeline (`yt-to-obsidian`) that watches `~/Downloads` for downloaded YouTube transcripts and automatically generates evergreen, Mastery Framework-aligned Obsidian reference notes staged for human review under `obsidian-notes/staging/<Category>/<Title>.md`.

---

## 1. Architecture Diagram

```mermaid
flowchart TB
    subgraph Browser["1. Capture (Browser)"]
        Ext["YouTube Transcript Extension"]
        Downloads["~/Downloads\ne.g. Protocol_Buffers_Crash_Course_transcript"]
        Ext -->|"Downloads file\n(.crdownload -> rename)"| Downloads
    end

    subgraph Daemon["2. Python Watcher Daemon (yt-to-obsidian / uv + Python 3.12)"]
        Watcher["watcher.py\nwatchdog (FSEvents / inotify)\n+ StabilityDebouncer"]
        Matcher["matcher.py\n*_transcript filter\n+ fallback title"]
        Worker["queue_worker.py\nSingle Sequential Worker\n+ TranscriptProcessor"]
        Parser["parser.py\nUTF-8 / .vtt / .srt / timestamps\n+ SHA-256 hash"]
        State[("state.py\nSQLite WAL state.db\n+ Rotating Logs")]
        Runner["runner.py\nAgentRunner Protocol\n-> AgyCliRunner"]
        Validator["scripts/validate_note.py\nDeterministic Frontmatter,\nTag & Hygiene Validator"]
        Notifier["notifier.py\nosascript (macOS) /\nnotify-send (Linux)"]

        Watcher --> Matcher
        Matcher -->|"Matched & stable"| Worker
        Worker --> Parser
        Worker <-->|"Dedup check & run ledger"| State
        Worker --> Runner
        Runner -->|"Post-run check\n(strict warnings)"| Validator
        Worker --> Notifier
    end

    subgraph Agy["3. Headless Antigravity Agent (agy -p, Zero-Shell --mode accept-edits)"]
        Agent["agy -p CLI\n(--output-format json\n--json-schema output_schema.json)"]
        Skill["Skill Symlink\n~/.gemini/config/skills/obsidian-youtube-note\n(SKILL.md, vault_conventions.md, golden_notes.md)"]
        Agent -->|"Loads skill playbook"| Skill
    end

    subgraph Vault["4. Obsidian Vault (../obsidian-notes)"]
        Existing["Existing Category Notes\n(Read-Only Wikilink Inventory)"]
        Staging["staging/<Recommended Category>/<Note Title>.md\n(Isolated from .base views)"]
        Prod["<Recommended Category>/<Note Title>.md\n(Indexed by Obsidian Bases)"]
        Staging -->|"Human review &\ndrag-and-drop promotion"| Prod
    end

    Downloads -->|"OS FS Event\n(on_created / on_moved)"| Watcher
    Runner -->|"Pre-scans notes\n(read-only)"| Existing
    Runner -->|"Spawns zero-shell subprocess\nwith normalized transcript"| Agent
    Agent -->|"Writes staged Markdown"| Staging
    Validator -->|"Validates path containment\n& Markdown rules"| Staging
```

---

## 2. End-to-End Processing Flow

```mermaid
sequenceDiagram
    autonumber
    participant Browser as Browser Extension
    participant FS as ~/Downloads
    participant Watcher as watcher.py + matcher.py
    participant Worker as queue_worker.py + parser.py
    participant DB as state.py (SQLite WAL)
    participant Runner as AgyCliRunner (runner.py)
    participant Agy as agy -p (obsidian-youtube-note)
    participant Vault as ../obsidian-notes

    Browser->>FS: Write temp file (*_transcript.crdownload)
    FS-->>Watcher: on_created (.crdownload)
    Note over Watcher: Ignored by IGNORED_TEMP_SUFFIXES

    Browser->>FS: Atomic rename -> Protocol_Buffers_Crash_Course_transcript
    FS-->>Watcher: on_moved (dest_path)
    Watcher->>Watcher: StabilityDebouncer waits for non-empty + 2 identical (size, mtime_ns) checks
    Watcher->>Worker: Enqueue stabilized file path

    Worker->>FS: Read raw bytes, compute SHA-256, extract headers & strip timestamps
    Worker->>DB: get_completed(sha256)

    alt Already completed (and not --force)
        DB-->>Worker: Existing LedgerRecord
        Note over Worker: Log duplicate skip & return
    else New transcript
        Worker->>DB: record_start(sha256, source_path, fallback_title)
        Worker->>Runner: run(RunRequest)
        Runner->>Vault: Pre-scan existing .md titles & aliases (read-only)
        Runner->>Agy: Spawn agy -p --mode accept-edits --json-schema (zero Bash)
        Agy->>Vault: Write staging/<Recommended Category>/<Note Title>.md
        Agy-->>Runner: JSON envelope with structured_output

        Runner->>Runner: Enforce output_path inside output_dir
        Runner->>Vault: Run scripts/validate_note.py --strict-warnings

        opt Validation fails (up to max_retries)
            Runner->>Agy: Retry prompt with exact validator errors/warnings
            Agy->>Vault: Rewrite corrected note
            Runner->>Vault: Re-run validate_note.py
        end

        alt Validation passed
            Runner-->>Worker: RunResult (status="created", validation_passed=true)
            Worker->>DB: record_completed(category, note_title, output_path, tags, duration)
            opt post_process.action == "move"
                Worker->>FS: Move source transcript to archive_dir
            end
            Worker-->>Browser: Desktop notification (Obsidian note staged)
        else Runner or validation error
            Runner-->>Worker: Raise RunnerError
            Worker->>DB: record_failed(error, duration)
            Worker-->>Browser: Desktop notification (yt-to-obsidian failed)
        end
    end
```

---

## 3. Data & State Diagram

```mermaid
erDiagram
    RAW_TRANSCRIPT_FILE ||--|| TRANSCRIPT_DOCUMENT : "parsed & hashed by parser.py"
    TRANSCRIPT_DOCUMENT ||--o{ TRANSCRIPT_RUNS : "deduplicated by sha256 in state.db"
    TRANSCRIPT_DOCUMENT ||--|| AGY_STRUCTURED_OUTPUT : "processed by agy -p (--json-schema)"
    AGY_STRUCTURED_OUTPUT ||--|| STAGED_OBSIDIAN_NOTE : "validated by validate_note.py"
    TRANSCRIPT_RUNS ||--o| STAGED_OBSIDIAN_NOTE : "records output_note_path"

    RAW_TRANSCRIPT_FILE {
        string filename "*_transcript or .txt/.md/.srt/.vtt"
        bytes raw_bytes "UTF-8 / BOM text (binary rejected)"
        int st_size "Must be > 0 and stable"
        int st_mtime_ns "Checked across stability_checks"
    }

    TRANSCRIPT_DOCUMENT {
        string sha256 "64-char hex digest of raw_bytes"
        string source_path "Resolved path in ~/Downloads"
        string fallback_title "Derived from filename stem"
        string detected_title "Optional Title header"
        string channel "Optional Channel/Author header"
        string url "Optional URL/Link header"
        string detected_format "plain | timestamped | srt | vtt"
        string cleaned_text "Normalized cues without timestamp noise"
        int char_count "Length of cleaned_text"
    }

    TRANSCRIPT_RUNS {
        int id PK "AUTOINCREMENT"
        string sha256 "Indexed with status"
        string source_path "Original transcript path"
        string fallback_title "Fallback title"
        string status "processing | completed | failed"
        string recommended_category "One of 6 Mastery Framework categories"
        string note_title "Clean Title Case concept title"
        string output_note_path "Resolved path under staging/"
        string tags_json "JSON array of hierarchical kebab-case tags"
        string error "Diagnostics on failure"
        float duration_seconds "Total run time"
        string created_at "UTC ISO-8601"
        string updated_at "UTC ISO-8601"
    }

    AGY_STRUCTURED_OUTPUT {
        string status "created | failed"
        string recommended_category "Mastery Framework enum"
        string note_title "Title Case note filename stem"
        string output_path "Must resolve inside output_dir"
        string_list tags "Hierarchical category/focus-area/subtopic"
        string_list aliases "Optional acronyms or alternates"
        string_list existing_wikilinks "Matched notes in obsidian-notes"
        string_list overlapping_notes "Potential duplicate notes flagged"
        boolean validation_passed "Verified by validate_note.py"
        string summary "Concise run summary"
    }

    STAGED_OBSIDIAN_NOTE {
        string path "staging/Category/Note Title.md"
        string_list fm_tags "YAML list, hierarchical kebab-case"
        string_list fm_aliases "Optional YAML list"
        string fm_source "Video title"
        string fm_source_type "Literal: youtube"
        string fm_channel "Optional channel"
        string fm_url "Optional URL"
        date fm_created "ISO YYYY-MM-DD"
        markdown body "Evergreen reference (no duplicate H1, no inline tags)"
    }
```

---

## 4. Quick Start

### Install the Skill Symlink
From the repository root:

```bash
python3 scripts/install_skill.py obsidian-youtube-note
python3 scripts/install_skill.py --check
```

### Set Up the Python Environment (`uv`)
From `obsidian-youtube-note/`:

```bash
uv sync --no-editable
cp config.example.yaml config.yaml   # edit paths if needed (gitignored)
```

*(Note: `--no-editable` installs the package directly into `.venv/lib/python3.12/site-packages/` instead of a `.pth` file, avoiding macOS `UF_HIDDEN` `.pth` skips inside `~/Documents` on Python 3.12.14+.)*

### CLI Commands

```bash
# Validate config, paths, agy binary, and skill symlink
.venv/bin/yt-to-obsidian validate-config

# Single-shot dry run (writes to preview directory; does not touch obsidian-notes or state.db)
.venv/bin/yt-to-obsidian process tests/fixtures/Protocol_Buffers_Crash_Course_transcript \
  --dry-run --output-dir /tmp/yt-preview

# Process a single transcript into obsidian-notes/staging/<Category>/<Title>.md
.venv/bin/yt-to-obsidian process ~/Downloads/Protocol_Buffers_Crash_Course_transcript

# Run the continuous directory watcher
.venv/bin/yt-to-obsidian watch

# Inspect recent processing runs from state.db
.venv/bin/yt-to-obsidian history
```

---

## 5. Repository Contents

- [SKILL.md](./SKILL.md) — Antigravity skill instructions and 6-step workflow
- [references/vault_conventions.md](./references/vault_conventions.md) — Mastery Framework categories, canonical hierarchical tags, frontmatter schema, and hygiene rules
- [examples/golden_notes.md](./examples/golden_notes.md) — Annotated style exemplars from `obsidian-notes`
- [resources/output_schema.json](./resources/output_schema.json) — JSON Schema enforced on `agy -p` output
- [scripts/validate_note.py](./scripts/validate_note.py) — Standalone stdlib note validator
- [src/yt_to_obsidian/](./src/yt_to_obsidian/) — Watcher, parser, SQLite ledger, queue worker, and `AgyCliRunner`
- [plans/](./plans/) — Phased implementation plans (`01_` through `03_`)
- [docs/phase1_vault_style_audit.md](./docs/phase1_vault_style_audit.md) — Full Phase 1 vault style audit
