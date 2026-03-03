import os
import re
from datetime import datetime
from pathlib import Path
from logger import get_logger

log = get_logger("diagrams")
OUTPUT_DIR = "diagrams"

TOPIC_COLORS = {
    "ai": "#00D4AA", "llm": "#00D4AA", "ml": "#00D4AA",
    "cloud": "#4ECDC4", "aws": "#4ECDC4", "kubernetes": "#4ECDC4", "docker": "#4ECDC4",
    "security": "#FF6B6B", "zero": "#FF6B6B", "devsecops": "#FF6B6B",
    "data": "#A29BFE", "kafka": "#A29BFE",
    "engineering": "#FFE66D", "solid": "#FFE66D", "api": "#FFE66D", "git": "#FFE66D",
}

def get_color(topic_id):
    for key, color in TOPIC_COLORS.items():
        if key in topic_id.lower():
            return color
    return "#00D4AA"

def sanitize_svg(svg):
    """Fix common XML entity issues in AI-generated SVGs."""
    # Replace bare & not already part of an entity
    svg = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#)', '&amp;', svg)
    # Remove any null bytes or invalid chars
    svg = svg.replace('\x00', '')
    return svg

def make_fallback_svg(topic_name, topic_id, diagram_type):
    """Generate a clean, always-valid SVG diagram programmatically."""
    color = get_color(topic_id)
    now = datetime.now().strftime("%B %Y")

    # Build boxes based on diagram type
    if "flow" in diagram_type.lower():
        boxes = [
            ("Start", 120), ("Plan", 240), ("Build", 360),
            ("Test", 480), ("Deploy", 600), ("Monitor", 720),
        ]
        shapes = ""
        for i, (label, x) in enumerate(boxes):
            shapes += f'<rect x="{x-50}" y="220" width="100" height="50" rx="8" fill="{color}" opacity="0.15" stroke="{color}" stroke-width="1.5"/>'
            shapes += f'<text x="{x}" y="250" text-anchor="middle" fill="{color}" font-size="13" font-weight="bold">{label}</text>'
            if i < len(boxes) - 1:
                shapes += f'<line x1="{x+50}" y1="245" x2="{x+70}" y2="245" stroke="{color}" stroke-width="1.5" marker-end="url(#arrow)"/>'

    elif "cheat" in diagram_type.lower() or "command" in diagram_type.lower():
        commands = [
            ("Setup", "Initialize and configure environment"),
            ("Build", "Compile and package application"),
            ("Test", "Run unit and integration tests"),
            ("Deploy", "Push to staging or production"),
            ("Monitor", "Check logs and metrics"),
            ("Rollback", "Revert to previous version"),
        ]
        shapes = ""
        for i, (cmd, desc) in enumerate(commands):
            row = i % 3
            col = i // 3
            x = 120 + col * 340
            y = 160 + row * 110
            shapes += f'<rect x="{x-90}" y="{y-30}" width="260" height="70" rx="10" fill="{color}" opacity="0.1" stroke="{color}" stroke-width="1"/>'
            shapes += f'<rect x="{x-90}" y="{y-30}" width="80" height="70" rx="10" fill="{color}" opacity="0.3"/>'
            shapes += f'<text x="{x-50}" y="{y+10}" text-anchor="middle" fill="{color}" font-size="13" font-weight="bold">{cmd}</text>'
            shapes += f'<text x="{x+50}" y="{y+5}" text-anchor="middle" fill="#94A3B8" font-size="11">{desc}</text>'

    elif "comparison" in diagram_type.lower():
        headers = ["Feature", "Option A", "Option B", "Option C"]
        rows = ["Performance", "Scalability", "Cost", "Complexity", "Community"]
        vals = [["High", "Medium", "Low"], ["Auto", "Manual", "Semi"],
                ["$$$", "$$", "$"], ["Low", "High", "Medium"], ["Large", "Growing", "Small"]]
        shapes = ""
        col_w = 160
        for j, h in enumerate(headers):
            x = 80 + j * col_w
            shapes += f'<rect x="{x-70}" y="130" width="{col_w-10}" height="36" rx="6" fill="{color}" opacity="0.25"/>'
            shapes += f'<text x="{x}" y="153" text-anchor="middle" fill="{color}" font-size="13" font-weight="bold">{h}</text>'
        for i, row in enumerate(rows):
            y = 185 + i * 46
            bg = "0.06" if i % 2 == 0 else "0.03"
            shapes += f'<rect x="10" y="{y-18}" width="870" height="40" rx="4" fill="white" opacity="{bg}"/>'
            shapes += f'<text x="80" y="{y+8}" text-anchor="middle" fill="#94A3B8" font-size="12">{row}</text>'
            for j, val in enumerate(vals[i]):
                x = 80 + (j+1) * col_w
                shapes += f'<text x="{x}" y="{y+8}" text-anchor="middle" fill="#E2E8F0" font-size="12">{val}</text>'
    else:
        # Default: Architecture diagram with boxes and connections
        layers = [
            ("Client Layer", ["Web App", "Mobile", "API Client"], 100),
            ("API Gateway", ["Load Balancer", "Auth", "Rate Limit"], 220),
            ("Service Layer", ["Service A", "Service B", "Service C"], 340),
            ("Data Layer", ["Primary DB", "Cache", "Queue"], 460),
        ]
        shapes = ""
        for layer_name, components, y in layers:
            shapes += f'<rect x="20" y="{y-25}" width="860" height="80" rx="10" fill="white" opacity="0.03"/>'
            shapes += f'<text x="30" y="{y}" fill="#475569" font-size="11">{layer_name}</text>'
            spacing = 860 // (len(components) + 1)
            for i, comp in enumerate(components):
                x = spacing * (i + 1)
                shapes += f'<rect x="{x-70}" y="{y}" width="140" height="40" rx="8" fill="{color}" opacity="0.15" stroke="{color}" stroke-width="1"/>'
                shapes += f'<text x="{x}" y="{y+25}" text-anchor="middle" fill="{color}" font-size="12" font-weight="bold">{comp}</text>'
            if y < 460:
                shapes += f'<line x1="450" y1="{y+55}" x2="450" y2="{y+80}" stroke="{color}" stroke-width="1" stroke-dasharray="4,2" opacity="0.4"/>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 550" width="900" height="550">
  <defs>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="{color}"/>
    </marker>
    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="white" stroke-width="0.3" opacity="0.15"/>
    </pattern>
  </defs>
  <rect width="900" height="550" fill="#0A0F1E"/>
  <rect width="900" height="550" fill="url(#grid)"/>
  <rect x="0" y="0" width="900" height="4" fill="{color}"/>
  <text x="450" y="55" text-anchor="middle" fill="white" font-size="22" font-weight="bold" font-family="Arial, sans-serif">{topic_name}</text>
  <text x="450" y="80" text-anchor="middle" fill="#475569" font-size="13" font-family="Arial, sans-serif">{diagram_type} · {now}</text>
  <line x1="50" y1="95" x2="850" y2="95" stroke="{color}" stroke-width="0.5" opacity="0.4"/>
  {shapes}
  <text x="880" y="540" text-anchor="end" fill="#475569" font-size="11" font-family="Arial, sans-serif">© Komal Batra</text>
