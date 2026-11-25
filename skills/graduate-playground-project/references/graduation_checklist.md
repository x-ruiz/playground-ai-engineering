# Graduation Checklist: Extraction, Decoupling & Verification

Load this reference during **Phase 1 (Audit)** and **Phases 3–6 (Execution)**.

---

## 1. Phase 1 Coupling & Hygiene Audit Commands

Run read-only inside the source playground repository (replacing `<source_dir>` with the target subdirectory):

```bash
# 1. Working tree cleanliness & remotes/tags
git status -sb
git remote -v
git tag --list

# 2. Parent-directory traversals & monorepo-name references inside <source_dir>
grep -rnE '\.\./|playground-' <source_dir> \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules \
  --exclude-dir=target --exclude-dir=.terraform --exclude-dir=.terragrunt-cache || true

# 3. Root workflows referencing <source_dir>
grep -rn "<source_dir>" .github/ 2>/dev/null || true

# 4. Working-tree & historical secret/hygiene scan (paths only)
git log --all --name-only --pretty=format: -- <source_dir> \
  | sort -u \
  | grep -iE '(^|/)\.env($|\.)|\.tfstate|\.tfvars$|\.pem$|\.key$|credentials.*\.json|\.DS_Store' || true

# 5. Hardcoded machine-local paths
grep -rnE '/Users/|/home/|C:\\Users\\' <source_dir> \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules || true
```

**Red Flag Rule:** If the history scan surfaces real secrets or state files (`.env`, `.tfstate`, private keys, real `.tfvars`), flag it immediately in Phase 2 and recommend either **fresh-init** or history scrubbing (`git filter-repo`) before pushing to any remote.

---

## 2. Git Extraction Recipes (Phase 3)

### Option A: Preserve Commit History (`git subtree split`) — Default

Run from the **source playground repo root** (`<source_repo>`) after confirming `<source_dir>` has no uncommitted changes:

```bash
SOURCE_REPO="$(pwd)"
SOURCE_DIR="<source_dir>"        # e.g., platform_unified_data_gcp or agents/obsidian-note-generator
TARGET_REPO="../<new-repo-name>" # e.g., ../platform-unified-data-gcp
SPLIT_BRANCH="graduate/<new-repo-name>"

# 1. Split subdirectory history onto a temporary branch
git subtree split --prefix="${SOURCE_DIR}" -b "${SPLIT_BRANCH}"

# 2. Initialize standalone repo on main and import split history cleanly
mkdir -p "${TARGET_REPO}"
git -C "${TARGET_REPO}" init -b main
git -C "${TARGET_REPO}" pull "${SOURCE_REPO}" "${SPLIT_BRANCH}"

# 3. Clean up temporary split branch in the playground repo
git branch -D "${SPLIT_BRANCH}"
```

Verify in `${TARGET_REPO}`:
```bash
git -C "${TARGET_REPO}" log --oneline -n 10
git -C "${TARGET_REPO}" remote -v   # Should be empty (no lingering local path remote)
```

#### Remapping Annotated Release Tags After `git subtree split`

> **CRITICAL:** `git subtree split` rewrites commit SHAs so `<source_dir>` becomes the repo root. Monorepo tags still point to the monorepo commit SHAs (containing the full monorepo tree) and **must not** be copied blindly.

If the project uses Git tags (e.g., `udp-gcp-v0.1.0` pinned in `release.yaml` or semantic version releases):
1. List matching tags in `<source_repo>`: `git tag -l '<prefix>*' --format='%(refname:short) %(objectname:short) %(creatordate:iso-strict) %(subject)'`.
2. For each tag that touches `<source_dir>`, split at that tag (`git subtree split --prefix="${SOURCE_DIR}" "<tag>"`) to obtain the exact corresponding split commit SHA in `${TARGET_REPO}` (since `git subtree split` is deterministic for identical history).
3. Create the matching annotated tag on that split commit inside `${TARGET_REPO}`:
   ```bash
   SPLIT_SHA="$(git -C "${SOURCE_REPO}" subtree split --prefix="${SOURCE_DIR}" "<tag>")"
   git -C "${TARGET_REPO}" tag -a "<tag>" "${SPLIT_SHA}" -m "Graduated release <tag>"
   ```
4. Verify `git -C "${TARGET_REPO}" show --stat "<tag>"` shows standalone root paths, not `<source_dir>/...`.

### Option B: Clean Single-Commit Start (Fresh Init)

Use when the user chooses a clean slate or when monorepo history contains secrets/noise:

```bash
SOURCE_DIR="<source_dir>"
TARGET_REPO="../<new-repo-name>"

mkdir -p "${TARGET_REPO}"
git archive "HEAD:${SOURCE_DIR}" | tar -x -C "${TARGET_REPO}"
git -C "${TARGET_REPO}" init -b main
git -C "${TARGET_REPO}" add .
git -C "${TARGET_REPO}" commit -m "chore: initial standalone extraction from ${SOURCE_DIR}"
```

---

## 3. Stack-Specific Decoupling & Verification Matrix

