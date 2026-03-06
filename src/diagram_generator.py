import os
from datetime import datetime
from pathlib import Path
from logger import get_logger

log = get_logger("diagrams")
OUTPUT_DIR = "diagrams"

# ── LIGHT VIBRANT PALETTES ────────────────────────────────────────────────────
# Each palette: [primary, accent1, accent2, accent3, accent4, accent5]
# All colours are vivid — used for headers/cards on WHITE background
PALETTES = {
    "ai":       ["#7C3AED","#2563EB","#0891B2","#059669","#D97706","#DB2777"],
    "cloud":    ["#2563EB","#0891B2","#059669","#D97706","#7C3AED","#DB2777"],
    "security": ["#DC2626","#EA580C","#7C3AED","#0891B2","#059669","#2563EB"],
    "data":     ["#7C3AED","#2563EB","#0891B2","#059669","#D97706","#DC2626"],
    "devops":   ["#059669","#2563EB","#7C3AED","#D97706","#DC2626","#0891B2"],
    "default":  ["#2563EB","#7C3AED","#059669","#D97706","#DC2626","#0891B2"],
}

BG        = "#FFFFFF"   # canvas white
BG2       = "#F8FAFC"   # subtle section tint
BORDER    = "#E2E8F0"   # light border
TEXT_DARK = "#1E293B"   # main text
TEXT_MID  = "#475569"   # subtitle text
TEXT_LITE = "#94A3B8"   # muted text

def get_pal(tid):
    t = tid.lower()
    if any(x in t for x in ["llm","rag","agent","mlops"]): return PALETTES["ai"]
    if any(x in t for x in ["kube","docker","aws","cicd"]): return PALETTES["cloud"]
    if any(x in t for x in ["zero","devsec"]):              return PALETTES["security"]
    if any(x in t for x in ["kafka","data","lake"]):        return PALETTES["data"]
    return PALETTES["default"]

def clamp(text, max_chars):
    """Truncate text to prevent overflow."""
    return text if len(text) <= max_chars else text[:max_chars-1] + "…"

# ── PRIMITIVES ────────────────────────────────────────────────────────────────

def section(x, y, w, h, title, color, rx=10):
    """Vibrant header bar + white content area with subtle border."""
    bh = 30
    s  = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{BG}" stroke="{BORDER}" stroke-width="1.5"/>'
    # header bar
    s += f'<rect x="{x}" y="{y}" width="{w}" height="{bh}" rx="{rx}" fill="{color}"/>'
    s += f'<rect x="{x}" y="{y+rx}" width="{w}" height="{bh-rx}" fill="{color}"/>'
    s += f'<text x="{x+w//2}" y="{y+21}" text-anchor="middle" fill="white" font-size="12" font-weight="700" font-family="Arial,sans-serif">{clamp(title,30)}</text>'
    return s

