---
name: graduate-playground-project
description: >-
  Graduate a self-contained project directory from a playground or incubator monorepo
  (e.g., `playground-cloud-engineering`, `playground-ai-engineering`,
  `playground-data-engineering`) into its own standalone Git repository with preserved
  history (`git subtree split`) or fresh init, decoupled paths and CI/CD workflows,
  tailored `.gitignore`, polished standalone `README.md`, migration of relevant specs
  (moved into the new repo and renumbered, with the playground's remaining specs
  re-sequenced), optional `LICENSE`, local
  build/test verification, optional GitHub creation via `gh`, automatic GitHub profile
  homepage (`<owner>/<owner>` README) update, and explicitly gated playground cleanup.
  Use whenever the user asks to graduate, promote, extract, split out, or mature a
  playground directory into a standalone repository.
---

# Graduate Playground Project

Extracts a mature subdirectory from a playground monorepo into a clean, self-sufficient standalone repository without breaking builds, CI/CD, tags, or cloud/GitHub bindings.

## Reference Assets
- **Extraction, Decoupling & Stack Checklist (Required for Phases 1, 3–6):** [references/graduation_checklist.md](./references/graduation_checklist.md) — Coupling audit matrix across stacks (IaC/OpenTofu/Terragrunt, Python/ADK, Java/Maven, TS/Go/Rust), `git subtree split` vs. fresh-init recipes, tag remapping, secret-hygiene checks, and post-move re-bindings.
- **Spec Migration & Renumbering (Required for Phases 1, 2, 4, 5, 6):** [references/graduation_checklist.md §8](./references/graduation_checklist.md#8-spec-migration--renumbering-phases-1-2-4-5-6) — Discovering specs outside `<source_dir>` that belong to the project, old → new renumbering plans, reference rewriting, and re-sequencing the playground's remaining specs.
- **Standalone README Guide (Required for Phase 4):** [references/readme_template.md](./references/readme_template.md) — Adaptive standalone `README.md` structure, Mermaid diagram criteria, and polish checklist.

## Non-Negotiable Guardrails
1. **Audit and plan before mutating.** Never run `git subtree split`, create target directories, modify files, invoke `gh repo create`, or push until the user reviews and approves the Phase 2 Graduation Plan.
2. **Clean source tree before splitting.** Refuse `git subtree split` if `<source_dir>` has uncommitted or untracked project changes; ask the user to commit or stash first so history is complete.
3. **Zero secret leakage.** Audit both the working tree and (when preserving history) commit history for `.env`, `*.tfstate*`, `*.tfvars`, private keys, credentials, or hardcoded machine-local paths before creating or pushing a remote.
4. **Verify locally before publishing.** Always run the project's real format, lint, static check, and test commands from the standalone repository root—never push untested path or CI rewrites.
5. **Gate playground cleanup.** Never delete `<source_dir>` or its workflows from the source playground repo automatically. Only prune after the standalone repo is verified (and pushed, if remote was requested) **and** the user explicitly confirms cleanup.

---

## Workflow

### Phase 1: Read-Only Reconnaissance & Coupling Audit
1. Read [references/graduation_checklist.md](./references/graduation_checklist.md).
2. Inspect the source playground repo read-only:
   - `git status`, current branch, `git remote -v`, and existing tags (`git tag --list`).
   - Playground root `.gitignore`, root `README.md`, and `.github/workflows/` for files referencing `<source_dir>`.
   - Target `<source_dir>` layout, build/package manifests, `README.md`, `specs/`/`docs/`, scripts, and tests.
3. Audit for **monorepo coupling** and **hygiene risks**:
   - Relative parent traversals (`../`, `../../`) in source code, build manifests (e.g., Maven `<relativePath>`), Terragrunt/IaC modules, ADK skill loaders, or docs.
   - Monorepo-prefixed paths in scripts, CI workflows (`PROJECT_DIR`, `working-directory`, `paths:`), and README commands.
   - Root `.gitignore` rules that `<source_dir>` relies on.
   - Matching release tags (e.g., `udp-gcp-v*`) and external bindings (GCP WIF `attribute_condition`, GitHub Actions vars/secrets, local symlinks).
   - Secret/hygiene risks in working tree and `git log -- <source_dir>`.
   - **Specs:** find every `specs/` directory in the playground and classify each spec as *Inside*, *Relevant (outside)*, *Shared*, or *Unrelated* to `<source_dir>`, plus every file that references a spec by filename or number (checklist §8.1).
4. Present a concise **Graduation Readiness Snapshot** (detected stack, coupling items, associated workflows/tags, hygiene findings, spec classification, and suggested target repo name/path).

### Phase 2: Graduation Plan & Confirmation
Confirm the exact plan in one concise round (proposing concrete defaults):
1. **Target repo name & local path** (default: sibling directory `../<repo-name>` next to the playground repo).
2. **Git history strategy:** `git subtree split` (default, preserves `<source_dir>` commit history) vs. clean single-commit `git init` (recommended if history has secrets/noise or user prefers a clean slate).
3. **Coupling resolution:** how to decouple each Phase 1 cross-directory dependency (bundle/vendor, parameterize, or extract).
4. **Spec migration & renumbering:** which specs move to the new repo, which *Shared* specs stay (or are copied), and the two old → new renumbering tables—one for `<target_repo>/specs/` and one for each affected playground `specs/` directory (checklist §8.2).
5. **Repo polish:** standalone `README.md` upgrade, tailored `.gitignore`, CI workflow migration, and optional `LICENSE` (e.g., MIT / Apache-2.0 / none).
6. **Remote publishing:** local-only vs. `gh repo create` — if creating on GitHub, explicitly confirm **private** vs. **public** and owner/org.

Stop and wait for explicit approval before Phase 3.

### Phase 3: Extract into Standalone Local Repository
1. Verify `<target_path>` does not already exist and `<source_dir>` is clean in `git status`.
2. Execute the approved extraction recipe from [references/graduation_checklist.md](./references/graduation_checklist.md):
   - **History-preserving (`git subtree split`):** split `<source_dir>` onto a temporary branch, initialize `<target_path>` on `main`, pull the split history cleanly, remove the temporary remote from `<target_path>`, and delete the temporary branch in the playground repo.
   - **Fresh init:** export tracked files cleanly via `git archive HEAD:<source_dir>` into `<target_path>`, `git init -b main`, and create the initial commit.
3. If the project uses release tags (e.g., for Terragrunt/IaC tag pinning or package releases) and history was preserved, remap annotated tags onto the corresponding split commit SHAs—never push monorepo-root tags blindly, because their SHAs point to the monorepo tree.

### Phase 4: Decouple, Mature & Polish
1. Read [references/readme_template.md](./references/readme_template.md).
2. **Decouple paths & dependencies:** apply all approved Phase 2 fixes for `../` references, root-prefixed commands, parent POMs, IaC repo/subpath variables, or shared skills/packages.
3. **Migrate & adapt CI/CD workflows:** copy matching `.github/workflows/*.yml` files into `<target_path>/.github/workflows/`, update `PROJECT_DIR` to `"."` (or drop the subdirectory prefix), rewrite `paths:` triggers to root-relative paths, and remove monorepo-only prefixes from workflow names if desired.
4. **Tailor `.gitignore`:** create a root `.gitignore` combining the applicable rules from the playground root `.gitignore` plus stack-specific ignores; verify example config templates (`.env.example`, `*.tfvars.example`, `config.example.yaml`) exist where real configs are ignored.
5. **Polish `README.md`:** write or upgrade `<target_path>/README.md` using [references/readme_template.md](./references/readme_template.md). Rewrite all commands and relative links for repo root, strip playground-only "Graduating to a Standalone Repository" boilerplate, and ensure architecture, Quick Start, and verification commands match the actual codebase.
6. **Migrate & renumber specs:** copy the approved *Relevant* specs into `<target_repo>/specs/`, apply the target renumbering table, rewrite all spec references, add provenance notes, and keep `REQ-*`/`TC-*` IDs unchanged (checklist §8.3).
7. **Optional `LICENSE` & metadata:** add `LICENSE` if requested, and update repository URLs in package manifests (`pyproject.toml`, `package.json`, `pom.xml`, `Cargo.toml`, `go.mod`).
8. Inspect `git status` and `git diff`, then commit the maturation changes cleanly (e.g., `chore: mature standalone repository layout, CI, and README`).

### Phase 5: Local Verification Gate
1. Run the project's actual build, format, lint, static/security scan, and unit test suite from `<target_path>` root.
2. Verify:
   - Zero lingering references to the old playground repo name or `<source_dir>/` prefix (unless intentional attribution).
   - Zero broken local Markdown links in `README.md`, `docs/`, and `specs/`.
   - `specs/` is a contiguous, duplicate-free sequence with no references to old spec filenames or playground spec paths (checklist §8.4).
   - Clean `git status` (no untracked build artifacts, caches, `.env`, or state files).
3. Fix any failures and commit the fixes before moving to Phase 6.

### Phase 6: Remote Publishing, Profile Homepage Update, Re-Bindings & Gated Playground Cleanup
1. **Remote Publishing (if approved):**
   - Match the user's remote protocol (SSH vs. HTTPS) from existing sibling repos.
   - Create the GitHub repo via `gh repo create` with the confirmed visibility (`--private` or `--public`), push `main`, and push any remapped release tags.
2. **GitHub Profile Homepage Update (`<owner>/<owner>` README — Automatic on Remote Graduation):**
   - Whenever a repo is published to GitHub (unless the user explicitly opts out or the repo is strictly private and shouldn't be linked publicly), automatically update the owner's GitHub profile repository README (e.g., `x-ruiz/x-ruiz/README.md`) following [references/graduation_checklist.md](./references/graduation_checklist.md):
     - Add the newly graduated repository to the matching category table (e.g., `Cloud & Platform Engineering`, `Data Engineering`, etc.) with a crisp description and stack summary.
     - Update any `Graduations in progress`, `Featured`, `Playgrounds`, or `Mastery Framework` rows that referenced the old playground subdirectory so the GitHub homepage stays accurate.
     - Commit and push the profile README update to `main` cleanly.
3. **Post-Move Re-Bindings Checklist:** if Phase 1 identified external dependencies (e.g., GCP WIF `attribute_condition`, GitHub Actions vars/secrets, branch protection rules, `install_skills.py` symlinks in `~/.gemini/config/skills` and `~/.claude/skills`), present the exact manual/operator steps—never mutate cloud IAM/WIF unprompted.
4. **Gated Playground Cleanup:** ask explicitly whether the user wants to prune `<source_dir>` from the source playground repo now. Only after explicit confirmation:
   - Remove `<source_dir>` and its migrated `.github/workflows/` files from the playground repo.
   - Remove the migrated *Relevant* specs (never *Shared* ones), renumber the remaining specs in each affected `specs/` directory with `git mv` per the approved table, and rewrite playground references—links to moved specs point to the new repo (checklist §8.5).
   - Update the playground `README.md` (remove from active projects/layout tree and add an entry under `## Graduated Projects` linking to the new standalone repository).
   - Show `git status` and `git diff` in the playground repo and confirm before committing/pushing the cleanup.
