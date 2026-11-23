# Antigravity Skills & ADK Agents Repository

Monorepo housing custom Antigravity skills and Google ADK agents, supporting scripts, references, implementation plans, and tests.

## Repository Layout

`scripts/install_skill.py` auto-discovers skills in either layout:
- **Standalone skill:** `<repo-root>/<skill-name>/SKILL.md`
- **Grouped project package:** `<repo-root>/<project>/skills/<skill-name>/SKILL.md`

```text
<repo-root>/
├── scripts/
│   └── install_skill.py                            # Cross-platform symlink installer for Antigravity skills
├── obsidian-note-generator/                        # Google ADK URL-driven Obsidian Note Agent + unified skill
│   ├── README.md                                   # Architecture, adk web/run & CLI quick start
│   ├── pyproject.toml                              # obsidian-note-agent (google-adk + fetchers)
│   ├── skills/
│   │   └── obsidian-note-generator/                # Single unified skill (ADK SkillToolset + Antigravity)
│   │       ├── SKILL.md
│   │       ├── references/vault_conventions.md     # Concise composable tags, create & update-draft schemas
│   │       ├── references/exemplars.md
│   │       └── scripts/validate_note.py
│   ├── src/obsidian_note_agent/                    # ADK root_agent, fetchers, vault indexer, guarded tools, CLI
│   ├── docs/
│   ├── plans/
│   └── tests/
└── README.md
```

## Available Skills & Agents

| Package / Skill | Input | Docs | Description |
| :--- | :--- | :--- | :--- |
| [obsidian-note-generator](./obsidian-note-generator/skills/obsidian-note-generator/SKILL.md) | YouTube URLs, engineering article/blog URLs, technical/product documentation URLs, or pasted text | [README](./obsidian-note-generator/README.md) | Google ADK agent (`adk web`, `adk run`, `obsidian-note`) + portable Antigravity skill that produces Mastery Framework Obsidian notes or staged Update Drafts (`<Existing> (Update).md`) with concise composable tags. |

## Installing Antigravity Skill Symlinks (macOS & Linux)

```bash
# List discovered skills and install status
python3 scripts/install_skill.py --list

# Install all skills into ~/.gemini/config/skills/
python3 scripts/install_skill.py --force

# Verify installed symlinks
python3 scripts/install_skill.py --check
```
