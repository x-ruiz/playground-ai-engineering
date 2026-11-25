# AI Engineering Agents & Skills Repository

Monorepo housing Google ADK agents under `agents/` and reusable Antigravity / ADK skills under `skills/`.

## Repository Layout

```text
<repo-root>/
├── agents/
│   └── obsidian-note-generator/               # Google ADK URL-driven Obsidian Note Agent
│       ├── README.md                          # Architecture, sequence/ER diagrams, file reference & quick start
│       ├── pyproject.toml                     # obsidian-note-agent (google-adk + fetchers)
│       ├── .env.example                       # Gemini Developer API or Vertex AI auth
│       ├── config.example.yaml                # Vault path, model, fallbacks, retry policy, token caps
│       ├── src/obsidian_note_agent/           # ADK root_agent, ResilientGemini, fetchers, vault tools, CLI
│       ├── docs/
│       ├── plans/
│       └── tests/
├── skills/
│   ├── install_skills.py                      # Cross-platform symlink installer for all skills under skills/
│   ├── graduate-playground-project/           # Graduate a playground subdirectory into a standalone repo
│   │   ├── SKILL.md
│   │   └── references/
│   ├── obsidian-note-generator/               # Unified skill (ADK SkillToolset + Antigravity)
│   │   ├── SKILL.md
│   │   ├── references/vault_conventions.md    # Concise composable tags, create & update-draft schemas
│   │   ├── references/exemplars.md
│   │   └── scripts/validate_note.py
│   └── spec-driven-development/               # Language-agnostic SDD coach & Staff diff review
│       ├── SKILL.md
│       └── references/
└── README.md
```

## Available Agents & Skills

| Type | Name | Docs | Description |
| :--- | :--- | :--- | :--- |
| **Agent** | [obsidian-note-generator](./agents/obsidian-note-generator/README.md) | [README](./agents/obsidian-note-generator/README.md) | Google ADK agent (`adk web`, `adk run`, `obsidian-note`) that turns YouTube, engineering article, and technical documentation URLs into Mastery Framework Obsidian notes or staged Update Drafts (`<Existing> (Update).md`). |
| **Skill** | [graduate-playground-project](./skills/graduate-playground-project/SKILL.md) | [graduation_checklist.md](./skills/graduate-playground-project/references/graduation_checklist.md) | End-to-end runbook for graduating a playground monorepo directory into a standalone repository: coupling/secret audit, `git subtree split` (or fresh init), CI/path decoupling, standalone `README.md` & `.gitignore`, local verification, optional `gh repo create`, and gated playground cleanup. |
| **Skill** | [obsidian-note-generator](./skills/obsidian-note-generator/SKILL.md) | [vault_conventions.md](./skills/obsidian-note-generator/references/vault_conventions.md) | Portable skill playbook + stdlib validator shared by the ADK agent (`SkillToolset`) and Antigravity (`~/.gemini/config/skills/`). |
| **Skill** | [spec-driven-development](./skills/spec-driven-development/SKILL.md) | [spec_template.md](./skills/spec-driven-development/references/spec_template.md) | Language-agnostic Spec-Driven Development coach: read-only repo survey, 1–2 round interview, implementation-free spec in `specs/`, and strict Staff Engineer `git diff` review. |

## Installing Antigravity Skill Symlinks (macOS & Linux)

```bash
# List discovered skills and install status
python3 skills/install_skills.py --list

# Install all skills under skills/ into ~/.gemini/config/skills/ (Antigravity) and ~/.claude/skills/ (Claude Code)
python3 skills/install_skills.py --force

# Verify installed symlinks
python3 skills/install_skills.py --check
```

## Adding a New Skill or Agent

- **New skill:** Create `skills/<skill-name>/SKILL.md` (plus optional `references/`, `scripts/`, `assets/`), then run `python3 skills/install_skills.py --force`.
- **New agent:** Create `agents/<agent-name>/` with its own `pyproject.toml` and ADK package, loading any shared skills from `skills/<skill-name>/`.
