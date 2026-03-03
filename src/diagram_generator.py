import os
import re
from datetime import datetime
from pathlib import Path
from logger import get_logger

log = get_logger("diagrams")
OUTPUT_DIR = "diagrams"

def get_color(topic_id):
    tid = topic_id.lower()
    if any(x in tid for x in ["ai", "llm", "ml", "rag", "agent"]): return "#00D4AA"
    if any(x in tid for x in ["cloud", "aws", "kube", "docker", "cicd"]): return "#4ECDC4"
    if any(x in tid for x in ["security", "zero", "devsec"]): return "#FF6B6B"
    if any(x in tid for x in ["data", "kafka", "lake"]): return "#A29BFE"
    return "#FFE66D"

def sanitize_svg(svg):
    svg = re.sub(r'&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', svg)
    svg = svg.replace('\x00', '')
    return svg

def make_architecture_svg(topic_name, topic_id, color, now):
    tid = topic_id.lower()

    if "llm" in tid or "agent" in tid:
        layers = [
            ("User / Application", ["Chat UI", "API Client", "SDK"]),
            ("Orchestration Layer", ["LangChain / AutoGen", "Prompt Manager", "Memory Store"]),
            ("LLM Core", ["Transformer", "Attention", "Tokenizer"]),
            ("Infrastructure", ["GPU Cluster", "Vector DB", "Cache"]),
        ]
    elif "kube" in tid:
        layers = [
            ("Developer", ["kubectl", "Helm", "CI/CD"]),
            ("Control Plane", ["API Server", "Scheduler", "etcd"]),
            ("Worker Nodes", ["Pod", "Container", "Kubelet"]),
            ("Networking", ["Ingress", "Service", "DNS"]),
        ]
    elif "aws" in tid:
        layers = [
            ("Client", ["Browser", "Mobile App", "API Client"]),
            ("Edge", ["CloudFront CDN", "Route 53", "WAF"]),
            ("Compute", ["API Gateway", "Lambda", "ECS/EKS"]),
            ("Storage & DB", ["S3", "DynamoDB", "RDS"]),
        ]
    elif "rag" in tid:
        layers = [
            ("Ingestion", ["PDF/Docs", "Web Scraper", "DB Connector"]),
            ("Processing", ["Chunker", "Embedder", "Metadata"]),
            ("Storage", ["Vector DB", "Index", "Cache"]),
            ("Retrieval & Gen", ["Query Engine", "Re-ranker", "LLM"]),
        ]
    elif "kafka" in tid:
        layers = [
            ("Producers", ["App Server", "IoT Device", "DB CDC"]),
            ("Kafka Cluster", ["Broker 1", "Broker 2", "Broker 3"]),
            ("Stream Processing", ["Flink", "Spark", "KSQL"]),
            ("Consumers", ["Analytics", "Data Lake", "Alerts"]),
        ]
    elif "zero" in tid or "security" in tid:
        layers = [
            ("Identity", ["SSO/IdP", "MFA", "RBAC"]),
            ("Network", ["Microsegment", "Zero Trust Edge", "Firewall"]),
            ("Application", ["mTLS", "API Gateway", "WAF"]),
            ("Data", ["Encryption", "DLP", "Audit Logs"]),
        ]
    elif "data" in tid or "lake" in tid:
        layers = [
            ("Ingestion", ["Batch ETL", "Stream", "API"]),
            ("Storage", ["Raw Zone", "Curated Zone", "Delta Lake"]),
            ("Processing", ["Spark", "dbt", "Airflow"]),
            ("Consumption", ["BI Tools", "ML Platform", "API"]),
        ]
    else:
        layers = [
            ("Client Layer", ["Web App", "Mobile", "API Client"]),
            ("API Gateway", ["Load Balancer", "Auth", "Rate Limit"]),
            ("Service Layer", ["Service A", "Service B", "Service C"]),
            ("Data Layer", ["Primary DB", "Cache", "Queue"]),
        ]

    boxes = ""
    arrows = ""
    layer_y = [105, 205, 305, 405]

    for li, (layer_name, components) in enumerate(layers):
        y = layer_y[li]
        bg_opacity = "0.06" if li % 2 == 0 else "0.03"
        boxes += f'<rect x="20" y="{y-15}" width="860" height="70" rx="12" fill="white" opacity="{bg_opacity}"/>'
        boxes += f'<text x="35" y="{y+5}" fill="#475569" font-size="10" font-family="Arial,sans-serif" font-weight="bold">{layer_name.upper()}</text>'

        spacing = 220
        start_x = 450 - (len(components) - 1) * spacing // 2
        for ci, comp in enumerate(components):
            cx = start_x + ci * spacing
            boxes += f'<rect x="{cx-80}" y="{y+15}" width="160" height="36" rx="8" fill="{color}" opacity="0.18" stroke="{color}" stroke-width="1.5"/>'
            boxes += f'<text x="{cx}" y="{y+38}" text-anchor="middle" fill="{color}" font-size="12" font-weight="bold" font-family="Arial,sans-serif">{comp}</text>'

        if li < len(layers) - 1:
            next_y = layer_y[li + 1]
            arrows += f'<line x1="450" y1="{y+51}" x2="450" y2="{next_y-15}" stroke="{color}" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.5" marker-end="url(#arr)"/>'

    return boxes, arrows

