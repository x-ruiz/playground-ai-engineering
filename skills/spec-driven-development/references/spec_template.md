# Spec Template: Core Skeleton + Archetype Contract Modules

Use this structure when drafting a spec in `specs/NN_<feature_name>.md`.

> **CRITICAL RULES:**
> 1. **No application source code blocks:** Do **not** include application code (`java`, `python`, `typescript`, `go`, `rust`, etc.) in the spec. Describe all types, signatures, interfaces, and errors using Markdown tables and prose. Only external data/config/wire payload formats (YAML, JSON, TOML, `.textproto`, CLI examples) may appear in fenced code blocks.
> 2. **Spec Sizing & Chunking Guardrails:** Keep every spec right-sized so the Human Approval Gate stays sharp:
>    - **Mini-Spec:** ~80–160 lines, **5–10** `REQ-*` / `TC-*` (1 focused feature, plugin, or bounded change — 1 PR).
>    - **Full Spec:** ~160–250 lines, **10–15** `REQ-*` / `TC-*` (1 cohesive new module or subsystem — 1–2 PRs).
>    - **Split Threshold (> 250 lines or > 15 `TC-*`):** Treat as an Epic. Write a concise `00_` structural/architecture overview and split implementation into 2–4 sequential specs along **lifecycle/blast-radius boundaries** (e.g., one-time bootstrap vs. continuous GitOps), **build-artifact/module boundaries** (e.g., core adapter vs. cloud plugin), **title "and" smells** (2+ unrelated topics), and **independent verification gates**.
> 3. **Spec Altitude Rule:** Lock **public contracts, module boundaries, invariants, and observable `TC-*` behaviors**—do **not** over-specify private/package-private helper method signatures or internal decomposition so refactoring internals never causes unnecessary spec churn.

---

## Core Skeleton

```markdown
# Feature Spec: <Feature Name>

- **Status:** Draft (Pending Approval) | Approved | Superseded
- **Module / Component:** <Single cohesive module, package, or service & runtime>
- **Archetype:** Library Contract | API / Service | Data Pipeline | CLI Tool | IaC & GitOps
- **Tier:** Mini-Spec (80–160 lines, 5–10 TCs) | Full Spec (160–250 lines, 10–15 TCs)
- **Owner:** <Owner Name>
- **Depends On:** <Prior spec paths, if any>

---

## 1. Goal & Context

### Problem Statement
<2–4 sentences describing the concrete problem, current limitation, and why this feature is needed now.>

### Success Metrics
- <Objective, verifiable outcome (build/test command, zero forbidden dependencies, performance or correctness bar)>
- <Coverage of TC-001 through TC-NNN>

---

## 2. Scope & Explicit Non-Goals

### In Scope
- <Concrete boundaries of what must be built>

### Non-Goals (Do Not Implement)
- <Explicit guardrails preventing scope creep, premature abstraction, or unrelated refactors>

---

## 3. Functional Requirements

- `REQ-01`: The <library/service/pipeline/CLI> shall <testable behavioral statement>.
- `REQ-02`: ...

---

## 4. Interface & Data Contract

<!-- Pick the matching Archetype Contract Module below (tables + prose; external payload code blocks only). -->

---

## 5. Invariants, Edge Cases & Failure Modes

### Key Invariants
1. **<Invariant Name>:** <Immutability, thread-safety, dependency boundaries, idempotency, security/PII rules, etc.>

### Failure Mode Matrix

| Failure Condition | Expected Error / Exception / Status | Notes |
| :--- | :--- | :--- |
| <Invalid input / boundary / upstream outage> | <Deterministic error type/code> | <Preserves cause? No partial mutation?> |

---

## 6. Acceptance Criteria & Verification Matrix

| Case ID | Scenario | Input / Precondition | Expected Outcome |
| :--- | :--- | :--- | :--- |
| `TC-001` | Happy path | <Concrete input> | <Exact return value + side effects> |
| `TC-002` | Idempotency / Repeat | <Repeated valid input> | <Deterministic no-op or conflict behavior> |
| `TC-003` | Validation failure | <Malformed / missing / duplicate input> | <Exact error type/code, zero state mutation> |
| `TC-004` | Boundary / Concurrency / Hygiene | <Edge condition, concurrency, module dependency check> | <Verified invariant> |
```

---

## Archetype Contract Modules (Choose One for Section 4)

### A. Software Library Contract (Java / Python / TS / Go / Rust)
Use structured Markdown tables—never language syntax blocks:
- **Package / Module Layout:** Bullet list of public packages/modules and their responsibilities.
- **Domain Models & Value Objects Table:** `| Type | Kind (record/dataclass/struct/enum) | Fields / Values | Required Methods & Validation Behavior |`
- **Service / Port Interfaces Table:** `| Interface / Protocol | Operations (inputs → outputs) | Behavioral Contract |`
- **Error / Exception Hierarchy Table:** `| Error Type | Parent | Required Fields / Constructors | When Raised / Thrown |`
- **External Config / Wire Formats (Optional):** Fenced `yaml` / `json` / `toml` / `protobuf` data examples only.

### B. HTTP / gRPC API Service Contract
- **Endpoints / RPCs Table:** `| Method & Path / RPC | Auth | Idempotency | Request Schema | Success Response | Error Codes |`
- **Request & Response Payloads:** Fenced `json` or schema payload examples (no controller/handler code).
- **Pagination, Rate Limits & Timeouts:** Concise bullet list.

### C. Data Pipeline / ETL Contract
- **Source & Sink Inventory Table:** `| Role | System / Path / Table | Format | Partitioning / Ordering | Schema Contract |`
- **Transformation & Data Quality Rules:** Numbered rules mapping source fields → target fields, null/late-data handling, deduplication key.
- **Idempotency & Backfill Semantics:** Watermark, overwrite vs. merge strategy, SLA targets.

### D. CLI Tool Contract
- **Command Grammar & Subcommands Table:** `| Command | Positional Args | Flags (name, type, default, required) | Exit Codes |`
- **Stdout / Stderr Contract:** Machine-readable vs. human-readable output format.
- **Usage Examples:** Fenced `bash` invocation examples only.

### E. Infrastructure-as-Code & GitOps Contract
- **Directory & Module Boundary Tree:** Concise `text` tree scoped to this spec's lifecycle tier (separate one-time bootstrap, reusable modules, and continuous CI/CD environment composition into distinct specs).
- **Module Input / Output Tables:** `| Direction | Name | Type | Default / Required | Validation & Contract |`
- **IAM / Security Principal Matrix:** `| Principal | Auth / Condition | Scope | Assigned Roles | Purpose |`
- **Mandatory Tagging / Labeling & Cost Baseline:** Required labels and default `$0`/idle-cost invariants.
- **External Payload Example:** Fenced `json` / `tfvars` / `yaml` input example only (no HCL resource blocks).
