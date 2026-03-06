import os
from datetime import datetime
from pathlib import Path
from logger import get_logger

log = get_logger("diagrams")
OUTPUT_DIR = "diagrams"

# ── PALETTES ──────────────────────────────────────────────────────────────────
PALETTES = {
    "ai":       ["#6D28D9","#2563EB","#0891B2","#059669","#D97706","#BE185D"],
    "cloud":    ["#1D4ED8","#0891B2","#047857","#B45309","#7C3AED","#BE185D"],
    "security": ["#B91C1C","#C2410C","#7C3AED","#0891B2","#047857","#1D4ED8"],
    "data":     ["#7C3AED","#1D4ED8","#0891B2","#047857","#D97706","#B91C1C"],
    "devops":   ["#047857","#1D4ED8","#7C3AED","#D97706","#B91C1C","#0891B2"],
    "default":  ["#1D4ED8","#7C3AED","#047857","#D97706","#B91C1C","#0891B2"],
}

def get_pal(tid):
    t = tid.lower()
    if any(x in t for x in ["llm","rag","agent","mlops"]): return PALETTES["ai"]
    if any(x in t for x in ["kube","docker","aws","cicd"]): return PALETTES["cloud"]
    if any(x in t for x in ["zero","devsec"]): return PALETTES["security"]
    if any(x in t for x in ["kafka","data","lake"]): return PALETTES["data"]
    return PALETTES["default"]

# ── PRIMITIVES ────────────────────────────────────────────────────────────────

def banner_section(x, y, w, h, label, color, rx=10):
    """Full-width solid color header bar + tinted content area — key new pattern."""
    bh = 28  # header bar height
    s  = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}" fill-opacity="0.07" stroke="{color}" stroke-width="1.5" stroke-opacity="0.4"/>'
    s += f'<rect x="{x}" y="{y}" width="{w}" height="{bh}" rx="{rx}" fill="{color}"/>'
    s += f'<rect x="{x}" y="{y+rx}" width="{w}" height="{bh-rx}" fill="{color}"/>'  # square bottom of header
    s += f'<text x="{x+w//2}" y="{y+19}" text-anchor="middle" fill="white" font-size="12" font-weight="bold" font-family="Arial,sans-serif" letter-spacing="0.5">{label}</text>'
    return s

def card(x, y, w, h, color, title, sub="", rx=8):
    """Solid filled card with white title and lighter subtitle."""
    s  = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}"/>'
    s += f'<rect x="{x}" y="{y}" width="{w}" height="3" rx="{rx}" fill="white" opacity="0.25"/>'
    mid = y + h//2
    if sub:
        s += f'<text x="{x+w//2}" y="{mid-3}" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">{title}</text>'
        s += f'<text x="{x+w//2}" y="{mid+11}" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-size="9" font-family="Arial,sans-serif">{sub}</text>'
    else:
        s += f'<text x="{x+w//2}" y="{mid+4}" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">{title}</text>'
    return s

