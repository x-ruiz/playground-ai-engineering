# Obsidian Violet Theme System & Portability Spec

Authoritative visual design system and parser-safety specification for `mermaid-diagrams`. Every diagram must draw strictly from this purple, black, and graphite grey palette so outputs look cohesive, editorial, and effortless to scan for Senior–Staff engineers.

---

## 1. Canonical Color Palette (WCAG AAA Verified)

Every foreground/background pair below exceeds **11:1 contrast (WCAG AAA)** and uses explicit fills, borders, and text colors so styled elements never degrade across dark or light host themes.

### Surfaces (Obsidian Blacks & Charcoal Greys)
| Token | Hex | Role |
| :--- | :--- | :--- |
| `obsidian-950` | `#09090B` | Pitch obsidian — data stores, cylinders, deep canvas background |
| `obsidian-900` | `#0F0F14` | Midnight charcoal — outer subgraph/zone containers |
| `aubergine-900` | `#16141F` | Deep purple-tinted obsidian — inner subgraph/sub-layer containers |
| `zinc-900` | `#18181B` | Primary dark slate — standard compute/service nodes, edge label pills |
| `aubergine-850` | `#1E1B2E` | Muted midnight violet — async workers, telemetry, metadata, sequence notes |
| `zinc-800` | `#27272A` | Graphite grey — external clients, actors, untrusted ingress |

### Accents (Imperial Violet, Vivid Purple & Lavender)
| Token | Hex | Role |
| :--- | :--- | :--- |
| `violet-950` | `#2E1065` | Deep imperial violet — Tier-1 core engine / control plane fill, ER headers |
| `plum-950` | `#3B0764` | Intense ultraviolet — critical guardrails, circuit breakers, auth/policy gates |
| `violet-900` | `#4C1D95` | Dark royal violet — sequence activation bars, highlighted state headers |
| `violet-700` | `#6D28D9` | Royal violet — inner subgraph borders, note borders |
| `violet-600` | `#7C3AED` | Vivid violet — standard service borders, primary structural accents |
| `violet-500` | `#8B5CF6` | Medium violet — default edge/connector lines (dual-canvas legible) |
| `purple-500` | `#A855F7` | Electric purple — core node borders, sequence signals (dual-canvas legible) |
| `purple-400` | `#C084FC` | Luminous lavender — data store/queue borders, activation borders |
| `orchid-400` | `#E879F9` | Bright orchid violet — critical/guardrail dashed borders |

### Greys & High-Contrast Typography
| Token | Hex | Role |
| :--- | :--- | :--- |
| `zinc-700` | `#3F3F46` | Dark steel — subtle dividers, sequence gridlines |
| `zinc-600` | `#52525B` | Charcoal grey — outer zone borders, sequence lifelines |
| `slate-500` | `#6B7280` | Cool slate grey — async/telemetry dashed borders |
| `zinc-500` | `#71717A` | Steel grey — external node borders, secondary/async edge strokes |
| `zinc-400` | `#A1A1AA` | Ash silver — external subgraph titles |
| `zinc-300` | `#D4D4D8` | Cool silver — async/meta node text |
| `zinc-200` | `#E4E4E7` | Crisp silver — external node text, edge label pill text |
| `zinc-100` | `#F4F4F5` | Bright white-grey — service node text, primary labels |
| `violet-300` | `#C4B5FD` | Soft periwinkle — inner subgraph titles |
| `purple-300` | `#D8B4FE` | Soft lilac — outer subgraph titles, loop headers |
| `violet-100` | `#EDE9FE` | Pale violet white — data store text, sequence note text |
| `violet-50` | `#F5F3FF` | Soft lavender white — core node text |
| `fuchsia-50` | `#FAF5FF` | Pure lilac white — guardrail node text, sequence autonumbers |

---

## 2. True Obsidian Dark Mode Enforcement (Never White Background)

Mermaid's `base` theme defaults to `darkMode: false` and renders SVGs with a transparent background—causing light-mode hosts (such as GitHub Light Mode or web viewers) to show a stark white canvas and causing ER/class/state internals to derive light fills. Enforce dark mode with all four layers:

1. **Always set `"darkMode": true`** inside `themeVariables` so Mermaid's `base` color derivation engine computes dark-mode defaults across all diagram types (`flowchart`, `sequenceDiagram`, `stateDiagram-v2`, `erDiagram`, `classDiagram`).
2. **Always set explicit dark base variables:** `"background": "#09090B"`, `"mainBkg": "#18181B"`, `"textColor": "#F4F4F5"`, and `"edgeLabelBackground": "#18181B"`.
3. **Always force a dark SVG canvas via `themeCSS`:** `"themeCSS": "svg { background-color: #09090B !important; border-radius: 8px; }"` so the diagram always renders on a pitch obsidian dark card instead of bleeding through a white page background.
4. **Always set explicit `fill`, `stroke`, and `color`** on every `classDef` and subgraph `style`, and keep `"theme": "base"` (never `"theme": "default"` or `"theme": "neutral"`).