</svg>'''
    return svg


class DiagramGenerator:
    def __init__(self):
        Path(OUTPUT_DIR).mkdir(exist_ok=True)
        log.info("Diagram output directory: " + OUTPUT_DIR + "/")

    def save_svg(self, svg_content, topic_id, topic_name="", diagram_type="Architecture Diagram"):
        """Save SVG — sanitize AI output, fall back to clean diagram if broken."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = OUTPUT_DIR + "/" + topic_id + "_" + timestamp + ".svg"

        # Try sanitizing AI-generated SVG first
        try:
            clean_svg = sanitize_svg(svg_content)
            # Quick validity check
            if "<svg" in clean_svg and "</svg>" in clean_svg and len(clean_svg) > 200:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(clean_svg)
                size_kb = os.path.getsize(filename) / 1024
                log.info("Diagram saved: " + filename + " (" + str(round(size_kb, 1)) + " KB)")
                return filename
        except Exception as e:
            log.warning("AI SVG sanitize failed: " + str(e) + " — using fallback")

        # Fallback: generate clean diagram programmatically
        log.info("Generating fallback diagram for: " + topic_id)
        fallback_svg = make_fallback_svg(topic_name or topic_id, topic_id, diagram_type)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(fallback_svg)
        size_kb = os.path.getsize(filename) / 1024
        log.info("Fallback diagram saved: " + filename + " (" + str(round(size_kb, 1)) + " KB)")
        return filename