| Stack | Common Monorepo Couplings to Fix | Local Verification Commands |
| :--- | :--- | :--- |
| **IaC & GitOps** (OpenTofu / Terraform / Terragrunt) | `.github/workflows/*.yml` `PROJECT_DIR` → `"."` and `paths:` drop `<source_dir>/`; Terragrunt `root.hcl` git-root subpath derivation; `release.yaml` pinned tags remapped; `.tflint.hcl` / `.trivyignore` paths; `README.md` `-chdir` & script paths. | `tofu fmt -check -recursive`, `terragrunt hcl fmt --check`, `tofu validate`, `tflint`, `trivy config`, mocked `tofu test` / `terragrunt test` / shell tests. |
| **Python** (`uv` / Hatchling / Poetry / ADK) | Relative path deps (`../`, `../../skills/...`) in `pyproject.toml`, config defaults, or tests; `.env.example` & `config.example.yaml`; update `project.urls` / repo metadata; root `.gitignore` (`__pycache__/`, `.venv/`, `.ruff_cache/`, `*.db`, `.env`). | `uv sync` (or `uv sync --no-editable` on macOS `~/Documents`), `pytest`, `ruff check`, CLI smoke test (`--help` / `validate-config`). |
| **Java / JVM** (Maven / Gradle) | Parent POM `<relativePath>../parent_poms/...</relativePath>` (either inline properties/dependencyManagement or publish parent POM); multi-module `<modules>` paths; `.gitignore` (`target/`, `build/`, `.idea/`). | `mvn clean test` (or `./mvnw test` / `./gradlew check`). |
| **Node / TypeScript** | Monorepo workspace refs (`workspace:*`, `extends: "../../tsconfig.base.json"`); root ESLint/Prettier configs; regenerate lockfile cleanly; `.gitignore` (`node_modules/`, `dist/`, `.env*`). | `npm ci` / `pnpm install`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`. |
| **Go / Rust** | `replace ../...` in `go.mod` or `path = "../..."` / `workspace = true` in `Cargo.toml`; regenerate `go.sum` / `Cargo.lock`. | `go vet ./... && go test ./...` or `cargo clippy && cargo test`. |

---

## 4. GitHub Creation & Protocol Matching (Phase 6)

1. Check the user's preferred Git remote protocol from the source playground repo:
   - `git@github.com:<owner>/...` → SSH (`gh config get git_protocol` or configure SSH remote).
   - `https://github.com/<owner>/...` → HTTPS.
2. Confirm repository visibility (`--private` or `--public`) explicitly with the user before running:
   ```bash
   # Run from inside <target_repo>
   gh repo create "<owner>/<new-repo-name>" --private --description "<one-line summary>" --source=. --remote=origin --push
   # If remapped release tags exist:
   git push origin --tags
   ```
3. If `gh` defaults to HTTPS while the user uses SSH remotes, set the SSH URL cleanly:
   ```bash
   git remote set-url origin "git@github.com:<owner>/<new-repo-name>.git"
   ```

---

## 5. GitHub Profile Homepage Update (`<owner>/<owner>` README)

After publishing a graduated repo to GitHub, keep the owner's GitHub profile homepage (`https://github.com/<owner>` → `<owner>/<owner>/README.md`) in sync automatically:

1. Check if `<owner>/<owner>` exists locally (e.g., `../<owner>`) or clone/fetch via `gh`:
   ```bash
   gh repo view "<owner>/<owner>" --json nameWithOwner,defaultBranchRef,sshUrl
   ```
2. Update `<owner>/<owner>/README.md` cleanly while preserving its existing voice, badges, and tables:
   - Add a row for `[<new-repo-name>](https://github.com/<owner>/<new-repo-name>)` in the appropriate section/table (e.g., `Cloud & Platform Engineering`, `Data Engineering`, `Platforms`, `SDKs`).
   - Update any `Graduations in progress`, `Featured`, `Playgrounds`, or `Mastery Framework` references that pointed to `<source_dir>` inside the playground monorepo.
   - Skip adding private-only repos unless the user explicitly asks to list them.
3. Commit (`docs: add graduated <new-repo-name> to profile README`) and push to `<owner>/<owner>`'s default branch (via local clone or `gh api` Contents update).

---

## 6. Post-Move External Re-Bindings Checklist (Report to User)

Surface only the items that apply to the graduated project:
- **GCP Workload Identity Federation (WIF):** Update `github_repository` (e.g., in `infra/bootstrap/terraform.tfvars`) and apply bootstrap so the WIF `attribute_condition` and declaratively managed GitHub Actions repository variables bind to the new repo.
- **GitHub Repository Settings:** Recreate required repository secrets (e.g., `*_PROMOTE_TOKEN`), Environments (`dev` / `uat` / `prod` approval reviewers), and branch protection rules on `main`.
- **Skill / Tool Symlinks:** If a skill or CLI was symlinked from the playground (e.g., `~/.gemini/config/skills/<name>`), update the symlink target or reinstall from the new repo.
- **Downstream References:** Update any sibling repos, Obsidian notes, or bookmarks that pointed to the old monorepo subdirectory URL.

---

## 7. Playground Cleanup Format (Only After Explicit Confirmation)

When the user confirms pruning `<source_dir>` from the playground repo:
1. Delete `<source_dir>` and any migrated `.github/workflows/` files in the playground repo.
2. Remove `<source_dir>` from the playground `README.md` layout tree and active projects table, and record it under a `## Graduated Projects` section:

```markdown
## Graduated Projects

| Project | Standalone Repository | Graduated | Notes |
| :--- | :--- | :--- | :--- |
| `<source_dir>` | [<owner>/<new-repo-name>](https://github.com/<owner>/<new-repo-name>) | YYYY-MM-DD | <1-line summary of what graduated> |
```

3. Review `git status` and `git diff` in the playground repo and ask before committing/pushing.