---

## 3. Semantic `classDef` & Subgraph Styles (Flowcharts & State Diagrams)

Include only the classes actually used in the diagram (typically 3–5 classes per view). Keep the exact class names so diagrams stay consistent across repositories:

```mermaid
classDef core fill:#2E1065,stroke:#A855F7,stroke-width:2px,color:#F5F3FF
classDef service fill:#18181B,stroke:#7C3AED,stroke-width:1.5px,color:#F4F4F5
classDef store fill:#09090B,stroke:#C084FC,stroke-width:1.5px,color:#EDE9FE
classDef external fill:#27272A,stroke:#71717A,stroke-width:1.5px,color:#E4E4E7
classDef async fill:#1E1B2E,stroke:#6B7280,stroke-width:1.25px,stroke-dasharray:4 3,color:#D4D4D8
classDef guard fill:#3B0764,stroke:#E879F9,stroke-width:2px,stroke-dasharray:5 3,color:#FAF5FF
```

### When to Use Each Class
- `core` — Primary orchestrator, control plane, scheduler, consensus leader, or the hero component of the diagram (limit to **1–3 nodes** so visual focus stays unmistakable).
- `service` — Stateless microservices, compute workers, APIs, gateways, transformation stages.
- `store` — Databases, object storage, caches, WAL ledgers, message brokers/topics, vector indexes (prefer cylinder `[("...")]` or stadium `(["..."])` shapes).
- `external` — End users, browsers, third-party SaaS APIs, partner systems, CI triggers.
- `async` — Background jobs, DLQs, observability/telemetry sinks, cron triggers, sidecars, batch indexers.
- `guard` — Auth/WIF/IAM trust boundaries, circuit breakers, rate limiters, schema validation gates, policy engines, idempotency locks.

### Subgraph Container Styles
Apply explicit styles at the bottom of `flowchart` blocks using each subgraph's ID:

```text
%% Outer trust boundary / VPC / platform tier
style OuterZone fill:#0F0F14,stroke:#52525B,stroke-width:1.5px,color:#D8B4FE

%% Inner domain / execution plane / private subnet
style InnerZone fill:#16141F,stroke:#6D28D9,stroke-width:1.25px,stroke-dasharray:4 3,color:#C4B5FD

%% External / untrusted / third-party zone
style ExternalZone fill:#18181B,stroke:#52525B,stroke-width:1.25px,stroke-dasharray:5 4,color:#A1A1AA
```

---

## 4. Copy-Ready `%%{init}%%` Directives (Valid Double-Quoted JSON)

Always place `%%{init: ...}%%` on **line 1** of the Mermaid block using strict double-quoted JSON with `"darkMode": true` and obsidian `themeCSS`.

### A. `flowchart` (`TB` or `LR`)
```text
%%{init: {"theme": "base", "themeCSS": "svg { background-color: #09090B !important; border-radius: 8px; }", "themeVariables": {"darkMode": true, "background": "#09090B", "mainBkg": "#18181B", "textColor": "#F4F4F5", "primaryColor": "#18181B", "primaryTextColor": "#F4F4F5", "primaryBorderColor": "#7C3AED", "lineColor": "#A855F7", "secondaryColor": "#16141F", "tertiaryColor": "#0F0F14", "edgeLabelBackground": "#18181B", "clusterBkg": "#0F0F14", "clusterBorder": "#52525B", "titleColor": "#D8B4FE", "fontFamily": "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif", "fontSize": "13px"}, "flowchart": {"curve": "basis", "nodeSpacing": 42, "rankSpacing": 56, "padding": 14}}}%%
```

### B. `sequenceDiagram`
```text
%%{init: {"theme": "base", "themeCSS": "svg { background-color: #09090B !important; border-radius: 8px; }", "themeVariables": {"darkMode": true, "background": "#09090B", "mainBkg": "#18181B", "textColor": "#F4F4F5", "primaryColor": "#18181B", "primaryTextColor": "#F4F4F5", "primaryBorderColor": "#7C3AED", "lineColor": "#A855F7", "actorBkg": "#18181B", "actorBorder": "#7C3AED", "actorTextColor": "#F4F4F5", "actorLineColor": "#52525B", "signalColor": "#A855F7", "signalTextColor": "#E4E4E7", "labelBoxBkgColor": "#2E1065", "labelBoxBorderColor": "#A855F7", "labelTextColor": "#F5F3FF", "loopTextColor": "#D8B4FE", "noteBkgColor": "#1E1B2E", "noteBorderColor": "#6D28D9", "noteTextColor": "#EDE9FE", "activationBkgColor": "#4C1D95", "activationBorderColor": "#C084FC", "sequenceNumberColor": "#FAF5FF", "fontFamily": "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif", "fontSize": "13px"}}}%%
```

