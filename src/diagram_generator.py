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
import shutil
import math
import hashlib
import random
import re
import io
from datetime import datetime
from pathlib import Path

try:
    _DIAGRAM_AUTHOR = os.environ.get("USER_NAME") or os.environ.get("AUTHOR_NAME") or "Komal Batra"
except Exception:
    _DIAGRAM_AUTHOR = "Komal Batra"

_COPYRIGHT_NAME = "Komal Batra"

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
_MOTION_PHASE = None

# ── Colour palettes ────────────────────────────────────────────────────────────
PALETTES = {
    "ai":       ["#7C3AED","#2563EB","#059669","#D97706","#DB2777","#0891B2"],
    "cloud":    ["#2563EB","#0891B2","#059669","#7C3AED","#D97706","#DB2777"],
    "security": ["#DC2626","#D97706","#7C3AED","#2563EB","#059669","#DB2777"],
    "data":     ["#059669","#7C3AED","#2563EB","#0891B2","#D97706","#DC2626"],
    "devops":   ["#059669","#2563EB","#7C3AED","#D97706","#DC2626","#0891B2"],
    "career":   ["#7C3AED","#DB2777","#D97706","#059669","#2563EB","#0891B2"],
    "default":  ["#2563EB","#7C3AED","#059669","#D97706","#DC2626","#0891B2"],
}

def get_pal(tid, topic_name=""):
    t = ((tid or "") + " " + (topic_name or "")).lower()
    if any(x in t for x in ["llm","rag","agent","mlops","ai","genai","agentic"]): pal = PALETTES["ai"]
    elif any(x in t for x in ["kube","docker","aws","cicd","cloud"]): pal = PALETTES["cloud"]
    elif any(x in t for x in ["zero","devsec","security"]): pal = PALETTES["security"]
    elif any(x in t for x in ["kafka","data","lake","lakehouse"]): pal = PALETTES["data"]
    elif any(x in t for x in ["git","devops","solid","api"]): pal = PALETTES["devops"]
    elif any(x in t for x in ["career","skill","learn","roadmap","job","growth","tips",
                               "engineer","developer","branding","prompt","interview",
                               "brand","leadership","talent","discipline"]): pal = PALETTES["career"]
    else: pal = PALETTES["default"]
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


def fit_lines(text, max_chars, max_lines):
    lines = [clamp(ln, max_chars) for ln in wrap_lines(str(text or ""), max_chars)]
    if len(lines) <= max_lines:
        return lines
    lines = lines[:max_lines]
    last = lines[-1]
    if not last.endswith("..."):
        if len(last) >= max_chars:
            last = clamp(last, max_chars)
        if len(last) >= 3:
            last = clamp(last, max(3, max_chars - 1))
        if not last.endswith("..."):
            last = (last[: max(0, max_chars - 3)] + "...") if max_chars > 3 else "..."
    lines[-1] = last
    return lines


def _animated_dot_path(path_d, dot_colors=("#2563EB", "#DC2626"), dot_radius=3.2, duration=3.2, begin=0.0):
    path_id = "p" + hashlib.md5(f"{path_d}|{dot_colors}|{dot_radius}|{duration}".encode("utf-8")).hexdigest()[:12]
    lead = dot_colors[0]
    trail = dot_colors[1] if len(dot_colors) > 1 else dot_colors[0]
    return (
        f'<path id="{path_id}" d="{path_d}" fill="none" stroke="none"/>'
        f'<circle r="{dot_radius}" fill="{lead}" opacity="0.95">'
        f'<animateMotion dur="{duration:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite" path="{path_d}"/>'
        f'<animate attributeName="opacity" values="0.35;1;0.35" dur="{duration:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite"/>'
        f'</circle>'
        f'<circle r="{max(2.4, dot_radius-0.6):.1f}" fill="{trail}" opacity="0.85">'
        f'<animateMotion dur="{duration:.2f}s" begin="{begin + duration/2:.2f}s" repeatCount="indefinite" path="{path_d}"/>'
        f'<animate attributeName="opacity" values="0.2;0.85;0.2" dur="{duration:.2f}s" begin="{begin + duration/2:.2f}s" repeatCount="indefinite"/>'
        f'</circle>'
    )


