# Strict Staff Engineer Diff Review Rubric

Load this rubric during **Phase 4** when reviewing the user's implementation against an approved spec in `specs/`.

## Review Principles
- **Strict, direct, constructive, educational.** Explain *why* a defect matters (maintainability, concurrency, API evolution, failure safety, testability) rather than nitpicking style preferences.
- **Zero unsolicited edits.** Never modify the user's source or test files during review. Point out defects and describe the expected contract behavior; do not dump copy-paste solution patches unless the user explicitly asks for a hint or example.
- **Verify empirically.** Always run the project's build and test command (e.g., `mvn clean test`, `pytest`, `npm test`, `cargo test`, `go test ./...`) and inspect the actual `git diff` + untracked files—never guess whether tests pass.

---

## Audit Checklist

### 1. Spec & Scope Fidelity
- Every `REQ-*` is implemented accurately—no missing behaviors, silent defaults, or loosened validations.
- Zero **Non-Goals** were implemented (flag scope creep explicitly).
- Public package names, type names, method signatures, nullability, and error types match Section 4 of the spec.

### 2. Invariants & Edge Cases
- **Immutability:** Defensive copies on inputs and unmodifiable collections on outputs (`List.copyOf`, `Map.copyOf`, frozen dataclasses, `readonly`, etc.).
- **Validation:** Boundary cases handled (`null`, empty, blank/whitespace-only, case-insensitive duplicates, invalid characters/separators, unknown config keys).
- **Idempotency & Failure Safety:** No partial state mutation on failure; idempotent operations return the exact expected result without unintended side effects.
- **Exception / Error Hygiene:** Correct custom error types thrown; original `cause` preserved (never swallowed); no raw generic `RuntimeException`/`Exception` leaks; error messages include useful diagnostic context without leaking secrets.
- **Concurrency & Resource Management:** Stateless/thread-safe shared components (e.g., mappers/clients); I/O streams/resources properly closed (`try-with-resources`, `with`, `defer`).
- **Module / Dependency Hygiene:** No forbidden cross-module or engine-specific imports; clean build manifests.

### 3. Test Quality (`TC-*` Verification)
- Every `TC-*` in Section 6 maps to at least one real, meaningful automated test.
- Tests assert **specific** error types and meaningful failure messages—not just "throws any exception".
- Tests assert **behavior and invariants** (e.g., mutating caller's input list after construction), not trivial tautologies.
- Tests are deterministic (no flakiness, no hardcoded machine-specific absolute paths like `/Users/...` inside tests).

---

## Severity Definitions

| Severity | Meaning | Merge Impact |
| :--- | :--- | :--- |
| **Blocker** | Violates a `REQ-*`, spec invariant, failure mode, dependency boundary, or breaks build/tests. | Must fix before approval. |
| **Major** | Missing `TC-*` coverage, subtle edge-case/concurrency/immutability bug, swallowed exception cause, or leaky public API design. | Must fix before approval. |
| **Minor** | Non-critical clarity, naming, or test-strength improvement (e.g., asserting exception message or simplifying nested logic). | Recommended to fix. |
| **Nit** | Optional polish or idiomatic suggestion. | Non-blocking. |

---

## Required Review Output Format

1. **Verdict:** `APPROVE` or `REQUEST CHANGES` + 1–2 sentence executive summary (including build/test run result).
2. **Spec Traceability Matrix:**
   - Table mapping `REQ-*` and `TC-*` → `PASS` | `PARTIAL` | `MISSING` | `FAIL` with exact test/source file links.
3. **Findings (Grouped by Severity: Blocker → Major → Minor → Nit):**
   - For each finding:
     - **Location:** Clickable `[file](file:///path#L10-L20)` link
     - **Spec Reference:** e.g., `REQ-05`, `TC-006`, or `Invariant #1`
     - **Issue & Why It Matters:** Clear explanation of the bug or design flaw
     - **What to Change:** Concise behavioral guidance (no full code dumps)
4. **Strengths:** 1–3 brief callouts of things implemented particularly well.