### C. `stateDiagram-v2`
```text
%%{init: {"theme": "base", "themeCSS": "svg { background-color: #09090B !important; border-radius: 8px; }", "themeVariables": {"darkMode": true, "background": "#09090B", "mainBkg": "#18181B", "textColor": "#F4F4F5", "primaryColor": "#18181B", "primaryTextColor": "#F4F4F5", "primaryBorderColor": "#7C3AED", "lineColor": "#A855F7", "secondaryColor": "#16141F", "tertiaryColor": "#0F0F14", "altBackground": "#16141F", "edgeLabelBackground": "#18181B", "labelBackgroundColor": "#18181B", "transitionColor": "#A855F7", "transitionLabelColor": "#E4E4E7", "stateBkg": "#18181B", "stateLabelColor": "#F4F4F5", "compositeBackground": "#0F0F14", "compositeTitleBackground": "#2E1065", "fontFamily": "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif", "fontSize": "13px"}}}%%
```

### D. `erDiagram`
```text
%%{init: {"theme": "base", "themeCSS": "svg { background-color: #09090B !important; border-radius: 8px; }", "themeVariables": {"darkMode": true, "background": "#09090B", "mainBkg": "#18181B", "textColor": "#F4F4F5", "primaryColor": "#2E1065", "primaryTextColor": "#F5F3FF", "primaryBorderColor": "#7C3AED", "lineColor": "#A855F7", "secondaryColor": "#18181B", "tertiaryColor": "#0F0F14", "edgeLabelBackground": "#18181B", "attributeBackgroundColorOdd": "#18181B", "attributeBackgroundColorEven": "#0F0F14", "fontFamily": "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif", "fontSize": "13px"}}}%%
```

### E. `classDiagram`
```text
%%{init: {"theme": "base", "themeCSS": "svg { background-color: #09090B !important; border-radius: 8px; }", "themeVariables": {"darkMode": true, "background": "#09090B", "mainBkg": "#18181B", "textColor": "#F4F4F5", "primaryColor": "#18181B", "primaryTextColor": "#F4F4F5", "primaryBorderColor": "#7C3AED", "lineColor": "#A855F7", "secondaryColor": "#2E1065", "tertiaryColor": "#0F0F14", "edgeLabelBackground": "#18181B", "classText": "#F4F4F5", "fontFamily": "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif", "fontSize": "13px"}}}%%
```

---

## 5. Edge & Shape Semantics (Staff-Level Visual Grammar)

### Arrow Semantics
| Syntax | Visual | Architectural Meaning |
| :--- | :--- | :--- |
| `==>` | Thick solid arrow | Hot data path, primary write/commit path, or critical synchronous flow |
| `-->` | Standard solid arrow | Synchronous RPC/HTTP call, direct read/write, deterministic dependency |
| `-.->` | Dashed arrow | Asynchronous event/queue, fallback path, control-plane config push, or OTel telemetry |
| `<-->` | Bidirectional solid | Interactive control loop, bidirectional stream, or read-modify-write handshake |

### Node Shape Semantics
| Syntax | Shape | Use For |
| :--- | :--- | :--- |
| `ID["Label"]` | Sharp rectangle | Services, controllers, gateways, policy engines |
| `ID(["Label"])` | Stadium / pill | External entry points, CLI/UI triggers, event topics/queues |
| `ID[("Label")]` | Cylinder | Databases, object stores, caches, WAL ledgers, registries |
| `ID{"Label"}` | Diamond | Deterministic routing decisions, guard checks, circuit breaker branches |
| `ID[["Label"]]` | Subprocess | Reusable pipelines, shared modules, isolated sandboxes |

---

## 6. Strict Parser-Hygiene Rules (Zero Broken Renders)

1. **Double-quote all flowchart labels** (`NodeA["API Gateway\nEnvoy · mTLS"]`) and **all edge labels with punctuation** (`A -->|"gRPC · Proto v3\n(p99 < 25ms)"| B`).
2. **Use `\n` for line breaks—never HTML tags** (`<br>`, `<br/>`, `<b>`, `<i>`, `<span`, `<div`, `<font>`). `\n` inside quoted strings renders cleanly in GitHub, Obsidian, VS Code, and Antigravity without violating strict HTML-sanitizing renderers.
3. **Always give subgraphs explicit alphanumeric IDs plus quoted titles:**
   - Good: `subgraph DataPlane["2. Data Plane (Private VPC)"]`
   - Bad: `subgraph 2. Data Plane (Private VPC)`
4. **Never use Mermaid reserved keywords as node IDs:** `end`, `subgraph`, `class`, `style`, `click`, `default`, `graph`, `flowchart`, `linkStyle`, `classDef`.
5. **Keep labels scannable:** max **3–4 lines** per node (Line 1: Name, Line 2: Mechanism/Tech, Line 3: Key Invariant/SLO), and max **2 lines** per edge label.
6. **Keep flowcharts bounded:** target **8–18 nodes** (split into complementary views above ~20–22 nodes).
7. **Assign classes explicitly:** use `class NodeA,NodeB service` grouped cleanly at the bottom of the diagram (cleaner diffs and easier to audit than inline `:::service` everywhere, though both are valid).