def make_flow_svg(topic_name, topic_id, color, now):
    tid = topic_id.lower()

    if "cicd" in tid:
        steps = [("Code Push", "git push"), ("Lint & Test", "pytest / eslint"), ("Build", "docker build"), ("Scan", "trivy / snyk"), ("Deploy Staging", "helm upgrade"), ("Integration Tests", "selenium"), ("Deploy Prod", "blue/green")]
    elif "mlops" in tid:
        steps = [("Data Ingest", "collect & validate"), ("Feature Eng", "transform"), ("Train", "GPU cluster"), ("Evaluate", "metrics check"), ("Register", "model registry"), ("Deploy", "serve API"), ("Monitor", "drift detect")]
    elif "devsec" in tid:
        steps = [("Pre-commit", "secret scan"), ("SAST", "code analysis"), ("SCA", "dep check"), ("Build", "docker scan"), ("DAST", "runtime test"), ("Staging", "pen test"), ("Production", "monitor")]
    else:
        steps = [("Start", "trigger"), ("Plan", "design"), ("Build", "implement"), ("Test", "validate"), ("Review", "approve"), ("Deploy", "release"), ("Monitor", "observe")]

    boxes = ""
    arrows = ""
    total = len(steps)
    row1 = steps[:4]
    row2 = steps[4:]

    for i, (label, sub) in enumerate(row1):
        x = 100 + i * 195
        y = 200
        boxes += f'<rect x="{x-75}" y="{y-30}" width="150" height="60" rx="10" fill="{color}" opacity="0.15" stroke="{color}" stroke-width="1.5"/>'
        boxes += f'<text x="{x}" y="{y-5}" text-anchor="middle" fill="{color}" font-size="13" font-weight="bold" font-family="Arial,sans-serif">{label}</text>'
        boxes += f'<text x="{x}" y="{y+14}" text-anchor="middle" fill="#64748B" font-size="10" font-family="Arial,sans-serif">{sub}</text>'
        if i < len(row1) - 1:
            arrows += f'<line x1="{x+75}" y1="{y}" x2="{x+120}" y2="{y}" stroke="{color}" stroke-width="2" marker-end="url(#arr)"/>'

    if row2:
        x_end = 100 + (len(row1)-1) * 195
        arrows += f'<path d="M {x_end} 230 Q {x_end+50} 310 {x_end-len(row2)*195+195*len(row2)-100} 320" stroke="{color}" stroke-width="2" fill="none" stroke-dasharray="5,3" marker-end="url(#arr)" opacity="0.6"/>'

    for i, (label, sub) in enumerate(row2):
        x = 680 - i * 195
        y = 370
        boxes += f'<rect x="{x-75}" y="{y-30}" width="150" height="60" rx="10" fill="{color}" opacity="0.15" stroke="{color}" stroke-width="1.5"/>'
        boxes += f'<text x="{x}" y="{y-5}" text-anchor="middle" fill="{color}" font-size="13" font-weight="bold" font-family="Arial,sans-serif">{label}</text>'
        boxes += f'<text x="{x}" y="{y+14}" text-anchor="middle" fill="#64748B" font-size="10" font-family="Arial,sans-serif">{sub}</text>'
        if i < len(row2) - 1:
            arrows += f'<line x1="{x-75}" y1="{y}" x2="{x-120}" y2="{y}" stroke="{color}" stroke-width="2" marker-end="url(#arr)"/>'

    return boxes, arrows

