# Staff-Grade Mermaid Exemplars (Obsidian Violet Theme)

Production-ready reference templates for all 5 universal Mermaid diagram archetypes. Load only the section matching the diagram you are creating. Every block below passes `scripts/validate_mermaid.py --strict-warnings`.

---

## 1. System Architecture Topology (`flowchart TB`)

Demonstrates trust zones, Control vs. Data Plane separation, explicit guardrails, sync/hot/async edge semantics, and 3-line Staff node labels.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#09090B", "primaryColor": "#18181B", "primaryTextColor": "#F4F4F5", "primaryBorderColor": "#7C3AED", "lineColor": "#8B5CF6", "secondaryColor": "#16141F", "tertiaryColor": "#0F0F14", "edgeLabelBackground": "#18181B", "clusterBkg": "#0F0F14", "clusterBorder": "#52525B", "fontFamily": "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif", "fontSize": "13px"}, "flowchart": {"curve": "basis", "nodeSpacing": 42, "rankSpacing": 56, "padding": 14}}}%%
flowchart TB
    subgraph ExternalZone["1. External Producers & Clients"]
        Producers(["Upstream Services\nHTTPS / gRPC Producers\nIdempotency-Key: UUIDv7"])
        Operators(["SRE / Platform CLI\nSchema & Quota Admin"])
    end

    subgraph PlatformVPC["2. Ingestion Platform (Private VPC)"]
        subgraph EdgeGuard["2a. Ingress & Policy Boundary"]
            Gateway["Edge Gateway\nEnvoy · mTLS + JWT\nToken-Bucket 50k RPS"]
            SchemaGate{"Schema & Policy Gate\nProtobuf v3 Registry\nFail-Closed on Breaking Drift"}
        end

        subgraph ControlPlane["2b. Control Plane"]
            Orchestrator["Ingestion Coordinator\nGo · Raft Lease Leader\nPartition & Backpressure Control"]
            QuotaStore[("Config & Quota Store\nCloud Spanner\nStrong Consistency")]
        end

        subgraph DataPlane["2c. Data & Execution Plane"]
            IngestBus(["Durable Event Log\nKafka / Pub/Sub\n3x RF · 7d Retention"])
            Workers["Stream Normalizers\nRust · Stateless HPA 4-40\nExactly-Once Sink Commit"]
            DedupCache[("Idempotency Cache\nRedis Cluster\nTTL 24h · LRU")]
            Lakehouse[("Curated Iceberg Lake\nApache Iceberg v2 on GCS\nSnapshot Isolation")]
        end

        subgraph AsyncReliability["2d. Reliability & Observability"]
            DLQ(["Dead-Letter Topic\nQuarantine + Poison Payload\nReplayable via CLI"])
            Telemetry["OTel Collector\nTraces + Lag Metrics\nSLO Alerting"]
        end
    end

    Producers ==>|"HTTPS / mTLS\n(timeout 2s)"| Gateway
    Operators -.->|"OIDC + RBAC\nSchema / Quota Push"| Orchestrator
    Gateway ==>|"Validated Frame"| SchemaGate
    SchemaGate ==>|"Valid · Partition Key"| IngestBus
    SchemaGate -.->|"4xx / Schema Violation"| DLQ
    Orchestrator <-->|"Lease + Quota Rules"| QuotaStore
    Orchestrator -.->|"Rate & Backpressure Policy"| Gateway
    IngestBus ==>|"Pull Batch · At-Least-Once"| Workers
    Workers <-->|"Check/Set UUIDv7"| DedupCache
    Workers ==>|"Atomic Snapshot Append"| Lakehouse
    Workers -.->|"Exhausted 5x Backoff"| DLQ
    Workers -.->|"OTel Spans / Lag"| Telemetry

    class Orchestrator core
    class Gateway,Workers service
    class QuotaStore,IngestBus,DedupCache,Lakehouse store
    class Producers,Operators external
    class DLQ,Telemetry async
    class SchemaGate guard

    classDef core fill:#2E1065,stroke:#A855F7,stroke-width:2px,color:#F5F3FF
    classDef service fill:#18181B,stroke:#7C3AED,stroke-width:1.5px,color:#F4F4F5
    classDef store fill:#09090B,stroke:#C084FC,stroke-width:1.5px,color:#EDE9FE
    classDef external fill:#27272A,stroke:#71717A,stroke-width:1.5px,color:#E4E4E7
    classDef async fill:#1E1B2E,stroke:#6B7280,stroke-width:1.25px,stroke-dasharray:4 3,color:#D4D4D8
    classDef guard fill:#3B0764,stroke:#E879F9,stroke-width:2px,stroke-dasharray:5 3,color:#FAF5FF

    style ExternalZone fill:#18181B,stroke:#52525B,stroke-width:1.25px,stroke-dasharray:5 4,color:#A1A1AA
    style PlatformVPC fill:#0F0F14,stroke:#52525B,stroke-width:1.5px,color:#D8B4FE
    style EdgeGuard fill:#16141F,stroke:#6D28D9,stroke-width:1.25px,stroke-dasharray:4 3,color:#C4B5FD
    style ControlPlane fill:#16141F,stroke:#6D28D9,stroke-width:1.25px,stroke-dasharray:4 3,color:#C4B5FD
    style DataPlane fill:#16141F,stroke:#6D28D9,stroke-width:1.25px,stroke-dasharray:4 3,color:#C4B5FD
    style AsyncReliability fill:#16141F,stroke:#6D28D9,stroke-width:1.25px,stroke-dasharray:4 3,color:#C4B5FD