def fat_arrow_down(cx, y1, y2, color, label=""):
    """Large fat downward arrow between sections — key new pattern."""
    aw, ah = 14, y2 - y1
    hw = 22  # arrowhead width
    body_h = ah - 12
    pts = (f"{cx-aw//2},{y1} {cx+aw//2},{y1} {cx+aw//2},{y1+body_h} "
           f"{cx+hw//2},{y1+body_h} {cx},{y2} {cx-hw//2},{y1+body_h} {cx-aw//2},{y1+body_h}")
    s  = f'<polygon points="{pts}" fill="{color}" opacity="0.85"/>'
    if label:
        lx, ly = cx, y1 + (ah // 2) - 2
        bw = len(label)*6+10
        s += f'<rect x="{lx-bw//2}" y="{ly-8}" width="{bw}" height="14" rx="4" fill="#0F172A" opacity="0.8"/>'
        s += f'<text x="{lx}" y="{ly+3}" text-anchor="middle" fill="white" font-size="8" font-weight="bold" font-family="Arial,sans-serif">{label}</text>'
    return s

def fat_arrow_right(x1, x2, cy, color, label=""):
    """Large fat rightward arrow."""
    aw, aw2 = x2-x1, 14
    body_w = aw - 12
    ah2 = 22
    pts = (f"{x1},{cy-aw2//2} {x1+body_w},{cy-aw2//2} {x1+body_w},{cy-ah2//2} "
           f"{x2},{cy} {x1+body_w},{cy+ah2//2} {x1+body_w},{cy+aw2//2} {x1},{cy+aw2//2}")
    s = f'<polygon points="{pts}" fill="{color}" opacity="0.75"/>'
    if label:
        mx = x1 + aw//2
        bw = len(label)*6+10
        s += f'<rect x="{mx-bw//2}" y="{cy-8}" width="{bw}" height="14" rx="4" fill="#0F172A" opacity="0.8"/>'
        s += f'<text x="{mx}" y="{cy+3}" text-anchor="middle" fill="white" font-size="8" font-weight="bold" font-family="Arial,sans-serif">{label}</text>'
    return s

def thin_arrow(x1, y1, x2, y2, color="white", dashed=False):
    """Thin connector arrow for within-section links."""
    dash = 'stroke-dasharray="5,3"' if dashed else ''
    uid  = f"arr{abs(x1)}{abs(y1)}{abs(x2)}{abs(y2)}"
    s  = f'<defs><marker id="{uid}" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="{color}" opacity="0.9"/></marker></defs>'
    s += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.8" {dash} marker-end="url(#{uid})" opacity="0.7"/>'
    return s

def tool_strip(tools, y=90, accent="#0EA5E9"):
    """Top row of tool name badges — like the Grafana/Splunk/OTel strip in reference."""
    s = f'<rect x="15" y="{y}" width="870" height="32" rx="8" fill="white" fill-opacity="0.04" stroke="white" stroke-opacity="0.08" stroke-width="1"/>'
    n = len(tools)
    w = 870 // n
    for i, (ico, name, col) in enumerate(tools):
        cx = 15 + i*w + w//2
        s += f'<text x="{cx-18}" y="{y+20}" text-anchor="end" font-size="15" font-family="Arial,sans-serif" opacity="0.9">{ico}</text>'
        s += f'<text x="{cx-10}" y="{y+21}" fill="{col}" font-size="12" font-weight="bold" font-family="Arial,sans-serif" letter-spacing="0.3">{name}</text>'
        if i < n-1:
            lx = 15 + (i+1)*w
            s += f'<line x1="{lx}" y1="{y+6}" x2="{lx}" y2="{y+26}" stroke="white" stroke-width="0.5" opacity="0.15"/>'
    return s

def status_bar(items, y, h=26):
    """Dark pill row with coloured dots — like Healthy•Degraded•Critical in reference."""
    total_w = 870
    s = f'<rect x="15" y="{y}" width="{total_w}" height="{h}" rx="{h//2}" fill="#0F172A" stroke="white" stroke-opacity="0.12" stroke-width="1"/>'
    iw = total_w // len(items)
    for i, (label, color) in enumerate(items):
        cx = 15 + i*iw + iw//2
        s += f'<circle cx="{cx-len(label)*4-6}" cy="{y+h//2}" r="5" fill="{color}"/>'
        s += f'<text x="{cx-len(label)*4+2}" y="{y+h//2+4}" fill="white" font-size="11" font-weight="600" font-family="Arial,sans-serif">{label}</text>'
    return s

def two_col_header(x, y, w, h, label1, color1, label2, color2, split=0.55):
    """Two-column split section header — like Operational Signals | AI Intelligence."""
    w1 = int(w * split)
    w2 = w - w1
    rx = 10
    s  = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="none" stroke="white" stroke-opacity="0.08" stroke-width="1"/>'
    # left header
    s += f'<rect x="{x}" y="{y}" width="{w1}" height="28" rx="{rx}" fill="{color1}"/>'
    s += f'<rect x="{x+rx}" y="{y}" width="{w1-rx}" height="28" fill="{color1}"/>'
    s += f'<text x="{x+w1//2}" y="{y+19}" text-anchor="middle" fill="white" font-size="12" font-weight="bold" font-family="Arial,sans-serif">{label1}</text>'
    # right header
    s += f'<rect x="{x+w1}" y="{y}" width="{w2}" height="28" rx="{rx}" fill="{color2}"/>'
    s += f'<rect x="{x+w1}" y="{y}" width="{w2-rx}" height="28" fill="{color2}"/>'
    s += f'<text x="{x+w1+w2//2}" y="{y+19}" text-anchor="middle" fill="white" font-size="12" font-weight="bold" font-family="Arial,sans-serif">{label2}</text>'
    # divider
    s += f'<line x1="{x+w1}" y1="{y}" x2="{x+w1}" y2="{y+h}" stroke="white" stroke-opacity="0.15" stroke-width="1" stroke-dasharray="4,3"/>'
    # tinted backgrounds
    s += f'<rect x="{x}" y="{y+28}" width="{w1}" height="{h-28}" rx="0" fill="{color1}" fill-opacity="0.05"/>'
    s += f'<rect x="{x+w1}" y="{y+28}" width="{w2}" height="{h-28}" rx="0" fill="{color2}" fill-opacity="0.05"/>'
    return s


# ── NEW PRIMITIVES (Images 2 · 3 · 4 · 5) ────────────────────────────────────

def cheatsheet_row(y, h, label, color, items):
    """Image 2 style: left category label with accent bar → icon-card grid."""
    s  = f'<rect x="15" y="{y}" width="870" height="{h}" rx="8" fill="{color}" fill-opacity="0.06" stroke="{color}" stroke-width="1.2" stroke-opacity="0.3"/>'
    s += f'<rect x="15" y="{y}" width="5" height="{h}" rx="3" fill="{color}"/>'
    lbl_end = 22 + len(label)*7
    s += f'<text x="26" y="{y+h//2+4}" fill="{color}" font-size="11" font-weight="bold" font-family="Arial,sans-serif">{label}</text>'
    ax = lbl_end + 4
    s += f'<polygon points="{ax},{y+h//2-4} {ax+9},{y+h//2} {ax},{y+h//2+4}" fill="{color}" opacity="0.5"/>'
    card_x = ax + 14
    avail = 880 - card_x
    cw = avail // len(items) - 4
    for i, item in enumerate(items):
        ico, title, sub = item[0], item[1], item[2] if len(item)>2 else ""
        cx = card_x + i*(cw+4)
        s += f'<rect x="{cx}" y="{y+4}" width="{cw}" height="{h-8}" rx="7" fill="{color}" fill-opacity="0.16" stroke="{color}" stroke-opacity="0.22" stroke-width="1"/>'
        s += f'<text x="{cx+cw//2}" y="{y+18}" text-anchor="middle" font-size="15" font-family="Arial,sans-serif">{ico}</text>'
        s += f'<text x="{cx+cw//2}" y="{y+h//2+4}" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{title}</text>'
        if sub:
            s += f'<text x="{cx+cw//2}" y="{y+h-10}" text-anchor="middle" fill="rgba(255,255,255,0.5)" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
    return s

def subsystem_group(x, y, w, h, label, color, rx=10):
    """Image 4 style: colored-border box (NOT solid filled). Label badge on top border."""
    lw = len(label)*7 + 20
    s  = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}" fill-opacity="0.09" stroke="{color}" stroke-width="2"/>'
    s += f'<rect x="{x+12}" y="{y-10}" width="{lw}" height="20" rx="10" fill="{color}"/>'
    s += f'<text x="{x+12+lw//2}" y="{y+4}" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif" letter-spacing="0.4">{label}</text>'
    return s

def stat_tile(x, y, w, h, value, label, delta="", color="#0EA5E9"):
    """Image 5 style: KPI metric tile with large value and optional delta badge."""
    s  = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="1.5"/>'
    s += f'<rect x="{x}" y="{y}" width="{w}" height="3" rx="8" fill="{color}"/>'
    s += f'<text x="{x+w//2}" y="{y+h//2-2}" text-anchor="middle" fill="white" font-size="24" font-weight="bold" font-family="Arial,sans-serif">{value}</text>'
    s += f'<text x="{x+w//2}" y="{y+h//2+16}" text-anchor="middle" fill="rgba(255,255,255,0.6)" font-size="9" font-family="Arial,sans-serif">{label}</text>'
    if delta:
        dcol = "#22C55E" if "+" in delta else "#EF4444"
        s += f'<rect x="{x+w-34}" y="{y+6}" width="28" height="14" rx="7" fill="{dcol}" fill-opacity="0.2"/>'
        s += f'<text x="{x+w-20}" y="{y+17}" text-anchor="middle" fill="{dcol}" font-size="8" font-weight="bold" font-family="Arial,sans-serif">{delta}</text>'
    return s

def mini_sparkline(x, y, w, h, points, color):
    """Image 5 style: tiny inline sparkline."""
    if len(points) < 2: return ""
    mn, mx2 = min(points), max(points)
    rng = mx2 - mn or 1
    def px(i): return x + int(i * w / (len(points)-1))
    def py(v): return y + h - int((v-mn)/rng * h)
    pts = " ".join(f"{px(i)},{py(v)}" for i,v in enumerate(points))
    area = f"{x},{y+h} " + pts + f" {x+w},{y+h}"
    s  = f'<polygon points="{area}" fill="{color}" fill-opacity="0.18"/>'
    s += f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
    ex, ey = px(len(points)-1), py(points[-1])
    s += f'<circle cx="{ex}" cy="{ey}" r="3.5" fill="{color}"/>'
    return s

def roadmap_node(cx, cy, r, num, color, active=False):
    """Image 3 style: numbered milestone circle for roadmap/journey diagrams."""
    s  = f'<circle cx="{cx}" cy="{cy}" r="{r+8}" fill="{color}" opacity="0.12"/>'
    s += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>'
    if active:
        s += f'<circle cx="{cx}" cy="{cy}" r="{r+14}" fill="none" stroke="{color}" stroke-width="2.5" opacity="0.35"/>'
    s += f'<text x="{cx}" y="{cy+int(r*0.4)}" text-anchor="middle" fill="white" font-size="{int(r*0.75)}" font-weight="bold" font-family="Arial,sans-serif">{num}</text>'
    return s

def flow_box(x, y, w, h, label, sub, color, ico=""):
    """Image 4/5 style: bordered flow box with optional icon — not solid filled."""
    s  = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{color}" fill-opacity="0.1" stroke="{color}" stroke-width="1.8"/>'
    mid = y + h//2
    if ico:
        s += f'<text x="{x+w//2}" y="{mid-7}" text-anchor="middle" font-size="19" font-family="Arial,sans-serif">{ico}</text>'
        s += f'<text x="{x+w//2}" y="{mid+9}" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{label}</text>'
        if sub: s += f'<text x="{x+w//2}" y="{mid+22}" text-anchor="middle" fill="rgba(255,255,255,0.5)" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
    else:
        s += f'<text x="{x+w//2}" y="{mid-(4 if sub else -4)}" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">{label}</text>'
        if sub: s += f'<text x="{x+w//2}" y="{mid+12}" text-anchor="middle" fill="rgba(255,255,255,0.55)" font-size="9" font-family="Arial,sans-serif">{sub}</text>'
    return s

def labeled_arrow(x1, y1, x2, y2, label="", color="white"):
    """Image 4/5 style: arrow with optional mid-point text label."""
    uid = f"la{abs(x1)}{abs(y1)}{abs(x2)}{abs(y2)}"
    mx, my = (x1+x2)//2, (y1+y2)//2
    s  = f'<defs><marker id="{uid}" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="{color}" opacity="0.75"/></marker></defs>'
    s += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.5" marker-end="url(#{uid})" opacity="0.6"/>'
    if label:
        bw = len(label)*5+10
        s += f'<rect x="{mx-bw//2}" y="{my-8}" width="{bw}" height="14" rx="4" fill="#0F172A" opacity="0.85"/>'
        s += f'<text x="{mx}" y="{my+3}" text-anchor="middle" fill="{color}" font-size="8" font-family="Arial,sans-serif">{label}</text>'
    return s

# ── WRAPPER ───────────────────────────────────────────────────────────────────
def wrap(content, title, subtitle, C, date_str):
    accent = C[0]
    st = title.replace("&","and").replace("<","").replace(">","")
    # gradient stop colours
    g1, g2 = C[0], C[1]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 570" width="900" height="570">
  <defs>
    <pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">
      <circle cx="1" cy="1" r="1" fill="white" opacity="0.06"/>
    </pattern>
    <linearGradient id="titlegrd" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0%" stop-color="{g1}"/>
      <stop offset="100%" stop-color="{g2}" stop-opacity="0.7"/>
    </linearGradient>
    <linearGradient id="headbg" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" stop-color="#161E30"/>
      <stop offset="100%" stop-color="#0F172A"/>
    </linearGradient>
    <linearGradient id="sig" x1="0" x2="1">
      <stop offset="0%" stop-color="#0EA5E9"/>
      <stop offset="50%" stop-color="#8B5CF6"/>
      <stop offset="100%" stop-color="#EC4899"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="8" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <!-- Canvas -->
  <rect width="900" height="570" fill="#0F172A"/>
  <rect width="900" height="570" fill="url(#dots)"/>

  <!-- Ambient glow blobs -->
  <circle cx="830" cy="80" r="160" fill="{g1}" opacity="0.06"/>
  <circle cx="80"  cy="500" r="120" fill="{g2}" opacity="0.05"/>

  <!-- Header band -->
  <rect x="0" y="0" width="900" height="76" fill="url(#headbg)"/>
  <rect x="0" y="0" width="900" height="4" fill="url(#titlegrd)"/>
  <line x1="0" y1="76" x2="900" y2="76" stroke="white" stroke-width="0.5" opacity="0.08"/>

  <!-- Category label -->
  <rect x="15" y="14" width="{len(subtitle)*7+18}" height="18" rx="9" fill="{accent}" fill-opacity="0.15" stroke="{accent}" stroke-opacity="0.4" stroke-width="1"/>
  <text x="24" y="26" fill="{accent}" font-size="9" font-weight="bold" font-family="Arial,sans-serif" letter-spacing="1.5">{subtitle.upper()}</text>

  <!-- Title -->
  <text x="450" y="58" text-anchor="middle" fill="white" font-size="20" font-weight="bold" font-family="Arial,sans-serif" letter-spacing="-0.3">{st}</text>

  <!-- Content -->
  {content}

  <!-- Footer -->
  <line x1="15" y1="533" x2="885" y2="533" stroke="white" stroke-width="0.5" opacity="0.07"/>
  <text x="20" y="550" fill="#334155" font-size="8" font-family="Arial,sans-serif">{date_str}</text>
  <rect x="645" y="539" width="240" height="20" rx="10" fill="url(#sig)" fill-opacity="0.12" stroke="url(#sig)" stroke-width="0.8"/>
  <text x="765" y="553" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif" letter-spacing="0.5">&#10022; AI &#169; Komal Batra</text>
</svg>'''

# ── KUBERNETES ────────────────────────────────────────────────────────────────
def make_kubernetes(C):
    s = ""
    # Tool strip
    s += tool_strip([("☸️","Kubernetes","#326CE5"),("🐳","containerd","#0891B2"),("📡","etcd","#419EDA"),("🔀","Calico","#FB923C"),("📊","Prometheus","#E6522C"),("🔒","RBAC","#7C3AED")], 82, C[0])

    # Control Plane
    s += banner_section(15, 122, 870, 94, "CONTROL PLANE", C[0])
    for i,(x,lbl,sub,col) in enumerate([(22,"API Server","entry point",C[0]),(198,"Scheduler","node filter/score",C[1]),(374,"Controller Mgr","reconcile state",C[2]),(558,"etcd","key-value store",C[3]),(726,"Cloud Controller","cloud provider",C[4])]):
        s += card(x, 156, 168, 52, col, lbl, sub)
    for x in [190,366,542,718]: s += thin_arrow(x,182,x+8,182,"white")

    # Big arrow down
    s += fat_arrow_down(450, 216, 244, C[1])

    # Workers — two column
    s += two_col_header(15, 244, 870, 168, "WORKER NODE 1", C[1], "WORKER NODE 2", C[2])
    # Node 1 internals
    for x,lbl,sub,col in [(22,"Kubelet","node agent",C[1]),(188,"Kube-proxy","iptables/IPVS",C[2]),(354,"CNI Plugin","Calico/Flannel",C[3])]:
        s += card(x, 278, 158, 44, col, lbl, sub)
    for x in [180,346]: s += thin_arrow(x,300,x+8,300,"white")
    for x,lbl,sub,col in [(22,"Pod: nginx","web tier",C[0]),(140,"Pod: api","app tier",C[1]),(258,"Pod: worker","background",C[2]),(376,"Pod: cache","redis",C[3])]:
        s += card(x, 330, 110, 74, col, lbl, sub)
    # Node 2 internals
    for x,lbl,sub,col in [(452,"Kubelet","node agent",C[1]),(618,"Kube-proxy","networking",C[2]),(784,"Ingress","NGINX LB",C[4])]:
        s += card(x, 278, 158, 44, col, lbl, sub)
    for x in [610,776]: s += thin_arrow(x,300,x+8,300,"white")
    for x,lbl,sub,col in [(452,"Pod: db","postgres",C[3]),(570,"Pod: ml","inference",C[4]),(688,"Pod: search","elastic",C[5]),(806,"Pod: mon","prometheus",C[0])]:
        s += card(x, 330, 110, 74, col, lbl, sub)
    # vertical control plane → node arrows
    s += thin_arrow(200, 216, 200, 244, C[1], True)
    s += thin_arrow(700, 216, 700, 244, C[2], True)

    # Status bar
    s += fat_arrow_down(450, 412, 436, C[3])
    s += banner_section(15, 436, 870, 64, "CLUSTER SERVICES", C[3])
    for x,lbl,sub,col in [(22,"HPA","auto-scale pods",C[0]),(198,"VPA","right-size pods",C[1]),(374,"PVC / PV","storage claim",C[2]),(550,"StorageClass","dynamic provision",C[3]),(726,"Cert Manager","TLS rotate",C[4])]:
        s += card(x, 468, 168, 26, col, lbl, sub, 6)

    return s, "Cluster Architecture"

# ── LLM / AI AGENTS ──────────────────────────────────────────────────────────
def make_llm(C):
    s = ""
    s += tool_strip([("🤖","LLaMA 3","#6D28D9"),("🧠","GPT-4o","#10A37F"),("☁️","Claude","#C2410C"),("🔍","RAG","#0891B2"),("🛠️","LangChain","#059669"),("📊","LangSmith","#D97706")], 82, C[0])

    # Two-col: Processing | AI Models
    s += two_col_header(15, 122, 870, 390, "PROCESSING PIPELINE", C[0], "AI PROVIDERS", C[1], 0.62)

    # LEFT — pipeline rows
    rows = [
        (C[0], "INPUT LAYER", [(22,"User Query","natural language"),(200,"System Prompt","instructions"),(378,"History","conversation ctx"),(556,"Tools Def","function schema")]),
        (C[2], "CONTEXT LAYER", [(22,"Chunker","512 tok split"),(200,"Embedder","text-embed-3"),(378,"Vector Store","Pinecone ANN"),(556,"Re-ranker","cross-encoder")]),
        (C[3], "REASONING LAYER", [(22,"Planner","task decompose"),(200,"Tool Router","fn dispatch"),(378,"Memory","short+long term"),(556,"Agent Loop","plan→act→obs")]),
        (C[4], "OUTPUT LAYER", [(22,"Tokenizer","decode tokens"),(200,"Sampler","temp/top-p"),(378,"Guardrails","safety filter"),(556,"Streamer","SSE chunks")]),
    ]
    y = 155
    for col, label, items in rows:
        s += f'<rect x="20" y="{y}" width="530" height="18" rx="5" fill="{col}" fill-opacity="0.25"/>'
        s += f'<text x="285" y="{y+12}" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif" letter-spacing="1">{label}</text>'
        for j,(x,lbl,sub) in enumerate(items):
            s += card(x, y+22, 170, 46, C[j%len(C)], lbl, sub)
        if y < 400:
            s += fat_arrow_down(285, y+68, y+84, col)
        y += 84

    # RIGHT — AI providers column
    s += f'<text x="760" y="150" text-anchor="middle" fill="{C[1]}" font-size="10" font-weight="bold" font-family="Arial,sans-serif" letter-spacing="1">AI MODELS</text>'
    providers = [("🤖","GPT-4o","OpenAI",C[1]),("🧠","Claude 3","Anthropic",C[2]),("🦙","LLaMA 3","Meta / local",C[3]),("💎","Gemini","Google",C[4]),("⚡","Groq","fast inference",C[5])]
    for i,(ico,nm,sub,col) in enumerate(providers):
        cy = 162 + i*68
        s += f'<circle cx="730" cy="{cy}" r="24" fill="{col}" opacity="0.9"/>'
        s += f'<text x="730" y="{cy+6}" text-anchor="middle" font-size="18" font-family="Arial,sans-serif">{ico}</text>'
        s += f'<text x="768" y="{cy-4}" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">{nm}</text>'
        s += f'<text x="768" y="{cy+10}" fill="rgba(255,255,255,0.6)" font-size="9" font-family="Arial,sans-serif">{sub}</text>'
        if i < 4: s += thin_arrow(730, cy+24, 730, cy+44, col, True)
        s += thin_arrow(554, cy, 706, cy, "white", True)

    # Bottom eval bar
    s += fat_arrow_down(450, 512, 534, C[5])
    s += banner_section(15, 534, 870, 30, "EVALUATION  ·  Faithfulness  ·  Relevance  ·  RAGAS Score  ·  Latency p95  ·  Hallucination Rate", C[5])

    return s, "Architecture Diagram"

# ── CI/CD ─────────────────────────────────────────────────────────────────────
def make_cicd(C):
    s = ""
    s += tool_strip([("🐙","GitHub Actions","#7C3AED"),("🐳","Docker","#0891B2"),("☸️","Kubernetes","#326CE5"),("🛡️","Trivy","#D97706"),("📊","Grafana","#E6522C"),("🚨","PagerDuty","#06B6D4")], 82, C[0])

    # Pipeline stages as big numbered circles
    stages = [(75,"1","💻","Code","git push",C[0]),(195,"2","🔍","Test","pytest/jest",C[1]),(315,"3","🏗️","Build","docker build",C[2]),(435,"4","🛡️","Scan","trivy/snyk",C[3]),(555,"5","📦","Publish","push to ECR",C[4]),(675,"6","🚀","Deploy","helm upgrade",C[5]),(795,"7","✅","Verify","smoke tests",C[0])]
    for cx,num,ico,lbl,sub,col in stages:
        s += f'<circle cx="{cx}" cy="152" r="40" fill="{col}" opacity="0.15" stroke="{col}" stroke-width="2"/>'
        s += f'<circle cx="{cx}" cy="152" r="32" fill="{col}"/>'
        s += f'<text x="{cx}" y="147" text-anchor="middle" font-size="18" font-family="Arial,sans-serif">{ico}</text>'
        s += f'<text x="{cx}" y="163" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        s += f'<text x="{cx}" y="207" text-anchor="middle" fill="rgba(255,255,255,0.6)" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
        # Stage number badge
        s += f'<circle cx="{cx+24}" cy="124" r="9" fill="#0F172A" stroke="{col}" stroke-width="1.5"/>'
        s += f'<text x="{cx+24}" y="128" text-anchor="middle" fill="{col}" font-size="8" font-weight="bold" font-family="Arial,sans-serif">{num}</text>'
        if cx < 795: s += fat_arrow_right(cx+32, cx+83, 152, col)

    # Gate status bar
    s += status_bar([("Code Review","#22C55E"),("Unit Tests","#22C55E"),("SAST Scan","#22C55E"),("CVE Check","#F97316"),("Perf Budget","#EAB308"),("Canary","#3B82F6")], 220)

    # Three columns below
    s += two_col_header(15, 254, 425, 150, "ENVIRONMENTS", C[1], "QUALITY GATES", C[2], 0.5)
    for y,lbl,sub,col in [(282,"Development","feature branches",C[1]),(330,"Staging","pre-production",C[2]),(378,"Production","blue/green split",C[0])]:
        s += card(20, y, 195, 38, col, lbl, sub, 7)
    for y,lbl,sub,col in [(282,"Coverage",">80% required",C[2]),(330,"Perf Budget","LCP < 2.5s",C[3]),(378,"DAST","OWASP ZAP",C[4])]:
        s += card(225, y, 205, 38, col, lbl, sub, 7)

    s += banner_section(450, 254, 435, 150, "ROLLOUT STRATEGY", C[4])
    for y,lbl,sub,col in [(286,"Canary","1% → 10% → 100%",C[4]),(330,"Blue / Green","instant cutover",C[0]),(374,"Feature Flags","LaunchDarkly",C[1]),(418,"Auto-Rollback","error rate > 1%",C[3])]:
        s += card(458, y, 419, 36, col, lbl, sub, 7)

    # Observability row
    s += fat_arrow_down(450, 404, 424, C[3])
    s += banner_section(15, 424, 870, 80, "OBSERVABILITY", C[3])
    for x,lbl,sub,col in [(22,"Prometheus","metrics",C[3]),(200,"Grafana","dashboards",C[0]),(378,"Jaeger","distributed trace",C[1]),(556,"ELK Stack","logs",C[2]),(734,"PagerDuty","alerts→oncall",C[4])]:
        s += card(x, 456, 168, 40, col, lbl, sub, 7)

    return s, "Pipeline Architecture"

# ── KAFKA ─────────────────────────────────────────────────────────────────────
def make_kafka(C):
    s = ""
    s += tool_strip([("🌊","Apache Kafka","#231F20"),("📋","Schema Reg","#7C3AED"),("🔌","Kafka Connect","#0891B2"),("⚡","Apache Flink","#E6522C"),("🔥","Spark","#E25A1C"),("📊","ClickHouse","#FACC15")], 82, C[0])

    # Producers
    s += banner_section(15, 122, 175, 158, "PRODUCERS", C[1])
    for y,lbl,sub,col in [(154,"App Server","REST/gRPC events",C[1]),(206,"IoT / Edge","MQTT bridge",C[2]),(258,"DB CDC","Debezium",C[3])]:
        s += card(22, y, 160, 44, col, lbl, sub)
    s += fat_arrow_right(190, 210, 200, C[0])

    # Kafka cluster
    s += banner_section(210, 122, 330, 158, "KAFKA CLUSTER", C[0])
    for i,(lbl,role,col) in enumerate([("Broker 1","partition leader",C[0]),("Broker 2","ISR follower",C[1]),("Broker 3","ISR follower",C[2])]):
        s += card(218+i*105, 154, 97, 118, col, lbl, role)
    s += f'<text x="375" y="287" text-anchor="middle" fill="#94A3B8" font-size="9" font-family="Arial,sans-serif">RF=3 · 12 partitions · 7d retention</text>'

    # Schema + Connect
    s += banner_section(550, 122, 175, 158, "SCHEMA + CONNECT", C[4])
    s += card(558, 154, 158, 56, C[4], "Schema Registry", "Avro / Protobuf")
    s += card(558, 218, 158, 56, C[5], "Kafka Connect", "source + sink")
    s += thin_arrow(540, 200, 558, 200, "white")
    s += thin_arrow(540, 245, 558, 245, "white")

    # Stream processing
    s += banner_section(735, 122, 150, 158, "STREAM PROC", C[2])
    s += card(742, 154, 136, 44, C[2], "Apache Flink", "stateful / CEP")
    s += card(742, 206, 136, 44, C[3], "Spark Streaming", "micro-batch")
    s += card(742, 258, 136, 28, C[4], "KSQL", "SQL on Kafka")
    s += thin_arrow(725, 180, 742, 180, "white")
    s += thin_arrow(725, 228, 742, 228, "white")

    # Big arrow down
    s += fat_arrow_down(450, 280, 308, C[3], "consume")

    # Consumers
    s += banner_section(15, 308, 870, 90, "CONSUMER GROUPS  ·  SINKS", C[3])
    sinks = [("🏞️","Data Lake","S3 / GCS",C[3]),("📊","ClickHouse","analytics",C[4]),("🔍","OpenSearch","full-text",C[5]),("🤖","ML Platform","features",C[0]),("📡","Real-time","dashboards",C[1]),("🚨","Alerting","PagerDuty",C[2]),("⚡","Cache","Redis",C[3])]
    w = 870//len(sinks)
    for i,(ico,lbl,sub,col) in enumerate(sinks):
        cx = 15 + i*w + w//2
        s += f'<text x="{cx}" y="334" text-anchor="middle" font-size="18" font-family="Arial,sans-serif">{ico}</text>'
        s += card(cx-w//2+4, 346, w-8, 44, col, lbl, sub, 7)

    # Ops row
    s += fat_arrow_down(450, 398, 420, C[5])
    s += banner_section(15, 420, 870, 64, "OPERATIONS", C[5])
    ops=[("📊","Burrow","lag monitor"),("🔐","mTLS","auth+encrypt"),("📏","Quotas","producer throttle"),("🔄","MirrorMaker 2","geo-replicate"),("📋","Audit Log","compliance"),("💰","Cost","tier storage")]
    w2=870//len(ops)
    for i,(ico,lbl,sub) in enumerate(ops):
        cx=15+i*w2+w2//2
        s += f'<text x="{cx}" y="443" text-anchor="middle" font-size="15" font-family="Arial,sans-serif">{ico}</text>'
        s += f'<text x="{cx}" y="459" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        s += f'<text x="{cx}" y="473" text-anchor="middle" fill="rgba(255,255,255,0.55)" font-size="8" font-family="Arial,sans-serif">{sub}</text>'

    return s, "Streaming Architecture"

# ── ZERO TRUST ────────────────────────────────────────────────────────────────
def make_zero_trust(C):
    s = ""
    s += tool_strip([("🔐","Zero Trust","#B91C1C"),("🆔","Okta / AAD","#0078D4"),("📱","MDM Intune","#7C3AED"),("🌐","Zscaler","#0091DA"),("⚔️","Cloudflare","#F48120"),("📊","Sentinel","#0EA5E9")], 82, C[0])

    # Two-col: Controls | Intelligence
    s += two_col_header(15, 122, 870, 290, "CONTROL PLANE", C[0], "INTELLIGENCE LAYER", C[1], 0.60)

    # Left - pillars
    pillars = [(C[0],"IDENTITY","MFA • SSO • RBAC • JIT access"),(C[2],"DEVICE TRUST","MDM posture • patch level • cert"),(C[3],"NETWORK","microsegment • encrypt • inspect"),(C[4],"APPLICATION","least-priv • API auth • WAAP")]
    y = 154
    for col,lbl,desc in pillars:
        s += f'<rect x="20" y="{y}" width="505" height="56" rx="8" fill="{col}" fill-opacity="0.12" stroke="{col}" stroke-width="1.5"/>'
        s += f'<rect x="20" y="{y}" width="8" height="56" rx="4" fill="{col}"/>'
        s += f'<text x="36" y="{y+20}" fill="{col}" font-size="11" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        s += f'<text x="36" y="{y+38}" fill="rgba(255,255,255,0.65)" font-size="10" font-family="Arial,sans-serif">{desc}</text>'
        if y < 350: s += fat_arrow_down(272, y+56, y+66, col)
        y += 66

    # Center Policy Engine
    s += f'<circle cx="272" cy="290" r="0" fill="none"/>'  # spacer

    # Right - intelligence
    intel = [(C[1],"Threat Intel","IOC feeds / STIX / TAXII"),(C[2],"UEBA","anomaly detect / risk score"),(C[3],"SIEM","log correlate / SOAR auto"),(C[4],"AI Analysis","converge / diverge signals")]
    iy = 154
    for col,lbl,desc in intel:
        s += f'<rect x="535" y="{iy}" width="340" height="60" rx="8" fill="{col}" fill-opacity="0.12" stroke="{col}" stroke-width="1.5"/>'
        s += f'<text x="705" y="{iy+24}" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        s += f'<text x="705" y="{iy+42}" text-anchor="middle" fill="rgba(255,255,255,0.6)" font-size="9" font-family="Arial,sans-serif">{desc}</text>'
        if iy < 350: s += fat_arrow_down(705, iy+60, iy+70, col)
        iy += 70

    # Policy decision point
    s += fat_arrow_down(450, 412, 436, C[0])
    s += banner_section(15, 436, 870, 58, "POLICY DECISION POINT  (PDP / PEP)", C[0])
    for x,lbl,sub,col in [(22,"Authenticate","verify identity",C[0]),(192,"Authorise","check entitlement",C[1]),(362,"Enforce","allow / deny / log",C[2]),(532,"Audit","immutable trail",C[3]),(702,"Respond","revoke / alert",C[4])]:
        s += card(x, 468, 162, 22, col, lbl, sub, 6)

    # Principles bar
    s += status_bar([("Never Trust","#B91C1C"),("Always Verify","#D97706"),("Least Privilege","#059669"),("Assume Breach","#7C3AED"),("Continuous Monitor","#0891B2")], 504)

    return s, "Security Architecture"

# ── AWS ───────────────────────────────────────────────────────────────────────
def make_aws(C):
    s = ""
    s += tool_strip([("☁️","AWS","#FF9900"),("🔒","IAM","#DD344C"),("🌐","CloudFront","#7C3AED"),("⚡","Lambda","#FF9900"),("🗄️","Aurora","#527FFF"),("👁️","CloudWatch","#E6522C")], 82, C[0])

    # Client row
    s += banner_section(15, 122, 870, 44, "CLIENT LAYER", C[1])
    for x,ico,lbl in [(95,"🌐","Browser"),(230,"📱","Mobile"),(365,"💻","CLI / SDK"),(500,"🤝","Partners"),(635,"🤖","IoT"),(770,"🔌","Webhooks")]:
        s += f'<text x="{x}" y="139" text-anchor="middle" font-size="14" font-family="Arial,sans-serif">{ico}</text>'
        s += f'<text x="{x}" y="156" text-anchor="middle" fill="rgba(255,255,255,0.8)" font-size="9" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'

    s += fat_arrow_down(450, 166, 186, C[0])

    # Edge
    s += banner_section(15, 186, 870, 50, "EDGE LAYER", C[0])
    for x,lbl,sub,col in [(22,"CloudFront","CDN / PoPs",C[0]),(196,"Route 53","DNS + health",C[1]),(370,"WAF + Shield","DDoS L3/L7",C[3]),(544,"ACM","TLS certs",C[2]),(718,"API Gateway","REST / WS / gRPC",C[4])]:
        s += card(x, 200, 166, 28, col, lbl, sub, 7)
    for x in [188,362,536,710]: s += thin_arrow(x,214,x+8,214,"white")

    s += fat_arrow_down(450, 236, 256, C[1])

    # Compute + Messaging side by side
    s += two_col_header(15, 256, 870, 118, "COMPUTE", C[2], "MESSAGING", C[4], 0.49)
    for i,(x,lbl,sub,col) in enumerate([(22,"Lambda","serverless FaaS",C[2]),(175,"ECS / Fargate","containers",C[0]),(328,"EKS","managed K8s",C[1]),(22,"Step Functions","orchestration",C[3]),(175,"App Runner","web services",C[4]),(328,"Batch","job queues",C[5])]):
        s += card(x, 288 if i<3 else 334, 145, 38, col, lbl, sub, 7)
    for i,(x,lbl,sub,col) in enumerate([(450,"SQS","queues",C[4]),(600,"SNS","pub/sub",C[5]),(750,"EventBridge","event bus",C[0]),(450,"Kinesis","streaming",C[1]),(600,"MSK","Kafka mgd",C[2]),(750,"SES","email",C[3])]):
        s += card(x, 288 if i<3 else 334, 142, 38, col, lbl, sub, 7)

    s += fat_arrow_down(450, 374, 394, C[3])

    # Data + Security side by side
    s += two_col_header(15, 394, 870, 114, "DATA AND STORAGE", C[3], "SECURITY AND OBSERVABILITY", C[5], 0.49)
    for i,(x,lbl,sub,col) in enumerate([(22,"S3","object store",C[3]),(138,"DynamoDB","NoSQL",C[4]),(254,"RDS Aurora","Postgres/MySQL",C[5]),(370,"ElastiCache","Redis",C[0]),(22,"Redshift","data warehouse",C[1]),(138,"Glue","ETL catalog",C[2]),(254,"Athena","query on S3",C[3]),(370,"Timestream","time-series",C[4])]):
        s += card(x, 422 if i<4 else 464, 108, 34, col, lbl, sub, 6)
    for i,(x,lbl,sub,col) in enumerate([(455,"IAM","access ctrl",C[5]),(571,"CloudWatch","metrics+logs",C[0]),(687,"CloudTrail","audit",C[1]),(803,"GuardDuty","threat detect",C[2]),(455,"Secrets Mgr","rotate creds",C[3]),(571,"X-Ray","tracing",C[4]),(687,"Config","compliance",C[5]),(803,"Macie","data sec",C[0])]):
        s += card(x, 422 if i<4 else 464, 108, 34, col, lbl, sub, 6)

    return s, "Cloud Architecture"

# ── MLOPS ─────────────────────────────────────────────────────────────────────
def make_mlops(C):
    s = ""
    s += tool_strip([("📊","MLflow","#0194E2"),("🔄","DVC","#945DD6"),("🏗️","Kubeflow","#326CE5"),("🤗","HuggingFace","#FF9D00"),("⚡","Ray","#028CF0"),("📡","Evidently","#ED6C47")], 82, C[0])

    rows = [
        (C[0],"DATA PIPELINE",[("Data Sources","S3/DB/APIs"),("Feature Eng","Spark/dbt"),("Validation","Great Expect"),("Feature Store","Feast/Tecton"),("Versioning","DVC / Delta"),("Monitoring","drift detect")]),
        (C[1],"MODEL TRAINING",[("Experiment","MLflow/W&B"),("Training","GPU cluster"),("Hyperparam","Optuna/Ray"),("Evaluation","F1/AUC/BLEU"),("Registry","HuggingFace Hub"),("A/B Baseline","champion vs chall")]),
        (C[2],"MODEL SERVING",[("Online Serve","FastAPI/Triton"),("Batch Infer","Spark/Ray"),("Streaming","Kafka+Model"),("Edge Deploy","ONNX/TFLite"),("Shadow Mode","traffic mirror"),("Rollback","auto revert")]),
        (C[3],"MONITORING",[("Data Drift","PSI/KS-test"),("Model Perf","acc/F1 degrad"),("Latency","p50/p95/p99"),("Concept Drift","retrain trigger"),("Explain","SHAP/LIME"),("Cost","GPU/token $")]),
    ]
    y = 122
    for col,label,items in rows:
        s += banner_section(15, y, 870, 78, label, col)
        n = len(items)
        w = 860//n
        for i,(lbl,sub) in enumerate(items):
            x = 20 + i*w
            s += card(x, y+32, w-8, 38, C[i%len(C)], lbl, sub, 7)
        if y < 380:
            s += fat_arrow_down(450, y+78, y+96, col)
            y += 96
        else:
            y += 78
            # Final status bar
            s += fat_arrow_down(450, y, y+22, C[4])
            s += status_bar([("Experiment Tracking","#6D28D9"),("Model Versioned","#1D4ED8"),("Tests Passed","#059669"),("Serving Live","#0891B2"),("Alerts Active","#D97706")], y+22)

    return s, "MLOps Pipeline"

# ── RAG ───────────────────────────────────────────────────────────────────────
def make_rag(C):
    s = ""
    s += tool_strip([("📄","LangChain","#1C3C3C"),("🔍","Pinecone","#000000"),("🧠","OpenAI","#10A37F"),("🤗","HuggingFace","#FF9D00"),("📊","RAGAS","#7C3AED"),("⚡","Weaviate","#F93E3E")], 82, C[0])

    # Two-col: Ingestion | Retrieval
    s += two_col_header(15, 122, 870, 290, "INGESTION PIPELINE", C[1], "RETRIEVAL + GENERATION", C[4], 0.48)

    # LEFT — ingestion
    ing_rows = [
        (C[1],"SOURCES",[("📄 PDFs","unstructured"),("🌐 Web","scraped"),("🗄️ DB","SQL/NoSQL"),("📧 Email","attachments")]),
        (C[2],"CHUNKING",[("Recursive","512 tok split"),("Semantic","sentence-aware"),("Token Aware","model specific"),("Overlap","50 tok slide")]),
        (C[3],"EMBEDDING",[("text-embed-3","OpenAI large"),("E5-large","MTEB top"),("BGE-M3","multilingual"),("Cohere","rerank ready")]),
    ]
    ly = 154
    for col,label,items in ing_rows:
        s += f'<rect x="18" y="{ly}" width="405" height="16" rx="5" fill="{col}" fill-opacity="0.3"/>'
        s += f'<text x="220" y="{ly+11}" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif" letter-spacing="1">{label}</text>'
        for j,(lbl,sub) in enumerate(items):
            s += card(18+j*100, ly+20, 93, 44, C[(j+1)%len(C)], lbl, sub, 7)
        ly += 78
        if ly < 370: s += fat_arrow_down(220, ly, ly+12, col)
        ly += 12

    # RIGHT — retrieval
    ret_rows = [
        (C[4],"VECTOR STORE",[("HNSW Index","graph ANN"),("BM25 Sparse","keyword"),("Hybrid","dense+sparse"),("Metadata","filter+sort")]),
        (C[5],"RETRIEVAL",[("Query Expand","HyDE / RAG-Fusion"),("ANN Search","cosine sim"),("Re-ranker","cross-encoder"),("Context Pack","fill window")]),
        (C[0],"GENERATION",[("LLM Prompt","system+context"),("Guardrails","safety filter"),("Citations","source links"),("Stream Out","SSE tokens")]),
    ]
    ry = 154
    for col,label,items in ret_rows:
        s += f'<rect x="430" y="{ry}" width="440" height="16" rx="5" fill="{col}" fill-opacity="0.3"/>'
        s += f'<text x="650" y="{ry+11}" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif" letter-spacing="1">{label}</text>'
        for j,(lbl,sub) in enumerate(items):
            s += card(430+j*108, ry+20, 100, 44, C[(j+2)%len(C)], lbl, sub, 7)
        ry += 78
        if ry < 370: s += fat_arrow_down(650, ry, ry+12, col)
        ry += 12

    # Cross arrow
    s += thin_arrow(422, 250, 430, 250, "white", True)

    # Eval bar
    s += fat_arrow_down(450, 412, 434, C[3])
    s += banner_section(15, 434, 870, 30, "EVALUATION METRICS  ·  Faithfulness  ·  Answer Relevance  ·  Context Recall  ·  RAGAS Score  ·  Hallucination %", C[3])
    s += status_bar([("Faithful","#22C55E"),("Relevant","#22C55E"),("No Hallucination","#22C55E"),("Fast < 2s","#EAB308"),("Citations OK","#3B82F6")], 474)

    return s, "System Architecture"

# ── SYSTEM DESIGN ─────────────────────────────────────────────────────────────
def make_system_design(C):
    s = ""
    s += tool_strip([("🌐","React / Next","#61DAFB"),("🔀","Nginx","#009900"),("🔑","OAuth2","#7C3AED"),("🚀","Kubernetes","#326CE5"),("🗄️","PostgreSQL","#336791"),("📡","Redis","#DC382D")], 82, C[0])

    s += banner_section(15, 122, 870, 36, "CLIENT LAYER", C[0])
    for x,ico,lbl in [(100,"🌐","Web Browser"),(280,"📱","Mobile App"),(460,"💻","Desktop"),(640,"🤝","3rd Party API"),(820,"🤖","IoT")]:
        s += f'<text x="{x}" y="135" text-anchor="middle" font-size="13" font-family="Arial,sans-serif">{ico}</text>'
        s += f'<text x="{x}" y="150" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-size="9" font-family="Arial,sans-serif">{lbl}</text>'

    s += fat_arrow_down(450, 158, 178, C[1])

    s += banner_section(15, 178, 870, 46, "EDGE + AUTH", C[1])
    for x,lbl,sub,col in [(22,"CDN","CloudFront/Fastly",C[1]),(195,"Load Balancer","L7 / health",C[2]),(368,"API Gateway","rate limit / route",C[3]),(541,"Auth Service","OAuth2 / JWT",C[4]),(714,"WAF","L7 protect",C[0])]:
        s += card(x, 192, 165, 26, col, lbl, sub, 7)
    for x in [187,360,533,706]: s += thin_arrow(x,205,x+8,205,"white")

    s += fat_arrow_down(450, 224, 244, C[2])

    s += banner_section(15, 244, 870, 100, "MICROSERVICES", C[2])
    for x,lbl,sub,col in [(22,"User Svc","auth/profile",C[2]),(155,"Order Svc","cart/checkout",C[3]),(288,"Payment","Stripe/PCI",C[4]),(421,"Notification","email/SMS",C[5]),(554,"Search","Elasticsearch",C[0]),(687,"Recommend","ML-powered",C[1]),(820,"Analytics","event track",C[2])]:
        s += card(x, 276, 125, 60, col, lbl, sub)
    for x in [147,280,413,546,679,812]: s += thin_arrow(x,306,x+8,306,"white")

    s += fat_arrow_down(450, 344, 364, C[3])

    s += banner_section(15, 364, 870, 46, "MESSAGE BROKER", C[3])
    for x,lbl,sub,col in [(22,"Kafka","event stream",C[3]),(200,"RabbitMQ","task queues",C[4]),(378,"Redis PubSub","real-time",C[5]),(556,"Dead Letter Q","failed msgs",C[0]),(734,"Event Source","audit stream",C[1])]:
        s += card(x, 378, 168, 26, col, lbl, sub, 7)
    for x in [190,368,546,724]: s += thin_arrow(x,391,x+8,391,"white")

    s += fat_arrow_down(450, 410, 430, C[4])

    s += banner_section(15, 430, 870, 74, "DATA LAYER", C[4])
    for x,lbl,sub,col in [(22,"PostgreSQL","OLTP primary",C[4]),(178,"Redis","cache/session",C[5]),(334,"MongoDB","documents",C[0]),(490,"S3","blob/media",C[1]),(646,"Elasticsearch","search index",C[2]),(802,"ClickHouse","OLAP analytics",C[3])]:
        s += card(x, 462, 148, 34, col, lbl, sub, 7)

    return s, "System Architecture"

# ── DEVSECOPS ─────────────────────────────────────────────────────────────────
def make_devsecops(C):
    s = ""
    s += tool_strip([("🔒","SAST/DAST","#B91C1C"),("🐳","Trivy","#0891B2"),("☸️","Falco","#7C3AED"),("📋","Semgrep","#D97706"),("🛡️","OPA","#3B82F6"),("📊","Splunk","#EC4899")], 82, C[0])

    # Phase columns (pipeline)
    phases=[("IDE","💻","Pre-commit","git-secrets + lint",C[0]),("SCM","📝","Code Review","SAST + Semgrep",C[1]),("Build","🏗️","Compile","dep SCA + SBOM",C[2]),("Test","🧪","Quality","DAST + ZAP",C[3]),("Artifact","📦","Registry","Trivy + sign",C[4]),("Stage","🚀","Deploy","IaC scan + TF",C[5]),("Prod","🛡️","Runtime","Falco + eBPF",C[0])]
    pw = 124
    for i,(env,ico,phase,tools,col) in enumerate(phases):
        x = 15+i*(pw+2)
        # column card
        s += f'<rect x="{x}" y="122" width="{pw}" height="220" rx="8" fill="{col}" fill-opacity="0.07" stroke="{col}" stroke-width="1.5" stroke-opacity="0.5"/>'
        # header
        s += f'<rect x="{x}" y="122" width="{pw}" height="28" rx="8" fill="{col}"/>'
        s += f'<rect x="{x}" y="136" width="{pw}" height="14" fill="{col}"/>'
        s += f'<text x="{x+pw//2}" y="141" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">{env}</text>'
        # icon
        s += f'<text x="{x+pw//2}" y="178" text-anchor="middle" font-size="28" font-family="Arial,sans-serif">{ico}</text>'
        s += f'<text x="{x+pw//2}" y="200" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{phase}</text>'
        # tools (two lines)
        parts = tools.split("+")
        for li,pt in enumerate(parts):
            s += f'<text x="{x+pw//2}" y="{222+li*16}" text-anchor="middle" fill="{col}" font-size="9" font-family="Arial,sans-serif">{pt.strip()}</text>'
        if i < len(phases)-1:
            ax = x+pw+1
            s += fat_arrow_right(ax, ax+2, 232, col)

    # Security gates
    s += fat_arrow_down(450, 342, 362, C[3])
    s += banner_section(15, 362, 870, 62, "SECURITY GATES", C[3])
    gates=[("🔴","Critical CVE","block merge"),("🟠","Secrets Leak","block build"),("🟡","OWASP Top10","block deploy"),("🔵","Compliance","block release"),("🟢","Pen Test","quarterly req"),("⚪","Audit Trail","always active")]
    gw=870//len(gates)
    for i,(ico,lbl,action) in enumerate(gates):
        cx=15+i*gw+gw//2
        s += f'<text x="{cx}" y="385" text-anchor="middle" font-size="16" font-family="Arial,sans-serif">{ico}</text>'
        s += f'<text x="{cx}" y="400" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        s += f'<text x="{cx}" y="414" text-anchor="middle" fill="rgba(255,255,255,0.5)" font-size="8" font-family="Arial,sans-serif">{action}</text>'

    # SIEM + Compliance
    s += fat_arrow_down(450, 424, 444, C[4])
    s += two_col_header(15, 444, 870, 80, "SIEM + INCIDENT RESPONSE", C[4], "COMPLIANCE + POLICY", C[1], 0.5)
    for x,lbl,sub,col in [(22,"SIEM","Splunk/Sentinel",C[4]),(175,"SOAR","auto-remediate",C[5]),(328,"Threat Intel","feeds + IOCs",C[0])]:
        s += card(x, 478, 145, 40, col, lbl, sub)
    s += thin_arrow(167,498,175,498,"white"); s += thin_arrow(320,498,328,498,"white")
    for x,lbl,sub,col in [(455,"CIS Benchmarks","hardening",C[1]),(610,"SOC2 / ISO27K","audit ready",C[2]),(765,"OPA / Rego","policy as code",C[3])]:
        s += card(x, 478, 147, 40, col, lbl, sub)

    return s, "Security Pipeline"

# ── DATA LAKEHOUSE ────────────────────────────────────────────────────────────
def make_lakehouse(C):
    s = ""
    s += tool_strip([("🔥","Apache Spark","#E25A1C"),("❄️","Delta Lake","#0086F5"),("🧊","Iceberg","#3CB371"),("🌊","Apache Flink","#E6522C"),("🔵","dbt","#FF694B"),("📊","Trino","#DD00A1")], 82, C[0])

    s += banner_section(15, 122, 870, 62, "INGESTION SOURCES", C[0])
    srcs=[("📊","Batch ETL","Airflow",C[0]),("🌊","Streaming","Kafka/Kinesis",C[1]),("🔌","CDC","Debezium",C[2]),("📡","API Pull","REST / GQL",C[3]),("📂","File Drop","S3 trigger",C[4]),("🤖","IoT / MQTT","edge devices",C[5]),("📱","App Events","SDK tracking",C[0])]
    w=870//len(srcs)
    for i,(ico,lbl,sub,col) in enumerate(srcs):
        s += card(20+i*w, 140, w-8, 38, col, f"{ico} {lbl}", sub, 7)
    for x in [140,262,384,506,628,750]: s += thin_arrow(x,159,x+6,159,"white")

    s += fat_arrow_down(450, 184, 204, C[1])

    s += banner_section(15, 204, 870, 62, "OPEN TABLE FORMAT LAYER", C[1])
    for x,lbl,sub,col in [(22,"Delta Lake","ACID + time travel",C[1]),(240,"Apache Iceberg","schema evolution",C[2]),(458,"Apache Hudi","upserts/deletes",C[3]),(676,"Metadata Catalog","Glue/Hive Metastore",C[4])]:
        s += card(x, 220, 210, 40, col, lbl, sub)
    for x in [232,450,668]: s += thin_arrow(x,240,x+8,240,"white")

    s += fat_arrow_down(450, 266, 286, C[2])

    s += banner_section(15, 286, 870, 62, "COMPUTE ENGINE", C[2])
    for x,lbl,sub,col in [(22,"Apache Spark","SQL/ML/streaming",C[2]),(215,"Trino / Presto","interactive SQL",C[3]),(408,"dbt","transform/test/doc",C[4]),(601,"Ray","ML distributed",C[5]),(794,"Flink","stream proc",C[0])]:
        s += card(x, 302, 185, 40, col, lbl, sub)
    for x in [207,400,593,786]: s += thin_arrow(x,322,x+8,322,"white")

    s += fat_arrow_down(450, 348, 368, C[3])

    s += two_col_header(15, 368, 870, 96, "CONSUMPTION LAYER", C[3], "GOVERNANCE", C[5], 0.55)
    for x,lbl,sub,col in [(22,"BI Tools","Tableau/Superset",C[3]),(180,"ML Platform","SageMaker/Vertex",C[4]),(338,"Ad-hoc SQL","Athena/BigQuery",C[5]),(496,"Real-time","Grafana/Looker",C[0])]:
        s += card(x, 400, 150, 56, col, lbl, sub)
    for x,lbl,sub,col in [(700,"Data Catalog","column lineage",C[5]),(820,"Row-level Sec","GDPR/RBAC",C[0])]:
        s += card(x, 400, 112, 56, col, lbl, sub, 7)
    s += status_bar([("Bronze","#B45309"),("Silver","#94A3B8"),("Gold","#D97706"),("Serving","#22C55E"),("Governed","#7C3AED")], 464)

    return s, "Data Architecture"

# ── GENERIC FALLBACK ──────────────────────────────────────────────────────────
def make_generic(topic_name, C):
    s = ""
    s += tool_strip([("🌐","Web / Mobile","#0EA5E9"),("🔀","API Gateway","#7C3AED"),("⚡","Microservices","#059669"),("🚀","Queue","#D97706"),("🗄️","Database","#336791"),("📡","Cache","#DC382D")], 82, C[0])

    s += banner_section(15, 122, 870, 46, "CLIENT + EDGE", C[0])
    for x,lbl,sub,col in [(22,"Web / Mobile","React / Native",C[0]),(210,"CDN","CloudFront",C[1]),(398,"API Gateway","rate limit",C[2]),(586,"Auth Service","OAuth2 / JWT",C[3]),(774,"WAF + DNS","Route53",C[4])]:
        s += card(x, 136, 180, 26, col, lbl, sub, 7)
    for x in [202,390,578,766]: s += thin_arrow(x,149,x+8,149,"white")

    s += fat_arrow_down(450, 168, 188, C[1])

    s += two_col_header(15, 188, 870, 140, "MICROSERVICES", C[1], "SUPPORTING SERVICES", C[2], 0.5)
    for y,lbl,sub,col in [(216,"User Service","auth / profile",C[1]),(270,"Order Service","cart / checkout",C[2]),(324,"Notification Svc","email / SMS / push",C[3])]:
        s += card(20, y, 210, 40, col, lbl, sub, 7)
        s += card(242, y, 188, 40, lbl+" Worker", "async process", C[4])
        s += thin_arrow(230,y+20,242,y+20,"white")
    for y,lbl,sub,col in [(216,"Search Svc","Elasticsearch",C[2]),(270,"Analytics Svc","ClickHouse",C[3]),(324,"ML / AI Svc","model serving",C[4])]:
        s += card(452, y, 200, 40, col, lbl, sub, 7)
        s += card(664, y, 214, 40, lbl.split()[0]+" Store","primary data",C[5])
        s += thin_arrow(652,y+20,664,y+20,"white")

    s += fat_arrow_down(450, 328, 348, C[3])

    s += banner_section(15, 348, 870, 50, "MESSAGE LAYER", C[3])
    for x,lbl,sub,col in [(22,"Kafka","event stream",C[3]),(200,"RabbitMQ","task queues",C[4]),(378,"Redis","cache/pub-sub",C[5]),(556,"SQS","managed queue",C[0]),(734,"EventBridge","event bus",C[1])]:
        s += card(x, 362, 170, 30, col, lbl, sub, 7)
    for x in [192,370,548,726]: s += thin_arrow(x,377,x+8,377,"white")

    s += fat_arrow_down(450, 398, 418, C[4])

    s += banner_section(15, 418, 870, 96, "DATA STORES", C[4])
    for x,lbl,sub,col in [(22,"PostgreSQL","OLTP primary",C[4]),(178,"Redis","sessions/cache",C[5]),(334,"MongoDB","documents",C[0]),(490,"S3 / Blob","media/files",C[1]),(646,"Elasticsearch","search index",C[2]),(802,"ClickHouse","analytics OLAP",C[3])]:
        s += card(x, 438, 148, 68, col, lbl, sub)

    return s, "System Architecture"


# ── DOCKER (Image 2 cheatsheet style) ────────────────────────────────────────
def make_docker(C):
    s = ""
    s += tool_strip([("🐳","Docker Engine","#0891B2"),("📦","Docker Hub","#0052CC"),("🔧","Compose","#047857"),("🔒","Docker Scout","#7C3AED"),("☸️","Swarm","#1D4ED8"),("🏗️","Buildx","#D97706")], 82, C[0])
    rows = [
        (C[0],"Dockerfile", [("📝","FROM","base image"),("📋","RUN","exec cmd"),("📂","COPY / ADD","files in"),("🔌","EXPOSE","port hint"),("▶️","CMD / ENTRYPOINT","start proc"),("🏷️","LABEL / ARG","metadata")]),
        (C[1],"Images",     [("🏗️","docker build","create image"),("📋","docker images","list local"),("🔍","docker inspect","image detail"),("🏷️","docker tag","rename"),("⬆️","docker push","to registry"),("🗑️","docker rmi","delete")]),
        (C[2],"Containers", [("▶️","docker run","start new"),("⏸️","docker stop","graceful"),("📋","docker ps","list running"),("🔍","docker logs","stdout"),("💻","docker exec","shell in"),("🗑️","docker rm","cleanup")]),
        (C[3],"Networking", [("🌉","bridge","default LAN"),("🏠","host","share host net"),("🔒","none","no network"),("🔗","overlay","multi-host"),("📡","macvlan","L2 assign"),("🔌","port map","-p 8080:80")]),
        (C[4],"Volumes",    [("💾","volume","managed by Docker"),("📂","bind mount","host path"),("🧠","tmpfs","RAM only"),("📥","docker cp","copy files"),("📋","docker volume ls","list"),("🔄","backup","tar + cp")]),
        (C[5],"Compose",    [("📄","docker-compose.yml","define stack"),("🚀","up -d","start detached"),("📋","ps","check status"),("📊","logs -f","follow logs"),("🔄","restart","cycle svc"),("🛑","down","stop + rm")]),
    ]
    y = 122
    rh = 62
    for col, label, items in rows:
        s += cheatsheet_row(y, rh, label, col, items)
        y += rh + 4
    # Bottom tip bar
    s += status_bar([("Layer Cache","#0891B2"),("Multi-stage Build","#047857"),("Non-root User","#D97706"),(".dockerignore","#7C3AED"),("Health Check","#BE185D"),("Read-only FS","#1D4ED8")], y+2)
    return s, "Cheatsheet"

# ── GIT WORKFLOW (Image 2 cheatsheet style) ───────────────────────────────────
def make_git_workflow(C):
    s = ""
    s += tool_strip([("🌿","Git","#F05032"),("🐙","GitHub","#7C3AED"),("🦊","GitLab","#FC6D26"),("🪣","Bitbucket","#0052CC"),("🔄","Git Flow","#059669"),("📝","Conventional","#D97706")], 82, C[0])
    rows = [
        (C[0],"Setup",      [("👤","git config","name + email"),("🔑","SSH key","auth setup"),("📁","git init","new repo"),("📥","git clone","copy remote"),("🔗","git remote","add origin"),("📋","git status","see changes")]),
        (C[1],"Branching",  [("🌿","git branch","list / create"),("🔀","git checkout","switch / new"),("🔀","git switch","modern way"),("🌊","git flow","feature branch"),("🏷️","git tag","version mark"),("🗑️","branch -d","delete branch")]),
        (C[2],"Staging",    [("➕","git add .","stage all"),("➕","git add -p","stage hunks"),("📝","git commit","save snap"),("✏️","--amend","fix last msg"),("💾","git stash","shelve WIP"),("📋","stash pop","restore WIP")]),
        (C[3],"Remote",     [("⬆️","git push","upload"),("⬇️","git pull","fetch+merge"),("📥","git fetch","download only"),("🔄","git rebase","linearise"),("🔃","git merge","combine"),("🍒","cherry-pick","single commit")]),
        (C[4],"History",    [("📜","git log","see commits"),("🔍","git diff","what changed"),("🕰️","git blame","who changed"),("⏪","git reset","undo commits"),("↩️","git revert","safe undo"),("🔎","git bisect","find bug")]),
        (C[5],"Best Practice",[("📋","Commit msg","feat: / fix: / chore:"),("🛡️","Branch protect","require PR"),("✅","PR review","2 approvers"),("🔏","Sign commits","GPG key"),("📖","CHANGELOG","keep updated"),("🤖","CI on PR","auto checks")]),
    ]
    y = 122
    rh = 62
    for col, label, items in rows:
        s += cheatsheet_row(y, rh, label, col, items)
        y += rh + 4
    s += status_bar([("trunk-based dev","#F05032"),("feature flags","#7C3AED"),("atomic commits","#059669"),("no force-push main","#D97706"),("PR = 1 concern","#0891B2"),("rebase > merge","#BE185D")], y+2)
    return s, "Cheatsheet"

# ── API DESIGN (Image 2 cheatsheet + Image 4 flow hybrid) ────────────────────
def make_api_design(C):
    s = ""
    s += tool_strip([("🔌","REST","#1D4ED8"),("📡","GraphQL","#E10098"),("⚡","gRPC","#244C5A"),("🌐","WebSocket","#059669"),("📋","OpenAPI","#6BA539"),("🔐","OAuth2","#7C3AED")], 82, C[0])

    # Top: API types comparison (Image 4 subsystem groups)
    for i,(x,w2,lbl,col,items) in enumerate([
        (15,210,"REST",C[0],[("GET","read resource"),("POST","create"),("PUT/PATCH","update"),("DELETE","remove")]),
        (232,210,"GraphQL",C[1],[("Query","fetch data"),("Mutation","write data"),("Subscription","real-time"),("Resolver","field logic")]),
        (449,210,"gRPC",C[2],[("Unary","req→res"),("Server Stream","1→many"),("Client Stream","many→1"),("Bi-di Stream","both ways")]),
        (666,230,"WebSocket",C[3],[("Upgrade","HTTP→WS"),("Frame","data unit"),("Ping/Pong","heartbeat"),("Close","teardown")]),
    ]):
        s += subsystem_group(x, 122, w2, 130, lbl, col)
        for j,(k,v) in enumerate(items):
            s += f'<rect x="{x+8}" y="{122+22+j*26}" width="{w2-16}" height="22" rx="5" fill="{col}" fill-opacity="0.14"/>'
            s += f'<text x="{x+16}" y="{122+22+j*26+14}" fill="{col}" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{k}</text>'
            s += f'<text x="{x+w2-8}" y="{122+22+j*26+14}" text-anchor="end" fill="rgba(255,255,255,0.6)" font-size="9" font-family="Arial,sans-serif">{v}</text>'

    # Middle: Design principles cheatsheet rows
    mid_rows = [
        (C[4],"Design",   [("📝","Nouns not Verbs","/users not /getUsers"),("🔢","Versioning","v1/ in URL"),("📄","Pagination","limit+offset/cursor"),("🔗","HATEOAS","links in response"),("📦","Resource Nesting","/users/123/posts")]),
        (C[5],"Security", [("🔐","Auth","Bearer JWT / API key"),("⏱️","Rate Limit","429 Too Many Reqs"),("🔒","HTTPS","TLS 1.3 minimum"),("🛡️","Input Validate","schema + sanitise"),("📝","Audit Log","who/what/when")]),
        (C[0],"Responses",[("✅","200 OK","success"),("➕","201 Created","POST success"),("❌","400 Bad Req","client error"),("🔐","401/403","auth/authz fail"),("💥","500 Internal","server fault")]),
    ]
    y = 264
    for col, label, items in mid_rows:
        s += cheatsheet_row(y, 60, label, col, items)
        y += 64

    # Bottom: request lifecycle flow (Image 4 style)
    s += banner_section(15, y+4, 870, 54, "REQUEST LIFECYCLE", C[3])
    flow = [("🌐","Client","browser/app"),("🔀","Gateway","rate limit"),("🔐","Auth","JWT verify"),("📋","Validate","schema check"),("⚙️","Handler","business logic"),("💾","Data","DB / cache"),("📤","Response","format + send")]
    fw = 870 // len(flow)
    for i,(ico,lbl,sub) in enumerate(flow):
        fx = 15 + i*fw
        s += flow_box(fx+2, y+18, fw-4, 36, lbl, sub, C[i%len(C)], ico)
        if i < len(flow)-1: s += fat_arrow_right(fx+fw-2, fx+fw+2, y+36, C[i%len(C)])

    return s, "Design Reference"

# ── SOLID PRINCIPLES (Image 3 roadmap style) ──────────────────────────────────
def make_solid(C):
    s = ""
    s += tool_strip([("📐","SOLID","#7C3AED"),("🏗️","Clean Code","#1D4ED8"),("🔌","OOP","#059669"),("🧪","TDD","#D97706"),("🔄","Refactor","#0891B2"),("📦","DDD","#BE185D")], 82, C[0])

    principles = [
        ("S","Single Responsibility","One class = one reason to change",C[0],
         ["A class should do ONE thing","Separate concerns into different classes","Makes testing easier and focused","e.g. UserService vs UserEmailer"]),
        ("O","Open / Closed","Open for extension, closed for modification",C[1],
         ["Add behaviour via extension","Don't modify existing tested code","Use interfaces and abstractions","e.g. add PaymentMethod without touching Order"]),
        ("L","Liskov Substitution","Subtypes must be substitutable for base types",C[2],
         ["Child class must honour parent contract","Don't override to throw exceptions","Covariance of return types","e.g. Square should NOT extend Rectangle"]),
        ("I","Interface Segregation","Many specific interfaces > one general",C[3],
         ["Clients shouldn't depend on methods they don't use","Split fat interfaces into focused ones","Avoids forcing empty implementations","e.g. Printable, Scannable vs MachineInterface"]),
        ("D","Dependency Inversion","Depend on abstractions, not concretions",C[4],
         ["High-level modules → interfaces","Low-level modules → implementations","Inject dependencies, don't instantiate","e.g. UserService(IEmailer) not UserService(GmailSender)"]),
    ]

    card_w = 162
    cx_positions = [15 + i*(card_w+12) for i in range(5)]

    # Roadmap connecting spine
    spine_y = 175
    for i in range(4):
        cx1 = cx_positions[i] + card_w
        cx2 = cx_positions[i+1]
        s += f'<line x1="{cx1}" y1="{spine_y}" x2="{cx2}" y2="{spine_y}" stroke="{C[i]}" stroke-width="3" stroke-dasharray="6,3" opacity="0.4"/>'

    for i,(letter, name, tagline, col, bullets) in enumerate(principles):
        cx = cx_positions[i]
        # Numbered roadmap node
        s += roadmap_node(cx + card_w//2, spine_y, 24, letter, col, active=(i==2))
        # Card below node
        card_top = spine_y + 30
        s += f'<rect x="{cx}" y="{card_top}" width="{card_w}" height="230" rx="10" fill="{col}" fill-opacity="0.08" stroke="{col}" stroke-width="1.8"/>'
        s += f'<rect x="{cx}" y="{card_top}" width="{card_w}" height="36" rx="10" fill="{col}"/>'
        s += f'<rect x="{cx}" y="{card_top+20}" width="{card_w}" height="16" fill="{col}"/>'
        s += f'<text x="{cx+card_w//2}" y="{card_top+14}" text-anchor="middle" fill="white" font-size="12" font-weight="bold" font-family="Arial,sans-serif">{name}</text>'
        s += f'<text x="{cx+card_w//2}" y="{card_top+50}" text-anchor="middle" fill="{col}" font-size="9" font-family="Arial,sans-serif" font-style="italic">{tagline}</text>'
        for j, b in enumerate(bullets):
            by = card_top + 68 + j*36
            s += f'<rect x="{cx+8}" y="{by}" width="{card_w-16}" height="28" rx="6" fill="{col}" fill-opacity="0.16"/>'
            # Wrap long text
            words = b.split()
            line1 = " ".join(words[:4]); line2 = " ".join(words[4:])
            s += f'<text x="{cx+card_w//2}" y="{by+12}" text-anchor="middle" fill="white" font-size="8.5" font-family="Arial,sans-serif">{line1}</text>'
            if line2: s += f'<text x="{cx+card_w//2}" y="{by+23}" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-size="8" font-family="Arial,sans-serif">{line2}</text>'

    # Bottom bar
    s += status_bar([("Maintainable","#7C3AED"),("Testable","#1D4ED8"),("Extensible","#059669"),("Scalable","#D97706"),("Readable","#0891B2")], 508)
    return s, "Design Principles"

# ── SYSTEM DESIGN ENHANCED (Image 4 subsystem groups) ────────────────────────
def make_canary_deploy(C):
    """Image 4 style: AWS canary deploy with colored subsystem groups + flow arrows."""
    s = ""
    s += tool_strip([("🏗️","Terraform","#7B42BC"),("☸️","EKS","#326CE5"),("🔀","NGINX","#009900"),("📊","Prometheus","#E6522C"),("📈","Grafana","#E6522C"),("🚀","Helm","#277A9F")], 82, C[0])

    # PROVISIONING group (top-left)
    s += subsystem_group(15, 122, 170, 130, "PROVISIONING", C[5])
    s += flow_box(25, 138, 150, 98, "Terraform", "provisions AWS EKS", C[5], "🏗️")

    # Connection arrow
    s += labeled_arrow(185, 187, 225, 187, "provisions AWS EKS", C[5])

    # OBSERVABILITY group (center-left)
    s += subsystem_group(225, 122, 230, 130, "OBSERVABILITY", C[3])
    s += flow_box(235, 138, 100, 98, "Grafana", "dashboards", C[3], "📊")
    s += flow_box(345, 138, 100, 98, "Prometheus", "scrapes metrics", C[4], "📡")
    s += labeled_arrow(285, 187, 345, 187, "reads data", C[3])

    # SRE operator
    s += f'<circle cx="370" cy="300" r="24" fill="{C[2]}" fill-opacity="0.15" stroke="{C[2]}" stroke-width="1.5"/>'
    s += f'<text x="370" y="296" text-anchor="middle" font-size="18" font-family="Arial,sans-serif">👤</text>'
    s += f'<text x="370" y="315" text-anchor="middle" fill="{C[2]}" font-size="9" font-weight="bold" font-family="Arial,sans-serif">SRE</text>'
    s += labeled_arrow(370, 275, 370, 254, "manual canary weight / rollback", C[2])

    # INGRESS + APP group (right)
    s += subsystem_group(475, 100, 400, 270, "INGRESS + APP", C[1])
    s += flow_box(485, 132, 110, 60, "NGINX Ingress", "traffic split", C[1], "🔀")
    s += flow_box(620, 118, 130, 80, "Stable V1", "88% traffic", C[0], "☸️")
    s += flow_box(760, 118, 110, 80, "", "", C[0])
    s += f'<text x="815" y="155" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">Stable V1</text>'
    s += f'<text x="815" y="170" text-anchor="middle" fill="{C[0]}" font-size="11" font-weight="bold" font-family="Arial,sans-serif">(88%)</text>'
    s += flow_box(620, 222, 130, 80, "Canary V2", "12% traffic", C[2], "🌊")
    s += flow_box(760, 222, 110, 80, "", "", C[2])
    s += f'<text x="815" y="258" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">Canary V2</text>'
    s += f'<text x="815" y="273" text-anchor="middle" fill="{C[2]}" font-size="11" font-weight="bold" font-family="Arial,sans-serif">(12%)</text>'
    s += labeled_arrow(595, 162, 620, 162, "", C[0])
    s += labeled_arrow(595, 262, 620, 262, "", C[2])
    s += thin_arrow(455, 187, 485, 162, C[1])

    # User
    s += f'<circle cx="450" cy="310" r="24" fill="{C[4]}" fill-opacity="0.15" stroke="{C[4]}" stroke-width="1.5"/>'
    s += f'<text x="450" y="306" text-anchor="middle" font-size="18" font-family="Arial,sans-serif">👤</text>'
    s += f'<text x="450" y="325" text-anchor="middle" fill="{C[4]}" font-size="9" font-weight="bold" font-family="Arial,sans-serif">User</text>'
    s += labeled_arrow(450, 285, 500, 220, "request", C[4])

    # Prometheus scrapes
    s += labeled_arrow(340, 230, 380, 290, "scrapes metrics", C[3])

    # Stats row
    s += fat_arrow_down(450, 390, 410, C[0])
    s += banner_section(15, 410, 870, 80, "DEPLOYMENT METRICS", C[0])
    for x,val,lbl,delta,col in [(20,"99.97%","Availability","+0.02%",C[0]),(195,"12%","Canary Traffic","↑ from 5%",C[2]),(370,"1.2ms","P95 Latency","-0.3ms",C[1]),(545,"0.03%","Error Rate","-0.01%",C[4]),(720,"847","RPS","+12",C[3])]:
        s += stat_tile(x, 420, 166, 60, val, lbl, delta, col)

    return s, "Canary Deploy"

# ── KUBERNETES ENHANCED (with Image 4 subsystem groups + Image 5 stats) ───────
def make_kubernetes_ops(C):
    s = ""
    s += tool_strip([("☸️","Kubernetes","#326CE5"),("🔒","RBAC","#7C3AED"),("📊","Prometheus","#E6522C"),("🔀","Istio","#466BB0"),("🏗️","Helm","#277A9F"),("🚨","PagerDuty","#25C151")], 82, C[0])

    # Stats row (Image 5 style)
    for x,val,lbl,delta,col in [(15,"847","Pods Running","+12",C[0]),(185,"99.94%","Uptime","+0.01%",C[1]),(355,"23ms","API Server P95","-4ms",C[2]),(525,"68%","Node CPU","▼ -3%",C[3]),(695,"3.1GB","Mem / Node","stable",C[4])]:
        s += stat_tile(x, 86, 160, 52, val, lbl, delta, col)

    # Sparklines in stat tiles
    s += mini_sparkline(16, 116, 158, 18, [42,38,45,50,60,58,55,62,68,72,68,72], C[0])
    s += mini_sparkline(186, 116, 158, 18, [99.9,99.91,99.88,99.92,99.94,99.93,99.95,99.94], C[1])
    s += mini_sparkline(356, 116, 158, 18, [35,28,30,27,26,25,24,23,22,23], C[2])
    s += mini_sparkline(526, 116, 158, 18, [55,60,65,70,72,68,66,70,71,68], C[3])
    s += mini_sparkline(696, 116, 158, 18, [3.0,3.1,3.2,3.1,3.0,3.1,3.1,3.1], C[4])

    # Control Plane — subsystem group (Image 4 style)
    s += subsystem_group(15, 148, 870, 90, "CONTROL PLANE", C[0])
    for x,lbl,sub,col in [(25,"API Server","kube-apiserver",C[0]),(200,"Scheduler","filter + score",C[1]),(375,"Controller Mgr","reconcile loops",C[2]),(550,"etcd","distributed KV",C[3]),(725,"Cloud Controller","cloud provider",C[4])]:
        s += flow_box(x, 162, 165, 68, lbl, sub, col)
    for x in [190,365,540,715]: s += thin_arrow(x, 196, x+10, 196, "white")

    s += fat_arrow_down(450, 238, 258, C[1])

    # Worker nodes — two subsystem groups side by side
    s += subsystem_group(15, 258, 425, 168, "WORKER NODE 1", C[1])
    for x,lbl,sub,col in [(25,"Kubelet","node agent",C[1]),(160,"Kube-proxy","iptables",C[2]),(295,"Container RT","containerd",C[3])]:
        s += flow_box(x, 272, 127, 44, lbl, sub, col)
    for x,lbl,sub,col in [(25,"Pod: web","nginx:latest",C[0]),(160,"Pod: api","app:v3",C[1]),(295,"Pod: cache","redis:7",C[2]),(360,"Pod: bg","worker:v2",C[3])]:
        s += flow_box(x, 324, 118, 94, lbl, sub, col)
    s += mini_sparkline(16, 400, 423, 22, [30,45,38,50,42,48,55,52,58,60], C[1])

    s += subsystem_group(450, 258, 435, 168, "WORKER NODE 2", C[2])
    for x,lbl,sub,col in [(460,"Kubelet","node agent",C[2]),(595,"Kube-proxy","networking",C[3]),(730,"CNI Plugin","Calico",C[4])]:
        s += flow_box(x, 272, 127, 44, lbl, sub, col)
    for x,lbl,sub,col in [(460,"Pod: db","postgres:15",C[3]),(580,"Pod: ml","torch:2",C[4]),(700,"Pod: mon","prometheus",C[5]),(820,"Ingress","NGINX",C[0])]:
        s += flow_box(x, 324, 112, 94, lbl, sub, col)
    s += mini_sparkline(451, 400, 433, 22, [50,55,48,60,58,62,55,58,65,68], C[2])

    # Bottom — cluster services
    s += fat_arrow_down(450, 426, 446, C[3])
    s += subsystem_group(15, 446, 870, 68, "CLUSTER SERVICES", C[3])
    for x,lbl,sub,col in [(22,"HPA","pod autoscale",C[0]),(200,"VPA","resource size",C[1]),(378,"Cluster CA","node autoscale",C[2]),(556,"PVC + PV","storage mgmt",C[3]),(734,"Cert Manager","TLS rotate",C[4])]:
        s += flow_box(x, 460, 170, 48, lbl, sub, col)

    return s, "Operations Dashboard"

# ── DISPATCHER ────────────────────────────────────────────────────────────────
def make_diagram(topic_name, topic_id, diagram_type=""):
    C   = get_pal(topic_id)
    now = datetime.now().strftime("%B %Y")
    tid = topic_id.lower()

    if "kube-ops" in tid:                        content,sub = make_kubernetes_ops(C)
    elif "kube" in tid:                          content,sub = make_kubernetes(C)
    elif any(x in tid for x in ["llm","agent"]): content,sub = make_llm(C)
    elif "cicd" in tid:                          content,sub = make_cicd(C)
    elif "kafka" in tid:                         content,sub = make_kafka(C)
    elif "zero" in tid:                          content,sub = make_zero_trust(C)
    elif "aws" in tid:                           content,sub = make_aws(C)
    elif "devsec" in tid:                        content,sub = make_devsecops(C)
    elif "system" in tid:                        content,sub = make_system_design(C)
    elif "mlops" in tid:                         content,sub = make_mlops(C)
    elif any(x in tid for x in ["lake","data"]): content,sub = make_lakehouse(C)
    elif "rag" in tid:                           content,sub = make_rag(C)
    elif "docker" in tid:                        content,sub = make_docker(C)
    elif "git" in tid:                           content,sub = make_git_workflow(C)
    elif "api" in tid:                           content,sub = make_api_design(C)
    elif "solid" in tid:                         content,sub = make_solid(C)
    elif "canary" in tid:                        content,sub = make_canary_deploy(C)
    else:                                        content,sub = make_generic(topic_name, C)

    return wrap(content, topic_name, sub, C, now)

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