def make_cheatsheet_svg(topic_name, topic_id, color, now):
    tid = topic_id.lower()

    if "docker" in tid:
        items = [
            ("Build", "docker build -t app:v1 .", "Build image from Dockerfile"),
            ("Run", "docker run -p 8080:80 app:v1", "Run container with port mapping"),
            ("Exec", "docker exec -it container sh", "Shell into running container"),
            ("Logs", "docker logs -f container", "Stream container logs"),
            ("Compose", "docker compose up -d", "Start all services"),
            ("Prune", "docker system prune -af", "Remove all unused resources"),
        ]
    elif "git" in tid:
        items = [
            ("Branch", "git checkout -b feature/xyz", "Create and switch to new branch"),
            ("Stash", "git stash push -m 'wip'", "Save uncommitted changes"),
            ("Rebase", "git rebase -i HEAD~3", "Interactive rebase last 3 commits"),
            ("Cherry", "git cherry-pick abc123", "Apply specific commit"),
            ("Reset", "git reset --hard HEAD~1", "Undo last commit (destructive)"),
            ("Reflog", "git reflog --oneline", "View all HEAD movements"),
        ]
    elif "solid" in tid:
        items = [
            ("S", "Single Responsibility", "One class = one reason to change"),
            ("O", "Open / Closed", "Open for extension, closed for modification"),
            ("L", "Liskov Substitution", "Subtypes must be substitutable"),
            ("I", "Interface Segregation", "Many specific interfaces > one general"),
            ("D", "Dependency Inversion", "Depend on abstractions, not concretions"),
            ("DRY", "Don't Repeat Yourself", "Every piece of knowledge has one place"),
        ]
    else:
        items = [
            ("Tip 1", "command --flag value", "Description of what this does"),
            ("Tip 2", "command --option", "Description of what this does"),
            ("Tip 3", "command -f file.txt", "Description of what this does"),
            ("Tip 4", "command | grep pattern", "Description of what this does"),
            ("Tip 5", "command --verbose --all", "Description of what this does"),
            ("Tip 6", "command -n 100 output", "Description of what this does"),
        ]

    boxes = ""
    for i, (label, cmd, desc) in enumerate(items):
        row = i % 3
        col = i // 3
        x = 50 + col * 430
        y = 140 + row * 120
        boxes += f'<rect x="{x}" y="{y}" width="400" height="95" rx="12" fill="white" opacity="0.04" stroke="{color}" stroke-width="1" stroke-opacity="0.3"/>'
        boxes += f'<rect x="{x}" y="{y}" width="80" height="95" rx="12" fill="{color}" opacity="0.2"/>'
        boxes += f'<text x="{x+40}" y="{y+52}" text-anchor="middle" fill="{color}" font-size="14" font-weight="bold" font-family="Arial,sans-serif">{label}</text>'
        boxes += f'<rect x="{x+95}" y="{y+15}" width="290" height="28" rx="6" fill="black" opacity="0.3"/>'
        cmd_display = cmd[:35] + ("..." if len(cmd) > 35 else "")
        boxes += f'<text x="{x+105}" y="{y+33}" fill="#00D4AA" font-size="11" font-family="Courier New,monospace">{cmd_display}</text>'
        boxes += f'<text x="{x+105}" y="{y+68}" fill="#94A3B8" font-size="11" font-family="Arial,sans-serif">{desc}</text>'

    return boxes, ""