```

*Arrow Legend: Thick solid (`==>`) = primary hot/write data path · Solid (`-->`) = synchronous RPC/lookup · Dashed (`-.->`) = async event, policy push, DLQ, or telemetry.*

---

## 2. Protocol & Failure-Mode Sequence (`sequenceDiagram`)

Demonstrates `autonumber`, `alt`/`opt` branching for deduplication and transient retries, activation bars, and dual-canvas legible purple/grey styling.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#09090B", "primaryColor": "#18181B", "primaryTextColor": "#F4F4F5", "primaryBorderColor": "#7C3AED", "lineColor": "#8B5CF6", "actorBkg": "#18181B", "actorBorder": "#7C3AED", "actorTextColor": "#F4F4F5", "actorLineColor": "#52525B", "signalColor": "#8B5CF6", "signalTextColor": "#7C3AED", "labelBoxBkgColor": "#2E1065", "labelBoxBorderColor": "#A855F7", "labelTextColor": "#F5F3FF", "loopTextColor": "#8B5CF6", "noteBkgColor": "#1E1B2E", "noteBorderColor": "#6D28D9", "noteTextColor": "#EDE9FE", "activationBkgColor": "#4C1D95", "activationBorderColor": "#C084FC", "sequenceNumberColor": "#FAF5FF", "fontFamily": "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif", "fontSize": "13px"}}}%%
sequenceDiagram
    autonumber
    participant Client as Producer Client
    participant API as Order API (Go)
    participant Idem as Idempotency Store (Redis)
    participant DB as Ledger DB (Postgres)
    participant Bus as Outbox Relay / Kafka

    Client->>+API: POST /v1/orders (Idempotency-Key: K1, payload)
    API->>+Idem: SETNX K1 state="IN_FLIGHT" EX 300
    Idem-->>-API: Result (acquired | existing_record)

    alt Duplicate key already COMPLETED
        API-->>Client: 200 OK (cached response_body, replay=true)
    else Key IN_FLIGHT by concurrent worker
        API-->>Client: 409 Conflict (Retry-After: 2s)
    else Lock acquired (new request)
        API->>+DB: BEGIN TX: INSERT orders + INSERT outbox_events
        alt Commit succeeds
            DB-->>-API: COMMIT OK (order_id=O-9421)
            API->>Idem: SET K1 state="COMPLETED" response_body EX 86400
            API-->>-Client: 201 Created (order_id=O-9421)
            Note over DB,Bus: Transactional Outbox guarantees zero dual-write drift
            Bus->>DB: Poll unpublished outbox_events (FOR UPDATE SKIP LOCKED)
            DB-->>Bus: Batch of events
            Bus->>Bus: Publish to Kafka (acks=all, partition=order_id)
            Bus->>DB: Mark published_at = NOW()
        else Transient serialization / deadlock failure
            DB-->>API: 40001 Serialization Failure (ROLLBACK)
            API->>Idem: DEL K1 (release lock so client retry proceeds safely)
            API-->>Client: 503 Service Unavailable (retryable=true)
        end
    end
```

---

## 3. Job / Workflow Lifecycle State Machine (`stateDiagram-v2`)

Demonstrates explicit transition guards `[condition]`, retry budgets, quarantine/terminal states, and `classDef` tiering.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#09090B", "primaryColor": "#18181B", "primaryTextColor": "#F4F4F5", "primaryBorderColor": "#7C3AED", "lineColor": "#8B5CF6", "secondaryColor": "#16141F", "tertiaryColor": "#0F0F14", "edgeLabelBackground": "#18181B", "transitionColor": "#8B5CF6", "transitionLabelColor": "#E4E4E7", "stateBkg": "#18181B", "stateLabelColor": "#F4F4F5", "compositeBackground": "#0F0F14", "compositeTitleBackground": "#2E1065", "fontFamily": "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif", "fontSize": "13px"}}}%%
stateDiagram-v2
    [*] --> Queued: Enqueue job (UUIDv7)

    Queued --> Validating: Lease acquired (TTL 60s)
    Validating --> Running: [schema & quota valid]
    Validating --> Quarantined: [invalid schema / policy deny]

    Running --> Committing: [transform complete]
    Running --> BackoffWait: [transient 429/5xx & attempts < 5]
    Running --> DeadLetter: [attempts >= 5 or fatal error]

    BackoffWait --> Queued: [exp backoff + jitter elapsed]

    Committing --> Succeeded: [Iceberg snapshot CAS ok]
    Committing --> BackoffWait: [optimistic lock conflict & attempts < 5]
    Committing --> DeadLetter: [CAS retries exhausted]

    DeadLetter --> Queued: [operator replay with --force]
    Quarantined --> [*]
    Succeeded --> [*]

    classDef core fill:#2E1065,stroke:#A855F7,stroke-width:2px,color:#F5F3FF
    classDef service fill:#18181B,stroke:#7C3AED,stroke-width:1.5px,color:#F4F4F5
    classDef async fill:#1E1B2E,stroke:#6B7280,stroke-width:1.25px,stroke-dasharray:4 3,color:#D4D4D8
    classDef guard fill:#3B0764,stroke:#E879F9,stroke-width:2px,stroke-dasharray:5 3,color:#FAF5FF

    class Running,Committing core
    class Queued,Validating,Succeeded service
    class BackoffWait async
    class Quarantined,DeadLetter guard