def _dotted_flow_line(x1, y1, x2, y2, stroke, dot_colors=("#2563EB", "#DC2626"), dot_spacing=24, dot_radius=2.7, opacity=0.9):
    dx = x2 - x1
    dy = y2 - y1
    dist = max(math.hypot(dx, dy), 1.0)
    steps = max(1, int(dist // dot_spacing))
    svg = f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="1.8" opacity="{opacity}" />'
    phase = _MOTION_PHASE if _MOTION_PHASE is not None else 0.0
    for i in range(steps):
        t = ((i / steps) + phase) % 1.0
        if t <= 0.02 or t >= 0.98:
            continue
        cx = x1 + dx * t
        cy = y1 + dy * t
        col = dot_colors[i % len(dot_colors)]
        rr = dot_radius + (0.35 if i % 3 == 0 else 0)
        svg += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rr:.1f}" fill="{col}" opacity="0.95"/>'
    return svg

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
<text x="18" y="{H-11}" fill="{foot_txt}" font-size="8.5">{datetime.now().strftime("%B %Y")}</text>
<rect x="{W-220}" y="{H-24}" width="208" height="18" rx="9" fill="{rgba(accent,0.12)}" stroke="{accent}" stroke-width="1"/>
<text x="{W-116}" y="{H-12}" text-anchor="middle" fill="{accent}" font-size="9" font-weight="800" letter-spacing="0.8">AI (c) {_COPYRIGHT_NAME}</text>
</svg>'''


# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 0 — VERTICAL FLOW  (numbered steps with animated arrows)
# ══════════════════════════════════════════════════════════════════════════════
def _style_vertical_flow(topic_id, topic_name, C, structure=None):
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
    if structure and structure.get("sections"):
        steps = [
            (str(s.get("label", f"Step {i+1}")), str(s.get("desc", "")))
            for i, s in enumerate(structure.get("sections", [])[:8])
        ]
    else:
        steps = STEP_DATA[key] if key else [
        ("Ingest","Collect raw inputs from all upstream sources"),
        ("Validate","Schema checks, deduplication, quality gates"),
        ("Transform","Business logic, enrichment, join operations"),
        ("Store","Persist to primary data store with indexing"),
        ("Serve","REST / GraphQL API layer with caching"),
        ("Monitor","Metrics, SLO alerts, and automated reporting"),
        ]

    n_steps = max(1, len(steps))
    BOX_W, ARROW_H = 500, 30
    max_flow_h = H - 90
    BOX_H = max(50, int((max_flow_h - ARROW_H * (n_steps - 1)) / n_steps))
    BOX_H = min(64, BOX_H)
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
        label_lines = fit_lines(label, 34, 1)
        sub_lines = fit_lines(sub, 58, 2)
        label_y = y + max(18, BOX_H // 2 - 8)
        svg += f'<text x="{bx+58}" y="{label_y}" fill="{darken(col,0.08)}" font-size="13" font-weight="800">{xe(label_lines[0])}</text>'
        for li, ln in enumerate(sub_lines):
            svg += f'<text x="{bx+58}" y="{label_y+16+li*11}" fill="#64748B" font-size="9.5">{xe(ln)}</text>'
        svg += f'<text x="{bx+BOX_W-40}" y="{y+BOX_H//2+9}" fill="{rgba(col,0.18)}" font-size="28" font-weight="900">{i+1:02d}</text>'

        if i < len(steps) - 1:
            ax = cx; ay1 = y + BOX_H; ay2 = ay1 + ARROW_H - 8
            svg += f'<line x1="{ax}" y1="{ay1}" x2="{ax}" y2="{ay2}" stroke="{col}" stroke-width="2.5" class="flow" opacity="0.8"/>'
            svg += _dotted_flow_line(ax, ay1 + 3, ax, ay2 - 2, rgba(col,0.32), dot_spacing=14, dot_radius=2.6)
            svg += _animated_dot_path(f"M {ax} {ay1+3} L {ax} {ay2-2}", duration=2.4, begin=i * 0.12)
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
    svg += _dotted_flow_line(pad, spine_y, W-pad, spine_y, rgba(accent,0.22), dot_spacing=34, dot_radius=3.0, opacity=0.7)
    svg += _animated_dot_path(f"M {pad} {spine_y} L {W-pad} {spine_y}", duration=4.6)

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
        svg += _dotted_flow_line(mx, stem_y1, mx, stem_y2, rgba(col,0.28), dot_spacing=13, dot_radius=2.3, opacity=0.75)

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
def _style_comparison(topic_id, topic_name, C, structure=None):
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
    if structure and structure.get("cols") and structure.get("rows"):
        cols = structure["cols"]
        rows = structure["rows"]
    else:
        tid = topic_id.lower()
        key = next((k for k in TABLES if k in tid), None)
        if key:
            data = TABLES[key]
            cols = data["cols"]
            rows = data["rows"]
        else:
            cols = ["Comparison A","Comparison B"]
            rows = [
                ("Positioning",  ["Established approach","Emerging approach"]),
                ("Strength",     ["Operational maturity","Focused innovation"]),
                ("Trade-off",    ["Broader coverage","Sharper specialization"]),
                ("Best Fit",     ["Enterprise standardization","Fast-moving teams"]),
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
        line_x1 = cx + 63 * math.cos(a)
        line_y1 = cy + 63 * math.sin(a)
        line_x2 = sx - 38 * math.cos(a)
        line_y2 = sy - 38 * math.sin(a)
        svg += _dotted_flow_line(line_x1, line_y1, line_x2, line_y2, rgba(col,0.24), dot_spacing=16, dot_radius=2.5, opacity=0.72)
        svg += _animated_dot_path(f"M {line_x1:.1f} {line_y1:.1f} L {line_x2:.1f} {line_y2:.1f}", duration=2.8, begin=i * 0.18)

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
#  STYLE 8 — 3-TIER DATA EVOLUTION
# ══════════════════════════════════════════════════════════════════════════════
def _style_data_evolution(topic_id, topic_name, C):
    W, H = 900, 580
    accent = C[0]
    bg_top = lighten(accent, 0.90)
    bg_bot = lighten(accent, 0.95)

    svg = ""
    # Tiers setup
    tiers = [
        ("Data Sources",    ["APIs & SaaS", "Databases (CDC)", "IoT / Streaming", "Logs & Events"], C[1]),
        ("Data Lakehouse",  ["Ingestion Layer", "Storage (Iceberg)", "Processing (Spark)", "Serving Engine"], C[0]),
        ("Data Consumers",  ["BI Dashboards", "ML / AI Models", "Data Apps", "Reverse ETL"], C[2])
    ]

    # Draw the main flow arrows in background
    svg += f'<path d="M 230 {H//2} L 310 {H//2}" fill="none" stroke="{C[1]}" stroke-width="3" stroke-dasharray="8 4" class="flow"/>'
    svg += _dotted_flow_line(230, H//2, 310, H//2, rgba(C[1],0.24), dot_spacing=15, dot_radius=2.7, opacity=0.78)
    svg += _animated_dot_path(f"M 230 {H//2} L 310 {H//2}", duration=2.0)
    svg += f'<polygon points="310,{H//2} 300,{H//2-6} 300,{H//2+6}" fill="{C[1]}" class="pu"/>'
    svg += f'<path d="M 590 {H//2} L 670 {H//2}" fill="none" stroke="{C[0]}" stroke-width="3" stroke-dasharray="8 4" class="flow"/>'
    svg += _dotted_flow_line(590, H//2, 670, H//2, rgba(C[0],0.24), dot_spacing=15, dot_radius=2.7, opacity=0.78)
    svg += _animated_dot_path(f"M 590 {H//2} L 670 {H//2}", duration=2.0, begin=0.8)
    svg += f'<polygon points="670,{H//2} 660,{H//2-6} 660,{H//2+6}" fill="{C[0]}" class="pu"/>'

    x_offsets = [40, 320, 680]
    widths = [180, 260, 180]

    for ti, (title, items, col) in enumerate(tiers):
        tx = x_offsets[ti]
        tw = widths[ti]
        th = 400
        ty = 90
        delay = f"animation-delay:{ti*0.1:.2f}s"
        
        # Tier background
        svg += f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="12" fill="{lighten(col, 0.85)}" stroke="{lighten(col, 0.4)}" stroke-width="1.5" class="fi" style="{delay}"/>'
        
        # Tier header
        svg += f'<rect x="{tx}" y="{ty}" width="{tw}" height="36" rx="12" fill="{col}"/>'
        svg += f'<rect x="{tx}" y="{ty+20}" width="{tw}" height="16" fill="{col}"/>'
        svg += f'<text x="{tx+tw//2}" y="{ty+22}" text-anchor="middle" fill="white" font-size="12" font-weight="800" letter-spacing="0.5">{xe(title.upper())}</text>'
        
        # Items
        n_items = len(items)
        ih = (th - 60) // n_items - 12
        for ii, item in enumerate(items):
            iy = ty + 50 + ii * (ih + 12)
            icol = C[(ti + ii + 1) % len(C)]
            idelay = f"animation-delay:{ti*0.1 + ii*0.05 + 0.1:.2f}s"
            svg += f'<rect x="{tx+16}" y="{iy}" width="{tw-32}" height="{ih}" rx="8" fill="white" stroke="{lighten(icol, 0.3)}" stroke-width="1.5" class="fi" style="{idelay}"/>'
            svg += f'<circle cx="{tx+32}" cy="{iy+ih//2}" r="6" fill="{icol}" class="pu"/>'
            svg += f'<text x="{tx+46}" y="{iy+ih//2+4}" fill="{darken(icol, 0.1)}" font-size="10" font-weight="700">{xe(item)}</text>'

    return _wrap(svg, W, H, topic_name, "3-Tier Data Architecture", accent, bg_top, bg_bot)


# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 9 — HORIZONTAL TREE
# ══════════════════════════════════════════════════════════════════════════════
def _style_horizontal_tree(topic_id, topic_name, C):
    W, H = 900, 640
    accent = C[0]
    bg_top = lighten(accent, 0.92)
    bg_bot = lighten(accent, 0.96)

    TREE_DATA = {
        "ml-algorithms": {
            "root": "Machine Learning",
            "branches": [
                ("Supervised", [
                    ("Classification", ["Naïve Bayes", "Logistic Reg.", "KNN", "Random Forest", "SVM"]),
                    ("Regression", ["Decision Tree", "Linear Reg.", "Lasso Reg."])
                ]),
                ("Unsupervised", [
                    ("Clustering", ["K-Means", "DBSCAN", "PCA"]),
                    ("Association", ["Apriori", "FP-Growth"]),
                    ("Anomaly", ["Isolation Forest"])
                ]),
                ("Reinforcement", [
                    ("Model-Free", ["Q-Learning", "Policy Opt."]),
                    ("Model-Based", ["Learn Model", "Given Model"])
                ])
            ]
        }
    }
    tid = topic_id.lower()
    tree = TREE_DATA.get(tid)
    if not tree:
        tree = TREE_DATA["ml-algorithms"]

    svg = ""
    # We have 4 levels: root(L0), branches(L1), sub-branches(L2), leaves(L3)
    # x-coordinates for each level
    X0, X1, X2, X3 = 30, 240, 450, 680
    Y_start = 80
    Y_avail = H - Y_start - 40

    root_name = tree["root"]
    branches = tree["branches"]

    # Calculate total leaves to distribute vertical space
    total_leaves = sum(sum(len(sub[1]) for sub in b[1]) for b in branches)
    leaf_h = Y_avail / max(total_leaves, 1)

    cy_root = Y_start + Y_avail / 2

    # Draw Root Node
    rw, rh = 140, 36
    svg += f'<rect x="{X0}" y="{cy_root-rh/2}" width="{rw}" height="{rh}" rx="8" fill="{C[0]}" class="fi"/>'
    svg += f'<text x="{X0+rw/2}" y="{cy_root+5}" text-anchor="middle" fill="white" font-size="12" font-weight="800">{xe(root_name)}</text>'

    current_leaf_y = Y_start + leaf_h / 2

    for b_idx, (b_name, sub_branches) in enumerate(branches):
        b_col = C[(b_idx + 1) % len(C)]
        
        # Calculate branch Y center based on its leaves
        b_leaves = sum(len(sub[1]) for sub in sub_branches)
        b_cy = current_leaf_y + (b_leaves * leaf_h) / 2 - leaf_h / 2

        # Curve from Root to Branch
        svg += f'<path d="M {X0+rw} {cy_root} C {X0+rw+40} {cy_root}, {X1-40} {b_cy}, {X1} {b_cy}" fill="none" stroke="{b_col}" stroke-width="2" class="flow" style="animation-delay:{b_idx*0.1:.2f}s"/>'
        
        # Draw Branch Node
        bw, bh = 120, 30
        svg += f'<rect x="{X1}" y="{b_cy-bh/2}" width="{bw}" height="{bh}" rx="6" fill="{lighten(b_col,0.7)}" stroke="{b_col}" stroke-width="1.5" class="fi" style="animation-delay:{b_idx*0.15:.2f}s"/>'
        svg += f'<text x="{X1+bw/2}" y="{b_cy+4}" text-anchor="middle" fill="{darken(b_col,0.2)}" font-size="11" font-weight="700">{xe(b_name)}</text>'

        for sb_idx, (sb_name, leaves) in enumerate(sub_branches):
            sb_leaves = len(leaves)
            sb_cy = current_leaf_y + (sb_leaves * leaf_h) / 2 - leaf_h / 2

            # Curve from Branch to Sub-branch
            svg += f'<path d="M {X1+bw} {b_cy} C {X1+bw+30} {b_cy}, {X2-30} {sb_cy}, {X2} {sb_cy}" fill="none" stroke="{b_col}" stroke-width="1.5" stroke-dasharray="4 2"/>'
            
            # Draw Sub-branch Node
            sbw, sbh = 110, 26
            svg += f'<rect x="{X2}" y="{sb_cy-sbh/2}" width="{sbw}" height="{sbh}" rx="6" fill="{lighten(b_col,0.4)}" stroke="{b_col}" stroke-width="1" class="fi" style="animation-delay:{b_idx*0.15 + sb_idx*0.05:.2f}s"/>'
            svg += f'<text x="{X2+sbw/2}" y="{sb_cy+4}" text-anchor="middle" fill="{darken(b_col,0.4)}" font-size="10" font-weight="600">{xe(sb_name)}</text>'

            for l_idx, leaf_name in enumerate(leaves):
                l_cy = current_leaf_y
                
                # Curve from Sub-branch to Leaf
                svg += f'<path d="M {X2+sbw} {sb_cy} C {X2+sbw+20} {sb_cy}, {X3-20} {l_cy}, {X3} {l_cy}" fill="none" stroke="{lighten(b_col,0.2)}" stroke-width="1" class="flow"/>'
                
                # Draw Leaf Node
                lw, lh = 170, 22
                svg += f'<rect x="{X3}" y="{l_cy-lh/2}" width="{lw}" height="{lh}" rx="4" fill="{lighten(b_col,0.85)}" stroke="{lighten(b_col,0.2)}" stroke-width="1" class="fi" style="animation-delay:{b_idx*0.15 + sb_idx*0.05 + l_idx*0.02:.2f}s"/>'
                svg += f'<text x="{X3+10}" y="{l_cy+3}" text-anchor="start" fill="{darken(b_col,0.3)}" font-size="9.5" font-weight="600">{xe(leaf_name)}</text>'
                
                current_leaf_y += leaf_h

    return _wrap(svg, W, H, topic_name, "Algorithm Taxonomy", accent, bg_top, bg_bot)

# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 10 — LAYERED HORIZONTAL FLOW
# ══════════════════════════════════════════════════════════════════════════════
def _style_layered_flow(topic_id, topic_name, C):
    W, H = 900, 720
    accent = C[0]
    bg_top = lighten(accent, 0.94)
    bg_bot = lighten(accent, 0.98)

    LAYERS_DATA = {
        "ai-disciplines": [
            ("Artificial\nIntelligence", "Neural Network\nComputer Vision\nNLP", C[0]),
            ("Machine\nLearning", "Unsupervised\nSupervised\nReinforcement", C[1]),
            ("Deep\nLearning", "[IMAGE] -> [Hidden Layers] -> [Prediction]", C[2]),
            ("Generative\nAI", "[User] -> [LLM + Tools] -> [Output]", C[3]),
            ("RAG\nSystems", "[User] -> [Retriever] -> [Augment] -> [Generator]", C[4]),
            ("AI\nAgents", "[User] -> [Agent Loop (Brain+Memory+Tools)]", C[5])
        ]
    }
    
    tid = topic_id.lower()
    layers = LAYERS_DATA.get(tid)
    if not layers:
        layers = LAYERS_DATA["ai-disciplines"]

    svg = ""
    n_layers = len(layers)
    pad = 20
    avail_h = H - 100
    lh = avail_h // n_layers - 12
    ly = 70

    for i, (title, content, col) in enumerate(layers):
        delay = f"animation-delay:{i*0.1:.2f}s"
        
        # Lane Background
        svg += f'<rect x="{pad}" y="{ly}" width="{W-pad*2}" height="{lh}" rx="12" fill="{lighten(col, 0.90)}" stroke="{lighten(col, 0.6)}" stroke-width="1.5" class="fi" style="{delay}"/>'
        
        # Left Title Block
        title_w = 140
        svg += f'<rect x="{pad}" y="{ly}" width="{title_w}" height="{lh}" rx="12" fill="{lighten(col,0.1)}"/>'
        # Fix corners to connect seamlessly
        svg += f'<rect x="{pad+title_w-15}" y="{ly}" width="15" height="{lh}" fill="{lighten(col,0.1)}"/>'
        svg += f'<line x1="{pad+title_w}" y1="{ly}" x2="{pad+title_w}" y2="{ly+lh}" stroke="{col}" stroke-width="3"/>'
        
        cy = ly + lh/2
        
        # Draw Icon Placeholder
        svg += f'<circle cx="{pad+title_w/2}" cy="{cy-12}" r="16" fill="white" opacity="0.2"/>'
        svg += f'<text x="{pad+title_w/2}" y="{cy-8}" text-anchor="middle" fill="white" font-size="14">⚙️</text>'
        
        t_lines = title.split('\n')
        for ti, tln in enumerate(t_lines):
            svg += f'<text x="{pad+title_w/2}" y="{cy+14+ti*14}" text-anchor="middle" fill="white" font-size="12" font-weight="800">{xe(tln)}</text>'

        # Right Content Area (Simplified abstract representations based on the string hint)
        cx_start = pad + title_w + 30
        avail_w = W - pad*2 - title_w - 60
        
        svg += f'<g class="fi" style="animation-delay:{i*0.1+0.2:.2f}s">'
        
        # Super simplified parsing of the content string to render visual blocks
        if "->" in content:
            # Flow sequence
            steps = [s.strip(" []") for s in content.split("->")]
            step_w = min(130, avail_w // len(steps) - 30)
            step_spacing = avail_w // len(steps)
            
            for si, step in enumerate(steps):
                sx = cx_start + si * step_spacing
                if si < len(steps) - 1:
                    nx = cx_start + (si+1) * step_spacing
                    svg += f'<line x1="{sx+step_w}" y1="{cy}" x2="{nx}" y2="{cy}" stroke="{col}" stroke-width="2" class="flow"/>'
                    svg += f'<polygon points="{nx},{cy} {nx-6},{cy-4} {nx-6},{cy+4}" fill="{col}" class="pu"/>'
                
                svg += f'<rect x="{sx}" y="{cy-18}" width="{step_w}" height="36" rx="6" fill="white" stroke="{col}" stroke-width="1.5"/>'
                svg += f'<text x="{sx+step_w/2}" y="{cy+4}" text-anchor="middle" fill="{darken(col,0.2)}" font-size="10" font-weight="700">{xe(clamp(step,18))}</text>'

        else:
            # Bulleted clustering
            bullets = content.split('\n')
            bw = 140
            spacing = avail_w // max(len(bullets), 1)
            for bi, bull in enumerate(bullets):
                bx = cx_start + bi * spacing
                svg += f'<rect x="{bx}" y="{cy-14}" width="{bw}" height="28" rx="14" fill="white" stroke="{lighten(col,0.3)}" stroke-width="1.5"/>'
                svg += f'<circle cx="{bx+14}" cy="{cy}" r="4" fill="{col}"/>'
                svg += f'<text x="{bx+26}" y="{cy+4}" fill="{darken(col,0.4)}" font-size="10" font-weight="600">{xe(bull)}</text>'
                
                # Draw connecting abstract lines to center title to simulate the image
                if i < 2:  # For AI and ML
                    ly_target = cy - 40 + bi*40
                    svg += f'<path d="M {pad+title_w+10} {cy} C {pad+title_w+40} {cy}, {bx-20} {cy}, {bx} {cy}" fill="none" stroke="{lighten(col,0.5)}" stroke-width="1"/>'

        svg += '</g>'
        ly += lh + 12

    return _wrap(svg, W, H, topic_name, "Conceptual Layers", accent, bg_top, bg_bot)

# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 11 — ECOSYSTEM TREE (RAG STACK)
# ══════════════════════════════════════════════════════════════════════════════
def _style_ecosystem_tree(topic_id, topic_name, C):
    W, H = 1000, 850
    accent = C[0]
    bg_top = lighten(accent, 0.95)
    bg_bot = lighten(accent, 0.98)

    svg = ""
    # Central Hub
    cx, cy = W/2, H/2 - 20
    
    # 3D Stack / Server Illustration in center
    svg += f'<rect x="{cx-60}" y="{cy-80}" width="120" height="160" rx="10" fill="{darken(accent,0.6)}"/>'
    svg += f'<path d="M {cx-40} {cy-100} Q {cx} {cy-110} {cx+40} {cy-100} L {cx+60} {cy-80} L {cx-60} {cy-80} Z" fill="{lighten(accent,0.4)}"/>'
    svg += f'<rect x="{cx-50}" y="{cy-60}" width="100" height="15" rx="4" fill="{lighten(accent,0.2)}"/>'
    svg += f'<rect x="{cx-50}" y="{cy-30}" width="100" height="15" rx="4" fill="{lighten(accent,0.2)}"/>'
    svg += f'<rect x="{cx-50}" y="{cy}" width="100" height="15" rx="4" fill="{lighten(accent,0.2)}"/>'
    svg += f'<rect x="{cx-50}" y="{cy+30}" width="100" height="15" rx="4" fill="{lighten(accent,0.2)}"/>'

    GROUPS = [
        # (title, x, y, spine_dir, items)
        ("Ingest/Data Processing", cx-250, cy-70, "left_down", ["Kubeflow", "Apache Airflow", "Apache Nifi", "LangChain Loaders", "Haystack Pipelines", "OpenSearch"]),
        ("Retrieval & Ranking", cx-150, cy-220, "up_horiz", ["Elasticsearch", "Haystack Retrivers", "JinaAI", "Weaviate", "FAISS"]),
        ("LLM Frameworks", cx+150, cy-220, "up_horiz", ["LlamaIndex", "LangChain", "Huggingface", "Haystack", "CrewAI"]),
        ("Embedding Model", cx+280, cy-120, "right_down", ["HuggingFace", "LLMWare", "Sentence Transformers", "JinaAI", "Cognita", "Nomic"]),
        ("Vector Database", cx+250, cy+180, "right_down", ["Milvus", "Weaviate", "PgVector", "Chroma", "Qdrant"]),
        ("LLM", cx, cy+180, "down_split", ["Phi-2", "Deepseek", "Qwen", "LLaMa", "Mistral", "Gemma"]),
        ("Frontend Frameworks", cx-250, cy+180, "left_down", ["NextJS", "SvelteKit", "Streamlit", "VueJS"])
    ]

    for i, (g_title, gx, gy, sdir, items) in enumerate(GROUPS):
        col = C[i % len(C)]
        # Connector from Center to Bubble
        svg += f'<path d="M {cx} {cy} L {gx} {gy}" stroke="{col}" stroke-width="3" fill="none" class="flow" style="animation-delay:{i*0.1:.2f}s"/>'
        svg += f'<circle cx="{cx}" cy="{cy}" r="6" fill="{col}"/>'
        
        # Draw Spine
        if sdir == "left_down":
            svg += f'<path d="M {gx-50} {gy} L {gx-80} {gy} L {gx-80} {gy+(len(items)*40)}" stroke="gray" stroke-width="2" fill="none"/>'
            for j, item in enumerate(items):
                ix, iy = gx-80, gy + 30 + j*40
                svg += f'<line x1="{ix}" y1="{iy}" x2="{ix-20}" y2="{iy}" stroke="gray" stroke-width="2"/>'
                svg += f'<text x="{ix-30}" y="{iy+4}" text-anchor="end" fill="black" font-size="11" font-weight="600">{xe(item)}</text>'
        
        elif sdir == "right_down":
            svg += f'<path d="M {gx+50} {gy} L {gx+80} {gy} L {gx+80} {gy+(len(items)*40)}" stroke="gray" stroke-width="2" fill="none"/>'
            for j, item in enumerate(items):
                ix, iy = gx+80, gy + 30 + j*40
                svg += f'<line x1="{ix}" y1="{iy}" x2="{ix+20}" y2="{iy}" stroke="gray" stroke-width="2"/>'
                svg += f'<text x="{ix+30}" y="{iy+4}" text-anchor="start" fill="black" font-size="11" font-weight="600">{xe(item)}</text>'
        
        elif sdir == "up_horiz":
            svg += f'<path d="M {gx} {gy-40} L {gx} {gy-70} L {gx-100} {gy-70} L {gx+100} {gy-70}" stroke="gray" stroke-width="2" fill="none"/>'
            for j, item in enumerate(items):
                ix = gx - 90 + j*45
                iy = gy - 70
                y_offset = -20 if j % 2 == 0 else 20
                svg += f'<line x1="{ix}" y1="{iy}" x2="{ix}" y2="{iy+y_offset}" stroke="gray" stroke-width="2"/>'
                svg += f'<text x="{ix}" y="{iy+(y_offset*1.5)+4}" text-anchor="middle" fill="black" font-size="10" font-weight="600">{xe(item)}</text>'
                
        elif sdir == "down_split":
            svg += f'<path d="M {gx} {gy+40} L {gx} {gy+80} M {gx-60} {gy+80} L {gx+60} {gy+80} L {gx+60} {gy+160} M {gx-60} {gy+80} L {gx-60} {gy+160}" stroke="gray" stroke-width="2" fill="none"/>'
            for j, item in enumerate(items):
                # Split roughly in half
                if j < len(items)/2:
                    ix, iy = gx - 60, gy + 100 + j*35
                    svg += f'<line x1="{ix}" y1="{iy}" x2="{ix-20}" y2="{iy}" stroke="gray" stroke-width="2"/>'
                    svg += f'<text x="{ix-30}" y="{iy+4}" text-anchor="end" fill="black" font-size="11" font-weight="600">{xe(item)}</text>'
                else:
                    k = j - int(len(items)/2)
                    ix, iy = gx + 60, gy + 100 + k*35
                    svg += f'<line x1="{ix}" y1="{iy}" x2="{ix+20}" y2="{iy}" stroke="gray" stroke-width="2"/>'
                    svg += f'<text x="{ix+30}" y="{iy+4}" text-anchor="start" fill="black" font-size="11" font-weight="600">{xe(item)}</text>'

        # Draw Bubble (over lines)
        svg += f'<circle cx="{gx}" cy="{gy}" r="45" fill="white" stroke="{col}" stroke-width="3" class="fi" style="animation-delay:{i*0.1+0.2:.2f}s"/>'
        parts = g_title.split()
        if len(parts) == 1:
            svg += f'<text x="{gx}" y="{gy+5}" text-anchor="middle" fill="{darken(col,0.4)}" font-size="12" font-weight="800">{xe(parts[0])}</text>'
        elif len(parts) == 2:
            svg += f'<text x="{gx}" y="{gy-5}" text-anchor="middle" fill="{darken(col,0.4)}" font-size="11" font-weight="800">{xe(parts[0])}</text>'
            svg += f'<text x="{gx}" y="{gy+10}" text-anchor="middle" fill="{darken(col,0.4)}" font-size="11" font-weight="800">{xe(parts[1])}</text>'
        else:
            svg += f'<text x="{gx}" y="{gy-10}" text-anchor="middle" fill="{darken(col,0.4)}" font-size="11" font-weight="800">{xe(parts[0])}</text>'
            svg += f'<text x="{gx}" y="{gy+5}" text-anchor="middle" fill="{darken(col,0.4)}" font-size="11" font-weight="800">{xe(parts[1])}</text>'
            svg += f'<text x="{gx}" y="{gy+20}" text-anchor="middle" fill="{darken(col,0.4)}" font-size="11" font-weight="800">{xe(" ".join(parts[2:]))}</text>'

    return _wrap(svg, W, H, topic_name, "Data & AI Pipeline ecosystem map", accent, bg_top, bg_bot)

# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 12 — HONEYCOMB MAP
# ══════════════════════════════════════════════════════════════════════════════
import math
def _hex_poly(cx, cy, r):
    pts = []
    for i in range(6):
        angle_deg = 60 * i + 30
        angle_rad = math.pi / 180 * angle_deg
        pts.append(f"{cx + r * math.cos(angle_rad)},{cy + r * math.sin(angle_rad)}")
    return " ".join(pts)

def _style_honeycomb_map(topic_id, topic_name, C):
    W, H = 1000, 950
    accent = C[0]
    bg_top = lighten(accent, 0.98)
    bg_bot = lighten(accent, 0.99)

    svg = ""
    HexR = 50
    HexW = math.sqrt(3) * HexR
    HexH = 2 * HexR
    
    cx_center = W/2
    cy_center = H/2 - 20

    # Layout:
    # Row 1: Agentic AI
    # Row 2: Deep Learning, Machine Learning, NLP, Generative AI
    # Row 3: AI Ethics, Computer Vision, Robotics, AI Agents
    # We will hardcode approximate coordinates to cluster 9 hexes based on standard rendering
    # Actually, a manual cluster layout coordinates relative to center:
    coords = [
        (0, -110, "AI Agents", C[0]),
        (-80, -55, "Agentic AI", C[1]),
        (80, -55, "Generative AI", C[2]),
        (-160, 0, "Deep Learning", C[3]),
        (0, 0, "Machine\nLearning", C[4]),
        (160, 0, "NLP", C[5]),
        (-80, 55, "AI Ethics &\nGovernance", C[0]),
        (80, 55, "Computer\nVision", C[1]),
        (160, -110, "Robotics &\nAuto Sys", C[2]), # moved slightly
    ]

    # Draw hexes
    for i, (dx, dy, txt, col) in enumerate(coords):
        hx, hy = cx_center + dx, cy_center + dy
        svg += f'<polygon points="{_hex_poly(hx, hy, HexR)}" fill="{darken(col,0.2)}" stroke="{darken(col,0.4)}" stroke-width="4" class="pu" style="animation-delay:{i*0.1:.2f}s"/>'
        parts = txt.split('\n')
        if len(parts) == 1:
            svg += f'<text x="{hx}" y="{hy+5}" text-anchor="middle" fill="white" font-size="12" font-weight="700">{xe(parts[0])}</text>'
        else:
            svg += f'<text x="{hx}" y="{hy-2}" text-anchor="middle" fill="white" font-size="11" font-weight="700">{xe(parts[0])}</text>'
            svg += f'<text x="{hx}" y="{hy+12}" text-anchor="middle" fill="white" font-size="11" font-weight="700">{xe(parts[1])}</text>'

    # Surrounding Cards
    CARDS = [
        ("AI Agents", cx_center-400, cy_center-280, ["Multi-agent systems", "Prompt engineering"], ["LangChain", "AutoGen"]),
        ("Agentic AI", cx_center-150, cy_center-280, ["Reasoning algorithms", "Task orchestration"], ["AutoGPT", "BabyAGI"]),
        ("Generative AI", cx_center+100, cy_center-280, ["Prompt chaining", "Multimodal models"], ["GPT / Claude", "MidJourney"]),
        ("Deep Learning", cx_center-450, cy_center-20, ["Neural net architecture", "GPU optimization"], ["PyTorch", "TensorFlow"]),
        ("Machine Learning", cx_center-450, cy_center+180, ["Data preprocessing", "Hyperparameter tuning"], ["Scikit-learn", "XGBoost"]),
        ("AI Ethics", cx_center-150, cy_center+280, ["Bias mitigation", "XAI design"], ["AI Fairness 360", "SHAP"]),
        ("Computer Vision", cx_center+100, cy_center+280, ["Image preprocessing", "Object detection"], ["OpenCV", "YOLOv8"]),
        ("NLP", cx_center+350, cy_center+80, ["Text embedding", "Semantic search"], ["Hugging Face", "Pinecone"]),
    ]

    for title, rx, ry, skills, tech in CARDS:
        # Draw connector path vaguely towards center
        c_cx, c_cy = rx + 120, ry + 60
        svg += f'<path d="M {c_cx} {c_cy} L {cx_center} {cy_center}" stroke="{accent}" stroke-width="2" stroke-dasharray="8 4" fill="none" class="flow" opacity="0.4"/>'
        
        # Draw Card
        cw, ch = 240, 160
        svg += f'<rect x="{rx}" y="{ry}" width="{cw}" height="{ch}" rx="8" fill="white" stroke="{lighten(accent,0.5)}" stroke-width="2" class="box-sd"/>'
        svg += f'<text x="{rx+10}" y="{ry+20}" font-size="14" font-weight="800" fill="{darken(accent,0.3)}">{xe(title)}</text>'
        
        # Skills column
        svg += f'<text x="{rx+10}" y="{ry+45}" font-size="11" font-weight="700" fill="gray">Skills:</text>'
        for si, s in enumerate(skills):
            svg += f'<circle cx="{rx+15}" cy="{ry+60+si*15}" r="2" fill="black"/>'
            svg += f'<text x="{rx+22}" y="{ry+63+si*15}" font-size="10" fill="black">{xe(s)}</text>'
            
        # Tech column
        tx_start = rx + 120
        svg += f'<text x="{tx_start}" y="{ry+45}" font-size="11" font-weight="700" fill="gray">Technologies:</text>'
        for ti, t in enumerate(tech):
            svg += f'<circle cx="{tx_start+5}" cy="{ry+60+ti*15}" r="2" fill="black"/>'
            svg += f'<text x="{tx_start+12}" y="{ry+63+ti*15}" font-size="10" fill="black">{xe(t)}</text>'

    return _wrap(svg, W, H, topic_name, "Skills & Technologies Map", accent, bg_top, bg_bot)

# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 13 — PARALLEL PIPELINES
# ══════════════════════════════════════════════════════════════════════════════
def _style_parallel_pipelines(topic_id, topic_name, C):
    W, H = 1000, 850
    accent = C[0]
    bg_top = lighten(accent, 0.94)
    bg_bot = lighten(accent, 0.96)
    
    COLUMNS = [
        ("LLM", C[0], ["Choose Cloud", "Tokenization", "Context Understanding", "[SPLIT: Apply Layers | Use Weights]", "Token Prediction", "Output Construct"]),
        ("Generative AI", C[1], ["Input Collection", "Feature Mapping", "Pattern Learning", "[SPLIT: Leverage models | Identify latent]", "Content Gen", "Refinement"]),
        ("AI Agents", C[2], ["Task Triggered", "Intent Detection", "[SPLIT: Understand | Classify]", "Rule Execution", "Tool / API Call", "Result Gen"]),
        ("Agentic AI", C[3], ["[SPLIT: Receive Obj | Understand Cxt]", "[SPLIT: Analyze Env | Identify Constr]", "Reasoning & Planning", "Autonomous Execution", "Real-time Monitor"])
    ]
    
    svg = ""
    col_w = W / len(COLUMNS)
    
    for c_idx, (col_title, col_color, steps) in enumerate(COLUMNS):
        cx = (c_idx * col_w) + (col_w / 2)
        
        # Column Background Header
        svg += f'<rect x="{cx - col_w/2 + 5}" y="50" width="{col_w-10}" height="40" rx="4" fill="{col_color}"/>'
        svg += f'<text x="{cx}" y="75" text-anchor="middle" fill="white" font-size="16" font-weight="bold">{xe(col_title)}</text>'
        
        # Lane Background
        svg += f'<rect x="{cx - col_w/2 + 5}" y="95" width="{col_w-10}" height="{H-150}" fill="{lighten(col_color,0.9)}" stroke="{lighten(col_color,0.7)}" stroke-width="1"/>'
        
        step_h = (H-200) / max(len(steps), 1)
        cy_current = 140
        
        for s_idx, step_txt in enumerate(steps):
            
            # Draw vertical line from previous step (except first)
            if s_idx > 0:
                prev_y = cy_current - step_h
                svg += f'<line x1="{cx}" y1="{prev_y+20}" x2="{cx}" y2="{cy_current-20}" stroke="{darken(col_color,0.2)}" stroke-width="2" class="flow" style="animation-delay:{c_idx*0.2 + s_idx*0.1:.2f}s"/>'
                svg += f'<polygon points="{cx},{cy_current-15} {cx-4},{cy_current-22} {cx+4},{cy_current-22}" fill="{darken(col_color,0.2)}"/>'
            
            if step_txt.startswith("[SPLIT:"):
                # Handle parallel split node
                inner = step_txt.replace("[SPLIT:", "").replace("]", "").strip()
                left_txt, right_txt = inner.split("|")
                
                # Split lines
                lx, rx = cx - 50, cx + 50
                svg += f'<path d="M {cx} {cy_current-20} L {cx} {cy_current-10} L {lx} {cy_current-10} L {lx} {cy_current}" fill="none" stroke="{darken(col_color,0.2)}" stroke-width="2"/>'
                svg += f'<path d="M {cx} {cy_current-20} L {cx} {cy_current-10} L {rx} {cy_current-10} L {rx} {cy_current}" fill="none" stroke="{darken(col_color,0.2)}" stroke-width="2"/>'
                
                # Left Node
                svg += f'<circle cx="{lx}" cy="{cy_current+10}" r="15" fill="white" stroke="{col_color}" stroke-width="2"/>'
                svg += f'<text x="{lx}" y="{cy_current+40}" text-anchor="middle" fill="black" font-size="10">{xe(left_txt.strip())}</text>'
                
                # Right Node
                svg += f'<circle cx="{rx}" cy="{cy_current+10}" r="15" fill="white" stroke="{col_color}" stroke-width="2"/>'
                svg += f'<text x="{rx}" y="{cy_current+40}" text-anchor="middle" fill="black" font-size="10">{xe(right_txt.strip())}</text>'
                
                # Merge lines back to center for next step
                svg += f'<path d="M {lx} {cy_current+50} L {lx} {cy_current+60} L {cx} {cy_current+60} L {cx} {cy_current+70}" fill="none" stroke="{darken(col_color,0.2)}" stroke-width="2"/>'
                svg += f'<path d="M {rx} {cy_current+50} L {rx} {cy_current+60} L {cx} {cy_current+60} L {cx} {cy_current+70}" fill="none" stroke="{darken(col_color,0.2)}" stroke-width="2"/>'
                
                cy_current += step_h + 30
            else:
                # Normal single node
                svg += f'<circle cx="{cx}" cy="{cy_current}" r="18" fill="white" stroke="{col_color}" stroke-width="3" class="pu"/>'
                svg += f'<text x="{cx}" y="{cy_current+4}" text-anchor="middle" fill="{darken(col_color,0.2)}" font-size="12" font-weight="bold">{s_idx+1}</text>'
                svg += f'<text x="{cx}" y="{cy_current+35}" text-anchor="middle" fill="black" font-size="11" font-weight="600">{xe(step_txt)}</text>'
                
                cy_current += step_h

    return _wrap(svg, W, H, topic_name, "Evolution & Execution Pipeline", accent, bg_top, bg_bot)


# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 14 — WINDING ROADMAP
# ══════════════════════════════════════════════════════════════════════════════
def _style_winding_roadmap(topic_id, topic_name, C):
    W, H = 1000, 1100
    accent = C[0]
    bg_top = lighten(accent, 0.94)
    bg_bot = lighten(accent, 0.97)

    svg = ""
    
    # Roadmap Steps (Title, subtitle, array of points)
    STEPS = [
        ("1. Start with the Basics", "AI -> ML -> DL -> GenAI", ["Learn how models generate data", "Clarity saves months later"]),
        ("2. Master Core Concepts", "Math Foundations", ["Probability & Stats", "Linear Algebra", "Calculus basics"]),
        ("3. Foundation Models", "Get Hands-on", ["GPT, Llama, Gemini, Claude", "Understand training & usage"]),
        ("4. GenAI Dev Stack", "Practical Tools", ["Python, LangChain", "Vector DBs, Hugging Face"]),
        ("5. Model Training", "The Lifecycle", ["Dataset -> Tokenization", "Training -> Eval -> Deploy"]),
        ("6. Build AI Agents", "The Future is Agentic", ["Memory & Tool usage", "Autonomy + Human control"]),
        ("7. Vision Models", "Text is just the start", ["GANs & Image Gen", "Vision + Language leap"]),
        ("8. Keep Learning", "Build. Ship. Iterate.", ["DeepLearning.AI, Kaggle", "Google Labs, Nvidia"])
    ]
    
    # Path coordinates
    cx = W/2
    y_start = 80
    y_step = 110
    
    # Draw the main winding background path
    path_d = f"M {cx} {y_start} "
    for i in range(len(STEPS)-1):
        # alternate swinging left and right
        swing = 150 if i % 2 == 0 else -150
        cy1 = y_start + (i)*y_step
        cy2 = y_start + (i+1)*y_step
        path_d += f"C {cx+swing} {cy1+y_step/2}, {cx+swing} {cy2-y_step/2}, {cx} {cy2} "
        
    svg += f'<path d="{path_d}" fill="none" class="flow" stroke="{lighten(accent,0.8)}" stroke-width="40" stroke-linecap="round"/>'
    svg += f'<path d="{path_d}" fill="none" class="flow" stroke="{accent}" stroke-width="6" stroke-dasharray="12 12" stroke-linecap="round"/>'

    for i, (title, sub, bullets) in enumerate(STEPS):
        col = C[i % len(C)]
        cy = y_start + i * y_step
        
        # Node on path
        svg += f'<circle cx="{cx}" cy="{cy}" r="25" fill="{col}" stroke="white" stroke-width="4" class="pu" style="animation-delay:{i*0.1:.2f}s"/>'
        svg += f'<text x="{cx}" y="{cy+8}" text-anchor="middle" fill="white" font-size="20" font-weight="900">{i+1}</text>'
        
        # Determine Card position (alternate left/right of path)
        is_left = (i % 2 == 1)
        card_w = 320
        card_h = 90
        
        if is_left:
            card_x = cx - card_w - 60
            # Connector
            svg += f'<path d="M {cx-25} {cy} L {card_x+card_w} {cy}" stroke="{col}" stroke-width="3" fill="none" opacity="0.5"/>'
        else:
            card_x = cx + 60
            # Connector
            svg += f'<path d="M {cx+25} {cy} L {card_x} {cy}" stroke="{col}" stroke-width="3" fill="none" opacity="0.5"/>'
            
        card_y = cy - card_h/2
        
        # Draw Card
        svg += f'<rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="12" fill="white" stroke="{col}" stroke-width="2" class="box-sd" style="animation-delay:{i*0.1+0.1:.2f}s"/>'
        
        # Title Background tab
        svg += f'<path d="M {card_x} {card_y+12} Q {card_x} {card_y} {card_x+12} {card_y} L {card_x+card_w-12} {card_y} Q {card_x+card_w} {card_y} {card_x+card_w} {card_y+12} L {card_x+card_w} {card_y+30} L {card_x} {card_y+30} Z" fill="{lighten(col,0.85)}"/>'
        svg += f'<text x="{card_x+15}" y="{card_y+20}" font-size="14" font-weight="900" fill="{darken(col,0.4)}">{xe(title)}</text>'
        
        # Subtitle
        svg += f'<text x="{card_x+15}" y="{card_y+45}" font-size="11" font-weight="700" fill="{darken(col,0.1)}">{xe(sub)}</text>'
        
        # Bullets
        for b_idx, bull in enumerate(bullets):
            svg += f'<circle cx="{card_x+20}" cy="{card_y+62+b_idx*16}" r="3" fill="{col}"/>'
            svg += f'<text x="{card_x+30}" y="{card_y+66+b_idx*16}" font-size="11" fill="#444">{xe(bull)}</text>'


    return _wrap(svg, W, H, topic_name, "Step-by-Step Learning Guide", accent, bg_top, bg_bot)

# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 15 — VERTICAL TIMELINE
# ══════════════════════════════════════════════════════════════════════════════
def _style_vertical_timeline(topic_id, topic_name, C):
    W, H = 1000, 1100
    accent = C[0]
    bg_top = lighten(accent, 0.96)
    bg_bot = lighten(accent, 0.98)

    svg = ""
    
    # Roadmap Steps (Title, subtitle, array of points). The layout from image: L, R, R, L, R, L, R, R
    STEPS = [
        ("1. What is Generative AI", "AI -> ML -> DL -> GenAI", ["Learn how models generate data", "Clarity saves months later"], "L"),
        ("2. Important Concepts", "Math Foundations", ["Probability & Stats", "Linear Algebra", "Calculus basics"], "R"),
        ("3. Foundation Models", "Get Hands-on", ["GPT, Llama, Gemini, Claude", "Understand training & usage"], "R"),
        ("4. GenAI Dev Stack", "Practical Tools", ["Python, LangChain", "Vector DBs, Hugging Face"], "L"),
        ("5. Training a Foundation Model", "The Lifecycle", ["Dataset -> Tokenization", "Training -> Eval -> Deploy"], "R"),
        ("6. Building AI Agents", "The Future is Agentic", ["Memory & Tool usage", "Autonomy + Human control"], "L"),
        ("7. GenAI Models for Computer Vision", "Text is just the start", ["GANs & Image Gen", "Vision + Language leap"], "R"),
        ("8. GenAI Learning Resources", "Build. Ship. Iterate.", ["DeepLearning.AI, Kaggle", "Google Labs, Nvidia"], "R")
    ]
    
    # Path coordinates
    cx = W/2
    y_start = 80
    y_step = 120
    
    # Main vertical dashed path
    svg += f'<line x1="{cx}" y1="{y_start-20}" x2="{cx}" y2="{H-50}" stroke="gray" stroke-width="8" class="flow" stroke-linecap="round"/>'
    svg += f'<line x1="{cx}" y1="{y_start-20}" x2="{cx}" y2="{H-50}" stroke="white" stroke-width="2" stroke-dasharray="12 12" stroke-linecap="round"/>'

    for i, (title, sub, bullets, side) in enumerate(STEPS):
        col = C[i % len(C)]
        cy = y_start + i * y_step
        
        # Determine Card position based on prescribed side
        is_left = (side == "L")
        card_w = 400
        card_h = 100
        
        if is_left:
            card_x = cx - card_w - 60
            # Connector dashed arrow
            svg += f'<path d="M {cx-10} {cy} L {card_x+card_w} {cy}" stroke="gray" stroke-width="3" stroke-dasharray="5 5" fill="none" class="flow"/>'
            svg += f'<polygon points="{card_x+card_w+5},{cy} {card_x+card_w-5},{cy-5} {card_x+card_w-5},{cy+5}" fill="gray"/>'
        else:
            card_x = cx + 60
            # Connector dashed arrow from timeline to card
            svg += f'<path d="M {cx+10} {cy} L {card_x} {cy}" stroke="gray" stroke-width="3" stroke-dasharray="5 5" fill="none" class="flow"/>'
            svg += f'<polygon points="{card_x-5},{cy} {card_x+5},{cy-5} {card_x+5},{cy+5}" fill="gray"/>'
            
        card_y = cy - card_h/2
        
        # Draw dotted background box
        svg += f'<rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="12" fill="white" stroke="{col}" stroke-width="3" stroke-dasharray="10 5" class="box-sd" style="animation-delay:{i*0.1:.2f}s"/>'
        
        # Header Badge
        header_w = 280
        hx = card_x + card_w/2 - header_w/2
        hy = card_y - 12
        svg += f'<rect x="{hx}" y="{hy}" width="{header_w}" height="24" rx="12" fill="{col}"/>'
        svg += f'<circle cx="{hx}" cy="{hy+12}" r="16" fill="{darken(col,0.3)}"/>'
        svg += f'<text x="{hx}" y="{hy+18}" text-anchor="middle" fill="white" font-size="16" font-weight="900">{i+1}</text>'
        
        # Render title properly inside badge
        parts = title.split(" ", 1)
        tit_text = parts[1] if len(parts) > 1 else title
        svg += f'<text x="{hx+25}" y="{hy+16}" text-anchor="start" fill="white" font-size="12" font-weight="800">{xe(tit_text)}</text>'
        
        # Subtitle and Info
        svg += f'<text x="{card_x+card_w/2}" y="{card_y+35}" text-anchor="middle" font-size="12" font-weight="800" fill="{darken(col,0.4)}">{xe(sub)}</text>'
        
        # Content elements
        box_w = 160
        left_bx = card_x + 20
        right_bx = card_x + card_w - box_w - 20
        
        # Left internal box
        svg += f'<rect x="{left_bx}" y="{card_y+50}" width="{box_w}" height="35" rx="6" fill="{lighten(col, 0.9)}"/>'
        svg += f'<text x="{left_bx+box_w/2}" y="{card_y+72}" text-anchor="middle" font-size="10" fill="gray" font-weight="600">{xe(bullets[0])}</text>'
        
        # Right internal box 
        if len(bullets) > 1:
            svg += f'<rect x="{right_bx}" y="{card_y+50}" width="{box_w}" height="35" rx="6" fill="{lighten(col, 0.95)}"/>'
            svg += f'<text x="{right_bx+box_w/2}" y="{card_y+72}" text-anchor="middle" font-size="10" fill="gray" font-weight="600">{xe(bullets[1])}</text>'

    return _wrap(svg, W, H, topic_name, "Concept & Tool Overview Strategy", accent, bg_top, bg_bot)
# ════════════════════════════════════════════════════════════════════════════
#  PASTE THESE 4 FUNCTIONS INTO diagram_generator.py
#  Location: right before the STYLES = [ list
# ════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 16 — INFOGRAPHIC PANELS  (white bg, coloured section boxes, dashed arrows)
#  Inspired by: RAG Design Patterns reference image
# ══════════════════════════════════════════════════════════════════════════════
def _style_infographic_panels(topic_id, topic_name, C, structure=None):
    W, H = 900, 680
    accent = C[0]
    bg = "#FAFAFA"
    sections = structure["sections"] if structure else [
        {"id":1,"label":"Pattern 1","desc":"First approach"},
        {"id":2,"label":"Pattern 2","desc":"Second approach"},
        {"id":3,"label":"Pattern 3","desc":"Third approach"},
        {"id":4,"label":"Pattern 4","desc":"Fourth approach"},
        {"id":5,"label":"Pattern 5","desc":"Fifth approach"},
        {"id":6,"label":"Pattern 6","desc":"Sixth approach"},
    ]
    subtitle = structure["subtitle"] if structure else "Key Patterns"

    svg = ""
    svg += f'<rect width="{W}" height="{H}" fill="{bg}"/>'
    svg += f'<rect x="0" y="0" width="6" height="{H}" fill="{accent}"/>'

    # Large title — two lines, mixed weight
    words = topic_name.split()
    mid = max(1, len(words)//2)
    t1 = " ".join(words[:mid]); t2 = " ".join(words[mid:])
    svg += f'<text x="30" y="48" fill="#111" font-size="32" font-weight="900" font-family="Arial,sans-serif">{xe(t1)}</text>'
    if t2:
        svg += f'<text x="30" y="82" fill="{accent}" font-size="28" font-weight="700" font-family="Arial,sans-serif">{xe(t2)}</text>'
    svg += f'<text x="30" y="108" fill="#888" font-size="13" font-family="Arial,sans-serif">{xe(subtitle)}</text>'
    svg += f'<line x1="30" y1="118" x2="{W-30}" y2="118" stroke="#E5E7EB" stroke-width="1.5"/>'

    n = len(sections)
    cols = 3 if n >= 5 else 2
    rows = math.ceil(n / cols)
    pad = 28; gap = 12
    avail_w = W - pad*2 - gap*(cols-1)
    avail_h = H - 130 - pad - gap*(rows-1)
    cw = avail_w // cols
    ch = avail_h // rows
    panel_colors = [C[i % len(C)] for i in range(n)]

    for i, sec in enumerate(sections):
        col_idx = i % cols; row_idx = i // cols
        px = pad + col_idx*(cw+gap)
        py = 130 + row_idx*(ch+gap)
        pc = panel_colors[i]
        delay = f"animation-delay:{i*0.08:.2f}s"

        svg += f'<rect x="{px}" y="{py}" width="{cw}" height="{ch}" rx="10" fill="white" stroke="{lighten(pc,0.55)}" stroke-width="1.5" class="fi" style="{delay}"/>'
        svg += f'<rect x="{px}" y="{py}" width="5" height="{ch}" rx="2" fill="{pc}"/>'
        pill_w = len(sec["label"])*8 + 20
        svg += f'<rect x="{px+14}" y="{py+12}" width="{pill_w}" height="22" rx="11" fill="{pc}"/>'
        svg += f'<text x="{px+24}" y="{py+27}" fill="white" font-size="10" font-weight="800" font-family="Arial,sans-serif">{xe(sec["label"])}</text>'
        svg += f'<circle cx="{px+cw-18}" cy="{py+18}" r="12" fill="{lighten(pc,0.85)}" stroke="{pc}" stroke-width="1.5"/>'
        svg += f'<text x="{px+cw-18}" y="{py+23}" text-anchor="middle" fill="{pc}" font-size="11" font-weight="900" font-family="Arial,sans-serif">{sec["id"]}</text>'
        desc_lines = wrap_lines(sec["desc"], cw//7)
        for li, ln in enumerate(desc_lines[:3]):
            svg += f'<text x="{px+14}" y="{py+50+li*16}" fill="#374151" font-size="11" font-family="Arial,sans-serif">{xe(ln)}</text>'

        if col_idx < cols-1 and i < n-1:
            ax1 = px+cw; ay = py+ch//2; ax2 = px+cw+gap
            svg += f'<line x1="{ax1}" y1="{ay}" x2="{ax2}" y2="{ay}" stroke="{lighten(pc,0.3)}" stroke-width="1.5" stroke-dasharray="4 3"/>'
            svg += f'<polygon points="{ax2+4},{ay} {ax2-4},{ay-4} {ax2-4},{ay+4}" fill="{lighten(pc,0.3)}"/>'

    svg += f'<rect x="0" y="{H-28}" width="{W}" height="28" fill="{lighten(accent,0.92)}"/>'
    svg += f'<text x="18" y="{H-10}" fill="#6B7280" font-size="9" font-family="Arial,sans-serif">{datetime.now().strftime("%B %Y")}</text>'
    svg += f'<rect x="{W-200}" y="{H-22}" width="188" height="16" rx="8" fill="{rgba(accent,0.15)}" stroke="{accent}" stroke-width="1"/>'
    svg += f'<text x="{W-106}" y="{H-11}" text-anchor="middle" fill="{accent}" font-size="8.5" font-weight="800" font-family="Arial,sans-serif">AI (c) Komal Batra</text>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="display:block;font-family:Arial,sans-serif">{ANIM}{svg}</svg>'


# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 17 — CHALKBOARD  (dark textured, chalk outlines, contrast sections)
#  Inspired by: "What is Agentic AI?" chalkboard image
# ══════════════════════════════════════════════════════════════════════════════
def _style_chalkboard(topic_id, topic_name, C, structure=None):
    W, H = 900, 660
    chalk_white = "#F5F0E8"; chalk_dim = "#C8BFA8"
    bg_dark = "#1A1F1A"; accent = C[0]
    sections = structure["sections"] if structure else [
        {"id":1,"label":"Concept A","desc":"First key idea"},
        {"id":2,"label":"Concept B","desc":"Second key idea"},
        {"id":3,"label":"Concept C","desc":"Third key idea"},
        {"id":4,"label":"Concept D","desc":"Fourth key idea"},
    ]
    subtitle = structure["subtitle"] if structure else ""
    mid = len(sections)//2
    not_group = sections[:mid] if mid > 0 else sections[:1]
    is_group   = sections[mid:] if mid > 0 else sections[1:]

    svg = ""
    svg += f'<rect width="{W}" height="{H}" fill="{bg_dark}"/>'
    for xi in range(0, W, 40):
        for yi in range(0, H, 40):
            svg += f'<circle cx="{xi+random.randint(-3,3)}" cy="{yi+random.randint(-3,3)}" r="0.4" fill="{chalk_dim}" opacity="0.15"/>'

    title_short = clamp(topic_name, 38)
    tw = len(title_short)*17 + 40
    svg += f'<rect x="{(W-tw)//2}" y="18" width="{tw}" height="46" rx="23" fill="none" stroke="{chalk_white}" stroke-width="2.5"/>'
    svg += f'<text x="{W//2}" y="49" text-anchor="middle" fill="{chalk_white}" font-size="24" font-weight="900" font-family="Georgia,serif">{xe(title_short)}</text>'
    if subtitle:
        svg += f'<text x="{W//2}" y="82" text-anchor="middle" fill="{chalk_dim}" font-size="12" font-family="Arial,sans-serif">{xe(subtitle)}</text>'

    box1_y = 96; box1_h = max(120, len(not_group)*70)
    svg += f'<rect x="24" y="{box1_y}" width="{W//2-36}" height="{box1_h}" rx="8" fill="{rgba(chalk_white,0.04)}" stroke="{chalk_dim}" stroke-width="1.5" stroke-dasharray="8 4"/>'
    svg += f'<rect x="40" y="{box1_y-9}" width="140" height="18" rx="9" fill="{bg_dark}"/>'
    svg += f'<text x="48" y="{box1_y+3}" fill="#E57373" font-size="11" font-weight="700" font-family="Arial,sans-serif">These are NOT ›</text>'

    for i, sec in enumerate(not_group):
        sy = box1_y + 20 + i*68
        svg += f'<text x="40" y="{sy+14}" fill="{chalk_white}" font-size="14" font-weight="800" font-family="Arial,sans-serif">{xe(sec["label"])}</text>'
        desc_parts = sec["desc"].split("→") if "→" in sec["desc"] else [sec["desc"]]
        for pi, part in enumerate(desc_parts[:4]):
            bx = 40 + pi*120
            svg += f'<rect x="{bx}" y="{sy+22}" width="110" height="26" rx="5" fill="none" stroke="{chalk_dim}" stroke-width="1"/>'
            svg += f'<text x="{bx+55}" y="{sy+39}" text-anchor="middle" fill="{chalk_dim}" font-size="9" font-family="Arial,sans-serif">{xe(clamp(part.strip(),14))}</text>'
            if pi < len(desc_parts)-1:
                svg += f'<line x1="{bx+110}" y1="{sy+35}" x2="{bx+120}" y2="{sy+35}" stroke="{chalk_dim}" stroke-width="1.5"/>'
                svg += f'<polygon points="{bx+122},{sy+35} {bx+118},{sy+32} {bx+118},{sy+38}" fill="{chalk_dim}"/>'

    box2_y = 96; box2_w = W//2 - 36; box2_x = W//2 + 12
    box2_h = max(120, len(is_group)*80 + 40)
    svg += f'<rect x="{box2_x}" y="{box2_y}" width="{box2_w}" height="{box2_h}" rx="8" fill="{rgba(accent,0.08)}" stroke="{accent}" stroke-width="2" stroke-dasharray="10 4"/>'
    svg += f'<rect x="{box2_x+16}" y="{box2_y-9}" width="140" height="18" rx="9" fill="{bg_dark}"/>'
    svg += f'<text x="{box2_x+24}" y="{box2_y+3}" fill="{accent}" font-size="11" font-weight="700" font-family="Arial,sans-serif">This IS ›</text>'

    for i, sec in enumerate(is_group):
        sy = box2_y + 20 + i*76
        svg += f'<text x="{box2_x+14}" y="{sy+14}" fill="{chalk_white}" font-size="13" font-weight="800" font-family="Arial,sans-serif">{xe(sec["label"])}</text>'
        components = sec["desc"].split("+") if "+" in sec["desc"] else sec["desc"].split(",")
        n_comp = min(len(components), 4)
        comp_w = (box2_w-28) // n_comp
        for ci, comp in enumerate(components[:4]):
            bx = box2_x+14 + ci*comp_w
            svg += f'<rect x="{bx}" y="{sy+20}" width="{comp_w-4}" height="32" rx="6" fill="{rgba(accent,0.15)}" stroke="{accent}" stroke-width="1"/>'
            svg += f'<text x="{bx+comp_w//2}" y="{sy+40}" text-anchor="middle" fill="{chalk_white}" font-size="9" font-weight="700" font-family="Arial,sans-serif">{xe(clamp(comp.strip(),12))}</text>'

    svg += f'<text x="18" y="{H-10}" fill="{chalk_dim}" font-size="9" font-family="Arial,sans-serif">{datetime.now().strftime("%B %Y")}</text>'
    svg += f'<text x="{W-18}" y="{H-10}" text-anchor="end" fill="{accent}" font-size="9" font-weight="800" font-family="Arial,sans-serif">AI (c) Komal Batra</text>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="display:block;font-family:Arial,sans-serif">{ANIM}{svg}</svg>'


# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 18 — DARK COLUMN FLOW  (black bg, 3 accent columns, circle nodes)
#  Inspired by: "RAG vs Agentic RAG vs AI Memory" evolution image
# ══════════════════════════════════════════════════════════════════════════════
def _style_dark_column_flow(topic_id, topic_name, C, structure=None):
    W, H = 900, 660
    bg = "#0D0D0D"; accent = C[0]
    sections = structure["sections"] if structure else [
        {"id":1,"label":"Approach A","desc":"Step 1 → Step 2 → Step 3"},
        {"id":2,"label":"Approach B","desc":"Step 1 → Branch → Step 3"},
        {"id":3,"label":"Approach C","desc":"Step 1 → Memory → Step 3"},
    ]
    subtitle = structure["subtitle"] if structure else ""
    n_cols = min(len(sections), 3)
    col_colors = [C[i % len(C)] for i in range(n_cols)]
    col_w = (W - 60) // n_cols
    node_r = 22

    svg = ""
    svg += f'<rect width="{W}" height="{H}" fill="{bg}"/>'
    svg += f'<text x="{W//2}" y="38" text-anchor="middle" fill="white" font-size="22" font-weight="900" font-family="Arial,sans-serif">{xe(clamp(topic_name,48))}</text>'
    if subtitle:
        svg += f'<text x="{W//2}" y="58" text-anchor="middle" fill="#888" font-size="12" font-family="Arial,sans-serif">{xe(subtitle)}</text>'

    for ci in range(n_cols):
        sec = sections[ci]; col = col_colors[ci]
        cx = 30 + ci*col_w + col_w//2
        if ci > 0:
            svg += f'<line x1="{30+ci*col_w}" y1="70" x2="{30+ci*col_w}" y2="{H-30}" stroke="#333" stroke-width="1" stroke-dasharray="6 4"/>'
        hw = len(sec["label"])*9+24
        svg += f'<rect x="{cx-hw//2}" y="70" width="{hw}" height="26" rx="13" fill="{col}" opacity="0.9"/>'
        svg += f'<text x="{cx}" y="87" text-anchor="middle" fill="white" font-size="11" font-weight="800" font-family="Arial,sans-serif">{xe(sec["label"])}</text>'

        steps = [s.strip() for s in sec["desc"].replace("→","|").split("|")]
        n_steps = len(steps)
        avail_h = H - 140
        step_gap = min(90, avail_h // max(n_steps, 1))
        start_y = 118

        for si, step in enumerate(steps):
            ny = start_y + si*step_gap
            delay = f"animation-delay:{ci*0.15+si*0.1:.2f}s"
            if si > 0:
                prev_y = start_y + (si-1)*step_gap
                svg += f'<line x1="{cx}" y1="{prev_y+node_r}" x2="{cx}" y2="{ny-node_r}" stroke="{col}" stroke-width="2" class="flow" style="{delay}"/>'
                svg += f'<polygon points="{cx},{ny-node_r+2} {cx-5},{ny-node_r-6} {cx+5},{ny-node_r-6}" fill="{col}"/>'

            if "," in step and si == n_steps-2:
                branches = [b.strip() for b in step.split(",")]
                branch_spacing = 80
                bstart = cx - (len(branches)-1)*branch_spacing//2
                for bi, branch in enumerate(branches):
                    bx = bstart + bi*branch_spacing
                    svg += f'<line x1="{cx}" y1="{ny-node_r}" x2="{bx}" y2="{ny}" stroke="{col}" stroke-width="1.5" stroke-dasharray="4 2"/>'
                    svg += f'<circle cx="{bx}" cy="{ny}" r="{node_r-6}" fill="{rgba(col,0.2)}" stroke="{col}" stroke-width="1.5" class="fi" style="{delay}"/>'
                    svg += f'<text x="{bx}" y="{ny+4}" text-anchor="middle" fill="{col}" font-size="8" font-weight="700" font-family="Arial,sans-serif">{xe(clamp(branch,10))}</text>'
            else:
                svg += f'<circle cx="{cx}" cy="{ny}" r="{node_r}" fill="{rgba(col,0.18)}" stroke="{col}" stroke-width="2" class="fi" style="{delay}"/>'
                svg += f'<circle cx="{cx}" cy="{ny}" r="{node_r-5}" fill="{rgba(col,0.08)}"/>'
                label_lines = wrap_lines(step, 12)
                for li, ln in enumerate(label_lines[:2]):
                    svg += f'<text x="{cx}" y="{ny+node_r+14+li*13}" text-anchor="middle" fill="{lighten(col,0.5)}" font-size="9.5" font-family="Arial,sans-serif">{xe(ln)}</text>'

    svg += f'<text x="18" y="{H-8}" fill="#555" font-size="9" font-family="Arial,sans-serif">{datetime.now().strftime("%B %Y")}</text>'
    svg += f'<text x="{W-18}" y="{H-8}" text-anchor="end" fill="{C[0]}" font-size="9" font-weight="800" font-family="Arial,sans-serif">AI (c) Komal Batra</text>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="display:block;font-family:Arial,sans-serif">{ANIM}{svg}</svg>'


# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 19 — THREE PANEL  (3 unequal bordered panels, bold headers, numbered steps)
#  Inspired by: Docker Client/Host/Hub infographic image
# ══════════════════════════════════════════════════════════════════════════════
def _style_three_panel(topic_id, topic_name, C, structure=None):
    W, H = 900, 620
    bg = "#F8F9FA"; accent = C[0]
    sections = structure["sections"] if structure else [
        {"id":1,"label":"Component 1","desc":"First player in the system"},
        {"id":2,"label":"Component 2","desc":"Second player in the system"},
        {"id":3,"label":"Component 3","desc":"Third player in the system"},
    ]
    subtitle = structure["subtitle"] if structure else ""
    n_panels = min(len(sections), 3)
    widths = [220, 270, 220] if n_panels == 3 else ([340, 340] if n_panels == 2 else [W-60])
    gaps = 15
    total_w = sum(widths) + gaps*(n_panels-1)
    start_x = (W - total_w)//2

    svg = ""
    svg += f'<rect width="{W}" height="{H}" fill="{bg}"/>'
    svg += f'<rect x="18" y="16" width="60" height="22" rx="4" fill="{C[0]}"/>'
    svg += f'<text x="48" y="31" text-anchor="middle" fill="white" font-size="10" font-weight="800" font-family="Arial,sans-serif">komalb</text>'

    words = topic_name.split()
    bold_words = words[:2]; rest_words = words[2:]
    svg += f'<text x="90" y="32" fill="#111" font-size="18" font-weight="400" font-family="Arial,sans-serif">Inside the <tspan font-weight="900" fill="{C[0]}">{xe(" ".join(bold_words))}</tspan> {xe(" ".join(rest_words))}</text>'

    px = start_x
    for i in range(n_panels):
        pw = widths[i]; pc = C[i % len(C)]; sec = sections[i]
        panel_h = H - 100
        svg += f'<rect x="{px}" y="56" width="{pw}" height="{panel_h}" rx="10" fill="white" stroke="{lighten(pc,0.5)}" stroke-width="1.5"/>'
        svg += f'<rect x="{px}" y="56" width="{pw}" height="36" rx="10" fill="{pc}"/>'
        svg += f'<rect x="{px}" y="74" width="{pw}" height="18" fill="{pc}"/>'
        svg += f'<text x="{px+pw//2}" y="79" text-anchor="middle" fill="white" font-size="12" font-weight="900" letter-spacing="1" font-family="Arial,sans-serif">{xe(sec["label"].upper())}</text>'

        content_lines = sec["desc"].split(",") if "," in sec["desc"] else [sec["desc"]]
        for ci2, line in enumerate(content_lines[:4]):
            ly = 110 + ci2*52
            svg += f'<rect x="{px+12}" y="{ly}" width="{pw-24}" height="40" rx="6" fill="{lighten(pc,0.90)}" stroke="{lighten(pc,0.6)}" stroke-width="1"/>'
            svg += f'<rect x="{px+12}" y="{ly}" width="4" height="40" rx="2" fill="{pc}"/>'
            lns = wrap_lines(line.strip(), (pw-30)//7)
            for li2, ln in enumerate(lns[:2]):
                svg += f'<text x="{px+22}" y="{ly+16+li2*14}" fill="#1F2937" font-size="10" font-weight="600" font-family="Arial,sans-serif">{xe(ln)}</text>'

        if i < n_panels-1:
            ax = px+pw+2; ay = 56+panel_h//2
            svg += f'<polygon points="{ax+gaps},{ay} {ax+4},{ay-10} {ax+4},{ay+10}" fill="{pc}"/>'
            svg += f'<line x1="{ax}" y1="{ay}" x2="{ax+gaps}" y2="{ay}" stroke="{pc}" stroke-width="3"/>'
        px += pw + gaps

    step_y = H - 38
    svg += f'<rect x="0" y="{step_y-12}" width="{W}" height="50" fill="{lighten(C[0],0.94)}"/>'
    col_w2 = W // max(n_panels, 1)
    for si in range(n_panels):
        sec = sections[si]; sx = 18 + si*col_w2
        svg += f'<circle cx="{sx+10}" cy="{step_y+6}" r="9" fill="{C[si%len(C)]}"/>'
        svg += f'<text x="{sx+10}" y="{step_y+10}" text-anchor="middle" fill="white" font-size="9" font-weight="900" font-family="Arial,sans-serif">{si+1}</text>'
        svg += f'<text x="{sx+24}" y="{step_y+10}" fill="#374151" font-size="9" font-family="Arial,sans-serif">{xe(clamp(sec["desc"], col_w2//6))}</text>'

    svg += f'<rect x="0" y="{H-22}" width="{W}" height="22" fill="{C[0]}"/>'
    svg += f'<text x="18" y="{H-7}" fill="white" font-size="9" font-family="Arial,sans-serif">{datetime.now().strftime("%B %Y")}</text>'
    svg += f'<text x="{W-18}" y="{H-7}" text-anchor="end" fill="white" font-size="9" font-weight="800" font-family="Arial,sans-serif">AI (c) Komal Batra</text>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="display:block;font-family:Arial,sans-serif">{ANIM}{svg}</svg>'

# ══════════════════════════════════════════════════════════════════════════════
#  DISPATCH — pick style per topic (override map + hash fallback)
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
#  STYLE 20 — NOTEBOOK SKETCH
#  Hand-drawn notebook aesthetic: spiral binding, ruled lines, serif titles,
#  light-tint boxes with thin borders, inline glyphs, mixed font stack.
#
#  HOW TO USE:
#  1. Paste this function into diagram_generator.py (before the STYLES list)
#  2. Add  _style_notebook  to the STYLES list as entry [20]
#  3. Add topic overrides to TOPIC_STYLE_OVERRIDES as needed, e.g.:
#        "system-design": 20,
#        "enterprise-ai": 20,
#
#  The function accepts the standard (topic_id, topic_name, C) signature
#  plus an optional `structure` dict for custom layouts (see below).
#
#  Optional `structure` dict shape:
#  {
#    "subtitle": "optional subtitle text",
#    "rows": [
#       {
#         "label": "Row Header",           # italic section label (top-left)
#         "type": "banner",                 # "banner" | "columns" | "datastores" | "obs"
#         "color": "#D0EAFE",              # fill colour for banner rows
#         "border": "#185FA5",             # stroke colour for banner rows
#         "text_color": "#0C447C",         # text colour for banner rows
#         "columns": [                     # for type="columns"
#           {
#             "glyph": "≡",               # prefix glyph
#             "title": "Col Title",
#             "items": ["item 1", "item 2", "item 3"]
#           },
#           ...
#         ],
#         "items": ["item 1", "item 2"],   # for type="obs" (flat text lines)
#       },
#       ...
#    ]
#  }
#
#  Without a structure dict the function uses built-in topic data (see
#  NOTEBOOK_DATA below) and falls back to a generic system-design layout.
# ══════════════════════════════════════════════════════════════════════════════

import math as _math

# ── Topic data ─────────────────────────────────────────────────────────────────
# Each entry drives the notebook layout for a matched topic_id keyword.
# Keys must match substrings in topic_id.lower() or topic_name.lower().

_NOTEBOOK_DATA = {
    # ── Enterprise / System Design ──────────────────────────────────────────
    "enterprise": {
        "subtitle": "High-level reference architecture",
        "rows": [
            {
                "label": "1. User Layer",
                "type": "chips",
                "chips": ["AI Developer", "Business User", "Employee", "AI Admin"],
                "chip_color": "#EEF2FF", "chip_border": "#7F77DD", "chip_text": "#3C3489",
            },
            {
                "label": "2. API Gateway & Identity",
                "type": "banner",
                "text": "GPT Gateway API — OAuth2 / OIDC · RBAC / Zero Trust",
                "color": "#E0F2E9", "border": "#0F6E56", "text_color": "#085041",
            },
            {
                "label": "3. Core Components",
                "type": "columns",
                "columns": [
                    {"glyph": "≡", "title": "RAG Ingestion",
                     "items": ["Doc Parsing", "Chunking", "Embedding + Index"]},
                    {"glyph": "⇄", "title": "Model Routing",
                     "items": ["Cost / Latency opt.", "Mistral · OpenAI", "Claude · Local"]},
                    {"glyph": "□", "title": "AI Guardrails",
                     "items": ["Prompt Injection", "PII Filtering", "Output Validation"]},
                ],
            },
            {
                "label": "4. Processing",
                "type": "columns",
                "columns": [
                    {"glyph": "⚙", "title": "LLM Processing",
                     "items": ["LLM API → Model", "Vector DB · Docs", "Knowledge Base"]},
                    {"glyph": "🤖", "title": "Agentic AI Flow",
                     "items": ["Task Planner Agent", "Tool Selection", "Execution Agent"]},
                ],
            },
            {
                "label": "5. Observability & Governance",
                "type": "obs",
                "items": [
                    "Monitoring · Logging · Tracing · Model Governance",
                    "Token Usage, Prompt Tracing, Evaluation Datasets, Hallucination Monitoring",
                ],
                "color": "#F3EBF9", "border": "#7F77DD", "text_color": "#3C3489",
            },
        ],
    },
    # ── System Design ───────────────────────────────────────────────────────
    "system": {
        "subtitle": "Scalable distributed system blueprint",
        "rows": [
            {
                "label": "Clients",
                "type": "chips",
                "chips": ["Browser", "Mobile", "Desktop", "IoT"],
                "chip_color": "#EEF2FF", "chip_border": "#7F77DD", "chip_text": "#3C3489",
            },
            {
                "label": "Edge",
                "type": "banner",
                "text": "CDN · Load Balancer · API Gateway · WAF",
                "color": "#E0F2E9", "border": "#0F6E56", "text_color": "#085041",
            },
            {
                "label": "Services",
                "type": "columns",
                "columns": [
                    {"glyph": "⚙", "title": "Core Services",
                     "items": ["User Svc", "Order Svc", "Payment Svc"]},
                    {"glyph": "✉", "title": "Messaging",
                     "items": ["Kafka", "RabbitMQ", "Redis PubSub"]},
                    {"glyph": "🗄", "title": "Data Layer",
                     "items": ["PostgreSQL", "Redis Cache", "S3 Storage"]},
                ],
            },
            {
                "label": "Observability",
                "type": "obs",
                "items": [
                    "Prometheus · Grafana · Jaeger · PagerDuty",
                    "SLO tracking, distributed tracing, anomaly alerts",
                ],
                "color": "#F3EBF9", "border": "#7F77DD", "text_color": "#3C3489",
            },
        ],
    },
    # ── Kubernetes ──────────────────────────────────────────────────────────
    "kube": {
        "subtitle": "Kubernetes cluster architecture",
        "rows": [
            {
                "label": "Control Plane",
                "type": "chips",
                "chips": ["API Server", "etcd", "Scheduler", "Controller Mgr"],
                "chip_color": "#E0F2E9", "chip_border": "#0F6E56", "chip_text": "#085041",
            },
            {
                "label": "Worker Nodes",
                "type": "banner",
                "text": "Kubelet · kube-proxy · containerd · CNI plugin",
                "color": "#D0EAFE", "border": "#185FA5", "text_color": "#0C447C",
            },
            {
                "label": "Workloads",
                "type": "columns",
                "columns": [
                    {"glyph": "□", "title": "Compute",
                     "items": ["Deployment", "StatefulSet", "DaemonSet", "CronJob"]},
                    {"glyph": "⇄", "title": "Networking",
                     "items": ["Service", "Ingress", "NetworkPolicy", "Istio"]},
                    {"glyph": "🗄", "title": "Storage",
                     "items": ["PersistentVol", "StorageClass", "ConfigMap", "Secret"]},
                ],
            },
            {
                "label": "Observability",
                "type": "obs",
                "items": [
                    "Prometheus · Grafana · Loki · OpenTelemetry",
                    "HPA autoscaling, RBAC policies, Helm chart releases",
                ],
                "color": "#F3EBF9", "border": "#7F77DD", "text_color": "#3C3489",
            },
        ],
    },
    # ── RAG ─────────────────────────────────────────────────────────────────
    "rag": {
        "subtitle": "Retrieval-Augmented Generation pipeline",
        "rows": [
            {
                "label": "Ingestion",
                "type": "chips",
                "chips": ["PDF / HTML", "Databases", "APIs", "Streaming"],
                "chip_color": "#EEF2FF", "chip_border": "#7F77DD", "chip_text": "#3C3489",
            },
            {
                "label": "Processing",
                "type": "banner",
                "text": "Chunking · Overlap · Embedding (text-embed-3) · Schema Registry",
                "color": "#D0EAFE", "border": "#185FA5", "text_color": "#0C447C",
            },
            {
                "label": "Retrieval & Generation",
                "type": "columns",
                "columns": [
                    {"glyph": "🔍", "title": "Vector Store",
                     "items": ["Pinecone", "Weaviate", "pgvector", "FAISS"]},
                    {"glyph": "⇄", "title": "Retrieval",
                     "items": ["BM25 + Dense", "Cross-encoder rerank", "Hybrid search"]},
                    {"glyph": "✦", "title": "LLM Generation",
                     "items": ["Grounded answer", "Citation sources", "Hallucination check"]},
                ],
            },
            {
                "label": "Evaluation",
                "type": "obs",
                "items": [
                    "RAGAS · LangSmith · Faithfulness · Answer Relevance",
                    "Latency tracking, context precision, retrieval recall metrics",
                ],
                "color": "#E0F2E9", "border": "#0F6E56", "text_color": "#085041",
            },
        ],
    },
    # ── DevOps / CI-CD ──────────────────────────────────────────────────────
    "devops": {
        "subtitle": "Modern CI/CD + DevOps toolchain",
        "rows": [
            {
                "label": "Source",
                "type": "chips",
                "chips": ["GitHub", "GitLab", "Bitbucket", "Azure DevOps"],
                "chip_color": "#F1EFE8", "chip_border": "#888780", "chip_text": "#2C2C2A",
            },
            {
                "label": "CI Pipeline",
                "type": "banner",
                "text": "Lint → Build → Unit Test → SAST → Docker Build → Push",
                "color": "#E0F2E9", "border": "#0F6E56", "text_color": "#085041",
            },
            {
                "label": "CD + Deploy",
                "type": "columns",
                "columns": [
                    {"glyph": "⚙", "title": "Packaging",
                     "items": ["Docker multi-stage", "Helm chart", "Kustomize overlay"]},
                    {"glyph": "🛡", "title": "Security Gates",
                     "items": ["Trivy CVE scan", "Snyk SCA", "OPA policy"]},
                    {"glyph": "🚀", "title": "Release",
                     "items": ["Blue/Green", "Canary 5%→100%", "Auto-rollback"]},
                ],
            },
            {
                "label": "Observability",
                "type": "obs",
                "items": [
                    "Prometheus · Grafana · DORA metrics · PagerDuty",
                    "Deployment frequency, change failure rate, MTTR tracking",
                ],
                "color": "#F3EBF9", "border": "#7F77DD", "text_color": "#3C3489",
            },
        ],
    },
}

# ── Colour helpers (duplicated here for self-containment; already in scope) ──

def _nb_lighten(hex_color, pct=0.88):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = int(r + (255 - r) * pct)
    g = int(g + (255 - g) * pct)
    b = int(b + (255 - b) * pct)
    return f"#{r:02X}{g:02X}{b:02X}"

def _nb_darken(hex_color, pct=0.25):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"#{int(r*(1-pct)):02X}{int(g*(1-pct)):02X}{int(b*(1-pct)):02X}"

def _nb_xe(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _nb_clamp(text, n):
    text = str(text)
    return text if len(text) <= n else text[:n - 1] + "…"


# ── Notebook background helpers ───────────────────────────────────────────────

def _nb_background(W, H):
    """Returns SVG string for notebook paper: off-white bg, ruled lines, binding."""
    svg = f'<rect x="0" y="0" width="{W}" height="{H}" fill="#FAFAF5"/>'
    # Ruled lines every 28px
    for yi in range(60, H, 28):
        svg += f'<line x1="36" y1="{yi}" x2="{W-12}" y2="{yi}" stroke="#EBEBDF" stroke-width="0.5"/>'
    # Binding margin line
    svg += f'<line x1="30" y1="0" x2="30" y2="{H}" stroke="#E2E2D8" stroke-width="1"/>'
    # Spiral dots
    for yi in range(28, H, 28):
        svg += f'<circle cx="16" cy="{yi}" r="4.5" fill="none" stroke="#C4C4B8" stroke-width="1.2"/>'
    return svg


def _nb_title(W, title, subtitle):
    """Returns SVG for serif title + underline + optional subtitle."""
    svg = (
        f'<text x="{W//2}" y="32" text-anchor="middle" '
        f'font-family="Georgia,serif" font-size="17" font-weight="700" '
        f'fill="#1A1A1A" letter-spacing="1.5">{_nb_xe(title.upper())}</text>'
    )
    svg += f'<line x1="60" y1="42" x2="{W-60}" y2="42" stroke="#1A1A1A" stroke-width="0.8"/>'
    if subtitle:
        svg += (
            f'<text x="{W//2}" y="56" text-anchor="middle" '
            f'font-family="Arial,sans-serif" font-size="10" fill="#888" '
            f'font-style="italic">{_nb_xe(subtitle)}</text>'
        )
    return svg


def _nb_footer(W, H, author):
    """Bottom rule + copyright credit."""
    svg = f'<line x1="42" y1="{H-20}" x2="{W-42}" y2="{H-20}" stroke="#D3D1C7" stroke-width="0.6"/>'
    svg += (
        f'<text x="{W-42}" y="{H-7}" text-anchor="end" '
        f'font-family="Georgia,serif" font-size="11" fill="#888" '
        f'font-style="italic">{_nb_xe(f"AI (c) {_COPYRIGHT_NAME}")}</text>'
    )
    return svg


# ── Row renderers ─────────────────────────────────────────────────────────────

def _nb_row_label(x, y, text):
    return (
        f'<text x="{x}" y="{y}" font-family="Georgia,serif" font-size="10" '
        f'fill="#999" font-style="italic">{_nb_xe(text)}</text>'
    )


def _nb_chips_row(x, y, W, chips, chip_color, chip_border, chip_text):
    """Row of evenly-spaced rounded chips, arrow below centre."""
    n = len(chips)
    usable = W - x - 50
    chip_w = min(130, (usable - (n - 1) * 12) // n)
    chip_h = 28
    gap = (usable - n * chip_w) // max(n - 1, 1)
    svg = ""
    for i, label in enumerate(chips):
        cx = x + i * (chip_w + gap)
        svg += (
            f'<rect x="{cx}" y="{y}" width="{chip_w}" height="{chip_h}" rx="4" '
            f'fill="{chip_color}" stroke="{chip_border}" stroke-width="0.8"/>'
            f'<text x="{cx + chip_w//2}" y="{y + chip_h//2 + 4}" text-anchor="middle" '
            f'font-family="Arial,sans-serif" font-size="10" font-weight="600" '
            f'fill="{chip_text}">{_nb_xe(_nb_clamp(label, 16))}</text>'
        )
    centre_x = x + (usable) // 2
    arrow_y1 = y + chip_h
    arrow_y2 = arrow_y1 + 12
    svg += (
        f'<line x1="{centre_x}" y1="{arrow_y1}" x2="{centre_x}" y2="{arrow_y2}" '
        f'stroke="#AAAAAA" stroke-width="1.2" marker-end="url(#nbarrow)"/>'
    )
    return svg, arrow_y2


def _nb_banner_row(x, y, W, text, color, border, text_color):
    """Full-width banner with text, arrow below centre."""
    bw = W - x - 50
    bh = 32
    svg = (
        f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="4" '
        f'fill="{color}" stroke="{border}" stroke-width="1.1"/>'
        f'<text x="{x + bw//2}" y="{y + bh//2 + 4}" text-anchor="middle" '
        f'font-family="Arial,sans-serif" font-size="11" font-weight="700" '
        f'fill="{text_color}">{_nb_xe(_nb_clamp(text, 72))}</text>'
    )
    centre_x = x + bw // 2
    arrow_y1 = y + bh
    arrow_y2 = arrow_y1 + 12
    svg += (
        f'<line x1="{centre_x}" y1="{arrow_y1}" x2="{centre_x}" y2="{arrow_y2}" '
        f'stroke="#AAAAAA" stroke-width="1.2" marker-end="url(#nbarrow)"/>'
    )
    return svg, arrow_y2


def _nb_columns_row(x, y, W, columns):
    """2–4 columns side by side, each with glyph + title + item list."""
    n = len(columns)
    usable = W - x - 50
    col_w = (usable - (n - 1) * 14) // n
    col_h = 20 + len(max(columns, key=lambda c: len(c["items"]))["items"]) * 16 + 8
    col_h = max(col_h, 70)

    svg = ""
    for i, col_def in enumerate(columns):
        cx = x + i * (col_w + 14)
        svg += (
            f'<rect x="{cx}" y="{y}" width="{col_w}" height="{col_h}" rx="4" '
            f'fill="#FAFAF0" stroke="#C4C4B8" stroke-width="0.8"/>'
        )
        # Glyph + title header
        glyph = col_def.get("glyph", "•")
        title = col_def.get("title", "")
        svg += (
            f'<text x="{cx + 10}" y="{y + 16}" '
            f'font-family="Arial,sans-serif" font-size="11" font-weight="700" '
            f'fill="#2C2C2A">{_nb_xe(glyph)} {_nb_xe(_nb_clamp(title, 18))}</text>'
        )
        # Items
        for j, item in enumerate(col_def.get("items", [])[:5]):
            svg += (
                f'<text x="{cx + 12}" y="{y + 32 + j*16}" '
                f'font-family="Arial,sans-serif" font-size="9.5" fill="#5F5E5A">'
                f'• {_nb_xe(_nb_clamp(item, 22))}</text>'
            )
    # Arrow from centre column down
    centre_x = x + usable // 2
    arrow_y1 = y + col_h
    arrow_y2 = arrow_y1 + 12
    svg += (
        f'<line x1="{centre_x}" y1="{arrow_y1}" x2="{centre_x}" y2="{arrow_y2}" '
        f'stroke="#AAAAAA" stroke-width="1.2" marker-end="url(#nbarrow)"/>'
    )
    return svg, arrow_y2, col_h


def _nb_obs_row(x, y, W, items, color, border, text_color):
    """Observability / notes banner with multiple text lines."""
    line_h = 16
    bh = 14 + len(items) * line_h + 8
    bw = W - x - 50
    svg = (
        f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="4" '
        f'fill="{color}" stroke="{border}" stroke-width="1"/>'
    )
    for i, item in enumerate(items):
        weight = "700" if i == 0 else "400"
        size = "10" if i == 0 else "9.5"
        fill = text_color if i == 0 else "#5F5E5A"
        svg += (
            f'<text x="{x + 12}" y="{y + 14 + i * line_h}" '
            f'font-family="Arial,sans-serif" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}">'
            f'{_nb_xe(_nb_clamp(item, 90))}</text>'
        )
    return svg, y + bh


# ── Main function ─────────────────────────────────────────────────────────────

def _style_notebook(topic_id, topic_name, C, structure=None):
    """
    Style 20 — Notebook Sketch.
    Renders a hand-drawn notebook diagram with spiral binding, ruled lines,
    serif titles, and thin-border sketch boxes.
    """
    # ── Pick data ────────────────────────────────────────────────────────────
    if structure and "rows" in structure:
        data = structure
    else:
        tid = topic_id.lower()
        name_lower = topic_name.lower()
        data = None
        for key, val in _NOTEBOOK_DATA.items():
            if key in tid or key in name_lower:
                data = val
                break
        if data is None:
            data = _NOTEBOOK_DATA["system"]

    subtitle = data.get("subtitle", "")
    rows = data.get("rows", [])

    # ── Layout pass: measure total height ────────────────────────────────────
    W = 680
    MARGIN_LEFT = 42
    LABEL_H = 16   # height of the italic row label
    ARROW_H = 14   # gap for the downward arrow between rows
    GAP = 10       # gap between rows

    # Estimate height
    H_est = 80  # title block
    for row in rows:
        H_est += LABEL_H
        rt = row.get("type", "banner")
        if rt == "chips":
            H_est += 28 + ARROW_H + GAP
        elif rt == "banner":
            H_est += 32 + ARROW_H + GAP
        elif rt == "columns":
            cols = row.get("columns", [])
            max_items = max((len(c.get("items", [])) for c in cols), default=0)
            col_h = 20 + max_items * 16 + 8
            col_h = max(col_h, 70)
            H_est += col_h + ARROW_H + GAP
        elif rt == "obs":
            items = row.get("items", [])
            H_est += 14 + len(items) * 16 + 8 + GAP
    H_est += 40  # footer

    H = max(H_est, 400)

    # ── Start building SVG ───────────────────────────────────────────────────
    inner = ""

    # Arrow marker (local id to avoid collision with parent page markers)
    inner += (
        '<defs>'
        '<marker id="nbarrow" viewBox="0 0 10 10" refX="8" refY="5" '
        'markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
        '<path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        '</marker>'
        '</defs>'
    )

    # Background
    inner += _nb_background(W, H)

    # Title
    inner += _nb_title(W, topic_name, subtitle)

    # ── Render rows ──────────────────────────────────────────────────────────
    y = 68

    for row in rows:
        label = row.get("label", "")
        rt = row.get("type", "banner")

        if label:
            inner += _nb_row_label(MARGIN_LEFT, y + LABEL_H - 2, label)
            y += LABEL_H

        if rt == "chips":
            chunk, y_after = _nb_chips_row(
                MARGIN_LEFT, y, W,
                chips=row.get("chips", []),
                chip_color=row.get("chip_color", "#EEF2FF"),
                chip_border=row.get("chip_border", "#7F77DD"),
                chip_text=row.get("chip_text", "#3C3489"),
            )
            inner += chunk
            y = y_after + GAP

        elif rt == "banner":
            chunk, y_after = _nb_banner_row(
                MARGIN_LEFT, y, W,
                text=row.get("text", ""),
                color=row.get("color", "#E0F2E9"),
                border=row.get("border", "#0F6E56"),
                text_color=row.get("text_color", "#085041"),
            )
            inner += chunk
            y = y_after + GAP

        elif rt == "columns":
            chunk, y_after, col_h = _nb_columns_row(
                MARGIN_LEFT, y, W,
                columns=row.get("columns", []),
            )
            inner += chunk
            y = y_after + GAP

        elif rt == "obs":
            chunk, y_after = _nb_obs_row(
                MARGIN_LEFT, y, W,
                items=row.get("items", []),
                color=row.get("color", "#F3EBF9"),
                border=row.get("border", "#7F77DD"),
                text_color=row.get("text_color", "#3C3489"),
            )
            inner += chunk
            y = y_after + GAP

    # Footer
    inner += _nb_footer(W, H, _DIAGRAM_AUTHOR)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'style="display:block;font-family:Arial,sans-serif;overflow:hidden">'
        f'{inner}'
        f'</svg>'
    )


# ── Quick smoke-test (run directly: python style_notebook.py) ─────────────────
if __name__ == "__main__":
    import os, sys

    # Stub the module-level name that _nb_footer uses
    _DIAGRAM_AUTHOR = "Komal Batra"  # noqa: F811

    svg = _style_notebook("enterprise-ai", "Enterprise AI Architecture", [])
    out_path = os.path.join(os.path.dirname(__file__), "notebook_test.svg")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Written: {out_path} ({len(svg)} bytes)")

    # Try a few other built-in topics
    for tid, tname in [
        ("kube", "Kubernetes Architecture"),
        ("rag", "RAG Systems Pipeline"),
        ("devops", "DevOps CI/CD Toolchain"),
    ]:
        svg2 = _style_notebook(tid, tname, [])
        p2 = os.path.join(os.path.dirname(__file__), f"notebook_{tid}.svg")
        with open(p2, "w", encoding="utf-8") as f:
            f.write(svg2)
        print(f"Written: {p2}")

def _style_lane_map_infographic(topic_id, topic_name, C, structure=None):
    W, H = 900, 620
    bg = "#FBFBFD"
    ink = "#0F172A"
    subtitle = structure["subtitle"] if structure else "Where retrieval, tools, agents, and protocols connect"
    sections = structure["sections"] if structure else [
        {"id": 1, "label": "RAG", "desc": "User question -> Retrieve -> Rerank -> Prompt -> Answer"},
        {"id": 2, "label": "AI Agent", "desc": "Plan -> Tool use -> Observe -> Reflect -> Finish"},
        {"id": 3, "label": "MCP", "desc": "Host -> Protocol -> Server -> Tool access"},
        {"id": 4, "label": "A2A", "desc": "Registry -> Route -> Delegate -> Status"},
    ]
    sections = sections[:6]

    def _clean_steps(desc):
        return [s.strip() for s in re.split(r"\s*(?:â†’|->|\|)\s*", desc or "") if s.strip()]

    svg = ""
    svg += f'<rect width="{W}" height="{H}" fill="{bg}"/>'
    svg += f'<line x1="44" y1="28" x2="{W-44}" y2="28" stroke="#111827" stroke-width="2"/>'
    svg += f'<text x="{W//2}" y="74" text-anchor="middle" fill="{ink}" font-size="30" font-weight="900">{xe(clamp(topic_name, 44))}</text>'
    svg += f'<text x="{W//2}" y="100" text-anchor="middle" fill="#475569" font-size="13" font-weight="600">{xe(clamp(subtitle, 84))}</text>'

    lane_x = 28
    lane_w = W - 56
    lane_gap = 12
    top_y = 124
    n_lanes = max(1, len(sections))
    avail_h = H - top_y - 40 - lane_gap * (n_lanes - 1)
    lane_h = max(78, int(avail_h / n_lanes))
    if lane_h * n_lanes + lane_gap * (n_lanes - 1) > (H - top_y - 24):
        lane_h = max(72, lane_h - 6)

    for i, sec in enumerate(sections):
        y = top_y + i * (lane_h + lane_gap)
        col = C[i % len(C)]
        left_fill = lighten(col, 0.93)
        chip_fill = lighten(col, 0.97)
        steps = _clean_steps(sec.get("desc", ""))
        if not steps:
            steps = ["Input", "Process", "Output"]

        svg += f'<rect x="{lane_x}" y="{y}" width="{lane_w}" height="{lane_h}" rx="8" fill="#FFFFFF" stroke="{lighten(col,0.45)}" stroke-width="1.4"/>'
        svg += f'<rect x="{lane_x}" y="{y}" width="{lane_w}" height="3" fill="{col}"/>'
        left_box_h = max(50, lane_h - 20)
        svg += f'<rect x="{lane_x+12}" y="{y+10}" width="162" height="{left_box_h}" rx="6" fill="{left_fill}" stroke="{col}" stroke-width="1.3"/>'
        label_lines = fit_lines(sec.get("label", ""), 12, 2)
        label_y = y + 48
        label_fs = 23 if len(label_lines) == 1 else 18
        for li, ln in enumerate(label_lines):
            svg += f'<text x="{lane_x+28}" y="{label_y+li*20}" fill="{darken(col,0.25)}" font-size="{label_fs}" font-weight="900">{xe(ln)}</text>'

        flow_x1 = lane_x + 208
        flow_x2 = lane_x + lane_w - 30
        flow_y = y + 42
        svg += f'<line x1="{flow_x1}" y1="{flow_y}" x2="{flow_x2}" y2="{flow_y}" stroke="{rgba(col,0.28)}" stroke-width="2"/>'
        svg += _dotted_flow_line(flow_x1, flow_y, flow_x2, flow_y, rgba(col,0.18), dot_spacing=20, dot_radius=2.4, opacity=0.78)
        svg += _animated_dot_path(f"M {flow_x1} {flow_y} L {flow_x2} {flow_y}", duration=3.1 + i*0.3, begin=i*0.18)

        step_gap = (flow_x2 - flow_x1) / max(len(steps), 1)
        for si, step in enumerate(steps):
            cx = flow_x1 + step_gap * si + step_gap * 0.45
            box_w = min(118, max(78, int(step_gap - 12)))
            box_x = cx - box_w / 2
            svg += f'<circle cx="{cx:.1f}" cy="{flow_y:.1f}" r="9" fill="#FFFFFF" stroke="{col}" stroke-width="2"/>'
            svg += f'<text x="{cx:.1f}" y="{flow_y+4:.1f}" text-anchor="middle" fill="{darken(col,0.20)}" font-size="10" font-weight="900">{si+1}</text>'
            svg += f'<rect x="{box_x:.1f}" y="{y+58}" width="{box_w:.1f}" height="30" rx="5" fill="{chip_fill}" stroke="{lighten(col,0.55)}" stroke-width="1"/>'
            lines = fit_lines(step, 14, 2)
            ty = y + 76 - (len(lines)-1)*5
            for li, ln in enumerate(lines[:2]):
                svg += f'<text x="{cx:.1f}" y="{ty+li*11:.1f}" text-anchor="middle" fill="{ink}" font-size="8.5" font-weight="700">{xe(clamp(ln,16))}</text>'

        if len(steps) >= 2:
            bubble = f"{steps[-2]} -> {steps[-1]}"
            bx = lane_x + lane_w - 155
            by = y + lane_h - 18
            svg += f'<ellipse cx="{bx}" cy="{by}" rx="78" ry="16" fill="#FFFFFF" stroke="{lighten(col,0.42)}" stroke-width="1.3"/>'
            bubble_line = fit_lines(bubble, 28, 1)[0]
            svg += f'<text x="{bx}" y="{by+4}" text-anchor="middle" fill="{darken(col,0.2)}" font-size="8.5" font-weight="700">{xe(bubble_line)}</text>'

    svg += f'<rect x="0" y="{H-28}" width="{W}" height="28" fill="#E5E7EB"/>'
    svg += f'<text x="18" y="{H-10}" fill="#64748B" font-size="9">{datetime.now().strftime("%B %Y")}</text>'
    svg += f'<text x="{W-18}" y="{H-10}" text-anchor="end" fill="{C[0]}" font-size="9" font-weight="800">AI (c) Komal Batra</text>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="display:block;font-family:Arial,sans-serif">{ANIM}{svg}</svg>'

def _style_modern_tech_cards(topic_id, topic_name, C, structure=None):
    W, H = 920, 640
    ink = "#E2E8F0"
    bg_top = "#0B1220"
    bg_bot = "#111827"
    subtitle = structure["subtitle"] if structure else "Practical comparison map"
    sections = structure["sections"] if structure else [
        {"id": 1, "label": "Option A", "desc": "Strong defaults and broad ecosystem"},
        {"id": 2, "label": "Option B", "desc": "Flexible architecture and rich filtering"},
        {"id": 3, "label": "Option C", "desc": "Low-friction fit for existing stack"},
        {"id": 4, "label": "Option D", "desc": "Hybrid retrieval and enterprise features"},
    ]
    sections = sections[:6]

    n = max(1, len(sections))
    cols = 3 if n > 4 else 2
    rows = math.ceil(n / cols)
    pad_x = 28
    top_y = 132
    gap = 14
    card_w = (W - pad_x * 2 - gap * (cols - 1)) // cols
    card_h = (H - top_y - 56 - gap * (rows - 1)) // max(rows, 1)

    icon_map = {
        "pinecone": "P",
        "weaviate": "W",
        "pgvector": "PG",
        "opensearch": "OS",
        "milvus": "M",
        "moment": "M",
        "insight": "I",
        "action": "A",
    }

    def _card_icon(label):
        ll = (label or "").lower()
        for key, icon in icon_map.items():
            if key in ll:
                return icon
        return "AI"

    svg = ""
    svg += (
        f'<defs>'
        f'<linearGradient id="mtc-bg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{bg_top}"/>'
        f'<stop offset="100%" stop-color="{bg_bot}"/>'
        f'</linearGradient>'
        f'</defs>'
    )
    svg += f'<rect width="{W}" height="{H}" fill="url(#mtc-bg)"/>'
    svg += f'<line x1="0" y1="96" x2="{W}" y2="96" stroke="{rgba("#60A5FA",0.22)}" stroke-width="1.5"/>'
    svg += f'<text x="26" y="40" fill="#93C5FD" font-size="14" font-weight="700" letter-spacing="1.2">TECH MAP</text>'
    title_lines = fit_lines(topic_name, 28, 2)
    if len(title_lines) == 1:
        svg += f'<text x="{W//2}" y="68" text-anchor="middle" fill="#F8FAFC" font-size="38" font-weight="900">{xe(title_lines[0])}</text>'
    else:
        svg += f'<text x="{W//2}" y="58" text-anchor="middle" fill="#F8FAFC" font-size="30" font-weight="900">{xe(title_lines[0])}</text>'
        svg += f'<text x="{W//2}" y="88" text-anchor="middle" fill="#F8FAFC" font-size="30" font-weight="900">{xe(title_lines[1])}</text>'
    svg += f'<text x="{W//2}" y="96" text-anchor="middle" fill="#94A3B8" font-size="13" font-weight="600">{xe(clamp(subtitle, 86))}</text>'

    for i, sec in enumerate(sections):
        r = i // cols
        c = i % cols
        x = pad_x + c * (card_w + gap)
        y = top_y + r * (card_h + gap)
        col = C[i % len(C)]
        delay = f"animation-delay:{i*0.07:.2f}s"

        svg += f'<rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" rx="12" fill="{rgba("#0F172A",0.72)}" stroke="{lighten(col,0.30)}" stroke-width="1.5" class="fi" style="{delay}"/>'
        svg += f'<rect x="{x}" y="{y}" width="{card_w}" height="6" rx="3" fill="{col}"/>'
        svg += f'<circle cx="{x+18}" cy="{y+22}" r="11" fill="{lighten(col,0.82)}" stroke="{col}" stroke-width="1.5"/>'
        svg += f'<text x="{x+18}" y="{y+26}" text-anchor="middle" fill="{darken(col,0.20)}" font-size="9" font-weight="900">{xe(_card_icon(sec.get("label","Option")))}</text>'
        svg += f'<text x="{x+36}" y="{y+26}" fill="{ink}" font-size="15" font-weight="900">{xe(clamp(sec.get("label","Option"), 22))}</text>'

        max_desc_lines = max(2, min(5, int((card_h - 64) / 16)))
        lines = fit_lines(sec.get("desc", ""), 26, max_desc_lines)
        for li, ln in enumerate(lines):
            svg += f'<text x="{x+16}" y="{y+56+li*16}" fill="#CBD5E1" font-size="12" font-weight="600">{xe(clamp(ln, 42))}</text>'

        # small index badge
        svg += f'<rect x="{x+card_w-58}" y="{y+14}" width="44" height="20" rx="10" fill="{rgba(col,0.20)}" stroke="{rgba(col,0.50)}" stroke-width="1"/>'
        svg += f'<text x="{x+card_w-36}" y="{y+28}" text-anchor="middle" fill="{lighten(col,0.68)}" font-size="9" font-weight="800">#{i+1}</text>'

    svg += f'<rect x="0" y="{H-28}" width="{W}" height="28" fill="{rgba("#0F172A",0.9)}"/>'
    svg += f'<text x="18" y="{H-10}" fill="#64748B" font-size="9">{datetime.now().strftime("%B %Y")}</text>'
    svg += f'<text x="{W-18}" y="{H-10}" text-anchor="end" fill="#93C5FD" font-size="9" font-weight="800">AI (c) Komal Batra</text>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="display:block;font-family:Arial,sans-serif">{ANIM}{svg}</svg>'


STYLES = [
    _style_vertical_flow,   # 0 — numbered pipeline steps
    _style_mind_map,        # 1 — radial hub + branches
    _style_pyramid,         # 2 — stacked trapezoids
    _style_timeline,        # 3 — horizontal spine, alternating cards
    _style_hexagon,         # 4 — honeycomb concept grid
    _style_comparison,      # 5 — side-by-side matrix
    _style_orbit,           # 6 — central hub + inner + outer rings
    _style_card_grid,       # 7 — grouped card layout
    _style_data_evolution,  # 8 — 3-tier data evolution
    _style_horizontal_tree, # 9 — horizontal tree branches
    _style_layered_flow,    # 10 — layered horizontal flow
    _style_ecosystem_tree,  # 11 — central core with orthogonal branches
    _style_honeycomb_map,   # 12 — honeycomb hex core with remote cards
    _style_parallel_pipelines, # 13 — parallel vertical sequences
    _style_winding_roadmap, # 14 - winding path with alternating nodes
    _style_vertical_timeline, # 15 - central static vertical dashed line
    _style_infographic_panels,  # 16
    _style_chalkboard,          # 17
    _style_dark_column_flow,    # 18
    _style_three_panel,         # 19
    _style_notebook,            # 20 - notebook style
    _style_lane_map_infographic, # 21 - editorial lane-map infographic
    _style_modern_tech_cards,   # 22 - modern comparison/stack cards
]

TOPIC_STYLE_OVERRIDES = {
    "llm-architecture":  1,   # mind map — concepts radiate naturally
    "ai-agents":         6,   # orbit — agent ecosystem
    "mlops-pipeline":    0,   # vertical flow — pipeline steps
    "rag-systems":       0,   # vertical flow — pipeline steps
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
    "data-evolution":    8,   # 3-tier data evolution
    "ml-algorithms":     9,   # horizontal tree
    "agentic-ai":       21,   # editorial lane map
    "ai-disciplines":    10,  # layered horizontal flow
    "rag-stack":         11,  # ecosystem tree
    "ai-skills-map":     12,  # honeycomb map
    "llm-vs-agentic":    13,  # parallel pipelines
    "genai-roadmap":     15, # vertical dashed timeline (overriding winding 14)
  # ── Career / Skills / Learning (also matches custom topic names) ───────
    "career":        7,
    "skill":         7,
    "talent":        7,
    "discipline":    6,
    "learning":      14,
    "roadmap":       14,
    "job":           5,
    "role":          5,
    "interview":     7,
    "brand":         2,
    "prompt":        7,
    "growth":        2,
    "leadership":    1,
    "tips":          0,
    "bootcamp":      0,
    "course":        0,
    "certification": 3,
    "agentic-ai":       20,   # dark column flow — RAG vs Agentic vs Memory
    "docker-cheatsheet": 19,  # three panel — Client/Host/Hub
    "enterprise-ai":  20,
    "system-design":  20,
    "kubernetes":     20,   # override existing if you want notebook style
    "rag-systems":    20,
}

DIAGRAM_TYPE_STYLE_MAP = {
    "architecture diagram": 7,
    "architecture": 7,
    "observability map": 20,
    "observability": 20,
    "flow chart": 0,
    "flow": 0,
    "comparison table": 5,
    "comparison": 5,
    "cheat sheet": 4,
    "cheatsheet": 4,
    "taxonomy tree": 9,
    "tree": 9,
    "conceptual layers": 2,
    "layers": 2,
    "ecosystem tree": 11,
    "ecosystem": 11,
    "honeycomb map": 12,
    "parallel pipelines": 13,
    "roadmap": 14,
    "timeline": 15,
    "notebook": 20,
    "lane map": 21,
    "lane infographic": 21,
    "modern cards": 22,
    "modern tech cards": 22,
    "decision tree": 9,
    "7 layers": 10,
    "signal vs noise": 17,
}

STYLE_FAMILIES_BY_TYPE = {
    "comparison table": [22, 16, 5],
    "comparison": [22, 16, 5],
    "decision tree": [9, 0, 16],
    "flow chart": [0, 21, 16],
    "lane map": [21, 0, 16],
    "observability map": [20, 21, 16],
    "winding roadmap": [14, 15, 3],
    "timeline": [15, 3, 14],
    "7 layers": [10, 2, 16],
    "architecture diagram": [7, 20, 16],
    "architecture": [7, 20, 16],
    "modern cards": [22, 16, 21],
}

_SCORE_STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "over", "this", "that",
    "about", "your", "what", "when", "where", "how", "map", "guide",
    "architecture", "diagram", "flow", "chart", "table", "framework",
}


def _normalize_diagram_type(diagram_type: str) -> str:
    return re.sub(r"\s+", " ", (diagram_type or "").strip().lower())


def _pick_style_from_metadata(topic_id: str, topic_name: str, diagram_type: str = "", structure: dict = None):
    if isinstance(structure, dict) and isinstance(structure.get("style"), int):
        return structure["style"], "structure"

    normalized_type = _normalize_diagram_type(diagram_type)
    if normalized_type in DIAGRAM_TYPE_STYLE_MAP:
        return DIAGRAM_TYPE_STYLE_MAP[normalized_type], "diagram_type"

    tid = (topic_id or "").lower()
    name_lower = (topic_name or "").lower()

    for key, idx in TOPIC_STYLE_OVERRIDES.items():
        if key in tid:
            return idx, "topic_id"

    for key, idx in TOPIC_STYLE_OVERRIDES.items():
        if key in name_lower:
            return idx, "topic_name"

    if normalized_type:
        return 7, "generic_type_fallback"

    return 7, "default"


def _maybe_variation_style(base_style_idx: int, topic_id: str, topic_name: str, source: str) -> int:
    if source not in {"topic_id", "topic_name"}:
        return base_style_idx

    digest = hashlib.md5(f"{topic_id}|{topic_name}".encode("utf-8")).hexdigest()
    if int(digest[:2], 16) % 10 >= 3:
        return base_style_idx

    candidate = int(digest[2:6], 16) % len(STYLES)
    return candidate if candidate != base_style_idx else base_style_idx


def _extract_scoring_keywords(topic_name: str, diagram_type: str = "", structure: dict = None):
    raw = [topic_name or "", diagram_type or ""]
    if isinstance(structure, dict):
        raw.append(structure.get("subtitle", ""))
        for section in structure.get("sections", [])[:8]:
            if isinstance(section, dict):
                raw.append(section.get("label", ""))
                raw.append(section.get("desc", ""))
            else:
                raw.append(str(section))
        for row in structure.get("rows", [])[:8]:
            if isinstance(row, dict):
                raw.append(row.get("label", ""))
                raw.append(row.get("text", ""))
            elif isinstance(row, (tuple, list)):
                raw.extend(str(x) for x in row[:2])
            else:
                raw.append(str(row))
    tokens = []
    for text in raw:
        for tok in re.split(r"[^a-z0-9]+", (text or "").lower()):
            if len(tok) < 3 or tok in _SCORE_STOPWORDS:
                continue
            tokens.append(tok)
    seen = set()
    deduped = []
    for tok in tokens:
        if tok in seen:
            continue
        seen.add(tok)
        deduped.append(tok)
    return deduped[:16]


def _score_svg_candidate(svg: str, topic_name: str, diagram_type: str = "", structure: dict = None) -> int:
    lowered = (svg or "").lower()
    keywords = _extract_scoring_keywords(topic_name, diagram_type, structure)
    score = 0

    score += sum(8 for kw in keywords if kw in lowered)

    text_nodes = lowered.count("<text")
    if 10 <= text_nodes <= 90:
        score += 14
    else:
        score -= min(12, abs(text_nodes - 40) // 3)

    if len(svg or "") >= 7000:
        score += 6

    topic_lower = (topic_name or "").lower()
    if "aws cloud" in lowered and "aws" not in topic_lower:
        score -= 24
    if "railway" in lowered and "railway" not in topic_lower:
        score -= 18

    if structure and structure.get("sections"):
        labels = [s.get("label", "").lower() for s in structure.get("sections", [])]
        covered = sum(1 for label in labels if label and label in lowered)
        score += min(18, covered * 4)
    if structure and structure.get("rows"):
        labels = [r.get("label", "").lower() for r in structure.get("rows", [])]
        covered = sum(1 for label in labels if label and label in lowered)
        score += min(16, covered * 4)

    return score


def _pick_candidate_styles(topic_id: str, topic_name: str, diagram_type: str = "", structure: dict = None, candidate_count: int = 3):
    base_style_idx, source = _pick_style_from_metadata(topic_id, topic_name, diagram_type, structure=structure)
    base_style_idx = _maybe_variation_style(base_style_idx, topic_id, topic_name, source)

    if isinstance(structure, dict) and isinstance(structure.get("style"), int):
        return [base_style_idx]

    normalized_type = _normalize_diagram_type(diagram_type)
    family = STYLE_FAMILIES_BY_TYPE.get(normalized_type, [])
    if not family:
        family = [base_style_idx, 16, 19, 0, 1, 3, 4, 7, 20, 21]

    rng = random.Random(int(hashlib.md5(f"{topic_id}|{topic_name}|{diagram_type}".encode("utf-8")).hexdigest()[:8], 16))
    tail = [idx for idx in range(len(STYLES)) if idx not in family and idx != base_style_idx]
    rng.shuffle(tail)

    ordered = [base_style_idx] + family + tail
    deduped = []
    for idx in ordered:
        if not isinstance(idx, int):
            continue
        if idx < 0 or idx >= len(STYLES):
            continue
        if idx in deduped:
            continue
        deduped.append(idx)
        if len(deduped) >= max(1, candidate_count):
            break
    return deduped


def make_diagram(topic_name: str, topic_id: str, diagram_type: str = "", structure: dict = None, style_override: int = None) -> str:
    C = get_pal(topic_id, topic_name)
    if isinstance(style_override, int):
        style_idx = style_override
        source = "override"
    else:
        style_idx, source = _pick_style_from_metadata(topic_id, topic_name, diagram_type, structure=structure)
        style_idx = _maybe_variation_style(style_idx, topic_id, topic_name, source)



    log.info(
        f"Diagram style {style_idx} selected via {source}"
        + (f" ({diagram_type})" if diagram_type else "")
    )

    fn = STYLES[style_idx]
    try:
        import inspect
        if "structure" in inspect.signature(fn).parameters:
            return fn(topic_id, topic_name, C, structure=structure)
        return fn(topic_id, topic_name, C)
    except Exception as e:
        log.warning(f"Style {style_idx} failed ({e}), falling back to card grid")
        return _style_card_grid(topic_id, topic_name, C)


def _style_supports_motion(style_idx: int) -> bool:
    return style_idx in {0, 3, 6, 8, 21}


def _render_gif(topic_name: str, topic_id: str, diagram_type: str = "", structure: dict = None,
                style_override: int = None,
                frame_count: int = 10, duration_ms: int = 120):
    try:
        import cairosvg
        from PIL import Image
    except Exception as e:
        log.warning(f"GIF export unavailable: {e}")
        return None

    if isinstance(style_override, int):
        style_idx = style_override
    else:
        style_idx, _ = _pick_style_from_metadata(topic_id, topic_name, diagram_type, structure=structure)
    if not _style_supports_motion(style_idx):
        return None

    frames = []
    global _MOTION_PHASE
    previous_phase = _MOTION_PHASE
    try:
        for idx in range(frame_count):
            _MOTION_PHASE = idx / frame_count
            svg = make_diagram(topic_name, topic_id, diagram_type, structure=structure, style_override=style_idx)
            png_bytes = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=1200, output_height=840)
            frame = Image.open(io.BytesIO(png_bytes)).convert("P", palette=Image.ADAPTIVE)
            frames.append(frame)
    finally:
        _MOTION_PHASE = previous_phase

    if not frames:
        return None

    return {
        "frames": frames,
        "duration_ms": duration_ms,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  DiagramGenerator — interface used by agent.py
# ══════════════════════════════════════════════════════════════════════════════

class DiagramGenerator:
    def __init__(self):
        Path(OUTPUT_DIR).mkdir(exist_ok=True)
        log.info("Diagram output dir: " + OUTPUT_DIR + "/")

    def save_svg(self, svg_content, topic_id, topic_name="", diagram_type="Architecture Diagram", structure=None):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{OUTPUT_DIR}/{topic_id}_{ts}.svg"
        
        # Check for existing diagram (SVG, PNG, or GIF)
        existing_svg = f"{OUTPUT_DIR}/{topic_id}.svg"
        existing_png = f"{OUTPUT_DIR}/{topic_id}.png"
        existing_gif = f"{OUTPUT_DIR}/{topic_id}.gif"
        
        allow_reuse = not structure and not (diagram_type or "").strip()

        use_existing = False
        if allow_reuse and os.path.exists(existing_gif) and random.random() < 0.5:
            gif_name = filename.replace(".svg", ".gif")
            shutil.copy(existing_gif, gif_name)
            log.info(f"Using existing GIF diagram: {gif_name}")
            return gif_name
        if allow_reuse and os.path.exists(existing_svg) and random.random() < 0.5:  # 50% chance to use existing SVG
            shutil.copy(existing_svg, filename)
            log.info(f"Using existing SVG diagram: {filename}")
            use_existing = True
        elif allow_reuse and os.path.exists(existing_png) and random.random() < 0.5:  # 50% chance to use existing PNG
            # For PNG, copy and treat as SVG (will be converted later)
            shutil.copy(existing_png, filename.replace('.svg', '.png'))
            log.info(f"Using existing PNG diagram: {filename.replace('.svg', '.png')}")
            # Note: This will be handled in linkedin_poster if needed
            use_existing = True
        
        if not use_existing:
            try:
                candidate_count = int(os.environ.get("DIAGRAM_CANDIDATES", "3"))
            except Exception:
                candidate_count = 3
            candidate_count = max(1, min(5, candidate_count))

            candidate_styles = _pick_candidate_styles(
                topic_id, topic_name or topic_id, diagram_type, structure=structure, candidate_count=candidate_count
            )
            scored_candidates = []
            for style_idx in candidate_styles:
                svg_candidate = make_diagram(
                    topic_name or topic_id, topic_id, diagram_type, structure=structure, style_override=style_idx
                )
                candidate_score = _score_svg_candidate(
                    svg_candidate, topic_name or topic_id, diagram_type=diagram_type, structure=structure
                )
                scored_candidates.append((candidate_score, style_idx, svg_candidate))
            scored_candidates.sort(key=lambda x: x[0], reverse=True)

            best_score, best_style, best_svg = scored_candidates[0]
            log.info(
                "Diagram candidates ranked: "
                + ", ".join(f"style {style}={score}" for score, style, _ in scored_candidates)
                + f" -> selected style {best_style}"
            )

            gif_bundle = _render_gif(
                topic_name or topic_id, topic_id, diagram_type, structure=structure, style_override=best_style
            )
            if gif_bundle:
                gif_name = filename.replace(".svg", ".gif")
                frames = gif_bundle["frames"]
                frames[0].save(
                    gif_name,
                    save_all=True,
                    append_images=frames[1:],
                    duration=gif_bundle["duration_ms"],
                    loop=0,
                    optimize=False,
                    disposal=2,
                )
                size_kb = os.path.getsize(gif_name) / 1024
                log.info(f"Generated animated GIF: {gif_name} ({round(size_kb, 1)} KB)")
                return gif_name

            with open(filename, "w", encoding="utf-8") as f:
                f.write(best_svg)
            size_kb = os.path.getsize(filename) / 1024
            log.info(f"Generated diagram: {filename} ({round(size_kb, 1)} KB, score={best_score})")
        
        return filename
