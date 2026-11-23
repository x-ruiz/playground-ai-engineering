# Compact Note Exemplars

## 1. New Note (`create`)

```markdown
---
tags:
  - data-processing/frameworks/spark
  - cloud-infrastructure/services/gcp
aliases:
  - Dataproc Serverless
source: "Google Cloud Managed Service for Apache Spark Documentation"
source-type: documentation
vendor: "Google Cloud"
url: "https://cloud.google.com/products/managed-service-for-apache-spark"
created: 2026-11-23
---
Google Cloud's managed execution platform for running Apache Spark batch, streaming, and interactive lakehouse workloads without administering cluster VMs or YARN/Kubernetes infrastructure.

## Execution Modes

| Mode | Compute Management | Best Fit | Senior Note |
| :--- | :--- | :--- | :--- |
| **Serverless Batches** | Fully autoscaled per job; zero idle clusters | Scheduled ETL and Apache Iceberg transforms | Eliminates zombie cluster spend; monitor DCU-hours and shuffle storage. |
| **Interactive Sessions** | Managed Spark Connect / Jupyter runtimes | Exploratory analysis | Enforce idle TTLs to prevent forgotten session burn. |
| **Standard Clusters** | Provisioned GCE clusters | Pinned OS dependencies or legacy HDFS locality | Prefer Serverless unless custom daemons force cluster ownership. |

## When Not to Use
- Pure SQL aggregations over BigQuery-native tables (use BigQuery directly).
- Sub-second event-by-event streaming watermarks (evaluate Dataflow or Flink).
```

---

## 2. Update Draft (`update`)

Filename: `staging/AI Engineering/Modern AI Architecture (Update).md`

```markdown
---
note-action: update
target-note: "[[Modern AI Architecture]]"
target-path: "AI Engineering/Modern AI Architecture.md"
tags:
  - ai-engineering/agents/harness
source: "Building Production AI Agent Harnesses"
source-type: article
author: "Databricks Engineering Blog"
published: 2026-04-15
url: "https://www.databricks.com/blog/ai-harness"
created: 2026-11-23
---
> [!NOTE]
> **Draft Modification for [[Modern AI Architecture]]** (`AI Engineering/Modern AI Architecture.md`)
> **Merge Rationale:** The existing note covers LLM core layers, MCP, RAG, and bounded loops. Merge the net-new harness control-plane and eval-gate patterns below rather than creating a duplicate note.

## Proposed Frontmatter Additions
- **Add tag:** `ai-engineering/agents/harness`
- **Append source:** `Building Production AI Agent Harnesses` (`https://www.databricks.com/blog/ai-harness`)

## Proposed New Section: `## Harness Control Plane & Eval Gates`
An **agent harness** encapsulates everything outside foundation model weights—step budgets, context scoping, IAM-enforced tool proxies, and automated offline/online evaluations.

| Control Plane Concern | Deterministic Mechanism | Senior Note |
| :--- | :--- | :--- |
| **Regression Safety** | Golden-dataset eval gates in CI | Block prompt or tool-schema merges when task pass rate drops below threshold. |
| **Blast Radius** | Scoped read/write proxy per tool | Keep destructive mutations behind deterministic approval gates outside the LLM. |
```
