"""
diagram_generator.py — visually varied SVG diagrams for LinkedIn posts.

8 distinct layout styles (selected deterministically per topic so the same
topic always gets the same style, but adjacent topics look completely different):

  0  VERTICAL FLOW      — numbered step-by-step pipeline (tall nodes, arrows)
  1  MIND MAP           — central hub with radiating branches + sub-leaves
  2  PYRAMID / FUNNEL   — stacked trapezoids, widest at base
  3  TIMELINE           — horizontal spine with alternating milestone cards
  4  HEXAGON GRID       — honeycomb cells for concept clusters
  5  COMPARISON TABLE   — side-by-side matrix with coloured headers
  6  CIRCULAR ORBIT     — central circle surrounded by satellite bubbles
  7  CARD GRID          — the original style (kept as variety, not the default)
"""

import os
import math
import hashlib
import random
from datetime import datetime
from pathlib import Path

try:
    import os as _os
    _DIAGRAM_AUTHOR = _os.environ.get("AUTHOR_NAME") or _os.environ.get("GITHUB_ACTOR") or "Author"
except Exception:
    _DIAGRAM_AUTHOR = "Author"

try:
    from logger import get_logger
    log = get_logger("diagrams")
except Exception:
    class _L:
        def info(self, m): print("[diagrams]", m)
        def warning(self, m): print("[diagrams] WARN", m)
        def error(self, m): print("[diagrams] ERR", m)
    log = _L()

OUTPUT_DIR = "diagrams"

# ── Colour palettes ────────────────────────────────────────────────────────────
PALETTES = {
    "ai":       ["#7C3AED","#2563EB","#059669","#D97706","#DB2777","#0891B2"],
    "cloud":    ["#2563EB","#0891B2","#059669","#7C3AED","#D97706","#DB2777"],
    "security": ["#DC2626","#D97706","#7C3AED","#2563EB","#059669","#DB2777"],
    "data":     ["#059669","#7C3AED","#2563EB","#0891B2","#D97706","#DC2626"],
    "devops":   ["#059669","#2563EB","#7C3AED","#D97706","#DC2626","#0891B2"],
    "default":  ["#2563EB","#7C3AED","#059669","#D97706","#DC2626","#0891B2"],
}

def get_pal(tid):
    t = tid.lower()
    if any(x in t for x in ["llm","rag","agent","mlops","ai"]): pal = PALETTES["ai"]
    elif any(x in t for x in ["kube","docker","aws","cicd","cloud"]): pal = PALETTES["cloud"]
    elif any(x in t for x in ["zero","devsec","security"]): pal = PALETTES["security"]
    elif any(x in t for x in ["kafka","data","lake","lakehouse"]): pal = PALETTES["data"]
    elif any(x in t for x in ["git","devops","solid","api","cicd"]): pal = PALETTES["devops"]
    else: pal = PALETTES["default"]
    # Randomize the color order for variety
    return random.sample(pal, len(pal))

# ── Utilities ──────────────────────────────────────────────────────────────────
def xe(t): return str(t).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def clamp(text, n): text=str(text); return text if len(text)<=n else text[:n-1]+"..."

def rgba(hex_color, alpha):
    h=hex_color.lstrip("#"); r,g,b=int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
    return f"rgba({r},{g},{b},{alpha})"

def lighten(hex_color, pct=0.85):
    h=hex_color.lstrip("#"); r,g,b=int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
    r=int(r+(255-r)*pct); g=int(g+(255-g)*pct); b=int(b+(255-b)*pct)
    return f"#{r:02X}{g:02X}{b:02X}"

def darken(hex_color, pct=0.25):
    h=hex_color.lstrip("#"); r,g,b=int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
    return f"#{int(r*(1-pct)):02X}{int(g*(1-pct)):02X}{int(b*(1-pct)):02X}"

def wrap_lines(text, max_chars):
    words=text.split(); lines=[]; cur=""
    for w in words:
        if len(cur)+len(w)+1<=max_chars: cur=(cur+" "+w).strip()
        else:
            if cur: lines.append(cur)
            cur=w
    if cur: lines.append(cur)
    return lines or [""]

# ── Shared CSS animations ──────────────────────────────────────────────────────
ANIM = """<style>
  @keyframes fd{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
  @keyframes fr{0%{stroke-dashoffset:24}100%{stroke-dashoffset:0}}
  @keyframes pu{0%,100%{opacity:1}50%{opacity:0.55}}
  .fi{animation:fd .5s ease-out both}
  .flow{stroke-dasharray:8 4;animation:fr 1.4s linear infinite}
  .pu{animation:pu 2.2s ease-in-out infinite}
</style>"""

# ── Common footer / header wrapper ─────────────────────────────────────────────
def _wrap(inner_svg, W, H, title, subtitle, accent, bg_top, bg_bot, dark=False):
    dark_hdr = darken(accent, 0.55)
    mid_hdr  = darken(accent, 0.35)
    foot_bg  = lighten(accent, 0.95) if not dark else "#0D1117"
    foot_bdr = "#E2E8F0" if not dark else rgba(accent, 0.35)
    foot_txt = "#94A3B8"

    bg_rect = f'<rect width="{W}" height="{H}" fill="url(#BG)"/>'
    if not dark:
        dot_pat = (f'<pattern id="dots" width="20" height="20" patternUnits="userSpaceOnUse">'
                   f'<circle cx="1" cy="1" r="0.65" fill="{rgba(accent,0.10)}"/></pattern>'
                   f'<rect width="{W}" height="{H}" fill="url(#dots)"/>')
    else:
        dot_pat = (f'<pattern id="grid" width="26" height="26" patternUnits="userSpaceOnUse">'
                   f'<path d="M26 0 L0 0 0 26" fill="none" stroke="{rgba(accent,0.06)}" stroke-width="0.5"/></pattern>'
                   f'<rect width="{W}" height="{H}" fill="url(#grid)"/>')

    pill_w = len(subtitle)*7 + 22

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="display:block;font-family:Arial,sans-serif;overflow:hidden">
<defs>
  <linearGradient id="HG" x1="0" x2="1" y1="0" y2="0">
    <stop offset="0%" stop-color="{dark_hdr}"/>
    <stop offset="100%" stop-color="{mid_hdr}"/>
  </linearGradient>
  <linearGradient id="BG" x1="0" x2="0" y1="0" y2="1">
    <stop offset="0%" stop-color="{bg_top}"/>
    <stop offset="100%" stop-color="{bg_bot}"/>
  </linearGradient>