```

---

## 4. Domain & Persistence Data Model (`erDiagram`)

Demonstrates clean cardinality, `PK`/`FK`/`UK` markers, and invariant comments on every non-obvious column.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#09090B", "primaryColor": "#2E1065", "primaryTextColor": "#F4F4F5", "primaryBorderColor": "#7C3AED", "lineColor": "#8B5CF6", "secondaryColor": "#18181B", "tertiaryColor": "#0F0F14", "edgeLabelBackground": "#18181B", "attributeBackgroundColorOdd": "#18181B", "attributeBackgroundColorEven": "#0F0F14", "fontFamily": "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif", "fontSize": "13px"}}}%%
erDiagram
    TENANT ||--o{ PIPELINE_RUN : "owns (quota enforced)"
    PIPELINE_RUN ||--|{ OUTBOX_EVENT : "emits atomically in TX"
    PIPELINE_RUN ||--o{ RUN_CHECKPOINT : "persists resumable cursor"

    TENANT {
        uuid tenant_id PK "Immutable partition key"
        string slug UK "Lowercase DNS-safe identifier"
        int max_concurrency "Hard cap enforced by Coordinator"
        string residency_region "us-central1 | europe-west4"
    }

    PIPELINE_RUN {
        uuid run_id PK "UUIDv7 time-ordered"
        uuid tenant_id FK "Indexed with status"
        string idempotency_key UK "Scoped per tenant_id"
        string state "queued | running | succeeded | dlq"
        int attempt_count "Monotonic, max 5"
        timestamp lease_expires_at "UTC; reclaimed if expired"
    }

    RUN_CHECKPOINT {
        uuid checkpoint_id PK "UUIDv7"
        uuid run_id FK "Cascade delete on retention purge"
        bigint offset_cursor "Monotonic source watermark"
        string content_sha256 "64-char payload digest"
        timestamp committed_at "UTC ISO-8601"
    }

    OUTBOX_EVENT {
        bigint seq_id PK "Strictly monotonic per partition"
        uuid run_id FK "Correlates to PIPELINE_RUN"
        string event_type "run.completed | run.quarantined"
        jsonb payload "Versioned Avro/JSON envelope"
        timestamp published_at "NULL until Kafka acks=all"
    }
```

---

## 5. Component & Interface Hierarchy (`classDiagram`)

Focuses on public contracts, composition, and failure/extension seams rather than noisy getter/setter boilerplate.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#09090B", "primaryColor": "#18181B", "primaryTextColor": "#F4F4F5", "primaryBorderColor": "#7C3AED", "lineColor": "#8B5CF6", "secondaryColor": "#2E1065", "tertiaryColor": "#0F0F14", "edgeLabelBackground": "#18181B", "classText": "#F4F4F5", "fontFamily": "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif", "fontSize": "13px"}}}%%
classDiagram
    class EventSink {
        <<interface>>
        +append(batch: RecordBatch) SnapshotReceipt
        +healthCheck() SinkStatus
    }

    class RetryPolicy {
        +int maxAttempts
        +Duration baseBackoff
        +bool jitterEnabled
        +nextDelay(attempt: int) Duration
    }

    class ResilientPipeline {
        -EventSink sink
        -RetryPolicy retryPolicy
        -IdempotencyLedger ledger
        +ingest(key: UUIDv7, payload: bytes) CommitResult
    }

    class IcebergCatalogSink {
        -string warehouseUri
        -string tableIdent
        +append(batch: RecordBatch) SnapshotReceipt
        +healthCheck() SinkStatus
    }

    class IdempotencyLedger {
        <<interface>>
        +tryAcquire(key: UUIDv7, ttl: Duration) LeaseState
        +markCommitted(key: UUIDv7, receipt: SnapshotReceipt) void
    }

    ResilientPipeline *-- RetryPolicy : enforces backoff
    ResilientPipeline o-- EventSink : writes via contract
    ResilientPipeline o-- IdempotencyLedger : guards exactly-once
    EventSink <|.. IcebergCatalogSink : implements CAS commit
```