def card(x, y, w, h, color, title, sub="", rx=8, light=False):
    """Coloured card. light=True uses pale fill with coloured text (more readable)."""
    if light:
        fill   = color + "18"   # ~10% opacity via hex alpha approximation
        tfill  = color
        sfill  = TEXT_MID
        border = color + "55"
        s  = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{border}" stroke-width="1.5"/>'
    else:
        s  = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}"/>'
        tfill  = "white"
        sfill  = "rgba(255,255,255,0.80)"

    pad = 6
    inner_w = w - pad*2
    mid = y + h//2

    # Title — safe font size: scale down if box is narrow
    tfsize = min(11, max(8, inner_w // 7))
    sfsize = min(9,  max(7, inner_w // 9))

    t = clamp(title, max(4, inner_w // (tfsize-2)))
    if sub:
        sv = clamp(sub, max(4, inner_w // (sfsize-2)))
        s += f'<text x="{x+w//2}" y="{mid-2}" text-anchor="middle" fill="{tfill}" font-size="{tfsize}" font-weight="700" font-family="Arial,sans-serif">{t}</text>'
        s += f'<text x="{x+w//2}" y="{mid+12}" text-anchor="middle" fill="{sfill}" font-size="{sfsize}" font-family="Arial,sans-serif">{sv}</text>'
    else:
        s += f'<text x="{x+w//2}" y="{mid+4}" text-anchor="middle" fill="{tfill}" font-size="{tfsize}" font-weight="700" font-family="Arial,sans-serif">{t}</text>'
    return s

def pill(x, y, w, h, color, text, rx=None):
    """Small rounded label pill."""
    rx = rx or h//2
    s  = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}"/>'
    fs = min(10, max(7, w//7))
    s += f'<text x="{x+w//2}" y="{y+h//2+3}" text-anchor="middle" fill="white" font-size="{fs}" font-weight="700" font-family="Arial,sans-serif">{clamp(text, w//5)}</text>'
    return s

def arrow_down(cx, y1, y2, color):
    """Clean downward arrow."""
    bw, hw = 10, 18
    by = y2 - 10
    s  = f'<rect x="{cx-bw//2}" y="{y1}" width="{bw}" height="{by-y1}" fill="{color}" opacity="0.7"/>'
    s += f'<polygon points="{cx-hw//2},{by} {cx+hw//2},{by} {cx},{y2}" fill="{color}" opacity="0.7"/>'
    return s

def arrow_right(x1, x2, cy, color):
    """Clean rightward arrow."""
    bh, hw = 8, 14
    bx = x2 - 10
    s  = f'<rect x="{x1}" y="{cy-bh//2}" width="{bx-x1}" height="{bh}" fill="{color}" opacity="0.65"/>'
    s += f'<polygon points="{bx},{cy-hw//2} {x2},{cy} {bx},{cy+hw//2}" fill="{color}" opacity="0.65"/>'
    return s

def connector(x1, y1, x2, y2, color=BORDER):
    """Thin connector line with arrowhead."""
    uid = f"c{abs(x1)}{abs(y1)}{abs(x2)}{abs(y2)}"
    s  = f'<defs><marker id="{uid}" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="{color}"/></marker></defs>'
    s += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.5" marker-end="url(#{uid})"/>'
    return s

def tool_strip(y, tools, color):
    """Light strip of tool badges across the top."""
    n = len(tools)
    tw = 870 // n
    s  = f'<rect x="15" y="{y}" width="870" height="30" rx="6" fill="{color}18" stroke="{color}40" stroke-width="1"/>'
    for i, (ico, name) in enumerate(tools):
        cx = 15 + i*tw + tw//2
        s += f'<text x="{cx}" y="{y+12}" text-anchor="middle" font-size="13" font-family="Arial,sans-serif">{ico}</text>'
        fs = min(10, max(7, tw//8))
        s += f'<text x="{cx}" y="{y+25}" text-anchor="middle" fill="{color}" font-size="{fs}" font-weight="700" font-family="Arial,sans-serif">{clamp(name,tw//5)}</text>'
        if i < n-1:
            lx = 15+(i+1)*tw
            s += f'<line x1="{lx}" y1="{y+5}" x2="{lx}" y2="{y+25}" stroke="{BORDER}" stroke-width="1"/>'
    return s

def status_row(y, items):
    """Light coloured status pill row."""
    n   = len(items)
    iw  = 870 // n
    s   = f'<rect x="15" y="{y}" width="870" height="24" rx="12" fill="{BG2}" stroke="{BORDER}" stroke-width="1"/>'
    for i, (label, color) in enumerate(items):
        cx = 15 + i*iw + iw//2
        s += f'<circle cx="{cx - len(label)*3 - 10}" cy="{y+12}" r="4" fill="{color}"/>'
        fs = min(10, max(7, iw//10))
        s += f'<text x="{cx - len(label)*3 - 3}" y="{y+16}" fill="{TEXT_DARK}" font-size="{fs}" font-weight="600" font-family="Arial,sans-serif">{label}</text>'
    return s

def two_col(x, y, w, h, lbl1, col1, lbl2, col2, split=0.5):
    """Two-column section with different header colours."""
    w1, w2, rx = int(w*split), w-int(w*split), 10
    bh = 30
    # outer border
    s  = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{BG}" stroke="{BORDER}" stroke-width="1.5"/>'
    # left header
    s += f'<rect x="{x}" y="{y}" width="{w1}" height="{bh}" rx="{rx}" fill="{col1}"/>'
    s += f'<rect x="{x+rx}" y="{y}" width="{w1-rx}" height="{bh}" fill="{col1}"/>'
    s += f'<text x="{x+w1//2}" y="{y+21}" text-anchor="middle" fill="white" font-size="12" font-weight="700" font-family="Arial,sans-serif">{clamp(lbl1,18)}</text>'
    # right header
    s += f'<rect x="{x+w1}" y="{y}" width="{w2}" height="{bh}" rx="{rx}" fill="{col2}"/>'
    s += f'<rect x="{x+w1}" y="{y}" width="{w2-rx}" height="{bh}" fill="{col2}"/>'
    s += f'<text x="{x+w1+w2//2}" y="{y+21}" text-anchor="middle" fill="white" font-size="12" font-weight="700" font-family="Arial,sans-serif">{clamp(lbl2,18)}</text>'
    # divider
    s += f'<line x1="{x+w1}" y1="{y}" x2="{x+w1}" y2="{y+h}" stroke="{BORDER}" stroke-width="1.5"/>'
    # tinted backgrounds
    s += f'<rect x="{x+1}" y="{y+bh}" width="{w1-1}" height="{h-bh-1}" fill="{col1}08"/>'
    s += f'<rect x="{x+w1}" y="{y+bh}" width="{w2-1}" height="{h-bh-1}" fill="{col2}08"/>'
    return s

def stat_tile(x, y, w, h, value, label, color):
    """KPI metric tile — vibrant border, white bg."""
    s  = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{BG}" stroke="{color}" stroke-width="2"/>'
    s += f'<rect x="{x}" y="{y}" width="{w}" height="4" rx="8" fill="{color}"/>'
    s += f'<text x="{x+w//2}" y="{y+h//2+2}" text-anchor="middle" fill="{color}" font-size="20" font-weight="800" font-family="Arial,sans-serif">{value}</text>'
    fs = min(9, max(7, w//14))
    s += f'<text x="{x+w//2}" y="{y+h//2+16}" text-anchor="middle" fill="{TEXT_MID}" font-size="{fs}" font-family="Arial,sans-serif">{clamp(label,w//5)}</text>'
    return s

def flow_box(x, y, w, h, ico, title, sub, color):
    """Bordered box with icon — used in flow diagrams."""
    s  = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{color}12" stroke="{color}" stroke-width="1.8"/>'
    inner = w - 8
    if ico:
        s += f'<text x="{x+w//2}" y="{y+20}" text-anchor="middle" font-size="16" font-family="Arial,sans-serif">{ico}</text>'
        s += f'<text x="{x+w//2}" y="{y+36}" text-anchor="middle" fill="{color}" font-size="{min(10,max(7,inner//7))}" font-weight="700" font-family="Arial,sans-serif">{clamp(title,inner//5)}</text>'
        if sub and h > 55:
            s += f'<text x="{x+w//2}" y="{y+49}" text-anchor="middle" fill="{TEXT_MID}" font-size="{min(8,max(6,inner//9))}" font-family="Arial,sans-serif">{clamp(sub,inner//4)}</text>'
    else:
        mid = y + h//2
        s += f'<text x="{x+w//2}" y="{mid+(0 if not sub else -4)}" text-anchor="middle" fill="{color}" font-size="{min(11,max(7,inner//7))}" font-weight="700" font-family="Arial,sans-serif">{clamp(title,inner//5)}</text>'
        if sub:
            s += f'<text x="{x+w//2}" y="{mid+11}" text-anchor="middle" fill="{TEXT_MID}" font-size="{min(9,max(6,inner//9))}" font-family="Arial,sans-serif">{clamp(sub,inner//4)}</text>'
    return s

def cheatrow(y, h, label, color, items):
    """Cheatsheet row: coloured left label → grid of mini cards."""
    lw = max(80, len(label)*8 + 16)
    s  = f'<rect x="15" y="{y}" width="870" height="{h}" rx="7" fill="{BG2}" stroke="{BORDER}" stroke-width="1"/>'
    s += f'<rect x="15" y="{y}" width="{lw}" height="{h}" rx="7" fill="{color}"/>'
    s += f'<rect x="{15+lw-7}" y="{y}" width="7" height="{h}" fill="{color}"/>'
    fs = min(11, max(8, lw//8))
    s += f'<text x="{15+lw//2}" y="{y+h//2+4}" text-anchor="middle" fill="white" font-size="{fs}" font-weight="700" font-family="Arial,sans-serif">{clamp(label,lw//6)}</text>'
    # cards
    gx    = 15 + lw + 6
    avail = 880 - gx
    n     = len(items)
    cw    = max(50, avail//n - 4)
    for i, item in enumerate(items):
        ico   = item[0] if len(item) > 0 else ""
        title = item[1] if len(item) > 1 else ""
        sub   = item[2] if len(item) > 2 else ""
        cx    = gx + i*(cw+4)
        s += f'<rect x="{cx}" y="{y+3}" width="{cw}" height="{h-6}" rx="6" fill="{color}15" stroke="{color}40" stroke-width="1"/>'
        if ico:
            s += f'<text x="{cx+cw//2}" y="{y+15}" text-anchor="middle" font-size="13" font-family="Arial,sans-serif">{ico}</text>'
        s += f'<text x="{cx+cw//2}" y="{y+h//2+(0 if not ico else 6)}" text-anchor="middle" fill="{color}" font-size="{min(9,max(6,cw//8))}" font-weight="700" font-family="Arial,sans-serif">{clamp(title,cw//5)}</text>'
        if sub and h >= 56:
            s += f'<text x="{cx+cw//2}" y="{y+h-8}" text-anchor="middle" fill="{TEXT_MID}" font-size="{min(8,max(6,cw//9))}" font-family="Arial,sans-serif">{clamp(sub,cw//4)}</text>'
    return s

# ── WRAPPER ────────────────────────────────────────────────────────────────────
def wrap(content, title, subtitle, color, date_str):
    st = clamp(title.replace("&","and").replace("<","").replace(">",""), 50)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 580" width="900" height="580">
  <defs>
    <linearGradient id="hdrg" x1="0" x2="1">
      <stop offset="0%" stop-color="{color}"/>
      <stop offset="100%" stop-color="{color}CC"/>
    </linearGradient>
  </defs>

  <!-- White canvas -->
  <rect width="900" height="580" fill="{BG}"/>

  <!-- Header bar -->
  <rect x="0" y="0" width="900" height="64" fill="url(#hdrg)"/>

  <!-- Category badge -->
  <rect x="15" y="16" width="{len(subtitle)*8+20}" height="18" rx="9" fill="white" fill-opacity="0.25"/>
  <text x="25" y="28" fill="white" font-size="9" font-weight="700" font-family="Arial,sans-serif" letter-spacing="1.5">{subtitle.upper()}</text>

  <!-- Title -->
  <text x="450" y="44" text-anchor="middle" fill="white" font-size="20" font-weight="800" font-family="Arial,sans-serif" letter-spacing="-0.3">{st}</text>

  <!-- Content area -->
  {content}

  <!-- Footer -->
  <rect x="0" y="554" width="900" height="26" fill="{color}0A"/>
  <line x1="0" y1="554" x2="900" y2="554" stroke="{BORDER}" stroke-width="1"/>
  <text x="20" y="570" fill="{TEXT_LITE}" font-size="9" font-family="Arial,sans-serif">{date_str}</text>
  <rect x="640" y="559" width="245" height="16" rx="8" fill="{color}20" stroke="{color}50" stroke-width="1"/>
  <text x="762" y="571" text-anchor="middle" fill="{color}" font-size="9" font-weight="700" font-family="Arial,sans-serif" letter-spacing="0.5">✦ AI · Komal Batra</text>
</svg>'''


# ── DIAGRAMS ──────────────────────────────────────────────────────────────────

def make_kubernetes(C):
    s = ""
    s += tool_strip(72, [("☸️","Kubernetes"),("🐳","containerd"),("📡","etcd"),("🔀","Calico"),("📊","Prometheus"),("🔒","RBAC")], C[0])

    # Control Plane
    s += section(15, 108, 870, 90, "CONTROL PLANE", C[0])
    items = [("API Server","entry point"),("Scheduler","filter+score"),("Controller Mgr","reconcile"),("etcd","key-value"),("Cloud Controller","provider")]
    cw = 860 // len(items)
    for i,(t,s2) in enumerate(items):
        s += card(18+i*cw, 142, cw-6, 48, C[i%len(C)], t, s2)
    for i in range(len(items)-1):
        s += arrow_right(18+(i+1)*cw-8, 18+(i+1)*cw+2, 166, C[i%len(C)])

    s += arrow_down(450, 198, 216, C[1])

    # Workers
    s += two_col(15, 216, 870, 180, "WORKER NODE 1", C[1], "WORKER NODE 2", C[2])
    # node 1
    for i,(t,s2,col) in enumerate([("Kubelet","node agent",C[1]),("kube-proxy","iptables",C[2]),("CNI","Calico",C[3])]):
        s += card(22+i*140, 250, 132, 36, col, t, s2)
    for i,(t,s2,col) in enumerate([("Pod:nginx","web",C[0]),("Pod:api","app",C[1]),("Pod:cache","redis",C[2]),("Pod:worker","bg",C[3])]):
        s += card(22+i*105, 294, 97, 94, col, t, s2)
    # node 2
    for i,(t,s2,col) in enumerate([("Kubelet","node agent",C[2]),("kube-proxy","network",C[3]),("Ingress","NGINX",C[4])]):
        s += card(457+i*140, 250, 132, 36, col, t, s2)
    for i,(t,s2,col) in enumerate([("Pod:db","postgres",C[3]),("Pod:ml","torch",C[4]),("Pod:mon","prom",C[5]),("Pod:search","elastic",C[0])]):
        s += card(457+i*105, 294, 97, 94, col, t, s2)

    s += arrow_down(450, 396, 414, C[3])

    # Cluster services
    s += section(15, 414, 870, 62, "CLUSTER SERVICES", C[3])
    for i,(t,s2) in enumerate([("HPA","pod autoscale"),("VPA","right-size"),("Cluster CA","node scale"),("PVC / PV","storage"),("Cert Manager","TLS")]):
        s += card(22+i*172, 446, 164, 24, C[i%len(C)], t, s2)

    s += status_row(488, [("Control Plane","#059669"),("Node 1 Ready","#2563EB"),("Node 2 Ready","#2563EB"),("HPA Active","#D97706"),("certs OK","#059669")])
    return s, "Cluster Architecture"


def make_llm(C):
    s = ""
    s += tool_strip(72, [("🤖","LLaMA 3"),("🧠","GPT-4o"),("☁️","Claude"),("🔍","RAG"),("🛠️","LangChain"),("📊","LangSmith")], C[0])

    s += two_col(15, 108, 870, 340, "PROCESSING PIPELINE", C[0], "AI PROVIDERS", C[1], 0.62)

    # Left pipeline 4 rows
    layer_data = [
        (C[0], "INPUT", [("Query","natural lang"),("System Prompt","instructions"),("History","conv ctx"),("Tool Defs","fn schema")]),
        (C[2], "CONTEXT", [("Chunker","512 tok"),("Embedder","text-embed-3"),("Vector Store","Pinecone"),("Re-ranker","cross-enc")]),
        (C[3], "REASONING", [("Planner","decompose"),("Tool Router","dispatch"),("Memory","short+long"),("Agent Loop","plan→act")]),
        (C[4], "OUTPUT", [("Tokenizer","decode"),("Sampler","temp/top-p"),("Guardrails","safety"),("Streamer","SSE")]),
    ]
    ly = 142
    for col, lbl, items in layer_data:
        s += pill(22, ly, 70, 16, col, lbl)
        for j,(t,sub) in enumerate(items):
            s += card(22+j*130, ly+20, 122, 44, col, t, sub, light=True)
        if ly < 360:
            s += arrow_down(280, ly+64, ly+74, col)
        ly += 74

    # Right AI providers
    providers = [("🤖","GPT-4o","OpenAI",C[1]),("🧠","Claude","Anthropic",C[2]),("🦙","LLaMA 3","Meta",C[3]),("💎","Gemini","Google",C[4]),("⚡","Groq","fast inf",C[5])]
    for i,(ico,nm,src2,col) in enumerate(providers):
        cy = 148 + i*62
        s += flow_box(560, cy, 310, 54, ico, nm, src2, col)
        if i < 4:
            s += connector(715, cy+54, 715, cy+62, col)

    s += arrow_down(450, 448, 466, C[5])
    s += status_row(466, [("Faithfulness","#059669"),("Relevance","#2563EB"),("RAGAS Score","#7C3AED"),("Latency p95","#D97706"),("Hallucination %","#DC2626")])
    return s, "Architecture Diagram"


def make_cicd(C):
    s = ""
    s += tool_strip(72, [("🐙","GitHub Actions"),("🐳","Docker"),("☸️","Kubernetes"),("🛡️","Trivy"),("📊","Grafana"),("🚨","PagerDuty")], C[0])

    # Pipeline circles
    stages = [("1","💻","Code","git push",C[0]),("2","🔍","Test","pytest",C[1]),("3","🏗️","Build","docker",C[2]),
              ("4","🛡️","Scan","trivy",C[3]),("5","📦","Publish","ECR",C[4]),("6","🚀","Deploy","helm",C[5]),("7","✅","Verify","smoke",C[0])]
    spacing = 870 // len(stages)
    for i,(num,ico,lbl,sub,col) in enumerate(stages):
        cx = 15 + i*spacing + spacing//2
        # circle
        s += f'<circle cx="{cx}" cy="152" r="34" fill="{col}20" stroke="{col}" stroke-width="2.5"/>'
        s += f'<circle cx="{cx}" cy="152" r="28" fill="{col}"/>'
        s += f'<text x="{cx}" y="147" text-anchor="middle" font-size="16" font-family="Arial,sans-serif">{ico}</text>'
        s += f'<text x="{cx}" y="163" text-anchor="middle" fill="white" font-size="9" font-weight="700" font-family="Arial,sans-serif">{lbl}</text>'
        s += f'<text x="{cx}" y="204" text-anchor="middle" fill="{TEXT_MID}" font-size="9" font-family="Arial,sans-serif">{sub}</text>'
        # number badge
        s += f'<circle cx="{cx+22}" cy="126" r="9" fill="{BG}" stroke="{col}" stroke-width="2"/>'
        s += f'<text x="{cx+22}" y="130" text-anchor="middle" fill="{col}" font-size="8" font-weight="700" font-family="Arial,sans-serif">{num}</text>'
        if i < len(stages)-1:
            nx = 15+(i+1)*spacing+spacing//2
            s += arrow_right(cx+28, nx-28, 152, col)

    s += status_row(216, [("Code Review","#059669"),("Unit Tests","#059669"),("SAST","#059669"),("CVE Check","#D97706"),("Perf Budget","#D97706"),("Canary","#2563EB"),("Prod","#059669")])

    # 3 sections
    s += two_col(15, 248, 430, 148, "ENVIRONMENTS", C[1], "QUALITY GATES", C[2])
    for i,(t,sub,col) in enumerate([("Development","feature branches",C[1]),("Staging","pre-prod",C[2]),("Production","blue/green",C[0])]):
        s += card(22, 282+i*36, 200, 30, col, t, sub, light=True)
    for i,(t,sub,col) in enumerate([("Coverage",">80%",C[2]),("Perf Budget","LCP<2.5s",C[3]),("DAST","OWASP ZAP",C[4])]):
        s += card(228, 282+i*36, 210, 30, col, t, sub, light=True)

    s += section(455, 248, 430, 148, "ROLLOUT STRATEGY", C[4])
    for i,(t,sub,col) in enumerate([("Canary","1%→10%→100%",C[4]),("Blue/Green","instant cutover",C[0]),("Feature Flags","LaunchDarkly",C[1]),("Auto Rollback","err rate>1%",C[3])]):
        s += card(462, 282+i*28, 416, 24, col, t, sub)

    s += arrow_down(450, 396, 414, C[3])
    s += section(15, 414, 870, 70, "OBSERVABILITY", C[3])
    for i,(t,sub) in enumerate([("Prometheus","metrics"),("Grafana","dashboards"),("Jaeger","traces"),("ELK Stack","logs"),("PagerDuty","alerts")]):
        s += card(22+i*172, 447, 164, 30, C[i%len(C)], t, sub)

    return s, "Pipeline Architecture"


def make_kafka(C):
    s = ""
    s += tool_strip(72, [("🌊","Kafka"),("📋","Schema Reg"),("🔌","Connect"),("⚡","Flink"),("🔥","Spark"),("📊","ClickHouse")], C[0])

    s += section(15, 108, 175, 150, "PRODUCERS", C[1])
    for i,(t,sub,col) in enumerate([("App Server","REST/gRPC",C[1]),("IoT / Edge","MQTT",C[2]),("DB CDC","Debezium",C[3])]):
        s += card(22, 140+i*38, 160, 32, col, t, sub)
    s += arrow_right(190, 218, 183, C[0])

    s += section(218, 108, 310, 150, "KAFKA CLUSTER", C[0])
    for i,(t,sub) in enumerate([("Broker 1","leader"),("Broker 2","ISR"),("Broker 3","ISR")]):
        s += card(225+i*100, 140, 93, 110, C[i%len(C)], t, sub)
    s += arrow_right(528, 555, 183, C[0])

    s += section(555, 108, 175, 150, "SCHEMA + CONNECT", C[4])
    s += card(562, 140, 160, 46, C[4], "Schema Registry", "Avro/Protobuf")
    s += card(562, 194, 160, 46, C[5], "Kafka Connect", "source+sink")
    s += arrow_right(730, 758, 183, C[2])

    s += section(758, 108, 132, 150, "STREAM PROC", C[2])
    s += card(765, 140, 118, 44, C[2], "Flink", "stateful/CEP")
    s += card(765, 190, 118, 34, C[3], "KSQL", "SQL on Kafka")
    s += card(765, 230, 118, 22, C[4], "Spark", "micro-batch")

    s += arrow_down(450, 258, 276, C[3])
    s += section(15, 276, 870, 86, "CONSUMER GROUPS — SINKS", C[3])
    sinks = [("🏞️","Data Lake","S3"),("📊","ClickHouse","analytics"),("🔍","OpenSearch","search"),("🤖","ML Platform","features"),("📡","Dashboards","real-time"),("🚨","Alerting","PagerDuty"),("⚡","Cache","Redis")]
    sw = 860//len(sinks)
    for i,(ico,t,sub) in enumerate(sinks):
        s += flow_box(20+i*sw, 308, sw-6, 46, ico, t, sub, C[i%len(C)])

    s += arrow_down(450, 362, 380, C[5])
    s += section(15, 380, 870, 70, "OPERATIONS", C[5])
    ops=[("📊","Burrow","lag"),("🔐","mTLS","security"),("📏","Quotas","throttle"),("🔄","MirrorMaker2","geo-rep"),("📋","Audit","compliance")]
    ow=860//len(ops)
    for i,(ico,t,sub) in enumerate(ops):
        s += flow_box(20+i*ow, 412, ow-6, 32, ico, t, sub, C[i%len(C)])

    s += status_row(460, [("RF=3","#059669"),("12 partitions","#2563EB"),("7d retention","#7C3AED"),("Consumer lag OK","#059669"),("Schema valid","#D97706")])
    return s, "Streaming Architecture"


def make_zero_trust(C):
    s = ""
    s += tool_strip(72, [("🔐","Zero Trust"),("🆔","Okta/AAD"),("📱","Intune"),("🌐","Zscaler"),("⚔️","Cloudflare"),("📊","Sentinel")], C[0])

    s += two_col(15, 108, 870, 330, "CONTROL PLANE", C[0], "INTELLIGENCE", C[1], 0.58)

    pillars = [(C[0],"IDENTITY","MFA · SSO · RBAC · JIT"),(C[2],"DEVICE","MDM · posture · cert"),(C[3],"NETWORK","microseg · encrypt"),(C[4],"APPLICATION","least-priv · WAAP")]
    for i,(col,lbl,desc) in enumerate(pillars):
        y = 142 + i*68
        s += f'<rect x="22" y="{y}" width="484" height="56" rx="8" fill="{col}12" stroke="{col}" stroke-width="1.8"/>'
        s += f'<rect x="22" y="{y}" width="6" height="56" rx="3" fill="{col}"/>'
        s += f'<text x="36" y="{y+22}" fill="{col}" font-size="11" font-weight="700" font-family="Arial,sans-serif">{lbl}</text>'
        s += f'<text x="36" y="{y+40}" fill="{TEXT_MID}" font-size="10" font-family="Arial,sans-serif">{clamp(desc,40)}</text>'
        if i < 3: s += arrow_down(264, y+56, y+66, col)

    intel = [(C[1],"Threat Intel","IOC / STIX / TAXII"),(C[2],"UEBA","anomaly / risk score"),(C[3],"SIEM","correlate / SOAR"),(C[4],"AI Analysis","converge/diverge")]
    for i,(col,lbl,desc) in enumerate(intel):
        y = 142 + i*70
        s += flow_box(525, y, 350, 58, "", lbl, desc, col)
        if i < 3: s += arrow_down(700, y+58, y+68, col)

    s += arrow_down(450, 438, 456, C[0])
    s += section(15, 456, 870, 56, "POLICY DECISION POINT (PDP / PEP)", C[0])
    for i,(t,sub) in enumerate([("Authenticate","identity"),("Authorise","entitlement"),("Enforce","allow/deny"),("Audit","trail"),("Respond","revoke/alert")]):
        s += card(22+i*172, 490, 164, 16, C[i%len(C)], t, sub)

    s += status_row(522, [("Never Trust","#DC2626"),("Always Verify","#D97706"),("Least Privilege","#059669"),("Assume Breach","#7C3AED"),("Continuous Monitor","#0891B2")])
    return s, "Security Architecture"


def make_aws(C):
    s = ""
    s += tool_strip(72, [("☁️","AWS"),("🔒","IAM"),("🌐","CloudFront"),("⚡","Lambda"),("🗄️","Aurora"),("👁️","CloudWatch")], C[0])

    s += section(15, 108, 870, 38, "CLIENT LAYER", C[1])
    for i,(ico,t) in enumerate([("🌐","Browser"),("📱","Mobile"),("💻","CLI/SDK"),("🤝","Partners"),("🤖","IoT"),("🔌","Webhooks")]):
        cx = 15 + i*145 + 72
        s += f'<text x="{cx}" y="124" text-anchor="middle" font-size="12" font-family="Arial,sans-serif">{ico}</text>'
        s += f'<text x="{cx}" y="138" text-anchor="middle" fill="{TEXT_DARK}" font-size="9" font-weight="700" font-family="Arial,sans-serif">{t}</text>'

    s += arrow_down(450, 146, 162, C[0])
    s += section(15, 162, 870, 44, "EDGE LAYER", C[0])
    for i,(t,sub) in enumerate([("CloudFront","CDN"),("Route 53","DNS"),("WAF+Shield","DDoS"),("ACM","TLS"),("API Gateway","REST/WS")]):
        s += card(22+i*172, 176, 164, 26, C[i%len(C)], t, sub)
    for i in range(4): s += arrow_right(22+(i+1)*172-4, 22+(i+1)*172+4, 189, C[i%len(C)])

    s += arrow_down(450, 206, 222, C[1])
    s += two_col(15, 222, 870, 110, "COMPUTE", C[2], "MESSAGING", C[4], 0.49)
    compute=[("Lambda","serverless"),("ECS/Fargate","containers"),("EKS","Kubernetes"),("Step Fns","orchestrate"),("App Runner","web svc"),("Batch","job queues")]
    msg=[("SQS","queues"),("SNS","pub/sub"),("EventBridge","event bus"),("Kinesis","streaming"),("MSK","Kafka"),("SES","email")]
    for i,((t,s2),(mt,ms)) in enumerate(zip(compute[:3],msg[:3])):
        s += card(22+i*140, 256, 132, 30, C[i%len(C)], t, s2)
        s += card(22+i*140, 290, 132, 30, C[(i+3)%len(C)], compute[i+3][0], compute[i+3][1])
        s += card(457+i*136, 256, 128, 30, C[i%len(C)], mt, ms)
        s += card(457+i*136, 290, 128, 30, C[(i+3)%len(C)], msg[i+3][0], msg[i+3][1])

    s += arrow_down(450, 332, 348, C[3])
    s += two_col(15, 348, 870, 110, "DATA + STORAGE", C[3], "SECURITY + OBSERVABILITY", C[5], 0.49)
    data=[("S3","object"),("DynamoDB","NoSQL"),("RDS Aurora","Postgres"),("ElastiCache","Redis"),("Redshift","warehouse"),("Athena","S3 query")]
    sec=[("IAM","access ctrl"),("CloudWatch","metrics"),("CloudTrail","audit"),("GuardDuty","threats"),("Secrets Mgr","creds"),("X-Ray","tracing")]
    for i,((t,s2),(st,ss)) in enumerate(zip(data[:3],sec[:3])):
        s += card(22+i*138, 382, 130, 30, C[i%len(C)], t, s2)
        s += card(22+i*138, 416, 130, 30, C[(i+3)%len(C)], data[i+3][0], data[i+3][1])
        s += card(452+i*137, 382, 129, 30, C[i%len(C)], st, ss)
        s += card(452+i*137, 416, 129, 30, C[(i+3)%len(C)], sec[i+3][0], sec[i+3][1])

    s += status_row(470, [("3 AZs","#059669"),("Auto Scaling","#2563EB"),("WAF Active","#DC2626"),("Encrypted","#7C3AED"),("Compliant","#059669")])
    return s, "Cloud Architecture"


def make_mlops(C):
    s = ""
    s += tool_strip(72, [("📊","MLflow"),("🔄","DVC"),("🏗️","Kubeflow"),("🤗","HuggingFace"),("⚡","Ray"),("📡","Evidently")], C[0])

    rows = [
        (C[0],"DATA PIPELINE", [("Data Sources","S3/DB/APIs"),("Feature Eng","Spark/dbt"),("Validation","Gr.Expect"),("Feature Store","Feast"),("Versioning","DVC"),("Monitoring","drift")]),
        (C[1],"TRAINING",      [("Experiment","MLflow/W&B"),("Training","GPU cluster"),("Hyperparam","Optuna"),("Evaluation","F1/AUC"),("Registry","HF Hub"),("Baseline","A/B")]),
        (C[2],"SERVING",       [("Online","FastAPI/Triton"),("Batch","Spark/Ray"),("Streaming","Kafka+Model"),("Edge","ONNX/TFLite"),("Shadow","mirror"),("Rollback","auto")]),
        (C[3],"MONITORING",    [("Data Drift","PSI/KS"),("Model Perf","F1 degrad"),("Latency","p95/p99"),("Concept Drift","retrain"),("Explain","SHAP/LIME"),("Cost","GPU/$")]),
    ]
    y = 108
    rh = 90
    for col, lbl, items in rows:
        s += section(15, y, 870, rh, lbl, col)
        cw = 860 // len(items)
        for i,(t,sub) in enumerate(items):
            s += card(22+i*cw, y+34, cw-6, 48, C[i%len(C)], t, sub)
        if y < 360:
            s += arrow_down(450, y+rh, y+rh+8, col)
            y += rh + 8
        else:
            y += rh

    s += arrow_down(450, y, y+16, C[4])
    s += status_row(y+16, [("Experiment tracked","#7C3AED"),("Model versioned","#2563EB"),("Tests passed","#059669"),("Serving live","#0891B2"),("Alerts on","#D97706")])
    return s, "MLOps Pipeline"


def make_rag(C):
    s = ""
    s += tool_strip(72, [("📄","LangChain"),("🔍","Pinecone"),("🧠","OpenAI"),("🤗","HuggingFace"),("📊","RAGAS"),("⚡","Weaviate")], C[0])

    s += two_col(15, 108, 870, 340, "INGESTION PIPELINE", C[1], "RETRIEVAL + GENERATION", C[4], 0.48)

    ing = [(C[1],"SOURCES",[("📄","PDFs",""),("🌐","Web",""),("🗄️","DB",""),("📧","Email","")]),
           (C[2],"CHUNKING",[("✂️","Recursive","512 tok"),("🔲","Semantic","sent-aware"),("🪙","Token","model-spec"),("🔄","Overlap","50 tok")]),
           (C[3],"EMBEDDING",[("🧠","text-embed-3","OpenAI"),("⚡","E5-large","MTEB top"),("🌍","BGE-M3","multilingual"),("🎯","Cohere","rerank")])]
    ly = 142
    for col, lbl, items in ing:
        s += pill(22, ly, 80, 16, col, lbl)
        cw = 400 // len(items)
        for j,(ico,t,sub) in enumerate(items):
            s += flow_box(22+j*cw, ly+20, cw-4, 50, ico, t, sub, col)
        if ly < 320: s += arrow_down(225, ly+70, ly+80, col)
        ly += 80

    ret = [(C[4],"VECTOR STORE",[("🗂️","HNSW","graph ANN"),("📝","BM25","sparse"),("🔗","Hybrid","dense+sparse"),("📌","Metadata","filter")]),
           (C[5],"RETRIEVAL",[("🔎","Query Expand","HyDE"),("🎯","ANN Search","cosine"),("🏆","Re-ranker","cross-enc"),("📦","Context Pack","fill ctx")]),
           (C[0],"GENERATION",[("💬","LLM Prompt","sys+ctx"),("🛡️","Guardrails","safety"),("🔗","Citations","sources"),("📡","Stream","SSE")])]
    ry = 142
    for col, lbl, items in ret:
        s += pill(432, ry, 100, 16, col, lbl)
        cw = 435 // len(items)
        for j,(ico,t,sub) in enumerate(items):
            s += flow_box(432+j*cw, ry+20, cw-4, 50, ico, t, sub, col)
        if ry < 320: s += arrow_down(650, ry+70, ry+80, col)
        ry += 80

    s += arrow_down(450, 448, 464, C[3])
    s += section(15, 464, 870, 28, "EVALUATION — Faithfulness · Relevance · Context Recall · RAGAS · Hallucination %", C[3])
    s += status_row(500, [("Faithful","#059669"),("Relevant","#059669"),("No Hallucin","#059669"),("Fast <2s","#D97706"),("Citations OK","#2563EB")])
    return s, "System Architecture"


def make_system_design(C):
    s = ""
    s += tool_strip(72, [("🌐","React/Next"),("🔀","Nginx"),("🔑","OAuth2"),("🚀","K8s"),("🗄️","PostgreSQL"),("📡","Redis")], C[0])

    s += section(15, 108, 870, 38, "CLIENT LAYER", C[0])
    for i,(ico,t) in enumerate([("🌐","Browser"),("📱","Mobile"),("💻","Desktop"),("🤝","3rd Party"),("🤖","IoT")]):
        cx = 15 + i*174 + 87
        s += f'<text x="{cx}" y="122" text-anchor="middle" font-size="13" font-family="Arial,sans-serif">{ico}</text>'
        s += f'<text x="{cx}" y="136" text-anchor="middle" fill="{TEXT_DARK}" font-size="9" font-weight="700" font-family="Arial,sans-serif">{t}</text>'

    s += arrow_down(450, 146, 162, C[1])
    s += section(15, 162, 870, 40, "EDGE + AUTH", C[1])
    for i,(t,sub) in enumerate([("CDN","CloudFront"),("Load Balancer","L7"),("API Gateway","rate limit"),("Auth Service","OAuth2/JWT"),("WAF","L7 protect")]):
        s += card(22+i*172, 176, 164, 22, C[i%len(C)], t, sub)

    s += arrow_down(450, 202, 218, C[2])
    s += section(15, 218, 870, 96, "MICROSERVICES", C[2])
    for i,(t,sub) in enumerate([("User Svc","auth/profile"),("Order Svc","cart/checkout"),("Payment","Stripe/PCI"),("Notification","email/SMS"),("Search","Elasticsearch"),("Recommend","ML-powered"),("Analytics","events")]):
        s += card(20+i*124, 252, 118, 54, C[i%len(C)], t, sub)

    s += arrow_down(450, 314, 330, C[3])
    s += section(15, 330, 870, 42, "MESSAGE BROKER", C[3])
    for i,(t,sub) in enumerate([("Kafka","event stream"),("RabbitMQ","task queues"),("Redis PubSub","real-time"),("Dead Letter Q","failed msgs"),("EventBridge","event bus")]):
        s += card(22+i*172, 344, 164, 24, C[i%len(C)], t, sub)

    s += arrow_down(450, 372, 388, C[4])
    s += section(15, 388, 870, 72, "DATA LAYER", C[4])
    for i,(t,sub) in enumerate([("PostgreSQL","OLTP"),("Redis","cache"),("MongoDB","documents"),("S3","blobs"),("Elasticsearch","search"),("ClickHouse","analytics")]):
        s += card(22+i*144, 422, 136, 30, C[i%len(C)], t, sub)

    s += status_row(470, [("Load Balanced","#059669"),("Auth Active","#7C3AED"),("Events flowing","#2563EB"),("DB healthy","#059669"),("Cache hit 94%","#D97706")])
    return s, "System Architecture"


def make_devsecops(C):
    s = ""
    s += tool_strip(72, [("🔒","SAST/DAST"),("🐳","Trivy"),("☸️","Falco"),("📋","Semgrep"),("🛡️","OPA"),("📊","Splunk")], C[0])

    phases=[("IDE","💻","Pre-commit","git-secrets",C[0]),("SCM","📝","Review","SAST",C[1]),("Build","🏗️","Compile","SCA/SBOM",C[2]),
            ("Test","🧪","Quality","DAST/ZAP",C[3]),("Artifact","📦","Registry","Trivy+sign",C[4]),("Stage","🚀","Deploy","IaC scan",C[5]),("Prod","🛡️","Runtime","Falco/eBPF",C[0])]
    pw = 870 // len(phases)
    for i,(env,ico,phase,tools,col) in enumerate(phases):
        x = 15 + i*pw
        s += f'<rect x="{x}" y="108" width="{pw-2}" height="196" rx="8" fill="{col}0D" stroke="{col}50" stroke-width="1.5"/>'
        s += f'<rect x="{x}" y="108" width="{pw-2}" height="28" rx="8" fill="{col}"/>'
        s += f'<rect x="{x}" y="122" width="{pw-2}" height="14" fill="{col}"/>'
        s += f'<text x="{x+(pw-2)//2}" y="127" text-anchor="middle" fill="white" font-size="10" font-weight="700" font-family="Arial,sans-serif">{env}</text>'
        s += f'<text x="{x+(pw-2)//2}" y="165" text-anchor="middle" font-size="22" font-family="Arial,sans-serif">{ico}</text>'
        s += f'<text x="{x+(pw-2)//2}" y="186" text-anchor="middle" fill="{col}" font-size="9" font-weight="700" font-family="Arial,sans-serif">{clamp(phase,10)}</text>'
        s += f'<text x="{x+(pw-2)//2}" y="202" text-anchor="middle" fill="{TEXT_MID}" font-size="8" font-family="Arial,sans-serif">{clamp(tools,12)}</text>'
        if i < len(phases)-1:
            s += arrow_right(x+pw-2, x+pw+2, 204, col)

    s += status_row(312, [("Secrets Blocked","#DC2626"),("CVE Scanned","#D97706"),("Signed Image","#059669"),("Policy Checked","#7C3AED"),("Runtime Watch","#2563EB"),("Audit Trail","#059669")])

    s += two_col(15, 344, 870, 114, "SIEM + INCIDENT RESPONSE", C[4], "COMPLIANCE + POLICY", C[1], 0.5)
    for i,(t,sub,col) in enumerate([("SIEM","Splunk/Sentinel",C[4]),("SOAR","auto-remediate",C[5]),("Threat Intel","IOC feeds",C[0])]):
        s += card(22+i*143, 378, 137, 72, col, t, sub)
    s += arrow_right(159, 165, 414, C[4]); s += arrow_right(302, 308, 414, C[5])
    for i,(t,sub,col) in enumerate([("CIS Benchmarks","hardening",C[1]),("SOC2/ISO27K","audit",C[2]),("OPA/Rego","policy-as-code",C[3])]):
        s += card(456+i*143, 378, 137, 72, col, t, sub)

    s += status_row(468, [("NIST CSF","#059669"),("ISO 27001","#2563EB"),("SOC2 Type II","#7C3AED"),("GDPR","#D97706"),("PCI-DSS","#DC2626")])
    return s, "Security Pipeline"


def make_lakehouse(C):
    s = ""
    s += tool_strip(72, [("🔥","Spark"),("❄️","Delta Lake"),("🧊","Iceberg"),("🌊","Flink"),("🔵","dbt"),("📊","Trino")], C[0])

    s += section(15, 108, 870, 58, "INGESTION SOURCES", C[0])
    srcs=[("📊","Batch ETL","Airflow"),("🌊","Streaming","Kafka"),("🔌","CDC","Debezium"),("📡","API Pull","REST"),("📂","File Drop","S3 trigger"),("🤖","IoT/MQTT","edge"),("📱","App Events","SDK")]
    sw = 860 // len(srcs)
    for i,(ico,t,sub) in enumerate(srcs):
        s += flow_box(20+i*sw, 118, sw-4, 42, ico, t, sub, C[i%len(C)])

    s += arrow_down(450, 166, 182, C[1])
    s += section(15, 182, 870, 58, "OPEN TABLE FORMAT LAYER", C[1])
    for i,(t,sub) in enumerate([("Delta Lake","ACID + time travel"),("Apache Iceberg","schema evolution"),("Apache Hudi","upserts/deletes"),("Metadata Catalog","Glue/Hive")]):
        s += card(22+i*214, 214, 206, 22, C[i%len(C)], t, sub)

    s += arrow_down(450, 240, 256, C[2])
    s += section(15, 256, 870, 58, "COMPUTE ENGINE", C[2])
    for i,(t,sub) in enumerate([("Apache Spark","SQL/ML/stream"),("Trino/Presto","interactive SQL"),("dbt","transform/test"),("Ray","ML distributed"),("Flink","stream proc")]):
        s += card(22+i*172, 288, 164, 22, C[i%len(C)], t, sub)

    s += arrow_down(450, 314, 330, C[3])
    s += two_col(15, 330, 870, 120, "CONSUMPTION LAYER", C[3], "GOVERNANCE", C[5], 0.55)
    for i,(t,sub,col) in enumerate([("BI Tools","Tableau/Superset",C[3]),("ML Platform","SageMaker",C[4]),("Ad-hoc SQL","Athena",C[5]),("Real-time","Grafana",C[0])]):
        s += card(22+i*118, 364, 112, 78, col, t, sub)
    s += card(502, 364, 175, 78, C[5], "Data Catalog", "lineage+search")
    s += card(684, 364, 188, 78, C[0], "Row-level Sec", "GDPR/RBAC")

    s += status_row(460, [("Bronze","#B45309"),("Silver","#94A3B8"),("Gold","#D97706"),("Serving","#059669"),("Governed","#7C3AED")])
    return s, "Data Architecture"


def make_docker(C):
    s = ""
    s += tool_strip(72, [("🐳","Docker Engine"),("📦","Docker Hub"),("🔧","Compose"),("🔒","Scout"),("☸️","Swarm"),("🏗️","Buildx")], C[0])

    rows = [
        (C[0],"Dockerfile", [("📝","FROM","base image"),("📋","RUN","exec cmd"),("📂","COPY/ADD","files in"),("🔌","EXPOSE","port hint"),("▶️","CMD","entrypoint"),("🏷️","LABEL/ARG","metadata")]),
        (C[1],"Images",     [("🏗️","build","create image"),("📋","images","list local"),("🔍","inspect","image detail"),("🏷️","tag","rename"),("⬆️","push","to registry"),("🗑️","rmi","delete")]),
        (C[2],"Containers", [("▶️","run","start new"),("⏸️","stop","graceful"),("📋","ps","list running"),("🔍","logs","stdout"),("💻","exec","shell in"),("🗑️","rm","cleanup")]),
        (C[3],"Networking", [("🌉","bridge","default LAN"),("🏠","host","share net"),("🔒","none","isolated"),("🔗","overlay","multi-host"),("📡","macvlan","L2 assign"),("🔌","port map","-p 8080:80")]),
        (C[4],"Volumes",    [("💾","volume","Docker managed"),("📂","bind mount","host path"),("🧠","tmpfs","RAM only"),("📥","docker cp","copy files"),("📋","volume ls","list all"),("🔄","backup","tar + cp")]),
        (C[5],"Compose",    [("📄","compose.yml","define stack"),("🚀","up -d","start detach"),("📋","ps","check status"),("📊","logs -f","follow"),("🔄","restart","cycle svc"),("🛑","down","stop+rm")]),
    ]
    y = 108
    for col, label, items in rows:
        s += cheatrow(y, 64, label, col, items)
        y += 68

    s += status_row(y+2, [("Layer Cache","#0891B2"),("Multi-stage","#059669"),("Non-root","#D97706"),(".dockerignore","#7C3AED"),("Healthcheck","#DC2626"),("Read-only FS","#2563EB")])
    return s, "Cheatsheet"


def make_git_workflow(C):
    s = ""
    s += tool_strip(72, [("🌿","Git"),("🐙","GitHub"),("🦊","GitLab"),("🪣","Bitbucket"),("🔄","Git Flow"),("📝","Conventional")], C[0])

    rows = [
        (C[0],"Setup",      [("👤","config","name+email"),("🔑","SSH key","auth setup"),("📁","init","new repo"),("📥","clone","copy remote"),("🔗","remote","add origin"),("📋","status","see changes")]),
        (C[1],"Branching",  [("🌿","branch","list/create"),("🔀","checkout","switch/new"),("🔀","switch","modern way"),("🌊","git flow","feature br"),("🏷️","tag","version mark"),("🗑️","branch -d","delete")]),
        (C[2],"Staging",    [("➕","add .","stage all"),("➕","add -p","stage hunks"),("📝","commit","save snap"),("✏️","--amend","fix last"),("💾","stash","shelve WIP"),("📋","stash pop","restore")]),
        (C[3],"Remote",     [("⬆️","push","upload"),("⬇️","pull","fetch+merge"),("📥","fetch","download"),("🔄","rebase","linearise"),("🔃","merge","combine"),("🍒","cherry-pick","single commit")]),
        (C[4],"History",    [("📜","log","see commits"),("🔍","diff","what changed"),("🕰️","blame","who changed"),("⏪","reset","undo"),("↩️","revert","safe undo"),("🔎","bisect","find bug")]),
        (C[5],"Practice",   [("📋","feat:/fix:","commit msg"),("🛡️","protect","require PR"),("✅","PR review","2 approvers"),("🔏","sign","GPG key"),("📖","CHANGELOG","keep updated"),("🤖","CI on PR","auto check")]),
    ]
    y = 108
    for col, label, items in rows:
        s += cheatrow(y, 64, label, col, items)
        y += 68

    s += status_row(y+2, [("trunk-based","#DC2626"),("feature flags","#7C3AED"),("atomic commits","#059669"),("no force-push","#D97706"),("rebase > merge","#0891B2")])
    return s, "Cheatsheet"


def make_api_design(C):
    s = ""
    s += tool_strip(72, [("🔌","REST"),("📡","GraphQL"),("⚡","gRPC"),("🌐","WebSocket"),("📋","OpenAPI"),("🔐","OAuth2")], C[0])

    # 4 API type boxes
    types=[("REST",C[0],[("GET","read"),("POST","create"),("PUT/PATCH","update"),("DELETE","remove")]),
           ("GraphQL",C[1],[("Query","fetch"),("Mutation","write"),("Subscription","realtime"),("Resolver","field logic")]),
           ("gRPC",C[2],[("Unary","req→res"),("Server Stream","1→many"),("Client Stream","many→1"),("Bi-di","both ways")]),
           ("WebSocket",C[3],[("Upgrade","HTTP→WS"),("Frame","data unit"),("Ping/Pong","heartbeat"),("Close","teardown")])]
    tw = 210
    for i,(nm,col,ops) in enumerate(types):
        x = 15 + i*(tw+6)
        s += section(x, 108, tw, 126, nm, col)
        for j,(op,desc) in enumerate(ops):
            s += f'<rect x="{x+6}" y="{140+j*22}" width="{tw-12}" height="18" rx="5" fill="{col}15"/>'
            s += f'<text x="{x+14}" y="{140+j*22+12}" fill="{col}" font-size="9" font-weight="700" font-family="Arial,sans-serif">{clamp(op,14)}</text>'
            s += f'<text x="{x+tw-8}" y="{140+j*22+12}" text-anchor="end" fill="{TEXT_MID}" font-size="9" font-family="Arial,sans-serif">{clamp(desc,12)}</text>'

    # Cheatsheet rows
    mid_rows = [
        (C[4],"Design",    [("📝","Nouns not Verbs","/users not /getUser"),("🔢","Versioning","v1/ in URL"),("📄","Pagination","cursor/offset"),("🔗","HATEOAS","links in resp"),("📦","Nesting","/users/123/posts")]),
        (C[5],"Security",  [("🔐","Bearer JWT","Authorization hdr"),("⏱️","Rate Limit","429 Too Many"),("🔒","HTTPS","TLS 1.3 min"),("🛡️","Validate","schema+sanitise"),("📝","Audit Log","who/what/when")]),
        (C[0],"Responses", [("✅","200 OK","success"),("➕","201 Created","POST ok"),("❌","400 Bad Req","client err"),("🔐","401/403","auth fail"),("💥","500 Internal","server fault")]),
    ]
    y = 246
    for col, label, items in mid_rows:
        s += cheatrow(y, 56, label, col, items)
        y += 60

    s += section(15, y+4, 870, 50, "REQUEST LIFECYCLE", C[3])
    flow=[("🌐","Client",""),("🔀","Gateway",""),("🔐","Auth",""),("📋","Validate",""),("⚙️","Handler",""),("💾","Data",""),("📤","Response","")]
    fw = 860 // len(flow)
    for i,(ico,t,sub) in enumerate(flow):
        s += flow_box(20+i*fw, y+18, fw-4, 32, ico, t, "", C[i%len(C)])
        if i < len(flow)-1: s += arrow_right(20+(i+1)*fw-4, 20+(i+1)*fw+2, y+34, C[i%len(C)])
    return s, "Design Reference"


def make_solid(C):
    s = ""
    s += tool_strip(72, [("📐","SOLID"),("🏗️","Clean Code"),("🔌","OOP"),("🧪","TDD"),("🔄","Refactor"),("📦","DDD")], C[0])

    principles = [
        ("S","Single Responsibility","One class, one reason to change",C[0],["One job only","Separate concerns","Easier testing","e.g. UserSvc vs Emailer"]),
        ("O","Open / Closed","Open to extend, closed to modify",C[1],["Extend via inheritance","Don't change tested code","Use interfaces","e.g. add PaymentMethod"]),
        ("L","Liskov Substitution","Subtypes must honour base contract",C[2],["Child = parent shape","No surprise exceptions","Covariant returns","e.g. Square ≠ Rectangle"]),
        ("I","Interface Segregation","Many small interfaces > one fat",C[3],["No unused methods","Split fat interfaces","Focused contracts","e.g. Printable, Scannable"]),
        ("D","Dependency Inversion","Depend on abstractions not concretions",C[4],["High-level → interfaces","Inject dependencies","Don't new() inside","e.g. UserSvc(IEmailer)"]),
    ]

    cw = 162
    spine_y = 172
    for i in range(4):
        cx1 = 15 + i*(cw+12) + cw
        cx2 = 15 + (i+1)*(cw+12)
        s += f'<line x1="{cx1}" y1="{spine_y}" x2="{cx2}" y2="{spine_y}" stroke="{C[i]}60" stroke-width="3" stroke-dasharray="5,3"/>'

    for i,(letter,name,tagline,col,bullets) in enumerate(principles):
        x = 15 + i*(cw+12)
        mid_x = x + cw//2
        # milestone node
        s += f'<circle cx="{mid_x}" cy="{spine_y}" r="26" fill="{col}20" stroke="{col}" stroke-width="2.5"/>'
        s += f'<circle cx="{mid_x}" cy="{spine_y}" r="20" fill="{col}"/>'
        s += f'<text x="{mid_x}" y="{spine_y+7}" text-anchor="middle" fill="white" font-size="16" font-weight="800" font-family="Arial,sans-serif">{letter}</text>'
        # card
        cy = spine_y + 32
        s += f'<rect x="{x}" y="{cy}" width="{cw}" height="266" rx="10" fill="{BG}" stroke="{col}50" stroke-width="1.5"/>'
        s += f'<rect x="{x}" y="{cy}" width="{cw}" height="30" rx="10" fill="{col}"/>'
        s += f'<rect x="{x}" y="{cy+16}" width="{cw}" height="14" fill="{col}"/>'
        s += f'<text x="{mid_x}" y="{cy+21}" text-anchor="middle" fill="white" font-size="10" font-weight="700" font-family="Arial,sans-serif">{clamp(name,14)}</text>'
        s += f'<text x="{mid_x}" y="{cy+48}" text-anchor="middle" fill="{col}" font-size="8" font-style="italic" font-family="Arial,sans-serif">{clamp(tagline,22)}</text>'
        for j,b in enumerate(bullets):
            by = cy + 62 + j*46
            s += f'<rect x="{x+6}" y="{by}" width="{cw-12}" height="38" rx="6" fill="{col}10" stroke="{col}30" stroke-width="1"/>'
            words = b.split(); mid = len(words)//2 or 1
            l1 = " ".join(words[:mid]); l2 = " ".join(words[mid:])
            s += f'<text x="{mid_x}" y="{by+14}" text-anchor="middle" fill="{TEXT_DARK}" font-size="8.5" font-weight="600" font-family="Arial,sans-serif">{clamp(l1,20)}</text>'
            s += f'<text x="{mid_x}" y="{by+27}" text-anchor="middle" fill="{TEXT_MID}" font-size="8" font-family="Arial,sans-serif">{clamp(l2,22)}</text>'

    s += status_row(490, [("Maintainable","#7C3AED"),("Testable","#2563EB"),("Extensible","#059669"),("Scalable","#D97706"),("Readable","#0891B2")])
    return s, "Design Principles"


def make_generic(topic_name, C):
    s = ""
    s += tool_strip(72, [("🌐","Web/Mobile"),("🔀","API Gateway"),("⚡","Services"),("🚀","Queue"),("🗄️","Database"),("📡","Cache")], C[0])

    s += section(15, 108, 870, 44, "CLIENT + EDGE", C[0])
    for i,(t,sub) in enumerate([("Web/Mobile","React/Native"),("CDN","CloudFront"),("API Gateway","rate limit"),("Auth Service","OAuth2/JWT"),("WAF + DNS","Route53")]):
        s += card(22+i*172, 122, 164, 24, C[i%len(C)], t, sub)

    s += arrow_down(450, 152, 168, C[1])
    s += two_col(15, 168, 870, 140, "MICROSERVICES", C[1], "SUPPORTING SERVICES", C[2])
    for j,(t,sub,col) in enumerate([("User Service","auth/profile",C[1]),("Order Service","cart/checkout",C[2]),("Notification","email/SMS",C[3])]):
        s += card(22, 202+j*38, 210, 32, col, t, sub, light=True)
        s += card(242, 202+j*38, 188, 32, t+" Worker","async process", C[4], light=True)
        s += arrow_right(230, 242, 202+j*38+16, C[1])
    for j,(t,sub,col) in enumerate([("Search","Elasticsearch",C[2]),("Analytics","ClickHouse",C[3]),("ML / AI","model serving",C[4])]):
        s += card(452, 202+j*38, 200, 32, col, t, sub, light=True)
        s += card(662, 202+j*38, 212, 32, t.split()[0]+" Store","primary data", C[5], light=True)
        s += arrow_right(652, 662, 202+j*38+16, C[2])

    s += arrow_down(450, 308, 324, C[3])
    s += section(15, 324, 870, 48, "MESSAGE LAYER", C[3])
    for i,(t,sub) in enumerate([("Kafka","event stream"),("RabbitMQ","task queues"),("Redis","cache/pub-sub"),("SQS","managed queue"),("EventBridge","event bus")]):
        s += card(22+i*172, 338, 164, 28, C[i%len(C)], t, sub)

    s += arrow_down(450, 372, 388, C[4])
    s += section(15, 388, 870, 86, "DATA STORES", C[4])
    for i,(t,sub) in enumerate([("PostgreSQL","OLTP"),("Redis","sessions"),("MongoDB","documents"),("S3/Blob","media"),("Elasticsearch","search"),("ClickHouse","analytics")]):
        s += card(22+i*144, 422, 136, 44, C[i%len(C)], t, sub)

    s += status_row(484, [("Load Balanced","#059669"),("Auth Active","#7C3AED"),("Events OK","#2563EB"),("DB Healthy","#059669"),("Cache Hot","#D97706")])
    return s, "System Architecture"


# ── DISPATCHER ────────────────────────────────────────────────────────────────
def make_diagram(topic_name, topic_id, diagram_type=""):
    C   = get_pal(topic_id)
    now = datetime.now().strftime("%B %Y")
    tid = topic_id.lower()

    if   "kube"  in tid:                            content, sub = make_kubernetes(C)
    elif any(x in tid for x in ["llm","agent"]):    content, sub = make_llm(C)
    elif "cicd"  in tid:                            content, sub = make_cicd(C)
    elif "kafka" in tid:                            content, sub = make_kafka(C)
    elif "zero"  in tid:                            content, sub = make_zero_trust(C)
    elif "aws"   in tid:                            content, sub = make_aws(C)
    elif "devsec" in tid:                           content, sub = make_devsecops(C)
    elif "system" in tid:                           content, sub = make_system_design(C)
    elif "mlops" in tid:                            content, sub = make_mlops(C)
    elif any(x in tid for x in ["lake","data"]):    content, sub = make_lakehouse(C)
    elif "rag"   in tid:                            content, sub = make_rag(C)
    elif "docker" in tid:                           content, sub = make_docker(C)
    elif "git"   in tid:                            content, sub = make_git_workflow(C)
    elif "api"   in tid:                            content, sub = make_api_design(C)
    elif "solid" in tid:                            content, sub = make_solid(C)
    else:                                           content, sub = make_generic(topic_name, C)

    return wrap(content, topic_name, sub, C[0], now)


# ── CLASS INTERFACE ───────────────────────────────────────────────────────────
class DiagramGenerator:
    def __init__(self):
        Path(OUTPUT_DIR).mkdir(exist_ok=True)
        log.info("Diagram output dir: " + OUTPUT_DIR + "/")

    def save_svg(self, svg_content, topic_id, topic_name="", diagram_type="Architecture Diagram"):
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{OUTPUT_DIR}/{topic_id}_{ts}.svg"
        svg      = make_diagram(topic_name or topic_id, topic_id, diagram_type)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(svg)
        size_kb = os.path.getsize(filename) / 1024
        log.info(f"Diagram saved: {filename} ({round(size_kb,1)} KB)")
        return filename
