# Phase 3 Implementation Plan: Watcher, Parser, Queue & Headless Agent Runner

> **Parent Plan:** [01_yt_to_obsidian_pipeline.md](./01_yt_to_obsidian_pipeline.md)  
> **Phase 1 Audit:** [phase1_vault_style_audit.md](../docs/phase1_vault_style_audit.md)  
> **Phase 2 Skill Plan:** [02_phase2_obsidian_youtube_note_skill.md](./02_phase2_obsidian_youtube_note_skill.md)

---

## 1. Objective & Scope

Build the complete, cross-platform (macOS + Linux) Python 3.11+ package **`yt_to_obsidian`** managed with `uv`, implementing:
- Configuration loading & validation (`config.py`)
- Transcript filename matching & title extraction (`matcher.py`)
- Multi-format transcript normalization & SHA-256 hashing (`parser.py`)
- SQLite deduplication ledger & run history (`state.py`)
- Event-driven `watchdog` directory watcher with write-stability debouncing (`watcher.py`)
- Sequential background worker queue (`queue_worker.py`)
- Clean `AgentRunner` protocol + zero-shell least-privilege `AgyCliRunner` (`runner.py`)
- Rotating logging + optional macOS/Linux desktop notifications (`logging_setup.py`, `notifier.py`)
- Full CLI (`cli.py`: `watch`, `process`, `validate-config`, `install-skill`, `history`)

Phase 3 is complete when `yt-to-obsidian` installs cleanly via `uv`, passes unit tests across all modules, successfully processes [Protocol_Buffers_Crash_Course_transcript](../tests/fixtures/Protocol_Buffers_Crash_Course_transcript) via `yt-to-obsidian process --dry-run`, and successfully reacts to file creation and atomic rename events in `yt-to-obsidian watch --dry-run` against a temporary watch directory.

*(macOS `launchd` plist, Linux `systemd --user` unit, and full user `README.md` remain scoped to Phase 4; full live `~/Downloads` → Obsidian E2E verification remains scoped to Phase 5.)*

---

## 2. Environment Prerequisite & Dependency Management

An environment check showed that macOS currently has `/opt/homebrew/bin/brew` and Apple CLT `/usr/bin/python3` (3.9.6), while `uv` and Python 3.11+ are not yet installed.

### Tooling Setup (Step 0 of Phase 3)
1. Install `uv` via Homebrew (`brew install uv`) — on Linux, install via Astral's installer.
2. Let `uv` provision Python 3.12 automatically (pinned via `.python-version` and `requires-python = ">=3.11"` in `pyproject.toml`) and manage `.venv/` cleanly with `uv sync` — **never** run global `pip install`.
3. Add a `.gitignore` covering `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `dist/`, `build/`, `*.egg-info/`, `.DS_Store`, `*.db`, and user-local `config.yaml`.

### Dependencies (`pyproject.toml`)
- **Build system**: `hatchling` (src-layout: `src/yt_to_obsidian`)
- **Runtime**:
  - `watchdog>=4.0` (native FSEvents on macOS, inotify on Linux)
  - `pyyaml>=6.0` (loading `config.yaml`)
  - `pydantic>=2.7` (typed config validation & path normalization)
- **Dev (`[dependency-groups] dev`)**:
  - `pytest>=8.0`
  - `ruff>=0.6`
- **Entry point**:
  - `yt-to-obsidian = "yt_to_obsidian.cli:main"`

---

## 3. Target Repository Layout After Phase 3

```text
<repo-root>/
├── README.md                             # Multi-skill repository guide
├── .gitignore
├── scripts/
│   └── install_skill.py                  # Multi-skill symlink manager (all `<skill-name>/SKILL.md`)
└── obsidian-youtube-note/                # Self-contained skill + automation package
    ├── SKILL.md                          # Existing Phase 2 skill entry point
    ├── references/                       # vault_conventions.md
    ├── examples/                         # golden_notes.md
    ├── resources/                        # output_schema.json
    ├── scripts/                          # validate_note.py
    ├── docs/                             # phase1_vault_style_audit.md
    ├── plans/                            # 01_, 02_, 03_ implementation plans
    ├── .python-version                   # 3.12
    ├── pyproject.toml                    # uv-managed Python 3.11+ package
    ├── uv.lock                           # Locked reproducible environment
    ├── config.example.yaml               # Documented default configuration
    ├── src/
    │   └── yt_to_obsidian/
    │       ├── __init__.py
    │       ├── config.py                 # Pydantic config schema & cross-platform defaults
    │       ├── matcher.py                # `*_transcript` (optional ext) matching & title extraction
    │       ├── parser.py                 # UTF-8/BOM, .srt/.vtt/timestamp normalization & SHA-256
    │       ├── state.py                  # SQLite WAL dedup ledger & processing history
    │       ├── runner.py                 # `AgentRunner` protocol + zero-shell `AgyCliRunner`
    │       ├── watcher.py                # watchdog Observer (on_created + on_moved + stability debounce)
    │       ├── queue_worker.py           # Single sequential worker thread + post-processing
    │       ├── notifier.py               # Best-effort macOS (osascript) & Linux (notify-send) alerts
    │       ├── logging_setup.py          # Rotating file + console logging setup
    │       └── cli.py                    # `watch`, `process`, `validate-config`, `install-skill`, `history`
    └── tests/
        ├── fixtures/
        │   └── Protocol_Buffers_Crash_Course_transcript
        ├── test_config.py
        ├── test_matcher.py
        ├── test_parser.py
        ├── test_state.py
        ├── test_watcher.py
        └── test_runner.py
