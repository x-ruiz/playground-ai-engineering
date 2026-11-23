# Antigravity Skills Repository

Monorepo housing custom Antigravity skills, supporting scripts, references, examples, fixtures, and implementation plans.

## Repository Layout

Each top-level directory containing a `SKILL.md` file is a self-contained skill package named after the skill:

```text
<repo-root>/
├── scripts/
│   └── install_skill.py           # Cross-platform symlink installer for all skills
├── <skill-name>/                  # e.g. obsidian-youtube-note/
│   ├── SKILL.md                   # Required: skill metadata & workflow instructions
│   ├── references/                # Conventions, playbooks, and domain docs
│   ├── examples/                  # Golden examples & annotated templates
│   ├── resources/                 # Schemas, prompts, and static assets
│   ├── scripts/                   # Skill-specific helper/validation scripts
│   ├── docs/                      # Audits and design notes
│   ├── plans/                     # Numbered implementation plans (NN_<title>.md)
│   └── tests/                     # Fixtures and test suites
└── README.md
```

## Available Skills

| Skill | Docs | Description |
| :--- | :--- | :--- |
| [obsidian-youtube-note](./obsidian-youtube-note/SKILL.md) | [README](./obsidian-youtube-note/README.md) | Converts YouTube transcripts into evergreen Mastery Framework Obsidian notes staged under `staging/<Category>/<Title>.md`. |

## Installing Skills (macOS & Linux)

Symlink all skills in this repository into `~/.gemini/config/skills/` so Antigravity CLI (`agy`), IDE, and Desktop App discover them automatically:

```bash
# List discovered skills and install status
python3 scripts/install_skill.py --list

# Install all skills (use --force to update moved/stale symlinks)
python3 scripts/install_skill.py

# Install or verify a single skill
python3 scripts/install_skill.py obsidian-youtube-note
python3 scripts/install_skill.py --check

# Uninstall symlinks
python3 scripts/install_skill.py --uninstall
```

## Adding a New Skill

1. Create a new top-level lowercase hyphenated directory `<my-new-skill>/`.
2. Add `<my-new-skill>/SKILL.md` with YAML frontmatter (`name` and `description`), plus any `references/`, `examples/`, `resources/`, `scripts/`, `plans/`, and `tests/` subdirectories.
3. Run `python3 scripts/install_skill.py <my-new-skill>` and verify with `python3 scripts/install_skill.py --check`.