def make_comparison_svg(topic_name, topic_id, color, now):
    tid = topic_id.lower()

    if "api" in tid:
        headers = ["Feature", "REST", "GraphQL", "gRPC"]
        rows = [
            ("Protocol", "HTTP/1.1", "HTTP/1.1", "HTTP/2"),
            ("Format", "JSON/XML", "JSON", "Protobuf"),
            ("Flexibility", "Fixed endpoints", "Query what you need", "Strict schema"),
            ("Performance", "Good", "Good", "Excellent"),
            ("Best For", "Public APIs", "Complex queries", "Microservices"),
            ("Learning Curve", "Low", "Medium", "High"),
        ]
        col_colors = ["#475569", "#00D4AA", "#A29BFE", "#FF6B6B"]
    else:
        headers = ["Feature", "Option A", "Option B", "Option C"]
        rows = [
            ("Performance", "High", "Medium", "Low"),
            ("Scalability", "Auto-scale", "Manual", "Semi-auto"),
            ("Cost", "$$$", "$$", "$"),
            ("Complexity", "Low", "High", "Medium"),
            ("Community", "Large", "Growing", "Small"),
            ("Best For", "Enterprise", "Startups", "Hobbyists"),
        ]
        col_colors = ["#475569", "#00D4AA", "#A29BFE", "#FF6B6B"]

    boxes = ""
    col_w = 195
    start_x = 65

    for j, (h, c) in enumerate(zip(headers, col_colors)):
        x = start_x + j * col_w
        boxes += f'<rect x="{x}" y="110" width="{col_w-10}" height="42" rx="8" fill="{c}" opacity="0.25"/>'
        boxes += f'<text x="{x + (col_w-10)//2}" y="136" text-anchor="middle" fill="{c}" font-size="13" font-weight="bold" font-family="Arial,sans-serif">{h}</text>'

    for i, row in enumerate(rows):
        y = 165 + i * 52
        bg = "0.05" if i % 2 == 0 else "0.02"
        boxes += f'<rect x="{start_x}" y="{y}" width="{col_w*4-10}" height="46" rx="6" fill="white" opacity="{bg}"/>'
        for j, (val, c) in enumerate(zip(row, col_colors)):
            x = start_x + j * col_w
            fill = "#94A3B8" if j == 0 else "#E2E8F0"
            fw = "bold" if j == 0 else "normal"
            boxes += f'<text x="{x + (col_w-10)//2}" y="{y+28}" text-anchor="middle" fill="{fill}" font-size="12" font-weight="{fw}" font-family="Arial,sans-serif">{val}</text>'

    return boxes, ""