```

---

## 4. Detailed Module Specifications

### 4.1 Configuration (`config.py` & `config.example.yaml`)
Pydantic v2 config model (`AppConfig`) with sensible cross-platform defaults and `~` / environment variable expansion:

```yaml
watch:
  path: "~/Downloads"
  recursive: false
  allowed_extensions: [".txt", ".md", ".srt", ".vtt"]
  debounce_ms: 500
  stability_checks: 2
  stability_timeout_seconds: 15.0

vault:
  path: "../obsidian-notes"
  staging_dir: "staging"            # Relative to vault.path unless absolute

state:
  db_path: "~/.local/state/yt-to-obsidian/state.db"
  log_file: "~/.local/state/yt-to-obsidian/logs/yt-to-obsidian.log"
  log_level: "INFO"

post_process:
  action: "keep"                    # "keep" | "move"
  archive_dir: "~/Downloads/processed-transcripts"

runner:
  backend: "agy-cli"                # Future-proofed for "sdk"
  agy_binary: null                  # Auto-resolved via PATH + /opt/homebrew/bin + ~/.local/bin
  skill_name: "obsidian-youtube-note"
  skill_dir: null                   # Auto-resolved from repo skills/ or ~/.gemini/config/skills/
  model: null                       # Optional --model override
  effort: null                      # Optional --effort override (low|medium|high|xhigh|max)
  timeout_seconds: 300
  max_retries: 1
  strict_validation_warnings: true

notifications:
  enabled: true
