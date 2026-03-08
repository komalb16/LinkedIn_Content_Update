import os
from datetime import datetime
from pathlib import Path
from logger import get_logger

log = get_logger("diagrams")
OUTPUT_DIR = "diagrams"

PALETTES = {
    "ai":       ["#7C3AED","#2563EB","#059669","#D97706","#DB2777","#0891B2"],
    "cloud":    ["#2563EB","#0891B2","#059669","#7C3AED","#D97706","#DB2777"],
    "security": ["#DC2626","#D97706","#7C3AED","#2563EB","#059669","#DB2777"],
    "data":     ["#059669","#7C3AED","#2563EB","#0891B2","#D97706","#DC2626"],
    "devops":   ["#059669","#2563EB","#7C3AED","#D97706","#DC2626","#0891B2"],
    "default":  ["#2563EB","#7C3AED","#059669","#D97706","#DC2626","#0891B2"],
}

def get_pal(tid):
    t=tid.lower()
    if any(x in t for x in ["llm","rag","agent","mlops"]): return PALETTES["ai"]
    if any(x in t for x in ["kube","docker","aws","cicd"]): return PALETTES["cloud"]
    if any(x in t for x in ["zero","devsec"]):              return PALETTES["security"]
    if any(x in t for x in ["kafka","data","lake"]):        return PALETTES["data"]
    if any(x in t for x in ["git","devops","solid","api"]): return PALETTES["devops"]
    return PALETTES["default"]

def xe(t):
    return str(t).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def clamp(text, n):
    text=str(text); return text if len(text)<=n else text[:n-1]+"..."

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

def wrap_text(text, max_chars):
    words=text.split(); lines=[]; cur=""
    for w in words:
        if len(cur)+len(w)+1<=max_chars: cur=(cur+" "+w).strip()
        else:
            if cur: lines.append(cur)
            cur=w
    if cur: lines.append(cur)
    return lines or [""]

# ── CSS ANIMATIONS ─────────────────────────────────────────────────────────────
ANIM_CSS = """
  <style>
    @keyframes flowRight {
      0%   { stroke-dashoffset: 24; }
      100% { stroke-dashoffset: 0;  }
    }
    @keyframes flowDown {
      0%   { stroke-dashoffset: 24; }
      100% { stroke-dashoffset: 0;  }
    }
    @keyframes pulse {
      0%,100% { opacity:1; r:5; }
      50%      { opacity:0.6; r:7; }
    }
    @keyframes fadeIn {
      from { opacity:0; transform:translateY(4px); }
      to   { opacity:1; transform:translateY(0); }
    }
    @keyframes shimmer {
      0%   { stop-color: #fff; stop-opacity:0; }
      50%  { stop-color: #fff; stop-opacity:0.08; }
      100% { stop-color: #fff; stop-opacity:0; }
    }
    .flow-r { stroke-dasharray:8 4; animation:flowRight 1.2s linear infinite; }
    .flow-d { stroke-dasharray:8 4; animation:flowDown  1.2s linear infinite; }
    .pulse-dot { animation:pulse 2s ease-in-out infinite; }
    .fadein { animation:fadeIn 0.6s ease-out both; }
  </style>
"""

# ── ANIMATED ARROW ─────────────────────────────────────────────────────────────
def arrow_down(ax, ay1, ay2, color, delay=0):
    mid = (ay1+ay2)//2
    tip = ay2+8
    ds = f"animation-delay:{delay:.1f}s" if delay else ""
    return (
        f'<line x1="{ax}" y1="{ay1}" x2="{ax}" y2="{ay2}" '
        f'stroke="{color}" stroke-width="2.5" class="flow-d" style="{ds}" opacity="0.9"/>'
        f'<polygon points="{ax-6},{ay2} {ax+6},{ay2} {ax},{tip}" fill="{color}" opacity="0.9"/>'
        f'<circle cx="{ax}" cy="{mid}" r="3.5" fill="{color}" class="pulse-dot" style="animation-delay:{delay+0.3:.1f}s" opacity="0.7"/>'
    )

def arrow_right(ax1, ax2, ay, color, delay=0):
    ds = f"animation-delay:{delay:.1f}s" if delay else ""
    return (
        f'<line x1="{ax1}" y1="{ay}" x2="{ax2}" y2="{ay}" '
        f'stroke="{color}" stroke-width="2" class="flow-r" style="{ds}" opacity="0.85"/>'
        f'<polygon points="{ax2},{ay-5} {ax2+9},{ay} {ax2},{ay+5}" fill="{color}" opacity="0.85"/>'
    )