def make_fallback_svg(topic_name, topic_id, diagram_type):
    color = get_color(topic_id)
    now = datetime.now().strftime("%B %Y")
    dt = diagram_type.lower()

    if "flow" in dt:
        boxes, arrows = make_flow_svg(topic_name, topic_id, color, now)
        subtitle = "Process Flow"
    elif "cheat" in dt or "command" in dt:
        boxes, arrows = make_cheatsheet_svg(topic_name, topic_id, color, now)
        subtitle = "Quick Reference"
    elif "comparison" in dt or "table" in dt:
        boxes, arrows = make_comparison_svg(topic_name, topic_id, color, now)
        subtitle = "Comparison Guide"
    else:
        boxes, arrows = make_architecture_svg(topic_name, topic_id, color, now)
        subtitle = "Architecture Overview"

    safe_name = topic_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 550" width="900" height="550">
  <defs>
    <marker id="arr" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
      <path d="M0,0 L0,6 L9,3 z" fill="{color}"/>
    </marker>
    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="white" stroke-width="0.3" opacity="0.1"/>
    </pattern>
    <linearGradient id="topbar" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0%" stop-color="{color}" stop-opacity="1"/>
      <stop offset="100%" stop-color="{color}" stop-opacity="0.3"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="900" height="550" fill="#0A0F1E"/>
  <rect width="900" height="550" fill="url(#grid)"/>

  <!-- Top accent bar -->
  <rect x="0" y="0" width="900" height="5" fill="url(#topbar)"/>

  <!-- Corner decoration -->
  <circle cx="870" cy="50" r="60" fill="{color}" opacity="0.04"/>
  <circle cx="30" cy="500" r="40" fill="{color}" opacity="0.04"/>

  <!-- Header -->
  <text x="40" y="42" fill="{color}" font-size="11" font-weight="bold" font-family="Arial,sans-serif" opacity="0.7">{subtitle.upper()}</text>
  <text x="450" y="75" text-anchor="middle" fill="white" font-size="22" font-weight="bold" font-family="Arial,sans-serif">{safe_name}</text>
  <line x1="40" y1="88" x2="860" y2="88" stroke="{color}" stroke-width="0.5" opacity="0.3"/>

  <!-- Diagram content -->
  {arrows}
  {boxes}

  <!-- Footer -->
  <line x1="40" y1="518" x2="860" y2="518" stroke="{color}" stroke-width="0.5" opacity="0.2"/>
  <text x="40" y="537" fill="#334155" font-size="10" font-family="Arial,sans-serif">{now}</text>
  <!-- AI-themed signature -->
  <defs>
    <linearGradient id="siggrad" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0%" stop-color="#00D4AA"/>
      <stop offset="50%" stop-color="#A29BFE"/>
      <stop offset="100%" stop-color="#FF6B6B"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <rect x="680" y="520" width="200" height="24" rx="12" fill="url(#siggrad)" opacity="0.15"/>
  <rect x="681" y="521" width="198" height="22" rx="11" fill="none" stroke="url(#siggrad)" stroke-width="0.8" opacity="0.6"/>
  <text x="688" y="536" fill="#A29BFE" font-size="10" font-family="Arial,sans-serif" filter="url(#glow)">✦ AI</text>
  <text x="718" y="537" fill="white" font-size="12" font-weight="bold" font-family="Arial,sans-serif" filter="url(#glow)" letter-spacing="1">© Komal Batra</text>
</svg>'''
    return svg


class DiagramGenerator:
    def __init__(self):
        Path(OUTPUT_DIR).mkdir(exist_ok=True)
        log.info("Diagram output directory: " + OUTPUT_DIR + "/")

    def save_svg(self, svg_content, topic_id, topic_name="", diagram_type="Architecture Diagram"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = OUTPUT_DIR + "/" + topic_id + "_" + timestamp + ".svg"

        # Try sanitizing AI SVG first
        try:
            clean_svg = sanitize_svg(svg_content)
            if "<svg" in clean_svg and "</svg>" in clean_svg and len(clean_svg) > 500:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(clean_svg)
                size_kb = os.path.getsize(filename) / 1024
                log.info("AI diagram saved: " + filename + " (" + str(round(size_kb, 1)) + " KB)")
                return filename
        except Exception as e:
            log.warning("AI SVG failed: " + str(e) + " — using fallback")

        # Always-valid fallback
        log.info("Using fallback diagram for: " + topic_id)
        fallback = make_fallback_svg(topic_name or topic_id, topic_id, diagram_type)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(fallback)
        size_kb = os.path.getsize(filename) / 1024
        log.info("Fallback diagram saved: " + filename + " (" + str(round(size_kb, 1)) + " KB)")
        return filename