```

- **Config lookup order**: `--config <path>` → `$YT_TO_OBSIDIAN_CONFIG` → `./config.yaml` → `~/.config/yt-to-obsidian/config.yaml` → built-in defaults.
- **Relative path resolution**: Paths relative to `config.yaml` (like `vault.path: "../obsidian-notes"`) resolve relative to the config file's parent directory (or CWD if using built-in defaults), avoiding working-directory surprises under `launchd`/`systemd`.
- **`validate_runtime_environment(config)`**: Returns structured pass/warn/fail checks for `watch.path`, `vault.path` (including `README.md`), `agy` binary discovery, `skill_dir` (`SKILL.md`, `output_schema.json`, `validate_note.py`), `~/.gemini/config/skills/obsidian-youtube-note` symlink, and `archive_dir` (when `post_process.action == "move"`).

### 4.2 Filename Matching & Title Extraction (`matcher.py`)
- `IGNORED_TEMP_SUFFIXES`: `{".crdownload", ".part", ".download", ".tmp", ".opdownload", ".swp"}`.
- `match_transcript_path(path: Path, allowed_extensions: Iterable[str]) -> MatchResult | None`:
  - Rejects hidden files (starting with `.`), `.DS_Store`, and any file whose final suffix is in `IGNORED_TEMP_SUFFIXES`.
  - Handles both extensionless files (`Protocol_Buffers_Crash_Course_transcript`) and allowed extensions (`Foo_transcript.txt`, `Foo_transcript.vtt`), case-insensitively.
  - Rejects unrelated extensions (e.g., `Video_transcript.pdf`, `Video_transcript.zip`, `notes.txt`, `Protocol_Buffers_Crash_Course_transcript.txt.crdownload`).
  - Matches when the stem (after stripping an allowed extension, if present) ends with `_transcript` (case-insensitive) and has at least 1 non-separator character before `_transcript`.
- `extract_fallback_title(stem: str) -> str`:
  - Strips trailing `_transcript` (case-insensitive), replaces `_` with spaces, collapses repeated whitespace, strips leading/trailing separators (`Protocol_Buffers_Crash_Course_transcript` → `Protocol Buffers Crash Course`).

### 4.3 Transcript Normalization & Hashing (`parser.py`)
- `TranscriptDocument` dataclass: `source_path`, `sha256`, `fallback_title`, `detected_title`, `channel`, `url`, `detected_format` (`plain` | `timestamped` | `srt` | `vtt`), `cleaned_text`, `char_count`.
- **Binary & empty guard**: Reads raw bytes, computes `hashlib.sha256(raw_bytes).hexdigest()`, rejects empty files (`0` bytes), binary files (contains `\x00` or >10% non-printable control bytes), and whitespace-only text by raising `TranscriptParseError`.
- **Encoding**: Decodes via `utf-8-sig` (strips UTF-8 BOM), falling back cleanly to `utf-8` with `errors="replace"` if malformed bytes exist.
- **Format detection & cleanup**:
  - Preserves leading metadata header lines (`Title:`, `Channel:`, `Author:`, `URL:`, `Link:`) and populates `detected_title`, `channel`, `url`.
  - **WebVTT (`.vtt` or starts with `WEBVTT`)**: removes header, cue timing lines (`-->`), inline cue tags (`<00:00:01.000>`, `<c>`), and deduplicates overlapping rolling captions.
  - **SubRip (`.srt`)**: removes numeric cue indices, `HH:MM:SS,mmm --> HH:MM:SS,mmm` lines, HTML formatting tags, and consecutive duplicate lines.
  - **Timestamped text** (`00:00`, `1:05:12`, `[00:12]`): removes standalone timestamp lines and leading inline timestamps while preserving paragraph structure and code snippets.
  - **Plain text**: normalizes `\r\n` → `\n` and collapses 3+ blank lines to 2.

### 4.4 SQLite State Ledger (`state.py`)
- SQLite database at `config.state.db_path` (parent directory auto-created), configured with `PRAGMA journal_mode=WAL;` and `PRAGMA busy_timeout=5000;`.
- Table `transcript_runs`:
  - `id` (`INTEGER PRIMARY KEY AUTOINCREMENT`)
  - `sha256` (`TEXT NOT NULL`)
  - `source_path` (`TEXT NOT NULL`)
  - `fallback_title` (`TEXT NOT NULL`)
  - `status` (`TEXT NOT NULL CHECK(status IN ('processing', 'completed', 'failed'))`)
  - `recommended_category` (`TEXT`)
  - `note_title` (`TEXT`)
  - `output_note_path` (`TEXT`)
  - `tags_json` (`TEXT`)
  - `error` (`TEXT`)
  - `duration_seconds` (`REAL`)
  - `created_at` (`TEXT NOT NULL`)
  - `updated_at` (`TEXT NOT NULL`)
- Index: `CREATE INDEX IF NOT EXISTS idx_transcript_runs_sha256_status ON transcript_runs (sha256, status);`.
- API:
  - `get_completed(sha256: str) -> LedgerRecord | None`
  - `record_start(sha256: str, source_path: Path, fallback_title: str) -> int`
  - `record_completed(run_id: int, *, category: str, note_title: str, output_note_path: Path, tags: list[str], duration_seconds: float) -> None`
  - `record_failed(run_id: int, *, error: str, duration_seconds: float) -> None`
  - `list_recent(limit: int = 20) -> list[LedgerRecord]`

### 4.5 Headless Agent Runner (`runner.py`) — Incorporating Phase 2 Findings
Carries forward our key Phase 2 discovery: **`agy -p --mode accept-edits` executes cleanly with zero shell permissions** when the runner supplies the read-only vault note inventory in the prompt and runs `validate_note.py` deterministically in Python afterward.

- **Protocol & Data Models**:
  - `RunRequest(transcript: TranscriptDocument, output_dir: Path, vault_path: Path, dry_run: bool, model_override: str | None, effort_override: str | None)`
  - `RunResult(status, recommended_category, note_title, output_path, tags, aliases, existing_wikilinks, overlapping_notes, validation_passed, summary, duration_seconds, raw_stdout, raw_stderr)`
  - `class AgentRunner(Protocol): def run(self, request: RunRequest) -> RunResult: ...`
- **`AgyCliRunner` Implementation**:
  1. **Binary Resolution (`resolve_agy_binary`)**: checks `config.runner.agy_binary`, then `shutil.which("agy")`, then standard fallback locations (`/opt/homebrew/bin/agy`, `/usr/local/bin/agy`, `~/.local/bin/agy`).
  2. **Vault Inventory Pre-Scan (Read-Only)**: walks `vault_path` in Python (skipping `misc/`, `.obsidian/`, `.git/`, `staging/`) to collect all existing `.md` note titles (and YAML `aliases` if present) and injects them into the prompt — saving subagent turns and eliminating any need for Bash inside `agy`.
  3. **Normalized Transcript Handoff**: writes normalized transcript text (with preserved header metadata) to a short-lived temp file inside a private temp directory passed via `--add-dir` (cleaned up in `finally`), so `agy` reads clean text without touching the original file in `~/Downloads`.
  4. **Command Construction** (subprocess list, `shell=False`):
     ```text
     [
       agy_bin,
       "-p", prompt,
       "--add-dir", str(vault_path),
       "--add-dir", str(output_dir),
       "--add-dir", str(temp_transcript_dir),
       "--mode", "accept-edits",
       "--output-format", "json",
       "--json-schema", str(output_schema_path),
       "--print-timeout", f"{timeout_seconds}s",
       # optional: "--model", model, "--effort", effort
     ]
     ```
  5. **Response Parsing & Path Containment Guard**:
     - Parses stdout JSON (`structured_output`, falling back to parsing `response` JSON if needed); raises `RunnerError` on non-zero exit code, subprocess timeout, `denied_actions` with empty output, or invalid JSON.
     - Verifies `Path(structured_output["output_path"]).resolve()` is strictly inside `output_dir.resolve()` (rejects any path traversal or accidental write outside `output_dir`).
  6. **Deterministic Post-Run Validation & Retry**:
     - Loads and invokes `validate_note()` from [validate_note.py](../scripts/validate_note.py) with `strict_warnings=config.runner.strict_validation_warnings`.
     - If `agy` fails transiently or `validate_note()` reports errors/warnings, retries up to `config.runner.max_retries` (default `1`), appending exact validation feedback to the prompt on a validation retry.
     - Never runs `git` commands on `obsidian-notes`.

### 4.6 Event-Driven Watcher (`watcher.py`)
- Uses `watchdog.observers.Observer` (FSEvents on macOS, inotify on Linux), `recursive=config.watch.recursive` (default `False`).
- `TranscriptEventHandler(FileSystemEventHandler)`:
  - Handles `on_created` (`event.src_path`), `on_moved` (`event.dest_path`), and `on_modified` (only if path is not already tracked/pending, as a safety net for extensions that create an empty file first).
  - Ignores directory events and non-matching filenames via `matcher.match_transcript_path`.
- **Non-blocking Write-Stability Debouncer**:
  - Maintains a thread-safe map of pending paths (`threading.Lock` + background `threading.Timer` / poller thread) so watchdog's event loop is never blocked.
  - Waits `debounce_ms` (500 ms), then checks `(st_size, st_mtime_ns)` across `stability_checks` consecutive intervals (default 2 checks = 1 s steady).
  - Enqueues the path onto `queue.Queue[Path]` once non-empty (`st_size > 0`) and stable; drops cleanly with a debug log if the file vanishes (e.g., cancelled download) or logs a warning if `stability_timeout_seconds` elapses without stabilizing.
  - Coalesces multiple rapid OS events for the same path into a single enqueue.

### 4.7 Sequential Queue Worker (`queue_worker.py`)
- Dedicated single daemon worker thread (`QueueWorker`) draining `queue.Queue[Path | None]`, ensuring only one `agy -p` process runs at a time (no concurrent races on vault reads/writes).
- Also exposes a synchronous `process_file(path: Path, *, dry_run: bool, output_dir: Path | None, force: bool) -> ProcessOutcome` method reused by both the worker loop and `yt-to-obsidian process <file>`!
- End-to-end processing lifecycle:
  1. Parse & hash (`parser.parse_transcript`).
  2. Dedup check (`state.get_completed(doc.sha256)`): if already completed and not `force`, log skip and return `skipped`.
  3. Record `processing` row in `state.db` (skipped when `dry_run=True` so dry runs never pollute the production dedup ledger!).
  4. Resolve `output_dir`: custom `--output-dir` → temp preview dir (when `--dry-run`) → `vault_path / staging_dir`.
  5. Invoke `runner.run(...)`.
  6. On success:
     - Record `completed` in `state.db` (if not `dry_run`).
     - If not `dry_run` and `post_process.action == "move"`, atomically move source transcript to `archive_dir` (adding a numeric suffix on collision).
     - Send success desktop notification (if enabled and not `dry_run`).
  7. On failure:
     - Record `failed` with diagnostics in `state.db` (if not `dry_run`).
     - Log full error & send failure notification (if enabled and not `dry_run`).

### 4.8 CLI, Logging & Notifications (`cli.py`, `logging_setup.py`, `notifier.py`)
- **`cli.py` subcommands**:
  - `yt-to-obsidian watch [--config PATH] [--dry-run] [--output-dir DIR] [--log-level LEVEL]`
  - `yt-to-obsidian process <file> [--config PATH] [--dry-run] [--output-dir DIR] [--force] [--model MODEL] [--effort EFFORT]`
  - `yt-to-obsidian validate-config [--config PATH]`
  - `yt-to-obsidian install-skill [--check | --uninstall | --force] [--target-dir DIR]`
  - `yt-to-obsidian history [--config PATH] [--limit N]`
- **`logging_setup.py`**: Configures `RotatingFileHandler` (5 MB × 5 backups, UTF-8) + `StreamHandler` with ISO timestamps and log level control.
- **`notifier.py`**:
  - macOS (`sys.platform == "darwin"`): `osascript -e 'display notification ...'` (properly escaped via stdin/args, never shell-interpolated).
  - Linux (`sys.platform.startswith("linux")`): `notify-send` if found on `PATH`.
  - Best-effort with short timeout (3 s); failures log at `DEBUG` and never fail transcript processing.

---

## 5. Step-by-Step Execution Order

1. **Bootstrap Python 3.12 + `uv` project**:
   - Install `uv` (`brew install uv`), create `.gitignore`, `.python-version`, `pyproject.toml`, and `config.example.yaml`, then run `uv sync`.
2. **Implement core pure-logic modules**:
   - `config.py`, `matcher.py`, `parser.py`, `state.py`.
3. **Implement runner, watcher, worker, logging, notifications, and CLI**:
   - `logging_setup.py`, `notifier.py`, `runner.py`, `watcher.py`, `queue_worker.py`, `cli.py`, `__init__.py`.
4. **Write & run unit test suite (`uv run pytest`) + linter (`uv run ruff check`)**:
   - `test_config.py`: path resolution, YAML loading, defaults, validation errors.
   - `test_matcher.py`: extensionless `*_transcript`, `.txt`/`.md`/`.srt`/`.vtt`, case insensitivity, `.crdownload`/`.part`/`.DS_Store`/unrelated rejections, fallback title extraction.
   - `test_parser.py`: plain text, `.vtt` rolling-caption dedup, `.srt`, timestamped text (including fixture), UTF-8 BOM, header metadata extraction, binary/empty rejections, SHA-256 stability.
   - `test_state.py`: WAL persistence across reconnects, dedup hits, failed runs not blocking retries, `list_recent`.
   - `test_watcher.py`: real `watchdog` observer on `tmp_path` verifying `on_created`, atomic `on_moved` rename (`.crdownload` → `*_transcript`), write-stability debounce, and event coalescing.
   - `test_runner.py`: mocked `subprocess.run` verifying `agy` CLI args, PATH fallback resolution, vault inventory injection, path-traversal guard, post-run `validate_note()` pass/retry-on-failure, timeout handling, and dry-run isolation.
5. **Live CLI verification**:
   - Run `uv run yt-to-obsidian validate-config` and `uv run yt-to-obsidian install-skill --check`.
   - Run `uv run yt-to-obsidian process tests/fixtures/Protocol_Buffers_Crash_Course_transcript --dry-run --output-dir /tmp/yt-to-obsidian-phase3-dryrun` and confirm end-to-end execution + validator pass + untouched `../obsidian-notes`.
   - Smoke-test `uv run yt-to-obsidian watch` against a temporary watch directory (dropping a copy of the fixture via atomic `.crdownload` → `*_transcript` rename in dry-run mode or with a mocked/real run) and confirm clean `SIGINT` shutdown.

---

## 6. Verification & Acceptance Criteria

Phase 3 is complete when ALL of the following pass:

- [ ] `uv sync` creates a clean Python 3.12 `.venv` with `yt-to-obsidian` CLI entry point installed.
- [ ] `uv run ruff check src tests` exits `0` with zero lint issues.
- [ ] `uv run pytest -v` passes 100% of unit tests across `config`, `matcher`, `parser`, `state`, `watcher`, and `runner`.
- [ ] `uv run yt-to-obsidian validate-config` and `uv run yt-to-obsidian install-skill --check` succeed cleanly.
- [ ] Single-shot `uv run yt-to-obsidian process tests/fixtures/Protocol_Buffers_Crash_Course_transcript --dry-run --output-dir /tmp/yt-to-obsidian-phase3-dryrun` succeeds end-to-end, writes a validated note (`validate_note.py --strict-warnings` passes with 0 errors/warnings), and leaves `../obsidian-notes` completely untouched.
- [ ] `uv run yt-to-obsidian watch` against a temporary watch directory detects both direct file creation and atomic `.crdownload` → `*_transcript` rename, debounces cleanly, processes once, deduplicates a second identical drop, and exits cleanly on `SIGINT`.

---

## 7. Risks & Mitigations

| Risk | Mitigation |
| :--- | :--- |
| **`launchd`/`systemd` stripped `PATH` hides `agy` or `uv`** | `runner.py` checks explicit config `agy_binary`, then `shutil.which`, then `/opt/homebrew/bin/agy`, `/usr/local/bin/agy`, and `~/.local/bin/agy`. |
| **macOS FSEvents fires burst of duplicate events on one download** | Per-path debounce map coalesces repeated events during the stability window, and `state.py` SHA-256 dedup prevents duplicate processing even across restarts. |
| **Dry runs accidentally pollute `state.db` or `../obsidian-notes`** | `dry_run=True` bypasses `state.db` writes, skips `post_process` moves, and writes exclusively to a temp or explicit `--output-dir` enforced by path-containment validation. |
| **Unattended `agy -p` attempts shell execution and gets soft-denied** | `AgyCliRunner` pre-scans `vault_path` in Python, embeds existing note names into the prompt, runs `agy -p` with zero-shell `--mode accept-edits`, and runs `validate_note.py` deterministically in Python afterward. |
| **Malformed transcript or LLM output crashes the daemon** | `QueueWorker` isolates per-file exceptions, records structured `failed` entries in SQLite with full logs, optionally alerts the user, and keeps watching for future downloads. |