# ── NUMBERED ROW (like Azure AI Ecosystem image) ─────────────────────────────
def numbered_row(ry, row_h, num, label, sublabel, color, cards, total_w=900, pad=18):
    """Left: numbered label. Right: card area. Returns (svg, next_y)."""
    LEFT_W = 165
    RIGHT_X = LEFT_W + 24
    RIGHT_W = total_w - RIGHT_X - pad
    CARD_AREA_Y = ry + 8
    CARD_H = row_h - 16

    bg = lighten(color, 0.88)
    border = lighten(color, 0.6)

    s = ""
    # Row background
    s += f'<rect x="{pad}" y="{ry}" width="{total_w-pad*2}" height="{row_h}" rx="12" fill="{bg}" stroke="{border}" stroke-width="1.2" class="fadein"/>'

    # Left label area
    s += f'<circle cx="{pad+22}" cy="{ry+row_h//2}" r="14" fill="{color}" class="fadein"/>'
    s += f'<text x="{pad+22}" y="{ry+row_h//2+5}" text-anchor="middle" fill="white" font-size="13" font-weight="900" font-family="Arial,sans-serif">{num}</text>'
    s += f'<text x="{pad+42}" y="{ry+row_h//2-4}" fill="{darken(color,0.1)}" font-size="11" font-weight="800" font-family="Arial,sans-serif">{xe(label)}</text>'
    if sublabel:
        s += f'<text x="{pad+42}" y="{ry+row_h//2+10}" fill="{darken(color,0.2)}" font-size="8.5" font-family="Arial,sans-serif" font-style="italic">{xe(sublabel)}</text>'

    # Animated connector line
    s += arrow_right(LEFT_W+pad-4, RIGHT_X+pad-8, ry+row_h//2, color)

    # Cards on the right
    n = len(cards)
    cw = RIGHT_W // n - 6
    for i, (title, sub) in enumerate(cards):
        cx = RIGHT_X + pad + i*(cw+6)
        cy = CARD_AREA_Y
        ch = CARD_H
        c2 = f'#{int(int(color.lstrip("#")[0:2],16)*0.95):02X}{int(int(color.lstrip("#")[2:4],16)*0.95):02X}FF' if i==0 else color
        col = PALETTES["default"][i % 6]

        # Card shadow effect
        s += f'<rect x="{cx+2}" y="{cy+2}" width="{cw}" height="{ch}" rx="9" fill="rgba(0,0,0,0.06)"/>'
        # Card body
        s += f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" rx="9" fill="white" stroke="{lighten(col,0.5)}" stroke-width="1.5" class="fadein"/>'
        # Top accent bar
        s += f'<rect x="{cx}" y="{cy}" width="{cw}" height="4" rx="2" fill="{col}"/>'
        # Title
        tf = min(10, max(8, cw//9))
        df = min(8.5, max(7, cw//11))
        s += f'<text x="{cx+cw//2}" y="{cy+ch//2}" text-anchor="middle" fill="{darken(col,0.05)}" font-size="{tf}" font-weight="800" font-family="Arial,sans-serif">{xe(clamp(title, cw//5))}</text>'
        if sub and ch >= 30:
            s += f'<text x="{cx+cw//2}" y="{cy+ch//2+12}" text-anchor="middle" fill="#64748B" font-size="{df}" font-family="Arial,sans-serif">{xe(clamp(sub, cw//4))}</text>'

    return s, ry + row_h

# ── PHASE PIPELINE (like CI/CD steps) ─────────────────────────────────────────
def pipeline_phases(sy, phases, color_list, pad=18, total_w=900):
    """Horizontal numbered pipeline with animated flow arrows."""
    n = len(phases)
    pw = (total_w - pad*2 - (n-1)*10) // n
    ph = 140
    s = ""
    for i, (env, title, sub) in enumerate(phases):
        col = color_list[i % len(color_list)]
        bx = pad + i*(pw+10)
        bg = lighten(col, 0.87)
        s += f'<rect x="{bx+2}" y="{sy+2}" width="{pw}" height="{ph}" rx="10" fill="rgba(0,0,0,0.05)"/>'
        s += f'<rect x="{bx}" y="{sy}" width="{pw}" height="{ph}" rx="10" fill="{bg}" stroke="{lighten(col,0.5)}" stroke-width="1.5" class="fadein" style="animation-delay:{i*0.08:.2f}s"/>'
        # Top band
        s += f'<rect x="{bx}" y="{sy}" width="{pw}" height="26" rx="10" fill="{col}"/>'
        s += f'<rect x="{bx}" y="{sy+18}" width="{pw}" height="8" fill="{col}"/>'
        s += f'<text x="{bx+pw//2}" y="{sy+17}" text-anchor="middle" fill="white" font-size="9" font-weight="800" font-family="Arial,sans-serif" letter-spacing="0.8">{xe(env.upper())}</text>'
        # Step number
        s += f'<circle cx="{bx+pw//2}" cy="{sy+55}" r="16" fill="{rgba(col,0.12)}" stroke="{lighten(col,0.4)}" stroke-width="1.5"/>'
        s += f'<text x="{bx+pw//2}" y="{sy+61}" text-anchor="middle" fill="{col}" font-size="18" font-weight="900" font-family="Arial,sans-serif">{i+1}</text>'
        s += f'<text x="{bx+pw//2}" y="{sy+88}" text-anchor="middle" fill="#1E293B" font-size="9" font-weight="700" font-family="Arial,sans-serif">{xe(clamp(title,pw//5))}</text>'
        s += f'<text x="{bx+pw//2}" y="{sy+102}" text-anchor="middle" fill="#64748B" font-size="8" font-family="Arial,sans-serif">{xe(clamp(sub,pw//4))}</text>'
        # Arrow to next
        if i < n-1:
            s += arrow_right(bx+pw+1, bx+pw+9, sy+ph//2, col, delay=i*0.1)
    return s, sy+ph

# ── BRANCH COLUMNS (git workflow) ─────────────────────────────────────────────
def branch_columns(sy, branches, pad=18, total_w=900):
    n = len(branches); bw = (total_w-pad*2-4*(n-1))//n; bh = 155
    s = ""
    for i,(name,role,deploy,col) in enumerate(branches):
        bx = pad+i*(bw+4); bg=lighten(col,0.88)
        s += f'<rect x="{bx+2}" y="{sy+2}" width="{bw}" height="{bh}" rx="10" fill="rgba(0,0,0,0.05)"/>'
        s += f'<rect x="{bx}" y="{sy}" width="{bw}" height="{bh}" rx="10" fill="{bg}" stroke="{lighten(col,0.5)}" stroke-width="1.5" class="fadein" style="animation-delay:{i*0.07:.2f}s"/>'
        s += f'<rect x="{bx}" y="{sy}" width="{bw}" height="24" rx="10" fill="{col}"/>'
        s += f'<rect x="{bx}" y="{sy+16}" width="{bw}" height="8" fill="{col}"/>'
        s += f'<text x="{bx+bw//2}" y="{sy+16}" text-anchor="middle" fill="white" font-size="9" font-weight="800" font-family="Arial,sans-serif">{xe(name)}</text>'
        s += f'<text x="{bx+bw//2}" y="{sy+62}" text-anchor="middle" fill="{col}" font-size="26" font-weight="900" font-family="Arial,sans-serif">{name[0].upper()}</text>'
        s += f'<text x="{bx+bw//2}" y="{sy+86}" text-anchor="middle" fill="#1E293B" font-size="9" font-weight="700" font-family="Arial,sans-serif">{xe(clamp(role,bw//5))}</text>'
        s += f'<text x="{bx+bw//2}" y="{sy+100}" text-anchor="middle" fill="#64748B" font-size="8" font-family="Arial,sans-serif">{xe(clamp(deploy,bw//4))}</text>'
        # Badge
        badge_col = "#DC2626" if i<2 else "#D97706"
        badge_txt = "protected" if i<2 else "PR required"
        s += f'<rect x="{bx+6}" y="{sy+bh-24}" width="{bw-12}" height="17" rx="8" fill="{rgba(badge_col,0.12)}" stroke="{badge_col}" stroke-width="1"/>'
        s += f'<text x="{bx+bw//2}" y="{sy+bh-12}" text-anchor="middle" fill="{badge_col}" font-size="7.5" font-weight="700" font-family="Arial,sans-serif">{badge_txt}</text>'
    return s, sy+bh

# ── CHEAT-ROW (docker layers etc) ─────────────────────────────────────────────
def cheatrow(ry, rh, label, color, items, pad=18, total_w=900):
    lw = max(90, len(label)*9+20); bg=lighten(color,0.88)
    s  = f'<rect x="{pad}" y="{ry}" width="{total_w-pad*2}" height="{rh}" rx="8" fill="{bg}" stroke="{lighten(color,0.55)}" stroke-width="1.2"/>'
    s += f'<rect x="{pad}" y="{ry}" width="{lw}" height="{rh}" rx="8" fill="{color}"/>'
    s += f'<rect x="{pad+lw-8}" y="{ry}" width="8" height="{rh}" fill="{color}"/>'
    s += f'<text x="{pad+lw//2}" y="{ry+rh//2+4}" text-anchor="middle" fill="white" font-size="{min(10,max(8,lw//9))}" font-weight="800" font-family="Arial,sans-serif">{xe(clamp(label,lw//5))}</text>'
    gx=pad+lw+8; avail=total_w-pad-gx-pad; n=len(items); cw=max(50,avail//n-4)
    for i,item in enumerate(items):
        t2=item[1] if len(item)>1 else ""; sub=item[2] if len(item)>2 else ""; cx2=gx+i*(cw+4)
        col2=PALETTES["default"][i%6]
        s += f'<rect x="{cx2}" y="{ry+3}" width="{cw}" height="{rh-6}" rx="7" fill="white" stroke="{lighten(col2,0.4)}" stroke-width="1"/>'
        s += f'<rect x="{cx2}" y="{ry+3}" width="{cw}" height="3" rx="1" fill="{col2}"/>'
        s += f'<text x="{cx2+cw//2}" y="{ry+rh//2}" text-anchor="middle" fill="{darken(col2,0.05)}" font-size="{min(10,max(8,cw//7))}" font-weight="700" font-family="Arial,sans-serif">{xe(clamp(t2,cw//4))}</text>'
        if sub and rh>=44:
            s += f'<text x="{cx2+cw//2}" y="{ry+rh-10}" text-anchor="middle" fill="#64748B" font-size="{min(8,max(6,cw//9))}" font-family="Arial,sans-serif">{xe(clamp(sub,cw//4))}</text>'
    return s

# ── SECTION HEADER + CARDS ─────────────────────────────────────────────────────
def sec(sx, sy, sw, content_h, title, color, subtitle="", pad=0):
    ht = 26 if not subtitle else 34
    sh = ht + 3 + content_h + 7
    bg = lighten(color, 0.90)
    s  = f'<rect x="{sx+2}" y="{sy+2}" width="{sw}" height="{sh}" rx="10" fill="rgba(0,0,0,0.04)"/>'
    s += f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="10" fill="{bg}" stroke="{lighten(color,0.55)}" stroke-width="1.5"/>'
    s += f'<rect x="{sx}" y="{sy}" width="{sw}" height="{ht}" rx="10" fill="{color}"/>'
    s += f'<rect x="{sx}" y="{sy+ht-8}" width="{sw}" height="8" fill="{color}"/>'
    s += f'<text x="{sx+14}" y="{sy+17}" fill="white" font-size="10.5" font-weight="800" font-family="Arial,sans-serif" letter-spacing="0.8">{xe(title.upper())}</text>'
    if subtitle:
        s += f'<text x="{sx+14}" y="{sy+29}" fill="rgba(255,255,255,0.85)" font-size="8.5" font-family="Arial,sans-serif">{xe(subtitle)}</text>'
    return s, sy+ht+3, sy+sh

def two_col(sy, lw, rw, content_h, ltitle, lcol, rtitle, rcol, lsub="", rsub="", pad=18):
    ht=34; sh=ht+3+content_h+7; s=""
    for sx,sw,title,color,sub in [(pad,lw,ltitle,lcol,lsub),(pad+lw+14,rw,rtitle,rcol,rsub)]:
        bg=lighten(color,0.90)
        s += f'<rect x="{sx+2}" y="{sy+2}" width="{sw}" height="{sh}" rx="10" fill="rgba(0,0,0,0.04)"/>'
        s += f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="10" fill="{bg}" stroke="{lighten(color,0.55)}" stroke-width="1.5"/>'
        s += f'<rect x="{sx}" y="{sy}" width="{sw}" height="{ht}" rx="10" fill="{color}"/>'
        s += f'<rect x="{sx}" y="{sy+ht-8}" width="{sw}" height="8" fill="{color}"/>'
        s += f'<text x="{sx+14}" y="{sy+17}" fill="white" font-size="10.5" font-weight="800" font-family="Arial,sans-serif" letter-spacing="0.8">{xe(title.upper())}</text>'
        if sub:
            s += f'<text x="{sx+14}" y="{sy+29}" fill="rgba(255,255,255,0.85)" font-size="8.5" font-family="Arial,sans-serif">{xe(sub)}</text>'
    return s, sy+ht+3, sy+sh

def card(cx, cy, cw, ch, color, title, desc="", rx=8):
    bg="white"; col=color
    s  = f'<rect x="{cx+1}" y="{cy+1}" width="{cw}" height="{ch}" rx="{rx}" fill="rgba(0,0,0,0.05)"/>'
    s += f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" rx="{rx}" fill="{bg}" stroke="{lighten(col,0.45)}" stroke-width="1.2"/>'
    s += f'<rect x="{cx}" y="{cy}" width="{cw}" height="4" rx="2" fill="{col}"/>'
    pad2=cx+8; avail=cw-16
    tf=min(10,max(8,avail//8)); df=min(8.5,max(7,avail//11))
    t_cl=xe(clamp(title,max(3,avail//max(1,tf-2))))
    if desc and ch>=32:
        max_lines=max(1,(ch-20)//12)
        s += f'<text x="{pad2}" y="{cy+16}" fill="{darken(col,0.05)}" font-size="{tf}" font-weight="700" font-family="Arial,sans-serif">{t_cl}</text>'
        lines=wrap_text(desc,max(8,avail//max(1,df)))
        for i,ln in enumerate(lines[:max_lines]):
            ly=cy+28+i*12
            if ly+3<=cy+ch:
                s += f'<text x="{pad2}" y="{ly}" fill="#64748B" font-size="{df}" font-family="Arial,sans-serif">{xe(ln)}</text>'
    else:
        s += f'<text x="{pad2}" y="{cy+ch//2+4}" fill="{darken(col,0.05)}" font-size="{tf}" font-weight="700" font-family="Arial,sans-serif">{t_cl}</text>'
    return s

def card_centered(cx, cy, cw, ch, color, title, sub="", rx=8):
    bg=lighten(color, 0.88)
    s  = f'<rect x="{cx+1}" y="{cy+1}" width="{cw}" height="{ch}" rx="{rx}" fill="rgba(0,0,0,0.05)"/>'
    s += f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" rx="{rx}" fill="{bg}" stroke="{lighten(color,0.45)}" stroke-width="1.4"/>'
    mid=cy+ch//2; tf=min(10,max(8,cw//9)); sf=min(8.5,max(7,cw//11))
    if sub:
        s += f'<text x="{cx+cw//2}" y="{mid-2}" text-anchor="middle" fill="{darken(color,0.1)}" font-size="{tf}" font-weight="800" font-family="Arial,sans-serif">{xe(clamp(title,cw//5))}</text>'
        s += f'<text x="{cx+cw//2}" y="{mid+12}" text-anchor="middle" fill="#64748B" font-size="{sf}" font-family="Arial,sans-serif">{xe(clamp(sub,cw//4))}</text>'
    else:
        s += f'<text x="{cx+cw//2}" y="{mid+4}" text-anchor="middle" fill="{darken(color,0.1)}" font-size="{tf}" font-weight="800" font-family="Arial,sans-serif">{xe(clamp(title,cw//5))}</text>'
    return s

def status_bar(ry, items, pad=18, total_w=900):
    n=len(items); iw=(total_w-pad*2)//n
    s=f'<rect x="{pad}" y="{ry}" width="{total_w-pad*2}" height="22" rx="11" fill="#F1F5F9" stroke="#E2E8F0" stroke-width="1"/>'
    for i,(label,color) in enumerate(items):
        lx=pad+i*iw+iw//2-len(label)*3-8
        s += f'<circle cx="{lx}" cy="{ry+11}" r="4" fill="{color}"/>'
        s += f'<text x="{lx+9}" y="{ry+15}" fill="#475569" font-size="{min(9,max(6,iw//10))}" font-weight="600" font-family="Arial,sans-serif">{xe(label)}</text>'
    return s

GAP=14  # vertical gap between sections

# ── WRAPPER ────────────────────────────────────────────────────────────────────
def wrap(content, title, subtitle, color, date_str, total_w=900, total_h=590):
    dark_bg = darken(color, 0.55)
    mid_bg = darken(color, 0.35)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} {total_h}" width="{total_w}" height="{total_h}" style="overflow:hidden;display:block;font-family:Arial,sans-serif">
  <defs>
    <linearGradient id="hg" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0%" stop-color="{dark_bg}"/>
      <stop offset="100%" stop-color="{mid_bg}"/>
    </linearGradient>
    <linearGradient id="bg_g" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" stop-color="#F8FAFF"/>
      <stop offset="100%" stop-color="{lighten(color,0.94)}"/>
    </linearGradient>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="115%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="rgba(0,0,0,0.12)"/>
    </filter>
  </defs>
  {ANIM_CSS}
  <rect width="{total_w}" height="{total_h}" fill="url(#bg_g)"/>
  <!-- dot grid -->
  <pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">
    <circle cx="1" cy="1" r="0.7" fill="{rgba(color,0.12)}"/>
  </pattern>
  <rect width="{total_w}" height="{total_h}" fill="url(#dots)"/>
  <!-- header -->
  <rect x="0" y="0" width="{total_w}" height="60" fill="url(#hg)"/>
  <rect x="0" y="58" width="{total_w}" height="3" fill="{color}" opacity="0.5"/>
  <!-- subtitle pill -->
  <rect x="16" y="14" width="{len(subtitle)*7+22}" height="18" rx="9" fill="rgba(255,255,255,0.18)" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>
  <text x="28" y="26" fill="white" font-size="8.5" font-weight="700" letter-spacing="1.8">{xe(subtitle.upper())}</text>
  <!-- title -->
  <text x="{total_w//2}" y="40" text-anchor="middle" fill="white" font-size="21" font-weight="900" letter-spacing="-0.5">{xe(clamp(title.replace("&","and"),52))}</text>
  {content}
  <!-- footer -->
  <rect x="0" y="{total_h-32}" width="{total_w}" height="32" fill="{lighten(color,0.95)}"/>
  <rect x="0" y="{total_h-33}" width="{total_w}" height="1" fill="#E2E8F0"/>
  <text x="20" y="{total_h-12}" fill="#94A3B8" font-size="9">{xe(date_str)}</text>
  <rect x="{total_w-310}" y="{total_h-26}" width="295" height="20" rx="10" fill="{rgba(color,0.1)}" stroke="{color}" stroke-width="1.2"/>
  <text x="{total_w-162}" y="{total_h-13}" text-anchor="middle" fill="{color}" font-size="9.5" font-weight="800" letter-spacing="0.8">AI (c) Komal Batra</text>
</svg>'''


# ── DIAGRAM FUNCTIONS ──────────────────────────────────────────────────────────

def make_system_design(C):
    s=""; y=68; P=18; W=900

    sv,cy,y=sec(P,y,W-P*2,24,"CLIENT LAYER",C[0]); s+=sv
    for i,(t,sub) in enumerate([("Browser","Web SPA"),("Mobile App","iOS/Android"),("Desktop","Electron"),("3rd Party","REST / SDK"),("IoT Device","MQTT")]):
        s+=card_centered(P+4+i*170,cy,162,24,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[1]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,26,"EDGE + AUTH",C[1],"Rate limit  |  JWT/OAuth2  |  WAF  |  CDN"); s+=sv
    for i,(t,sub) in enumerate([("CDN","CloudFront"),("Load Balancer","Layer-7"),("API Gateway","rate limit"),("Auth Service","OAuth2/JWT"),("WAF","shield")]):
        s+=card(P+4+i*170,cy,164,26,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[2]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,38,"MICROSERVICES",C[2]); s+=sv
    for i,(t,sub) in enumerate([("User Service","auth+profile"),("Order Service","cart+checkout"),("Payment","Stripe+PCI"),("Notification","email+SMS"),("Search","Elasticsearch"),("Analytics","event tracking")]):
        s+=card(P+4+i*142,cy,138,38,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[3]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,24,"MESSAGE BROKER",C[3]); s+=sv
    for i,(t,sub) in enumerate([("Kafka","event streams"),("RabbitMQ","task queues"),("Redis PubSub","real-time"),("Dead Letter Q","failed msgs"),("EventBridge","cloud events")]):
        s+=card_centered(P+4+i*170,cy,164,24,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[4]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,38,"DATA LAYER",C[4],"OLTP  |  Cache  |  Documents  |  Blobs  |  Search  |  Analytics"); s+=sv
    for i,(t,sub) in enumerate([("PostgreSQL","OLTP+ACID"),("Redis","cache+sessions"),("MongoDB","documents"),("S3","blob store"),("Elasticsearch","full-text"),("ClickHouse","analytics")]):
        s+=card(P+4+i*142,cy,138,38,C[i%len(C)],t,sub)

    s+=status_bar(y+8,[("Load Balanced","#059669"),("Auth Active","#7C3AED"),("Events Flowing","#2563EB"),("DB Healthy","#059669"),("Cache 94%","#D97706")])
    return s,"System Architecture"


def make_kubernetes(C):
    s=""; y=68; P=18; W=900

    sv,cy,y=sec(P,y,W-P*2,28,"CONTROL PLANE",C[0],"API Server  |  Scheduler  |  Controller Manager  |  etcd"); s+=sv
    for i,(t,sub) in enumerate([("API Server","entry point"),("Scheduler","node select"),("Controller Mgr","reconcile"),("etcd","state store"),("Cloud CM","cloud API")]):
        s+=card(P+4+i*170,cy,164,28,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[1]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,26,"WORKER NODES",C[1],"Kubelet  |  kube-proxy  |  Container Runtime  |  CNI"); s+=sv
    for i,(t,sub) in enumerate([("Kubelet","node agent"),("kube-proxy","networking"),("Container RT","containerd"),("CNI Plugin","Calico/Cilium"),("Node Exporter","metrics")]):
        s+=card(P+4+i*170,cy,164,26,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[2]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,28,"WORKLOADS",C[2]); s+=sv
    for i,(t,sub) in enumerate([("Deployment","rolling update"),("StatefulSet","ordered pods"),("DaemonSet","per-node"),("CronJob","scheduled"),("HPA","autoscale"),("PDB","disruption budget")]):
        s+=card(P+4+i*142,cy,138,28,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[3]); y+=GAP

    lw=426; rw=W-P*2-lw-14
    sv,cy,bot=two_col(y,lw,rw,74,"NETWORKING + INGRESS",C[3],"STORAGE + CONFIG",C[4],
                      "Ingress  |  Service Mesh  |  NetworkPolicy","PV  |  ConfigMap  |  Secrets",P); s+=sv
    for i,(t,sub,col) in enumerate([("Ingress Ctrl","nginx/traefik",C[3]),("Service Mesh","Istio/Linkerd",C[5]),("NetworkPolicy","microseg",C[3]),("LoadBalancer","cloud LB",C[0])]):
        s+=card(P+4+i*106,cy,102,74,col,t,sub)
    for i,(t,sub,col) in enumerate([("PersistentVol","dynamic prov",C[4]),("ConfigMap","env config",C[1]),("Secrets","encrypted kv",C[2]),("StorageClass","CSI driver",C[5])]):
        s+=card(P+lw+18+i*106,cy,102,74,col,t,sub)
    y=bot

    s+=status_bar(y+8,[("Nodes Ready","#059669"),("Pods Running","#2563EB"),("Services OK","#7C3AED"),("Storage Bound","#D97706"),("Certs Valid","#059669")])
    return s,"Cloud Architecture"


def make_llm(C):
    s=""; y=68; P=18; W=900

    sv,cy,y=sec(P,y,W-P*2,24,"FOUNDATION MODELS",C[0],"GPT-4o  |  Claude  |  Gemini  |  Llama 3.1  |  Mistral"); s+=sv
    for i,(t,sub) in enumerate([("GPT-4o","OpenAI"),("Claude 3.5","Anthropic"),("Gemini 1.5","Google"),("Llama 3.1","Meta OSS"),("Mistral","EU OSS"),("Qwen 2.5","Alibaba")]):
        s+=card_centered(P+4+i*142,cy,138,24,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[1]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,28,"CONTEXT + RETRIEVAL (RAG)",C[1],"Vector DB  |  Chunking  |  Embeddings  |  Reranker  |  Cache"); s+=sv
    for i,(t,sub) in enumerate([("Vector DB","Pinecone/Weaviate"),("Chunking","semantic split"),("Embeddings","text-embed-3"),("Reranker","cross-encoder"),("Semantic Cache","sim.lookup")]):
        s+=card(P+4+i*170,cy,164,28,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[2]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,32,"AGENT + ORCHESTRATION",C[2],"ReAct  |  Tool Use  |  Memory  |  Planner  |  Critic  |  Router"); s+=sv
    for i,(t,sub) in enumerate([("Agent Loop","ReAct/CoT"),("Tool Use","function call"),("Memory","episodic store"),("Planner","decompose"),("Critic","self-refine"),("Router","skill select")]):
        s+=card(P+4+i*142,cy,138,32,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[3]); y+=GAP

    lw=440; rw=W-P*2-lw-14
    sv,cy,bot=two_col(y,lw,rw,72,"INFERENCE + SERVING",C[3],"SAFETY + OPS",C[4],
                      "vLLM  |  TRT-LLM  |  Batching  |  KV Cache","Guardrails  |  Evals  |  Tracing",P); s+=sv
    for i,(t,sub,col) in enumerate([("vLLM","tensor parallel",C[3]),("TRT-LLM","NVIDIA opt",C[5]),("Batching","continuous",C[3]),("KV Cache","paged attn",C[0]),("Streaming","SSE/WS",C[1])]):
        s+=card(P+4+i*86,cy,82,72,col,t,sub)
    for i,(t,sub,col) in enumerate([("Guardrails","PII+toxic",C[4]),("Evals","RAGAS",C[2]),("LangSmith","trace+debug",C[5])]):
        s+=card(P+lw+18+i*138,cy,134,72,col,t,sub)
    y=bot

    s+=status_bar(y+8,[("P50 420ms","#059669"),("Tokens/s 1.2k","#2563EB"),("Cache 64%","#7C3AED"),("Cost -38%","#059669"),("Safety 99%","#D97706")])
    return s,"AI Architecture"


def make_system_design_numbered(C):
    """Like Azure AI Ecosystem — numbered rows with left label + right cards."""
    s=""; y=68; P=18; W=900
    rows=[
        (1,"CLIENT LAYER","browsers, mobile, IoT",C[0],[("Browser","Web SPA"),("Mobile App","iOS/Android"),("Desktop","Electron"),("IoT Device","MQTT")]),
        (2,"EDGE + AUTH","rate limit, CDN, WAF",C[1],[("CDN","CloudFront"),("Load Balancer","Layer-7"),("API Gateway","rate limit"),("Auth","OAuth2/JWT")]),
        (3,"MICROSERVICES","independent deployments",C[2],[("User Service","auth+profile"),("Order Service","cart+checkout"),("Payment","Stripe+PCI"),("Analytics","events")]),
        (4,"MESSAGE BROKER","async event streaming",C[3],[("Kafka","event streams"),("RabbitMQ","task queues"),("Redis PubSub","real-time"),("Dead Letter Q","retries")]),
        (5,"DATA LAYER","OLTP, cache, search, blobs",C[4],[("PostgreSQL","OLTP+ACID"),("Redis","cache"),("MongoDB","docs"),("S3","blobs"),("Elasticsearch","search")]),
    ]
    for num,label,sub,col,cards in rows:
        sv,y=numbered_row(y,76,num,label,sub,col,cards,W,P)
        s+=sv
        if num<len(rows): s+=arrow_down(W//2,y+2,y+10,col); y+=GAP
    s+=status_bar(y+10,[("Load Balanced","#059669"),("Auth Active","#7C3AED"),("Events Flowing","#2563EB"),("DB Healthy","#059669"),("Cache 94%","#D97706")])
    return s,"System Architecture"


def make_cicd(C):
    s=""; y=68; P=18; W=900
    phases=[("CODE","git push","pre-commit hooks"),("BUILD","compile","unit tests"),
            ("TEST","integration","DAST/SAST scan"),("SCAN","CVE scan","SCA/SBOM"),
            ("PACKAGE","Docker","sign+push registry"),("STAGE","deploy","smoke test"),("PROD","blue/green","canary rollout")]
    sv,y=pipeline_phases(y,phases,C,P,W); s+=sv
    s+=status_bar(y+6,[("Build 2m14s","#059669"),("Tests 97%","#2563EB"),("CVEs 0","#059669"),("Image Signed","#7C3AED"),("DORA Elite","#D97706")])
    y+=32

    sv,cy,y=sec(P,y,W-P*2,80,"OBSERVABILITY",C[4],"Metrics  |  Logs  |  Traces  |  Alerts  |  SLO"); s+=sv
    for i,(t,sub,col) in enumerate([("Prometheus","metrics collect",C[0]),("Grafana","dashboards",C[1]),("Loki/ELK","log aggregation",C[2]),("Jaeger","dist. tracing",C[3]),("PagerDuty","alerting",C[4])]):
        s+=card(P+4+i*170,cy,164,80,col,t,sub)

    s+=status_bar(y+8,[("Deploy daily","#059669"),("Lead time <1h","#2563EB"),("MTTR <30m","#7C3AED"),("Change fail <5%","#059669"),("Rollback <5m","#D97706")])
    return s,"DevOps Pipeline"


def make_kafka(C):
    s=""; y=68; P=18; W=900

    sv,cy,y=sec(P,y,W-P*2,34,"PRODUCERS",C[0],"Microservices  |  IoT  |  CDC  |  Clickstream  |  Batch"); s+=sv
    for i,(t,sub) in enumerate([("Microservices","REST/gRPC"),("IoT Devices","MQTT bridge"),("DB CDC","Debezium"),("Clickstream","JS SDK"),("Mobile Apps","SDK"),("Batch Import","file ingest")]):
        s+=card(P+4+i*142,cy,138,34,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[1]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,52,"KAFKA CLUSTER",C[1],"Brokers  |  Partitions  |  Schema Registry  |  Topics"); s+=sv
    for i,(t,sub) in enumerate([("Broker 1","leader"),("Broker 2","replica"),("Broker 3","replica"),("ZooKeeper","coord"),("Schema Reg","Avro/JSON"),("Kafka UI","monitoring")]):
        s+=card_centered(P+4+i*142,cy,138,24,C[1],t,sub)
    for i,(t,sub) in enumerate([("orders","p=6 rf=3"),("events","p=12 rf=3"),("errors","Dead Letter"),("audit","immutable"),("users.cdc","CDC stream")]):
        s+=card(P+4+i*170,cy+28,164,24,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[2]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,26,"STREAM PROCESSING",C[2],"Kafka Streams  |  Flink  |  ksqlDB  |  Spark  |  Bytewax"); s+=sv
    for i,(t,sub) in enumerate([("Kafka Streams","in-process"),("Apache Flink","stateful"),("ksqlDB","SQL stream"),("Spark Struct.","micro-batch"),("Bytewax","Python")]):
        s+=card(P+4+i*170,cy,164,26,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[3]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,30,"CONSUMERS + SINKS",C[3],"Elasticsearch  |  ClickHouse  |  S3  |  PostgreSQL  |  Redis"); s+=sv
    for i,(t,sub) in enumerate([("Elasticsearch","search sink"),("ClickHouse","analytics"),("S3/GCS","data lake"),("PostgreSQL","OLTP sink"),("Redis","cache warm"),("Alerting","PD/Slack")]):
        s+=card(P+4+i*142,cy,138,30,C[i%len(C)],t,sub)

    s+=status_bar(y+8,[("Throughput 2M/s","#059669"),("Lag 0","#2563EB"),("Partitions 48","#7C3AED"),("Retention 7d","#D97706"),("Replication 3x","#059669")])
    return s,"Data Architecture"


def make_zero_trust(C):
    s=""; y=68; P=18; W=900

    sv,cy,y=sec(P,y,W-P*2,26,"IDENTITY + ACCESS",C[0],"IdP/SSO  |  MFA  |  PAM  |  Service Identity  |  Certificates"); s+=sv
    for i,(t,sub) in enumerate([("IdP/SSO","Okta/Azure AD"),("MFA","FIDO2/TOTP"),("PAM","just-in-time"),("Service ID","SPIFFE/SPIRE"),("Certificates","mTLS/PKI")]):
        s+=card(P+4+i*170,cy,164,26,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[1]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,26,"POLICY ENGINE — NEVER TRUST, ALWAYS VERIFY",C[1]); s+=sv
    for i,(t,sub) in enumerate([("OPA/Rego","policy-as-code"),("ABAC","attribute-based"),("Context Aware","device posture"),("Time-based","lease expiry"),("Continuous","re-auth")]):
        s+=card(P+4+i*170,cy,164,26,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[2]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,36,"NETWORK MICRO-SEGMENTS",C[2],"Internet  |  DMZ  |  App Zone  |  Data Zone  |  Admin  |  IoT"); s+=sv
    for i,(t,sub) in enumerate([("Internet Zone","WAF+DDoS"),("DMZ","reverse proxy"),("App Zone","east-west mTLS"),("Data Zone","encrypted"),("Admin Zone","bastion/PAM"),("IoT Zone","MAC filter")]):
        s+=card(P+4+i*142,cy,138,36,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[3]); y+=GAP

    lw=426; rw=W-P*2-lw-14
    sv,cy,bot=two_col(y,lw,rw,72,"DETECT + RESPOND",C[3],"DATA PROTECTION",C[4],
                      "SIEM  |  SOAR  |  EDR  |  Deception","DLP  |  Encryption  |  Tokenization  |  Keys",P); s+=sv
    for i,(t,sub,col) in enumerate([("SIEM","Splunk/Sentinel",C[3]),("SOAR","auto-remediate",C[5]),("EDR","endpoint detect",C[3]),("Deception","honeypots",C[0])]):
        s+=card(P+4+i*106,cy,102,72,col,t,sub)
    for i,(t,sub,col) in enumerate([("DLP","data loss prev",C[4]),("Encryption","AES-256/TLS1.3",C[1]),("Tokenization","PCI/PII",C[2]),("Key Mgmt","Vault",C[5])]):
        s+=card(P+lw+18+i*106,cy,102,72,col,t,sub)
    y=bot

    s+=status_bar(y+8,[("Zero Standing Priv","#059669"),("mTLS 100%","#2563EB"),("Posture Check","#7C3AED"),("Least Privilege","#059669"),("Audit Logged","#D97706")])
    return s,"Security Architecture"


def make_aws(C):
    s=""; y=68; P=18; W=900

    sv,cy,y=sec(P,y,W-P*2,26,"EDGE + CDN LAYER",C[0],"Route 53  |  CloudFront  |  ACM  |  Shield  |  API Gateway"); s+=sv
    for i,(t,sub) in enumerate([("Route 53","DNS+health"),("CloudFront","CDN+WAF"),("ACM","SSL certs"),("Shield Adv","DDoS"),("API Gateway","REST/WS/GQL")]):
        s+=card(P+4+i*170,cy,164,26,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[1]); y+=GAP

    lw=426; rw=W-P*2-lw-14
    sv,cy,bot=two_col(y,lw,rw,64,"PUBLIC SUBNETS (AZ-a/b/c)",C[1],"PRIVATE SUBNETS",C[2],
                      "ALB  |  NAT Gateway  |  Bastion","ECS  |  Lambda  |  EC2 ASG  |  ElastiCache",P); s+=sv
    for i,(t,sub,col) in enumerate([("ALB","Layer-7 LB",C[1]),("NAT GW","outbound",C[5]),("Bastion","SSH jump",C[3])]):
        s+=card(P+4+i*140,cy,136,64,col,t,sub)
    for i,(t,sub,col) in enumerate([("ECS/EKS","containers",C[2]),("Lambda","serverless",C[0]),("EC2 ASG","VM fleet",C[4]),("ElastiCache","Redis",C[5])]):
        s+=card(P+lw+18+i*106,cy,102,64,col,t,sub)
    y=bot
    s+=arrow_down(W//2,y+2,y+11,C[3]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,32,"DATA LAYER",C[3],"RDS Aurora  |  DynamoDB  |  S3  |  Redshift  |  Elasticsearch  |  SQS/SNS"); s+=sv
    for i,(t,sub) in enumerate([("RDS Aurora","Multi-AZ"),("DynamoDB","global tables"),("S3","11-nines"),("Redshift","analytics DW"),("Elasticsearch","full-text"),("SQS/SNS","messaging")]):
        s+=card(P+4+i*142,cy,138,32,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[4]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,32,"MONITORING + SECURITY",C[4],"CloudWatch  |  X-Ray  |  GuardDuty  |  Config  |  CloudTrail"); s+=sv
    for i,(t,sub) in enumerate([("CloudWatch","metrics+logs"),("X-Ray","dist. tracing"),("GuardDuty","threat detect"),("Config","compliance"),("CloudTrail","audit log"),("Security Hub","findings")]):
        s+=card(P+4+i*142,cy,138,32,C[i%len(C)],t,sub)

    s+=status_bar(y+8,[("99.99% SLA","#059669"),("Multi-AZ","#2563EB"),("Auto Scaled","#7C3AED"),("Cost Opt","#D97706"),("Compliant","#059669")])
    return s,"Cloud Architecture"


def make_mlops(C):
    s=""; y=68; P=18; W=900
    rows=[
        (1,"DATA ENGINEERING","feature store, catalog, labeling",C[0],[("Feature Store","Feast/Tecton"),("Data Catalog","lineage"),("Label Studio","annotation"),("DVC","version")]),
        (2,"TRAINING + EXP","distributed, HPO, AutoML",C[1],[("MLflow","experiment"),("Ray Train","distributed"),("Optuna","HPO"),("Kubeflow","pipeline")]),
        (3,"MODEL REGISTRY","versioning, governance, approval",C[2],[("MLflow Reg","versioning"),("Model Card","bias+docs"),("A/B Test","champ/chal"),("Approval","review gate")]),
        (4,"SERVING","online + batch inference",C[3],[("Seldon Core","K8s serving"),("Triton","GPU inference"),("TorchServe","PyTorch"),("Ray Serve","multi-model")]),
        (5,"MONITORING","drift, metrics, auto-retrain",C[4],[("Evidently","data drift"),("Prometheus","perf metrics"),("Retraining","auto-trigger"),("Feedback","RLHF loop")]),
    ]
    for num,label,sub,col,cards in rows:
        sv,y=numbered_row(y,74,num,label,sub,col,cards,W,P)
        s+=sv
        if num<len(rows): s+=arrow_down(W//2,y+2,y+10,col); y+=GAP
    s+=status_bar(y+10,[("Acc 96.2%","#059669"),("Drift: None","#2563EB"),("P99 87ms","#7C3AED"),("Retrain weekly","#D97706"),("Registry v2.4","#059669")])
    return s,"AI Architecture"


def make_rag(C):
    s=""; y=68; P=18; W=900
    rows=[
        (1,"INGESTION","PDF/HTML → chunk → embed → store",C[0],[("Loader","PDF/HTML/MD"),("Chunker","semantic split"),("Cleaner","PII strip"),("Embedder","text-embed-3"),("VectorDB","Pinecone")]),
        (2,"RETRIEVAL","dense + sparse + rerank",C[1],[("Dense","cosine sim"),("Sparse BM25","TF-IDF"),("Hybrid RRF","score fusion"),("Reranker","cross-encoder"),("HyDE","hypothetical")]),
        (3,"AUGMENTATION","prompt + generate + cite",C[2],[("Context Inject","top-k chunks"),("Prompt Tmpl","few-shot"),("LLM Call","GPT-4o/Claude"),("Citation","source ref"),("Self-refine","critic loop")]),
        (4,"EVAL + OPS","measure + monitor + improve",C[3],[("RAGAS","faithfulness"),("Context Prec.","recall"),("Caching","GPTCache"),("LangSmith","observability"),("Feedback","RLHF")]),
    ]
    for num,label,sub,col,cards in rows:
        sv,y=numbered_row(y,82,num,label,sub,col,cards,W,P)
        s+=sv
        if num<len(rows): s+=arrow_down(W//2,y+2,y+10,col); y+=GAP
    s+=status_bar(y+10,[("Faithfulness 92%","#059669"),("Ctx Prec 87%","#2563EB"),("Latency 1.1s","#7C3AED"),("Cache 41%","#D97706"),("Cost -55%","#059669")])
    return s,"AI Architecture"


def make_lakehouse(C):
    s=""; y=68; P=18; W=900
    rows=[
        (1,"INGESTION","batch, streaming, CDC, IoT",C[0],[("Batch ETL","Airflow/Glue"),("Streaming","Kafka/Kinesis"),("CDC","Debezium"),("API Pull","REST/GraphQL"),("IoT","MQTT")]),
        (2,"TABLE FORMAT","ACID, time travel, schema evo",C[1],[("Delta Lake","ACID+time travel"),("Apache Iceberg","schema evolution"),("Apache Hudi","upserts+deletes"),("Metadata","Glue/Hive")]),
        (3,"COMPUTE","SQL, ML, streaming transforms",C[2],[("Apache Spark","SQL+ML"),("Trino/Presto","interactive SQL"),("dbt","transform+test"),("Apache Flink","stream proc")]),
        (4,"CONSUMPTION","BI, ML, dashboards, APIs",C[3],[("BI Tools","Tableau/Superset"),("ML Platform","SageMaker"),("Ad-hoc SQL","Athena"),("Dashboards","Grafana"),("Data APIs","REST/GQL")]),
    ]
    for num,label,sub,col,cards in rows:
        sv,y=numbered_row(y,80,num,label,sub,col,cards,W,P)
        s+=sv
        if num<len(rows): s+=arrow_down(W//2,y+2,y+10,col); y+=GAP
    s+=status_bar(y+10,[("Bronze","#B45309"),("Silver","#94A3B8"),("Gold","#D97706"),("Serving","#059669"),("Governed","#7C3AED")])
    return s,"Data Architecture"


def make_devsecops(C):
    s=""; y=68; P=18; W=900
    phases=[("IDE","Pre-commit","git-secrets"),("SCM","PR Review","SAST/Semgrep"),
            ("Build","Compile","SCA/SBOM"),("Test","Quality","DAST/ZAP"),
            ("Artifact","Registry","Trivy+sign"),("Stage","Deploy","IaC scan"),("Prod","Runtime","Falco/eBPF")]
    sv,y=pipeline_phases(y,phases,C,P,W); s+=sv
    s+=status_bar(y+6,[("Secrets Blocked","#DC2626"),("CVE Free","#D97706"),("Image Signed","#059669"),("Policy Pass","#7C3AED"),("Runtime Watch","#2563EB")])
    y+=32

    lw=426; rw=W-P*2-lw-14
    sv,cy,bot=two_col(y,lw,rw,76,"SIEM + INCIDENT RESPONSE",C[4],"COMPLIANCE + POLICY",C[1],
                      "Splunk  |  SOAR  |  Threat Intel","CIS  |  SOC2  |  ISO 27001  |  OPA",P); s+=sv
    for i,(t,sub,col) in enumerate([("SIEM","Splunk/Sentinel",C[4]),("SOAR","auto-remediation",C[5]),("Threat Intel","IOC feeds",C[0])]):
        s+=card(P+4+i*140,cy,136,76,col,t,sub)
    for i,(t,sub,col) in enumerate([("CIS Benchmarks","hardening",C[1]),("SOC2/ISO27K","audit",C[2]),("OPA/Rego","policy-as-code",C[3])]):
        s+=card(P+lw+18+i*140,cy,136,76,col,t,sub)
    y=bot

    s+=status_bar(y+8,[("NIST CSF","#059669"),("ISO 27001","#2563EB"),("SOC2 Type II","#7C3AED"),("GDPR","#D97706"),("PCI-DSS","#DC2626")])
    return s,"Security Architecture"


def make_docker(C):
    s=""; y=68; P=18; W=900
    rows=[("FROM/BASE",C[0],[("","Alpine","3.19"),("","Ubuntu","22.04 LTS"),("","Node","20-alpine"),("","Python","3.12-slim"),("","JDK","21-eclipse")]),
          ("BUILD",C[1],[("","COPY","src→workdir"),("","RUN","apt/pip"),("","ARG","build-time var"),("","CACHE","layer reuse"),("","Multi-stage","slim final")]),
          ("CONFIGURE",C[2],[("","ENV","runtime vars"),("","WORKDIR","app dir"),("","USER","non-root"),("","VOLUME","mounts"),("","EXPOSE","port decl")]),
          ("RUNTIME",C[3],[("","CMD","default exec"),("","ENTRYPOINT","fixed cmd"),("","HEALTHCHECK","liveness"),("","LABEL","metadata"),("","STOPSIGNAL","graceful")])]
    for label,col,items in rows:
        s+=cheatrow(y,50,label,col,items,P,W); y+=56

    sv,cy,y=sec(P,y,W-P*2,24,"COMPOSE ESSENTIALS",C[4]); s+=sv
    for i,(t,sub) in enumerate([("services","container defs"),("networks","bridge/overlay"),("volumes","named/bind"),("env_file","secrets"),("depends_on","start order"),("healthcheck","readiness")]):
        s+=card_centered(P+4+i*142,cy,138,24,C[i%len(C)],t,sub)
    y+=GAP

    sv,cy,y=sec(P,y,W-P*2,46,"SECURITY HARDENING",C[5],"Distroless  |  Read-only FS  |  Non-root  |  Secrets  |  Scan  |  Sign"); s+=sv
    for i,(t,sub) in enumerate([("Distroless","min attack surface"),("Read-only FS","immutable"),("No root","USER 1001"),("Docker Secrets","injection"),("Trivy Scan","CVE scan"),("cosign+SBOM","sign+BOM")]):
        s+=card(P+4+i*142,cy,138,46,C[i%len(C)],t,sub)

    s+=status_bar(y+8,[("Image <50MB","#059669"),("0 CVE Critical","#059669"),("Non-root","#2563EB"),("SBOM","#7C3AED"),("Signed","#D97706")])
    return s,"DevOps Pipeline"


def make_git_workflow(C):
    s=""; y=68; P=18; W=900
    branches=[("main","protected","prod on tag",C[0]),("develop","integration","staging deploy",C[1]),
              ("feature/*","short-lived","PR to develop",C[2]),("release/*","RC freeze","QA only",C[3]),("hotfix/*","critical fix","main+develop",C[4])]
    sv,y=branch_columns(y,branches,P,W); s+=sv
    s+=status_bar(y+6,[("Signed commits","#059669"),("DCO required","#2563EB"),("Branch protect","#7C3AED"),("Linear history","#D97706"),("Tag on release","#059669")])
    y+=32

    sv,cy,y=sec(P,y,W-P*2,30,"CONVENTIONAL COMMITS",C[2],"feat | fix | docs | style | refactor | test | ci  →  type(scope): description"); s+=sv
    for i,(t,sub) in enumerate([("feat","new feature"),("fix","bug fix"),("docs","docs only"),("style","formatting"),("refactor","restructure"),("test","add tests"),("ci","CI config")]):
        s+=card(P+4+i*122,cy,118,30,C[i%len(C)],t,sub)
    y+=GAP

    sv,cy,y=sec(P,y,W-P*2,44,"PR + REVIEW WORKFLOW",C[3],"Branch  →  Commit  →  Push  →  PR  →  Review  →  Merge  →  Delete"); s+=sv
    for i,(t,sub) in enumerate([("Branch","from develop"),("Commit","conventional"),("Push","trigger CI"),("PR Open","auto-assign"),("Review","2 approvals"),("Merge","squash/rebase"),("Delete","clean branch")]):
        s+=card(P+4+i*122,cy,118,44,C[i%len(C)],t,sub)

    s+=status_bar(y+8,[("PR coverage","#059669"),("Avg review 4h","#2563EB"),("Pass rate 94%","#7C3AED"),("Commits signed","#059669"),("Releases tagged","#D97706")])
    return s,"DevOps Pipeline"


def make_api_design(C):
    s=""; y=68; P=18; W=900
    phases=[("REST","HTTP/JSON","CRUD resources"),("GraphQL","SDL schema","flex queries"),
            ("gRPC","Protobuf","streaming RPC"),("WebSocket","ws://","bi-directional"),("Webhooks","HTTP push","async notify"),
            ("SSE","server push","real-time feed"),("AsyncAPI","event-driven","message spec")]
    sv,y=pipeline_phases(y,phases,C,P,W); s+=sv
    s+=status_bar(y+6,[("Versioned","#059669"),("Rate Limited","#2563EB"),("Auth Required","#7C3AED"),("Documented","#D97706"),("Monitored","#059669")])
    y+=32

    sv,cy,y=sec(P,y,W-P*2,30,"SECURITY LAYER",C[2],"OAuth2/OIDC  |  API Keys  |  JWT  |  mTLS  |  Rate Limit  |  IP Allowlist"); s+=sv
    for i,(t,sub) in enumerate([("OAuth2/OIDC","delegated auth"),("API Keys","svc-to-svc"),("JWT","stateless"),("mTLS","mesh auth"),("Rate Limit","token bucket"),("IP Allowlist","network ACL")]):
        s+=card(P+4+i*142,cy,138,30,C[i%len(C)],t,sub)
    y+=GAP

    sv,cy,y=sec(P,y,W-P*2,30,"GATEWAY + OBSERVABILITY",C[3],"Circuit Break  |  Retry  |  Cache  |  Tracing  |  Error Budget  |  Alerting"); s+=sv
    for i,(t,sub) in enumerate([("Circuit Break","hystrix/resilience"),("Retry Logic","exp backoff"),("Caching","Redis+CDN"),("Dist. Tracing","Jaeger/Tempo"),("Error Budget","SLO-based"),("Alerting","PagerDuty")]):
        s+=card(P+4+i*142,cy,138,30,C[i%len(C)],t,sub)

    s+=status_bar(y+8,[("OpenAPI 3.1","#059669"),("Breaking 0","#059669"),("p95<200ms","#2563EB"),("Uptime 99.9%","#7C3AED"),("Auth 100%","#D97706")])
    return s,"System Architecture"


def make_solid(C):
    s=""; y=68; P=18; W=900
    principles=[("S","Single Responsibility","One class — one reason to change",C[0]),
                ("O","Open / Closed","Open for extension, closed for modification",C[1]),
                ("L","Liskov Substitution","Subtypes must be replaceable for base types",C[2]),
                ("I","Interface Segregation","Many small, focused interfaces over one fat",C[3]),
                ("D","Dependency Inversion","Depend on abstractions, not concretions",C[4])]
    ph=205; pw=(W-P*2-4*(len(principles)-1))//len(principles)
    for i,(letter,name,rule,col) in enumerate(principles):
        bx=P+i*(pw+4); bg=lighten(col,0.89)
        s+=f'<rect x="{bx+2}" y="{y+2}" width="{pw}" height="{ph}" rx="11" fill="rgba(0,0,0,0.05)"/>'
        s+=f'<rect x="{bx}" y="{y}" width="{pw}" height="{ph}" rx="11" fill="{bg}" stroke="{lighten(col,0.5)}" stroke-width="1.8" class="fadein" style="animation-delay:{i*0.1:.1f}s"/>'
        s+=f'<rect x="{bx}" y="{y}" width="{pw}" height="28" rx="11" fill="{col}"/>'
        s+=f'<rect x="{bx}" y="{y+20}" width="{pw}" height="8" fill="{col}"/>'
        s+=f'<text x="{bx+pw//2}" y="{y+18}" text-anchor="middle" fill="white" font-size="8.5" font-weight="800" font-family="Arial,sans-serif">{xe(clamp(name,pw//5))}</text>'
        s+=f'<text x="{bx+pw//2}" y="{y+80}" text-anchor="middle" fill="{col}" font-size="40" font-weight="900" font-family="Arial,sans-serif">{letter}</text>'
        lines=wrap_text(rule,max(10,(pw-4)//6))
        for j,ln in enumerate(lines[:4]):
            s+=f'<text x="{bx+pw//2}" y="{y+110+j*14}" text-anchor="middle" fill="#334155" font-size="8" font-family="Arial,sans-serif">{xe(ln)}</text>'
    y+=ph
    s+=status_bar(y+6,[("Cohesion UP","#059669"),("Coupling DOWN","#2563EB"),("Testable","#7C3AED"),("Extensible","#D97706"),("Readable","#059669")])
    y+=32

    sv,cy,y=sec(P,y,W-P*2,54,"DESIGN PATTERNS — APPLY WITH SOLID",C[2],"Creational  |  Structural  |  Behavioral"); s+=sv
    for i,(t,sub,col) in enumerate([("Factory","object creation",C[0]),("Strategy","swappable algo",C[1]),("Observer","event pub/sub",C[2]),("Decorator","wrap+extend",C[3]),("Repository","data access",C[4]),("Command","encapsulate act",C[5])]):
        s+=card(P+4+i*142,cy,138,54,col,t,sub)

    s+=status_bar(y+8,[("DRY","#059669"),("YAGNI","#2563EB"),("KISS","#7C3AED"),("Clean Code","#D97706"),("Test First","#059669")])
    return s,"System Architecture"


def make_generic(topic_name, C):
    s=""; y=68; P=18; W=900

    sv,cy,y=sec(P,y,W-P*2,38,"CORE ARCHITECTURE",C[0]); s+=sv
    words=topic_name.split()[:6]
    for i,w in enumerate(words):
        s+=card(P+4+i*142,cy,138,38,C[i%len(C)],w,"core component")
    s+=arrow_down(W//2,y+2,y+11,C[1]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,30,"KEY SERVICES",C[1],"API Layer  |  Business Logic  |  Data Access  |  Cache  |  Auth"); s+=sv
    for i,(t,sub) in enumerate([("API Layer","REST/GraphQL"),("Business Logic","core rules"),("Data Access","ORM+queries"),("Cache Layer","Redis/CDN"),("Auth Service","JWT/OAuth2")]):
        s+=card(P+4+i*170,cy,164,30,C[i%len(C)],t,sub)
    s+=arrow_down(W//2,y+2,y+11,C[2]); y+=GAP

    lw=426; rw=W-P*2-lw-14
    sv,cy,bot=two_col(y,lw,rw,64,"DATA + STORAGE",C[2],"INFRASTRUCTURE",C[3],"Primary DB | Cache | Search","Containers | CI/CD | CDN",P); s+=sv
    for i,(t,sub,col) in enumerate([("Primary DB","PostgreSQL",C[2]),("Cache","Redis",C[5]),("Object Store","S3/GCS",C[2]),("Search","Elasticsearch",C[0])]):
        s+=card(P+4+i*106,cy,102,64,col,t,sub)
    for i,(t,sub,col) in enumerate([("Containers","Docker/K8s",C[3]),("CI/CD","GitHub Actions",C[1]),("CDN","CloudFront",C[4]),("DNS","Route53",C[5])]):
        s+=card(P+lw+18+i*106,cy,102,64,col,t,sub)
    y=bot
    s+=arrow_down(W//2,y+2,y+11,C[4]); y+=GAP

    sv,cy,y=sec(P,y,W-P*2,32,"OBSERVABILITY + SECURITY",C[4],"Metrics  |  Logs  |  Traces  |  Alerts  |  Auth  |  Audit"); s+=sv
    for i,(t,sub) in enumerate([("Metrics","Prometheus"),("Logs","ELK/Loki"),("Traces","Jaeger"),("Alerts","PagerDuty"),("Auth","mTLS+OAuth2"),("Audit","CloudTrail")]):
        s+=card(P+4+i*142,cy,138,32,C[i%len(C)],t,sub)

    s+=status_bar(y+8,[("Scalable","#059669"),("Resilient","#2563EB"),("Secure","#7C3AED"),("Observable","#D97706"),("Cost-Opt","#059669")])
    return s,"System Architecture"


# ── DISPATCH ──────────────────────────────────────────────────────────────────
def make_diagram(topic_name, topic_id, diagram_type=""):
    C=get_pal(topic_id); now=datetime.now().strftime("%B %Y"); tid=topic_id.lower()
    if   "kube"   in tid:                         content,sub=make_kubernetes(C)
    elif any(x in tid for x in["llm","agent"]):   content,sub=make_llm(C)
    elif "cicd"   in tid:                         content,sub=make_cicd(C)
    elif "kafka"  in tid:                         content,sub=make_kafka(C)
    elif "zero"   in tid:                         content,sub=make_zero_trust(C)
    elif "aws"    in tid:                         content,sub=make_aws(C)
    elif "devsec" in tid:                         content,sub=make_devsecops(C)
    elif "system" in tid:                         content,sub=make_system_design(C)
    elif "mlops"  in tid:                         content,sub=make_mlops(C)
    elif any(x in tid for x in["lake","data"]):   content,sub=make_lakehouse(C)
    elif "rag"    in tid:                         content,sub=make_rag(C)
    elif "docker" in tid:                         content,sub=make_docker(C)
    elif "git"    in tid:                         content,sub=make_git_workflow(C)
    elif "api"    in tid:                         content,sub=make_api_design(C)
    elif "solid"  in tid:                         content,sub=make_solid(C)
    else:                                         content,sub=make_generic(topic_name,C)
    return wrap(content, topic_name, sub, C[0], now)


class DiagramGenerator:
    def __init__(self):
        Path(OUTPUT_DIR).mkdir(exist_ok=True)
        log.info("Diagram output dir: "+OUTPUT_DIR+"/")

    def save_svg(self,svg_content,topic_id,topic_name="",diagram_type="Architecture Diagram"):
        ts=datetime.now().strftime("%Y%m%d_%H%M%S"); filename=f"{OUTPUT_DIR}/{topic_id}_{ts}.svg"
        svg=make_diagram(topic_name or topic_id,topic_id,diagram_type)
        with open(filename,"w",encoding="utf-8") as f: f.write(svg)
        size_kb=os.path.getsize(filename)/1024
        log.info(f"Diagram saved: {filename} ({round(size_kb,1)} KB)")
        return filename