</defs>
{ANIM}
{bg_rect}
{dot_pat}
<rect x="0" y="0" width="{W}" height="58" fill="url(#HG)"/>
<rect x="0" y="56" width="{W}" height="2" fill="{accent}" opacity="0.7"/>
<rect x="16" y="13" width="{pill_w}" height="18" rx="9" fill="{rgba(accent,0.25)}" stroke="{rgba(accent,0.55)}" stroke-width="1"/>
<text x="28" y="25" fill="white" font-size="8" font-weight="700" letter-spacing="1.6">{xe(subtitle.upper())}</text>
<text x="{W//2}" y="40" text-anchor="middle" fill="white" font-size="20" font-weight="900" letter-spacing="-0.3">{xe(clamp(title,54))}</text>
{inner_svg}
<rect x="0" y="{H-30}" width="{W}" height="30" fill="{foot_bg}"/>
<rect x="0" y="{H-31}" width="{W}" height="1" fill="{foot_bdr}"/>
<text x="18" y="{H-11}" fill="{foot_txt}" font-size="8.5">{datetime.now().strftime("%B %Y")} · {xe(_DIAGRAM_AUTHOR)}</text>
<rect x="{W-220}" y="{H-24}" width="208" height="18" rx="9" fill="{rgba(accent,0.12)}" stroke="{accent}" stroke-width="1"/>
<text x="{W-116}" y="{H-12}" text-anchor="middle" fill="{accent}" font-size="9" font-weight="800" letter-spacing="0.5">AI · copyright {xe(_DIAGRAM_AUTHOR)}</text>
</svg>'''


# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 0 — VERTICAL FLOW  (numbered steps with animated arrows)
# ══════════════════════════════════════════════════════════════════════════════
def _style_vertical_flow(topic_id, topic_name, C):
    W, H = 900, 620
    accent = C[0]
    bg_top = lighten(accent, 0.93)
    bg_bot = lighten(accent, 0.96)

    STEP_DATA = {
        "llm": [("Tokenisation","Raw text split into sub-word tokens via BPE"),
                ("Embedding Layer","Token IDs mapped to 768-4096d dense vectors"),
                ("Transformer Blocks","Multi-head attention + feed-forward x N layers"),
                ("Layer Norm + Residuals","Stable training via skip connections"),
                ("Output Projection","Hidden state projected to vocabulary logits"),
                ("Sampling / Decoding","Top-k / Nucleus sampling selects next token")],
        "rag": [("Document Ingestion","PDF, HTML, Markdown loaded and cleaned"),
                ("Chunking + Overlap","512-token semantic chunks, 10% overlap"),
                ("Embedding","text-embed-3 encodes chunks to 1536-d vectors"),
                ("Vector Store Index","Pinecone / Weaviate ANN index for fast search"),
                ("Query + Rerank","Hybrid BM25 + dense retrieval, cross-encoder rerank"),
                ("LLM Generation","Grounded answer generated with citation sources")],
        "mlops": [("Data Validation","Schema checks, dedup, Great Expectations"),
                  ("Feature Engineering","Feast feature store, transforms, versioning"),
                  ("Distributed Training","Ray Train / Kubeflow on GPU cluster"),
                  ("Experiment Tracking","MLflow: params, metrics, artefacts logged"),
                  ("Model Registry","Versioned models with cards and approval gate"),
                  ("Serving + Monitoring","Seldon/Triton, Evidently drift detection")],
        "cicd": [("Code Commit","git push triggers pre-commit hooks and linting"),
                 ("CI Build","Compile, unit tests, SAST scan run in parallel"),
                 ("Image Build","Docker multi-stage build with layer caching"),
                 ("Security Scan","Trivy CVE scan, Snyk SCA, SBOM generation"),
                 ("Stage Deploy","Helm upgrade, smoke tests, auto-rollback ready"),
                 ("Production Release","Blue/green switch, canary traffic, feature flags")],
        "devsec": [("IDE / Pre-commit","gitleaks, detect-secrets, git-secrets hooks"),
                   ("Pull Request","Semgrep SAST, CodeQL analysis, peer review"),
                   ("Build Stage","SCA SBOM, Snyk, dependency vulnerability audit"),
                   ("Container Scan","Trivy, Docker Scout CVE check, cosign signing"),
                   ("Deploy Stage","tfsec / checkov IaC scan, OPA policy gate"),
                   ("Runtime Security","Falco eBPF alerts, SIEM, SOAR auto-remediate")],
        "kafka": [("Producers","Microservices, IoT, DB CDC events via Debezium"),
                  ("Kafka Brokers","Partitioned topics with replication factor 3"),
                  ("Schema Registry","Avro / Protobuf contract enforcement"),
                  ("Stream Processing","Apache Flink / ksqlDB stateful transforms"),
                  ("Consumer Groups","Parallel reads, offset commit management"),
                  ("Sinks","Elasticsearch, ClickHouse, S3 data lake landing")],
    }
    tid = topic_id.lower()
    key = next((k for k in STEP_DATA if k in tid), None)
    steps = STEP_DATA[key] if key else [
        ("Ingest","Collect raw inputs from all upstream sources"),
        ("Validate","Schema checks, deduplication, quality gates"),
        ("Transform","Business logic, enrichment, join operations"),
        ("Store","Persist to primary data store with indexing"),
        ("Serve","REST / GraphQL API layer with caching"),
        ("Monitor","Metrics, SLO alerts, and automated reporting"),
    ]

    BOX_W, BOX_H, ARROW_H = 500, 56, 32
    cx = W // 2
    y = 70
    svg = ""

    for i, (label, sub) in enumerate(steps):
        col = C[i % len(C)]
        bx = cx - BOX_W // 2
        bg  = lighten(col, 0.88)
        delay = f"animation-delay:{i*0.08:.2f}s"

        svg += f'<rect x="{bx+3}" y="{y+3}" width="{BOX_W}" height="{BOX_H}" rx="13" fill="{rgba(col,0.12)}"/>'
        svg += f'<rect x="{bx}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="13" fill="{bg}" stroke="{col}" stroke-width="2" class="fi" style="{delay}"/>'
        svg += f'<rect x="{bx}" y="{y}" width="6" height="{BOX_H}" rx="3" fill="{col}"/>'
        svg += f'<circle cx="{bx+32}" cy="{y+BOX_H//2}" r="14" fill="{col}"/>'
        svg += f'<text x="{bx+32}" y="{y+BOX_H//2+5}" text-anchor="middle" fill="white" font-size="13" font-weight="900">{i+1}</text>'
        svg += f'<text x="{bx+58}" y="{y+BOX_H//2-7}" fill="{darken(col,0.08)}" font-size="13" font-weight="800">{xe(label)}</text>'
        svg += f'<text x="{bx+58}" y="{y+BOX_H//2+10}" fill="#64748B" font-size="9.5">{xe(sub)}</text>'
        svg += f'<text x="{bx+BOX_W-40}" y="{y+BOX_H//2+9}" fill="{rgba(col,0.18)}" font-size="28" font-weight="900">{i+1:02d}</text>'

        if i < len(steps) - 1:
            ax = cx; ay1 = y + BOX_H; ay2 = ay1 + ARROW_H - 8
            svg += f'<line x1="{ax}" y1="{ay1}" x2="{ax}" y2="{ay2}" stroke="{col}" stroke-width="2.5" class="flow" opacity="0.8"/>'
            svg += f'<polygon points="{ax},{ay2+8} {ax-7},{ay2} {ax+7},{ay2}" fill="{col}" class="pu"/>'
        y += BOX_H + ARROW_H

    return _wrap(svg, W, H, topic_name, "Step-by-Step", accent, bg_top, bg_bot)


# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 1 — MIND MAP  (hub + branches + sub-leaves, dark theme)
# ══════════════════════════════════════════════════════════════════════════════
def _style_mind_map(topic_id, topic_name, C):
    W, H = 900, 600
    accent = C[0]
    dark_bg  = darken(accent, 0.60)
    dark_bg2 = darken(accent, 0.72)

    BRANCHES = {
        "llm": [("Attention","Multi-head self-attention","Scaled dot-product"),
                ("Training","Pre-train then RLHF","Instruction tuning"),
                ("Inference","KV-cache + batching","vLLM / TRT-LLM"),
                ("Safety","Guardrails + evals","Constitutional AI"),
                ("Context","128k+ token window","RAG extension")],
        "kube": [("Control Plane","API server + etcd","Scheduler, CM"),
                 ("Networking","CNI + Service Mesh","Ingress, DNS"),
                 ("Workloads","Deployment, SS, DS","HPA autoscaling"),
                 ("Storage","PV / PVC + CSI","StorageClass"),
                 ("Security","RBAC + NetworkPol","Pod Security Std")],
        "zero": [("Identity","IdP, MFA, PAM creds","SPIFFE/SPIRE certs"),
                 ("Policy Engine","OPA / Rego rules","ABAC + time-limits"),
                 ("Network Segs","DMZ + micro-segs","mTLS everywhere"),
                 ("Detection","SIEM + EDR + SOAR","Threat intel feeds"),
                 ("Data","DLP + encryption","Tokenization + Vault")],
        "docker": [("Images","Multi-stage builds","Distroless, Alpine"),
                   ("Runtime","containerd / runc","cgroups + namespaces"),
                   ("Networking","bridge, overlay","host and none modes"),
                   ("Compose","services + volumes","health-checks, deps"),
                   ("Security","non-root, read-only","Trivy + cosign SBOM")],
        "git": [("Branching","main + develop","feature/* + hotfix/*"),
                ("Commits","Conventional Commits","DCO + GPG signed"),
                ("PR Flow","2-reviewer gate","squash or rebase merge"),
                ("Tags","SemVer releases","CHANGELOG generation"),
                ("Hooks","pre-commit linting","Secret leak scanning")],
        "api": [("Protocols","REST + GraphQL","gRPC + WebSocket SSE"),
                ("Auth","OAuth2 + JWT","mTLS + API keys"),
                ("Gateway","Rate limit + CB","Retry + caching layer"),
                ("Versioning","URI /v2 headers","Backward compatible"),
                ("Observability","OpenTelemetry","Jaeger traces + SLOs")],
        "solid": [("S SRP","One class one job","Cohesive modules"),
                  ("O OCP","Extend not modify","Plugin architecture"),
                  ("L LSP","Substitutable types","Contract test coverage"),
                  ("I ISP","Focused interfaces","No fat interface bloat"),
                  ("D DIP","Depend on abstracts","IoC + DI containers")],
        "aws": [("Compute","EC2, Lambda, ECS","Fargate + Batch jobs"),
                ("Storage","S3, EBS, EFS","Glacier + FSx options"),
                ("Database","RDS Aurora, Dynamo","Redshift + Neptune"),
                ("Network","VPC, ALB, CF","Route 53 + Transit GW"),
                ("Security","IAM + GuardDuty","KMS + Secrets Manager")],
    }
    tid = topic_id.lower()
    key = next((k for k in BRANCHES if k in tid), None)
    branches = BRANCHES[key] if key else [
        ("Ingest","Data collection layer","APIs + streams"),
        ("Process","Transform and enrich","Spark + dbt"),
        ("Store","Persist and index","PostgreSQL + S3"),
        ("Serve","APIs and dashboards","REST + Grafana"),
        ("Govern","Quality and lineage","Catalog + policies"),
    ]

    cx, cy = W // 2, H // 2 + 10
    r_hub = 68
    svg = ""

    svg += f'<circle cx="{cx}" cy="{cy}" r="{r_hub+6}" fill="{rgba(accent,0.15)}" class="pu"/>'
    svg += f'<circle cx="{cx}" cy="{cy}" r="{r_hub}" fill="{darken(accent,0.45)}"/>'
    svg += f'<circle cx="{cx}" cy="{cy}" r="{r_hub-4}" fill="{darken(accent,0.55)}" stroke="{lighten(accent,0.4)}" stroke-width="1.5"/>'

    words = topic_name.replace("&","and").split()
    mid = len(words) // 2
    line1 = " ".join(words[:mid]) or topic_name[:14]
    line2 = " ".join(words[mid:]) or ""
    svg += f'<text x="{cx}" y="{cy-6}" text-anchor="middle" fill="white" font-size="13" font-weight="900">{xe(clamp(line1,14))}</text>'
    if line2:
        svg += f'<text x="{cx}" y="{cy+12}" text-anchor="middle" fill="{lighten(accent,0.6)}" font-size="12" font-weight="700">{xe(clamp(line2,14))}</text>'

    n = len(branches)
    for i, (bname, bdesc, bsub) in enumerate(branches):
        angle_deg = -90 + i * (360 / n)
        angle_rad = math.radians(angle_deg)
        col = C[i % len(C)]

        R_branch = 195
        bx = cx + R_branch * math.cos(angle_rad)
        by = cy + R_branch * math.sin(angle_rad)

        start_x = cx + r_hub * math.cos(angle_rad)
        start_y = cy + r_hub * math.sin(angle_rad)
        svg += (f'<path d="M{start_x:.1f},{start_y:.1f} '
                f'Q{(cx+bx)/2:.1f},{(cy+by)/2:.1f} {bx:.1f},{by:.1f}" '
                f'fill="none" stroke="{col}" stroke-width="2.5" stroke-dasharray="6 3" class="flow" '
                f'style="animation-delay:{i*0.15:.2f}s"/>')

        br = 46
        svg += f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{br+3}" fill="{rgba(col,0.12)}"/>'
        svg += f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{br}" fill="{darken(col,0.50)}" stroke="{col}" stroke-width="2" class="fi" style="animation-delay:{i*0.1:.2f}s"/>'
        svg += f'<text x="{bx:.1f}" y="{by-7:.1f}" text-anchor="middle" fill="white" font-size="10" font-weight="800">{xe(clamp(bname,13))}</text>'
        svg += f'<text x="{bx:.1f}" y="{by+8:.1f}" text-anchor="middle" fill="{lighten(col,0.55)}" font-size="8">{xe(clamp(bdesc,16))}</text>'

        R_leaf = 308
        lx = cx + R_leaf * math.cos(angle_rad)
        ly = cy + R_leaf * math.sin(angle_rad)
        svg += (f'<line x1="{bx+br*math.cos(angle_rad):.1f}" y1="{by+br*math.sin(angle_rad):.1f}" '
                f'x2="{lx:.1f}" y2="{ly:.1f}" stroke="{rgba(col,0.5)}" stroke-width="1.5" stroke-dasharray="4 3"/>')
        lw, lh = 110, 28
        svg += f'<rect x="{lx-lw//2:.1f}" y="{ly-lh//2:.1f}" width="{lw}" height="{lh}" rx="14" fill="{darken(col,0.55)}" stroke="{lighten(col,0.3)}" stroke-width="1" class="fi" style="animation-delay:{i*0.1+0.2:.2f}s"/>'
        svg += f'<text x="{lx:.1f}" y="{ly+4:.1f}" text-anchor="middle" fill="{lighten(col,0.65)}" font-size="8.5" font-weight="700">{xe(clamp(bsub,16))}</text>'

    return _wrap(svg, W, H, topic_name, "Concept Map", accent, dark_bg2, dark_bg, dark=True)


# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 2 — PYRAMID  (stacked trapezoids, narrow at top)
# ══════════════════════════════════════════════════════════════════════════════
def _style_pyramid(topic_id, topic_name, C):
    W, H = 900, 600
    accent = C[0]
    bg_top = lighten(accent, 0.91)
    bg_bot = lighten(accent, 0.95)

    LAYERS = {
        "solid": [
            ("Maintainability","Clean, readable, easily refactorable code"),
            ("Testability","SOLID design makes unit testing natural"),
            ("Extensibility","Add features without touching existing code"),
            ("Scalability","Teams can grow without merge conflicts"),
            ("Business Value","Ship faster, break less, adapt quicker"),
        ],
        "zero": [
            ("Data Encryption","AES-256 at rest + TLS 1.3 in transit"),
            ("Data Classification","PII, confidential, public labelling"),
            ("Micro-segmentation","East-west mTLS between all services"),
            ("Identity and Access","Zero standing privileges, JIT access"),
            ("Culture and Process","Security-first mindset, DevSecOps"),
        ],
        "mlops": [
            ("Raw Data","Unstructured ingestion with no schema enforcement"),
            ("Curated Data","Validated, deduplicated, and properly labelled"),
            ("Feature Layer","Engineered and versioned in a feature store"),
            ("Model Registry","Trained, evaluated, and version-controlled"),
            ("Production","Served, monitored, retrained on data drift"),
        ],
        "kube": [
            ("Infrastructure","VMs, bare metal, or managed cloud nodes"),
            ("Container Runtime","containerd managing cgroups and namespaces"),
            ("Cluster Layer","Control plane, etcd, and the API server"),
            ("Platform Layer","Ingress, service mesh, and storage classes"),
            ("Application Layer","Your deployments, stateful sets, and jobs"),
        ],
        "api": [
            ("Transport","TCP over TLS — HTTP 1.1, HTTP/2, HTTP/3"),
            ("Protocol","REST, GraphQL, gRPC, WebSocket, SSE"),
            ("Security","OAuth2, JWT, mTLS, rate limiting, WAF"),
            ("Gateway","Routing, circuit breaker, cache, retry"),
            ("Business Logic","Domain services and orchestration layer"),
        ],
        "aws": [
            ("Physical","Data centres, AZs, regions, and edge PoPs"),
            ("Network","VPC, subnets, Transit GW, Direct Connect"),
            ("Compute","EC2, Lambda, ECS/EKS, Fargate workloads"),
            ("Platform Services","RDS, DynamoDB, S3, SQS, ElastiCache"),
            ("Application Layer","Your services, APIs, and business logic"),
        ],
    }
    tid = topic_id.lower()
    key = next((k for k in LAYERS if k in tid), None)
    layers = LAYERS[key] if key else [
        ("Foundation","Core infrastructure and platform services"),
        ("Data Layer","Storage, caching, and streaming systems"),
        ("Service Layer","Business logic and API endpoints"),
        ("Integration","Third-party services, messaging, and events"),
        ("User / Client","Web, mobile, and CLI consumers"),
    ]

    n = len(layers)
    pad_top = 75
    available_h = H - pad_top - 55
    layer_h = available_h // n
    max_w = W - 70
    min_w = 200

    svg = ""
    for i, (label, desc) in enumerate(layers):
        col = C[i % len(C)]
        ratio_top = (i / n)
        ratio_bot = ((i + 1) / n)
        w_top = int(min_w + (max_w - min_w) * ratio_top)
        w_bot = int(min_w + (max_w - min_w) * ratio_bot)
        x_top = (W - w_top) // 2
        x_bot = (W - w_bot) // 2
        y_top = pad_top + i * layer_h
        y_bot = y_top + layer_h - 3
        cx_row = W // 2

        pts = f"{x_top},{y_top} {x_top+w_top},{y_top} {x_bot+w_bot},{y_bot} {x_bot},{y_bot}"
        svg += f'<polygon points="{pts}" fill="{lighten(col,0.82)}" stroke="{col}" stroke-width="1.8" class="fi" style="animation-delay:{i*0.09:.2f}s"/>'
        svg += f'<polygon points="{x_top},{y_top} {x_top+8},{y_top} {x_bot+8},{y_bot} {x_bot},{y_bot}" fill="{col}"/>'

        ny = (y_top + y_bot) // 2
        svg += f'<circle cx="{x_top+26}" cy="{ny}" r="13" fill="{col}"/>'
        svg += f'<text x="{x_top+26}" y="{ny+5}" text-anchor="middle" fill="white" font-size="12" font-weight="900">{n-i}</text>'
        svg += f'<text x="{cx_row}" y="{ny-5}" text-anchor="middle" fill="{darken(col,0.10)}" font-size="13" font-weight="800">{xe(label)}</text>'
        svg += f'<text x="{cx_row}" y="{ny+12}" text-anchor="middle" fill="#475569" font-size="9.5">{xe(desc)}</text>'

    return _wrap(svg, W, H, topic_name, "Pyramid Model", accent, bg_top, bg_bot)


# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 3 — TIMELINE  (horizontal spine, cards alternate above/below)
# ══════════════════════════════════════════════════════════════════════════════
def _style_timeline(topic_id, topic_name, C):
    W, H = 900, 560
    accent = C[0]
    dark_bg  = darken(accent, 0.58)
    dark_bg2 = darken(accent, 0.72)

    MILESTONES = {
        "cicd": [("2004","CruiseControl","First CI server, polling SVN"),
                 ("2011","Jenkins","Open-source CI king, 1000+ plugins"),
                 ("2016","GitLab CI","Pipeline-as-code era begins"),
                 ("2018","GitHub Actions","YAML workflows + marketplace"),
                 ("2021","DORA Metrics","Measuring DevOps performance"),
                 ("2024","AI-Assisted CI","LLM test gen + PR review bots"),
                 ("2026","Autonomous CD","Self-healing auto-rollback agents")],
        "llm": [("2017","Transformer","Attention is All You Need paper"),
                ("2018","BERT + GPT","Bidirectional and generative"),
                ("2020","GPT-3","175B params, few-shot learning"),
                ("2022","InstructGPT","RLHF alignment, ChatGPT launch"),
                ("2023","Llama + Claude","Open weights, constitutional AI"),
                ("2024","MoE Models","GPT-4, Mixtral sparse routing"),
                ("2026","Agentic LLMs","Tool use, MCP, long context")],
        "docker": [("2013","Docker 0.1","LXC wrapper for dev-to-prod parity"),
                   ("2015","Compose","Multi-container local dev stacks"),
                   ("2016","Swarm","Native clustering, declarative YAML"),
                   ("2017","K8s wins","K8s standard, Docker as runtime"),
                   ("2020","containerd","CNCF grad, OCI compliant runtime"),
                   ("2022","BuildKit","Layer cache, multi-arch, SBOM"),
                   ("2025","Wasm + Docker","WebAssembly runtime alternative")],
        "kube": [("2014","K8s v0.1","Google open-sources Borg successor"),
                 ("2016","K8s 1.4","Helm charts, RBAC, StatefulSets"),
                 ("2018","CNCF Grad","Production ready, major cloud support"),
                 ("2020","K8s 1.18","Topology spread, sidecar containers"),
                 ("2022","Gateway API","Ingress v2 with traffic policies"),
                 ("2024","K8s 1.30","In-place pod resize, custom schedulers"),
                 ("2026","AI Workloads","GPU pooling, MIG, KubeAI operators")],
        "kafka": [("2011","Kafka 0.7","LinkedIn open-source pub-sub log"),
                  ("2014","Kafka 0.9","Consumer groups + security + replication"),
                  ("2016","Kafka Streams","Native stream processing library"),
                  ("2018","ksqlDB","SQL interface for event streaming"),
                  ("2021","KRaft Mode","ZooKeeper-free faster failover"),
                  ("2023","Tiered Storage","S3-backed log, infinite retention"),
                  ("2025","Kafka 4.0","KRaft GA, 2M msg/s per broker")],
    }
    tid = topic_id.lower()
    key = next((k for k in MILESTONES if k in tid), None)
    milestones = MILESTONES[key] if key else [
        ("Phase 1","Foundation","Core infrastructure established"),
        ("Phase 2","Build","Services and APIs developed"),
        ("Phase 3","Integrate","Systems connected, data flowing"),
        ("Phase 4","Test","Load testing and security scans"),
        ("Phase 5","Deploy","Staged rollout to production"),
        ("Phase 6","Operate","Monitor, alert, and improve"),
        ("Phase 7","Scale","Optimise and grow capacity"),
    ]

    svg = ""
    n = len(milestones)
    spine_y = H // 2 - 10
    pad = 55
    span_w = W - pad * 2
    step = span_w // (n - 1)

    svg += f'<line x1="{pad}" y1="{spine_y}" x2="{W-pad}" y2="{spine_y}" stroke="{lighten(accent,0.3)}" stroke-width="3" class="flow"/>'

    for i, (year, title, desc) in enumerate(milestones):
        col = C[i % len(C)]
        mx = pad + i * step
        above = (i % 2 == 0)

        card_h = 88
        card_w = min(step - 8, 115)
        cy_card = spine_y - card_h - 38 if above else spine_y + 38

        delay = f"animation-delay:{i*0.09:.2f}s"
        stem_y1 = spine_y - 12 if above else spine_y + 12
        stem_y2 = cy_card + card_h if above else cy_card
        svg += f'<line x1="{mx}" y1="{stem_y1}" x2="{mx}" y2="{stem_y2}" stroke="{col}" stroke-width="2" stroke-dasharray="4 2"/>'

        svg += f'<circle cx="{mx}" cy="{spine_y}" r="10" fill="{dark_bg2}" stroke="{col}" stroke-width="2.5" class="pu"/>'
        svg += f'<circle cx="{mx}" cy="{spine_y}" r="5" fill="{col}"/>'

        svg += f'<rect x="{mx-card_w//2}" y="{cy_card}" width="{card_w}" height="{card_h}" rx="10" fill="{darken(col,0.52)}" stroke="{lighten(col,0.28)}" stroke-width="1.5" class="fi" style="{delay}"/>'
        svg += f'<rect x="{mx-card_w//2}" y="{cy_card}" width="{card_w}" height="4" rx="2" fill="{col}"/>'
        svg += f'<text x="{mx}" y="{cy_card+18}" text-anchor="middle" fill="{col}" font-size="9" font-weight="900">{xe(year)}</text>'
        svg += f'<text x="{mx}" y="{cy_card+34}" text-anchor="middle" fill="white" font-size="9.5" font-weight="800">{xe(clamp(title,13))}</text>'
        lines = wrap_lines(desc, card_w // 5)
        for j, ln in enumerate(lines[:3]):
            svg += f'<text x="{mx}" y="{cy_card+50+j*12}" text-anchor="middle" fill="{lighten(col,0.45)}" font-size="7.5">{xe(ln)}</text>'

    return _wrap(svg, W, H, topic_name, "Evolution Timeline", accent, dark_bg2, dark_bg, dark=True)


# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 4 — HEXAGON GRID  (honeycomb concept cells, dark theme)
# ══════════════════════════════════════════════════════════════════════════════
def _style_hexagon(topic_id, topic_name, C):
    W, H = 900, 600
    accent = C[0]
    dark_bg  = darken(accent, 0.62)
    dark_bg2 = darken(accent, 0.74)

    HEXES = {
        "llm": [("GPT-4o",C[0]),("Claude 3.5",C[1]),("Gemini 1.5",C[2]),
                ("Llama 3.1",C[3]),("Mistral",C[4]),("Qwen 2.5",C[5]),
                ("Attention",C[0]),("RLHF",C[1]),("KV Cache",C[2]),
                ("LoRA",C[3]),("MoE",C[4]),("RAG",C[5]),
                ("Embeddings",C[0]),("Tokenizer",C[1]),("Safety",C[2])],
        "kube": [("Pod",C[0]),("Deployment",C[1]),("StatefulSet",C[2]),
                 ("DaemonSet",C[3]),("Service",C[4]),("Ingress",C[5]),
                 ("HPA",C[0]),("PVC",C[1]),("ConfigMap",C[2]),
                 ("Secret",C[3]),("RBAC",C[4]),("NetworkPol",C[5]),
                 ("Helm",C[0]),("Operator",C[1]),("etcd",C[2])],
        "aws": [("EC2",C[0]),("Lambda",C[1]),("ECS",C[2]),
                ("S3",C[3]),("RDS",C[4]),("DynamoDB",C[5]),
                ("VPC",C[0]),("ALB",C[1]),("CloudFront",C[2]),
                ("IAM",C[3]),("KMS",C[4]),("GuardDuty",C[5]),
                ("SQS",C[0]),("SNS",C[1]),("Route 53",C[2])],
        "docker": [("FROM",C[0]),("RUN",C[1]),("COPY",C[2]),
                   ("ENV",C[3]),("EXPOSE",C[4]),("CMD",C[5]),
                   ("ENTRYPOINT",C[0]),("VOLUME",C[1]),("ARG",C[2]),
                   ("HEALTHCHECK",C[3]),("USER",C[4]),("WORKDIR",C[5]),
                   ("Multi-stage",C[0]),("BuildKit",C[1]),("Compose",C[2])],
        "solid": [("SRP",C[0]),("OCP",C[1]),("LSP",C[2]),
                  ("ISP",C[3]),("DIP",C[4]),("Factory",C[5]),
                  ("Strategy",C[0]),("Observer",C[1]),("Decorator",C[2]),
                  ("Repository",C[3]),("Command",C[4]),("Facade",C[5]),
                  ("Adapter",C[0]),("DRY",C[1]),("YAGNI",C[2])],
        "kafka": [("Producer",C[0]),("Consumer",C[1]),("Broker",C[2]),
                  ("Topic",C[3]),("Partition",C[4]),("Offset",C[5]),
                  ("Consumer Grp",C[0]),("Schema Reg",C[1]),("KRaft",C[2]),
                  ("Flink",C[3]),("ksqlDB",C[4]),("Streams",C[5]),
                  ("Dead Letter",C[0]),("Compaction",C[1]),("Tiered",C[2])],
    }
    tid = topic_id.lower()
    key = next((k for k in HEXES if k in tid), None)
    hexes = HEXES[key] if key else [
        ("Ingest",C[0]),("Process",C[1]),("Store",C[2]),
        ("Cache",C[3]),("Serve",C[4]),("Monitor",C[5]),
        ("Alert",C[0]),("Scale",C[1]),("Deploy",C[2]),
        ("Test",C[3]),("Secure",C[4]),("Govern",C[5]),
        ("Observe",C[0]),("Optimise",C[1]),("Recover",C[2]),
    ]

    def hex_points(cx, cy, r):
        pts = []
        for k in range(6):
            a = math.radians(60 * k - 30)
            pts.append(f"{cx+r*math.cos(a):.1f},{cy+r*math.sin(a):.1f}")
        return " ".join(pts)

    R = 52
    rows_layout = [4, 5, 4, 2]
    start_y = 75
    row_h = R * 1.72

    svg = ""
    idx = 0
    for row, n_cols in enumerate(rows_layout):
        offset_x = (W - (n_cols * R * 1.73)) / 2 + R
        cy_row = start_y + row * row_h + (R * 0.86 if row % 2 else 0)
        for col in range(n_cols):
            if idx >= len(hexes): break
            label, col_hex = hexes[idx]
            hx = offset_x + col * R * 1.73 + (R * 0.865 if row % 2 else 0)

            delay = f"animation-delay:{idx*0.04:.2f}s"
            pts = hex_points(hx, cy_row, R - 2)
            inner_pts = hex_points(hx, cy_row, R - 6)

            svg += f'<polygon points="{pts}" fill="{darken(col_hex,0.55)}" stroke="{lighten(col_hex,0.3)}" stroke-width="1.8" class="fi" style="{delay}"/>'
            svg += f'<polygon points="{inner_pts}" fill="{darken(col_hex,0.62)}" opacity="0.6"/>'

            lines = wrap_lines(label, 9)
            base_y = cy_row - (len(lines)-1)*7
            for li, ln in enumerate(lines):
                svg += f'<text x="{hx:.1f}" y="{base_y+li*14:.1f}" text-anchor="middle" fill="white" font-size="9.5" font-weight="800">{xe(ln)}</text>'
            idx += 1

    return _wrap(svg, W, H, topic_name, "Concept Grid", accent, dark_bg2, dark_bg, dark=True)


# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 5 — COMPARISON TABLE  (side-by-side matrix)
# ══════════════════════════════════════════════════════════════════════════════
def _style_comparison(topic_id, topic_name, C):
    W, H = 900, 580
    accent = C[0]
    bg_top = lighten(accent, 0.90)
    bg_bot = lighten(accent, 0.94)

    TABLES = {
        "kafka": {
            "cols": ["Kafka","RabbitMQ","Redis Streams","Kinesis","Pulsar"],
            "rows": [
                ("Throughput",    ["Millions/s","100k/s","500k/s","1M/s","1M/s"]),
                ("Retention",     ["Configurable","Queue-depth","Memory/disk","7 days","Infinite"]),
                ("Ordering",      ["Per-partition","Per-queue","Per-stream","Per-shard","Per-partition"]),
                ("Replay",        ["Yes","No","Yes","Yes","Yes"]),
                ("Geo-replicate", ["MirrorMaker2","Shovel","Manual","Built-in","Built-in"]),
                ("Best For",      ["Event stream","Task queue","Low-latency","AWS-native","Multi-tenant"]),
            ],
        },
        "rag": {
            "cols": ["RAG","Fine-tuning","Full Training","Prompt Eng.","Hybrid"],
            "rows": [
                ("Cost",          ["Low","Medium","Very High","Zero","Medium"]),
                ("Freshness",     ["Real-time","Static","Static","Static","Real-time"]),
                ("Accuracy",      ["High","High","Highest","Moderate","Highest"]),
                ("Setup time",    ["Days","Weeks","Months","Hours","Weeks"]),
                ("Hallucination", ["Low","Medium","Low","High","Low"]),
                ("Best For",      ["Live data","Domain adapt","Novel tasks","Quick tests","Production"]),
            ],
        },
        "docker": {
            "cols": ["Docker","Podman","containerd","LXC","Wasm"],
            "rows": [
                ("Daemon",        ["Yes","No (rootless)","Yes","Yes","No"]),
                ("Compose",       ["Native","Compatible","No","No","Partial"]),
                ("K8s runtime",   ["Deprecated","via CRI","Default","No","Emerging"]),
                ("Root required", ["Optional","No","Yes","Yes","No"]),
                ("Image format",  ["OCI","OCI","OCI","LXD","WASI"]),
                ("Best For",      ["Dev teams","Security","Production","VMs","Edge"]),
            ],
        },
        "api": {
            "cols": ["REST","GraphQL","gRPC","WebSocket","AsyncAPI"],
            "rows": [
                ("Payload",       ["JSON","JSON","Protobuf","Binary/text","JSON/Avro"]),
                ("Streaming",     ["Limited","Subscriptions","Bi-direct","Native","Native"]),
                ("Type safety",   ["OpenAPI","Schema","Proto IDL","None","AsyncAPI spec"]),
                ("Caching",       ["HTTP native","Hard","No","No","No"]),
                ("Browser supp.", ["Yes","Yes","gRPC-web","Yes","Partial"]),
                ("Best For",      ["Public APIs","Flexible UI","Internal svcs","Real-time","Event-driven"]),
            ],
        },
        "kube": {
            "cols": ["K8s","Swarm","Nomad","Mesos","ECS"],
            "rows": [
                ("Complexity",    ["High","Low","Medium","Very High","Low"]),
                ("Auto-scaling",  ["HPA + VPA","Limited","Yes","Yes","Yes"]),
                ("Multi-cloud",   ["Yes","Partial","Yes","Yes","AWS only"]),
                ("Ecosystem",     ["Huge","Small","Growing","Declining","AWS-native"]),
                ("Stateful wkld", ["StatefulSet","Volumes","Yes","Yes","EFS"]),
                ("Best For",      ["Any scale","Small teams","Multi-runtime","Legacy","AWS shops"]),
            ],
        },
    }
    tid = topic_id.lower()
    key = next((k for k in TABLES if k in tid), None)
    if key:
        data = TABLES[key]
        cols = data["cols"]
        rows = data["rows"]
    else:
        cols = ["Option A","Option B","Option C","Option D"]
        rows = [
            ("Performance",  ["High","Medium","Very High","Medium"]),
            ("Complexity",   ["Low","Medium","High","Low"]),
            ("Cost",         ["Free","Paid","Enterprise","OSS"]),
            ("Scalability",  ["Linear","Limited","Excellent","Good"]),
            ("Maturity",     ["Stable","Beta","Stable","Stable"]),
            ("Best For",     ["Dev","Prototyping","Production","Edge"]),
        ]

    n_cols = len(cols)
    n_rows = len(rows)
    pad = 20
    label_w = 130
    avail_w = W - pad * 2 - label_w
    col_w = avail_w // n_cols
    row_h = min(56, (H - 130) // (n_rows + 1))
    tbl_x = pad
    tbl_y = 72

    svg = ""
    for ci, col_name in enumerate(cols):
        col_color = C[ci % len(C)]
        hx = tbl_x + label_w + ci * col_w
        svg += f'<rect x="{hx}" y="{tbl_y}" width="{col_w-2}" height="{row_h}" rx="8" fill="{col_color}" class="fi" style="animation-delay:{ci*0.07:.2f}s"/>'
        svg += f'<text x="{hx+col_w//2-1}" y="{tbl_y+row_h//2+5}" text-anchor="middle" fill="white" font-size="10" font-weight="800">{xe(clamp(col_name,11))}</text>'

    svg += f'<rect x="{tbl_x}" y="{tbl_y}" width="{label_w-4}" height="{row_h}" rx="8" fill="{darken(accent,0.35)}"/>'
    svg += f'<text x="{tbl_x+label_w//2}" y="{tbl_y+row_h//2+5}" text-anchor="middle" fill="white" font-size="9" font-weight="700">Feature</text>'

    for ri, (row_label, values) in enumerate(rows):
        ry = tbl_y + (ri + 1) * row_h
        bg = lighten(accent, 0.93) if ri % 2 == 0 else "white"

        svg += f'<rect x="{tbl_x}" y="{ry}" width="{label_w-4}" height="{row_h-1}" fill="{lighten(accent,0.80)}"/>'
        svg += f'<text x="{tbl_x+10}" y="{ry+row_h//2+4}" fill="{darken(accent,0.15)}" font-size="9.5" font-weight="700">{xe(row_label)}</text>'

        for ci, val in enumerate(values[:n_cols]):
            col_color = C[ci % len(C)]
            cx2 = tbl_x + label_w + ci * col_w
            svg += f'<rect x="{cx2}" y="{ry}" width="{col_w-2}" height="{row_h-1}" fill="{bg}"/>'
            is_yes = val.lower() in ["yes","native","built-in","yes (rootless)"]
            is_no  = val.lower() in ["no","deprecated","partial"]
            fill_c = "#059669" if is_yes else ("#DC2626" if is_no else darken(col_color, 0.05))
            svg += f'<text x="{cx2+col_w//2-1}" y="{ry+row_h//2+4}" text-anchor="middle" fill="{fill_c}" font-size="9" font-weight="600">{xe(clamp(val,13))}</text>'

    tbl_h = (n_rows + 1) * row_h
    tbl_w = label_w + n_cols * col_w - 2
    svg += f'<rect x="{tbl_x}" y="{tbl_y}" width="{tbl_w}" height="{tbl_h}" rx="8" fill="none" stroke="{lighten(accent,0.5)}" stroke-width="1.5"/>'

    return _wrap(svg, W, H, topic_name, "Comparison Matrix", accent, bg_top, bg_bot)


# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 6 — CIRCULAR ORBIT  (central hub + inner + outer satellites)
# ══════════════════════════════════════════════════════════════════════════════
def _style_orbit(topic_id, topic_name, C):
    W, H = 900, 600
    accent = C[0]
    dark_bg  = darken(accent, 0.62)
    dark_bg2 = darken(accent, 0.74)

    ORBITS = {
        "system": {
            "center": ("System\nDesign","Scale to millions"),
            "inner": [("Load\nBalancer","Layer-7 routing",C[1]),
                      ("API\nGateway","Rate limit + auth",C[2]),
                      ("Cache","Redis + CDN edge",C[3]),
                      ("Database","PostgreSQL replica",C[4]),
                      ("Queue","Kafka + SQS",C[5])],
            "outer": [("CDN","Edge delivery"),("Auth","JWT / OAuth2"),
                      ("Search","Elasticsearch"),("Blob","S3 / GCS"),
                      ("Monitor","Prometheus"),("Tracing","Jaeger"),
                      ("Alerting","PagerDuty"),("CI/CD","GitHub Actions")],
        },
        "mlops": {
            "center": ("MLOps\nPlatform","Train to production"),
            "inner": [("Data\nPipeline","ETL + features",C[1]),
                      ("Training","GPU cluster",C[2]),
                      ("Registry","Model versions",C[3]),
                      ("Serving","Seldon / Triton",C[4]),
                      ("Monitor","Drift detection",C[5])],
            "outer": [("Feature Store","Feast / Tecton"),("MLflow","Experiments"),
                      ("DVC","Data versioning"),("Kubeflow","Pipelines"),
                      ("Evidently","Drift alerts"),("RLHF","Feedback loop"),
                      ("A/B Test","Champ/challenger"),("Grafana","Dashboards")],
        },
        "aws": {
            "center": ("AWS\nCloud","Global infrastructure"),
            "inner": [("Compute","EC2 / Lambda / ECS",C[1]),
                      ("Storage","S3 / EFS / EBS",C[2]),
                      ("Database","RDS / DynamoDB",C[3]),
                      ("Network","VPC / ALB / CF",C[4]),
                      ("Security","IAM / KMS / GD",C[5])],
            "outer": [("Route 53","DNS"),("CloudFront","CDN"),
                      ("SQS / SNS","Messaging"),("ElastiCache","Redis"),
                      ("Redshift","Analytics"),("Glue","ETL"),
                      ("Bedrock","AI / ML"),("CloudWatch","Observability")],
        },
        "zero": {
            "center": ("Zero\nTrust","Never trust,\nalways verify"),
            "inner": [("Identity","IdP + MFA + PAM",C[1]),
                      ("Policy","OPA + ABAC rules",C[2]),
                      ("Network","mTLS + micro-seg",C[3]),
                      ("Device","Posture checks",C[4]),
                      ("Data","DLP + encryption",C[5])],
            "outer": [("SPIFFE","Workload ID"),("FIDO2","Passwordless"),
                      ("SIEM","Log analysis"),("SOAR","Auto-remediate"),
                      ("EDR","Endpoint detect"),("Deception","Honeypots"),
                      ("Vault","Secrets mgmt"),("PKI","Cert authority")],
        },
        "agent": {
            "center": ("AI\nAgents","Autonomous systems"),
            "inner": [("Planner","Decompose goals",C[1]),
                      ("Tool Use","Function calls",C[2]),
                      ("Memory","Short + long term",C[3]),
                      ("Critic","Self-reflection",C[4]),
                      ("Router","Skill selection",C[5])],
            "outer": [("LangGraph","Orchestration"),("AutoGen","Multi-agent"),
                      ("MCP","Tool protocol"),("Vector DB","Memory store"),
                      ("Web Search","Real-time data"),("Code Exec","Sandbox"),
                      ("Human Loop","Approval gate"),("Observ.","LangSmith")],
        },
    }
    tid = topic_id.lower()
    key = next((k for k in ORBITS if k in tid), "system")
    orb = ORBITS.get(key, ORBITS["system"])
    center_label, center_sub = orb["center"]
    inner = orb["inner"]
    outer = orb["outer"]

    cx, cy = W // 2, H // 2 + 5
    svg = ""

    svg += f'<circle cx="{cx}" cy="{cy}" r="160" fill="none" stroke="{rgba(accent,0.12)}" stroke-width="1" stroke-dasharray="5 4"/>'
    svg += f'<circle cx="{cx}" cy="{cy}" r="268" fill="none" stroke="{rgba(accent,0.07)}" stroke-width="1" stroke-dasharray="3 5"/>'

    svg += f'<circle cx="{cx}" cy="{cy}" r="66" fill="{rgba(accent,0.15)}" class="pu"/>'
    svg += f'<circle cx="{cx}" cy="{cy}" r="62" fill="{darken(accent,0.50)}" stroke="{lighten(accent,0.3)}" stroke-width="2"/>'
    for li, ln in enumerate(center_label.split("\n")):
        svg += f'<text x="{cx}" y="{cy-8+li*17}" text-anchor="middle" fill="white" font-size="13" font-weight="900">{xe(ln)}</text>'
    for li2, ln2 in enumerate(center_sub.split("\n")):
        svg += f'<text x="{cx}" y="{cy+22+li2*12}" text-anchor="middle" fill="{lighten(accent,0.55)}" font-size="8.5">{xe(ln2)}</text>'

    n_inner = len(inner)
    for i, (label, sub, col) in enumerate(inner):
        a = math.radians(-90 + i * 360 / n_inner)
        R_inner = 158
        sx = cx + R_inner * math.cos(a)
        sy = cy + R_inner * math.sin(a)

        svg += (f'<line x1="{cx+63*math.cos(a):.1f}" y1="{cy+63*math.sin(a):.1f}" '
                f'x2="{sx-38*math.cos(a):.1f}" y2="{sy-38*math.sin(a):.1f}" '
                f'stroke="{col}" stroke-width="1.8" stroke-dasharray="5 3" class="flow" style="animation-delay:{i*0.12:.2f}s"/>')

        r_sat = 38
        svg += f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{r_sat}" fill="{darken(col,0.52)}" stroke="{col}" stroke-width="2" class="fi" style="animation-delay:{i*0.1:.2f}s"/>'
        for li, ln in enumerate(label.split("\n")):
            svg += f'<text x="{sx:.1f}" y="{sy-5+li*13:.1f}" text-anchor="middle" fill="white" font-size="9" font-weight="800">{xe(clamp(ln,10))}</text>'
        svg += f'<text x="{sx:.1f}" y="{sy+23:.1f}" text-anchor="middle" fill="{lighten(col,0.45)}" font-size="7.5">{xe(clamp(sub,14))}</text>'

    n_outer = len(outer)
    for i, (label, sub) in enumerate(outer):
        a = math.radians(-90 + i * 360 / n_outer)
        R_outer = 268
        ox = cx + R_outer * math.cos(a)
        oy = cy + R_outer * math.sin(a)
        col = C[i % len(C)]
        w_pill, h_pill = 82, 26
        svg += f'<rect x="{ox-w_pill//2:.1f}" y="{oy-h_pill//2:.1f}" width="{w_pill}" height="{h_pill}" rx="13" fill="{darken(col,0.55)}" stroke="{lighten(col,0.28)}" stroke-width="1.2" class="fi" style="animation-delay:{i*0.06:.2f}s"/>'
        svg += f'<text x="{ox:.1f}" y="{oy-2:.1f}" text-anchor="middle" fill="white" font-size="8.5" font-weight="800">{xe(label)}</text>'
        svg += f'<text x="{ox:.1f}" y="{oy+10:.1f}" text-anchor="middle" fill="{lighten(col,0.45)}" font-size="7">{xe(sub)}</text>'

    return _wrap(svg, W, H, topic_name, "Ecosystem Map", accent, dark_bg2, dark_bg, dark=True)


# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 7 — CARD GRID  (grouped cards, light theme)
# ══════════════════════════════════════════════════════════════════════════════
def _style_card_grid(topic_id, topic_name, C):
    W, H = 900, 580
    accent = C[0]
    bg_top = lighten(accent, 0.91)
    bg_bot = lighten(accent, 0.95)
    P = 18

    CARDS = {
        "system": [("Client Layer",["Browser","Mobile","Desktop","IoT"],C[0]),
                   ("Edge + Auth",["CDN","Load Balancer","API Gateway","WAF"],C[1]),
                   ("Microservices",["User Svc","Order Svc","Payment","Notifs"],C[2]),
                   ("Messaging",["Kafka","RabbitMQ","Redis PubSub","SQS"],C[3]),
                   ("Data Layer",["PostgreSQL","Redis","MongoDB","S3"],C[4]),
                   ("Observability",["Prometheus","Grafana","Jaeger","PagerDuty"],C[5])],
        "llm": [("Foundation Models",["GPT-4o","Claude 3.5","Gemini","Llama 3.1"],C[0]),
                ("Context + RAG",["Vector DB","Chunking","Embeddings","Reranker"],C[1]),
                ("Agent Layer",["ReAct Loop","Tool Use","Memory","Planner"],C[2]),
                ("Serving",["vLLM","TRT-LLM","Batching","KV Cache"],C[3]),
                ("Guardrails",["PII Filter","Toxic Check","RAGAS","LangSmith"],C[4]),
                ("Infra",["GPU cluster","Kubernetes","Prometheus","Cost track"],C[5])],
        "kube": [("Control Plane",["API Server","Scheduler","etcd","Controller Mgr"],C[0]),
                 ("Worker Nodes",["Kubelet","kube-proxy","containerd","CNI"],C[1]),
                 ("Workloads",["Deployment","StatefulSet","DaemonSet","CronJob"],C[2]),
                 ("Networking",["Service","Ingress","Istio","NetworkPolicy"],C[3]),
                 ("Storage",["PersistentVol","StorageClass","ConfigMap","Secrets"],C[4]),
                 ("Observability",["Prometheus","Grafana","Loki","OpenTelemetry"],C[5])],
    }
    tid = topic_id.lower()
    key = next((k for k in CARDS if k in tid), None)
    groups = CARDS[key] if key else [
        ("Ingest",["Batch ETL","Streaming","CDC","REST Pull"],C[0]),
        ("Process",["Spark","Flink","dbt","ksqlDB"],C[1]),
        ("Store",["Delta Lake","Iceberg","Hudi","Hive Meta"],C[2]),
        ("Serve",["Trino","Athena","BI Tools","APIs"],C[3]),
        ("Govern",["Data Catalog","Lineage","Quality","Masking"],C[4]),
        ("Monitor",["Grafana","Great Expect.","Alerts","SLOs"],C[5]),
    ]

    cols = 3
    rows_g = math.ceil(len(groups) / cols)
    gw = (W - P * 2 - (cols - 1) * 14) // cols
    gh = (H - 80 - (rows_g - 1) * 14) // rows_g

    svg = ""
    for gi, (group_name, items, col) in enumerate(groups):
        gx = P + (gi % cols) * (gw + 14)
        gy = 70 + (gi // cols) * (gh + 14)
        delay = f"animation-delay:{gi*0.07:.2f}s"

        svg += f'<rect x="{gx+2}" y="{gy+2}" width="{gw}" height="{gh}" rx="10" fill="rgba(0,0,0,0.06)"/>'
        svg += f'<rect x="{gx}" y="{gy}" width="{gw}" height="{gh}" rx="10" fill="{lighten(col,0.88)}" stroke="{lighten(col,0.5)}" stroke-width="1.5" class="fi" style="{delay}"/>'
        svg += f'<rect x="{gx}" y="{gy}" width="{gw}" height="26" rx="10" fill="{col}"/>'
        svg += f'<rect x="{gx}" y="{gy+18}" width="{gw}" height="8" fill="{col}"/>'
        svg += f'<text x="{gx+gw//2}" y="{gy+17}" text-anchor="middle" fill="white" font-size="10" font-weight="800" letter-spacing="0.5">{xe(group_name.upper())}</text>'

        n_items = len(items)
        iw = (gw - 16) // min(n_items, 2)
        ih = (gh - 38) // math.ceil(n_items / 2) - 4
        for ii, item in enumerate(items):
            icol = C[(gi + ii) % len(C)]
            ix = gx + 8 + (ii % 2) * iw
            iy = gy + 30 + (ii // 2) * (ih + 4)
            svg += f'<rect x="{ix}" y="{iy}" width="{iw-4}" height="{ih}" rx="7" fill="white" stroke="{lighten(icol,0.4)}" stroke-width="1"/>'
            svg += f'<rect x="{ix}" y="{iy}" width="{iw-4}" height="3" rx="1" fill="{icol}"/>'
            svg += f'<text x="{ix+(iw-4)//2}" y="{iy+ih//2+4}" text-anchor="middle" fill="{darken(icol,0.05)}" font-size="8.5" font-weight="700">{xe(clamp(item,10))}</text>'

    return _wrap(svg, W, H, topic_name, "Architecture", accent, bg_top, bg_bot)


# ══════════════════════════════════════════════════════════════════════════════
#  DISPATCH — pick style per topic (override map + hash fallback)
# ══════════════════════════════════════════════════════════════════════════════

STYLES = [
    _style_vertical_flow,   # 0 — numbered pipeline steps
    _style_mind_map,        # 1 — radial hub + branches
    _style_pyramid,         # 2 — stacked trapezoids
    _style_timeline,        # 3 — horizontal spine, alternating cards
    _style_hexagon,         # 4 — honeycomb concept grid
    _style_comparison,      # 5 — side-by-side matrix
    _style_orbit,           # 6 — central hub + inner + outer rings
    _style_card_grid,       # 7 — grouped card layout
]

TOPIC_STYLE_OVERRIDES = {
    "llm-architecture":  1,   # mind map — concepts radiate naturally
    "ai-agents":         6,   # orbit — agent ecosystem
    "mlops-pipeline":    0,   # vertical flow — pipeline steps
    "rag-systems":       0,   # vertical flow — pipeline steps
    "kubernetes":        4,   # hexagon grid — many K8s concepts
    "docker":            4,   # hexagon grid — Dockerfile cheatsheet
    "aws-architecture":  6,   # orbit — AWS service ecosystem
    "cicd-pipelines":    3,   # timeline — CI/CD history
    "system-design":     7,   # card grid — layered architecture
    "api-design":        5,   # comparison — protocol matrix
    "git-workflow":      3,   # timeline — branching evolution
    "solid-principles":  2,   # pyramid — principle hierarchy
    "zero-trust":        1,   # mind map — concept web
    "devsecops":         0,   # vertical flow — shift-left pipeline
    "data-lakehouse":    2,   # pyramid — medallion architecture layers
    "kafka-streaming":   5,   # comparison — vs other brokers
}


def make_diagram(topic_name: str, topic_id: str, diagram_type: str = "") -> str:
    C = get_pal(topic_id)
    tid = topic_id.lower()

    style_idx = None
    for key, idx in TOPIC_STYLE_OVERRIDES.items():
        if key in tid:
            style_idx = idx
            break

    if style_idx is None:
        # Randomize style for variety instead of deterministic
        style_idx = random.randint(0, len(STYLES) - 1)

    fn = STYLES[style_idx]
    try:
        return fn(topic_id, topic_name, C)
    except Exception as e:
        log.warning(f"Style {style_idx} failed ({e}), falling back to card grid")
        return _style_card_grid(topic_id, topic_name, C)


# ══════════════════════════════════════════════════════════════════════════════
#  DiagramGenerator — interface used by agent.py
# ══════════════════════════════════════════════════════════════════════════════

class DiagramGenerator:
    def __init__(self):
        Path(OUTPUT_DIR).mkdir(exist_ok=True)
        log.info("Diagram output dir: " + OUTPUT_DIR + "/")

    def save_svg(self, svg_content, topic_id, topic_name="", diagram_type="Architecture Diagram"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{OUTPUT_DIR}/{topic_id}_{ts}.svg"
        svg = make_diagram(topic_name or topic_id, topic_id, diagram_type)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(svg)
        size_kb = os.path.getsize(filename) / 1024
        log.info(f"Diagram saved: {filename} ({round(size_kb, 1)} KB)")
        return filename