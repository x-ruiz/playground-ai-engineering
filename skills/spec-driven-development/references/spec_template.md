# Spec Template: Core Skeleton + Archetype Contract Modules

Use this structure when drafting a spec in `specs/NN_<feature_name>.md`.

> **CRITICAL RULE:** Do **not** include application source code blocks (`java`, `python`, `typescript`, `go`, `rust`, etc.) in the spec. Describe all types, signatures, interfaces, and errors using Markdown tables and prose. Only external data/config/wire payload formats (YAML, JSON, TOML, `.textproto`, CLI examples) may appear in fenced code blocks.

---

## Core Skeleton

```markdown
# Feature Spec: <Feature Name>

- **Status:** Draft (Pending Approval) | Approved | Superseded
- **Module / Component:** <Module, package, or service name & runtime>
- **Archetype:** Library Contract | API / Service | Data Pipeline | CLI Tool
- **Tier:** Mini-Spec | Full Spec
- **Owner:** <Owner Name>

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
