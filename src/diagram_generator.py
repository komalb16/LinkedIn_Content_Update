import os
from datetime import datetime
from pathlib import Path
from logger import get_logger

log = get_logger("diagrams")
OUTPUT_DIR = "diagrams"

# ── DARK THEME (matches Image 2 style) ───────────────────────────────────────
PALETTES = {
    "ai":       ["#A78BFA","#60A5FA","#34D399","#FB923C","#F472B6","#38BDF8"],
    "cloud":    ["#60A5FA","#38BDF8","#34D399","#A78BFA","#FB923C","#F472B6"],
    "security": ["#F87171","#FB923C","#A78BFA","#60A5FA","#34D399","#F472B6"],
    "data":     ["#34D399","#A78BFA","#60A5FA","#38BDF8","#FB923C","#F87171"],
    "devops":   ["#34D399","#60A5FA","#A78BFA","#FB923C","#F87171","#38BDF8"],
    "default":  ["#60A5FA","#A78BFA","#34D399","#FB923C","#F87171","#38BDF8"],
}

BG        = "#0D1117"
BG2       = "#161B22"
BG3       = "#1C2128"
BORDER    = "#21262D"
BORDER2   = "#30363D"
TEXT_MAIN = "#E6EDF3"
TEXT_MID  = "#8B949E"
TEXT_LITE = "#484F58"

def get_pal(tid):
    t = tid.lower()
    if any(x in t for x in ["llm","rag","agent","mlops"]): return PALETTES["ai"]
    if any(x in t for x in ["kube","docker","aws","cicd"]): return PALETTES["cloud"]
    if any(x in t for x in ["zero","devsec"]):              return PALETTES["security"]
    if any(x in t for x in ["kafka","data","lake"]):        return PALETTES["data"]
    if any(x in t for x in ["git","devops","solid","api"]): return PALETTES["devops"]
    return PALETTES["default"]

def clamp(text, n):
    text = str(text)
    return text if len(text) <= n else text[:n-1] + "…"

def x(t):
    return str(t).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

# ── PRIMITIVES ────────────────────────────────────────────────────────────────

def section(sx, sy, sw, sh, title, color, dashed=False):
    """Dark section box with colored dashed border + floating pill label."""
    dash = 'stroke-dasharray="6,3"' if dashed else ''
    lw   = min(len(title)*7 + 24, sw - 40)
    s    = f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="10" fill="{BG2}" stroke="{color}" stroke-width="1.8" {dash} opacity="0.95"/>'
    s   += f'<rect x="{sx+14}" y="{sy-11}" width="{lw}" height="22" rx="11" fill="{color}"/>'
    s   += f'<text x="{sx+14+lw//2}" y="{sy+5}" text-anchor="middle" fill="white" font-size="10" font-weight="700" font-family="Arial,sans-serif" letter-spacing="0.8">{x(clamp(title, lw//6+2))}</text>'
    return s

def card(cx, cy, cw, ch, color, title, sub="", rx=8):
    """Dark card — colored border, title in accent color, sub in muted."""
    s  = f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" rx="{rx}" fill="{BG3}" stroke="{color}" stroke-width="1.5"/>'
    iw = cw - 12
    mid = cy + ch // 2
    tf = min(11, max(7, iw // 7))
    sf = min(9, max(6, iw // 9))
    t  = x(clamp(title, max(3, iw // max(1, tf-2))))
    if sub:
        sv = x(clamp(sub, max(3, iw // max(1, sf-2))))
        s += f'<text x="{cx+cw//2}" y="{mid-3}" text-anchor="middle" fill="{color}" font-size="{tf}" font-weight="700" font-family="Arial,sans-serif">{t}</text>'
        s += f'<text x="{cx+cw//2}" y="{mid+11}" text-anchor="middle" fill="{TEXT_MID}" font-size="{sf}" font-family="Arial,sans-serif">{sv}</text>'
    else:
        s += f'<text x="{cx+cw//2}" y="{mid+4}" text-anchor="middle" fill="{color}" font-size="{tf}" font-weight="700" font-family="Arial,sans-serif">{t}</text>'
    return s

def flow_box(fx, fy, fw, fh, ico, title, sub, color):
    """Icon + label flow cell — emoji skipped, title+sub shown reliably."""
    s  = f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" rx="8" fill="{color}18" stroke="{color}" stroke-width="1.5"/>'
    iw = fw - 10
    mid = fy + fh // 2
    tf  = min(10, max(7, iw//7))
    sf  = min(8,  max(6, iw//9))
    if sub:
        s += f'<text x="{fx+fw//2}" y="{mid-4}" text-anchor="middle" fill="{color}" font-size="{tf}" font-weight="700" font-family="Arial,sans-serif">{x(clamp(title,iw//5))}</text>'
        s += f'<text x="{fx+fw//2}" y="{mid+11}" text-anchor="middle" fill="{TEXT_MID}" font-size="{sf}" font-family="Arial,sans-serif">{x(clamp(sub,iw//4))}</text>'
    else:
        s += f'<text x="{fx+fw//2}" y="{mid+4}" text-anchor="middle" fill="{color}" font-size="{tf}" font-weight="700" font-family="Arial,sans-serif">{x(clamp(title,iw//5))}</text>'
    return s

def arrow_down(ax, ay1, ay2, color):
    return (f'<line x1="{ax}" y1="{ay1}" x2="{ax}" y2="{ay2-8}" stroke="{color}" stroke-width="2" opacity="0.7"/>'
            f'<polygon points="{ax-5},{ay2-8} {ax+5},{ay2-8} {ax},{ay2}" fill="{color}" opacity="0.8"/>')

def arrow_right(ax1, ax2, acy, color):
    return (f'<line x1="{ax1}" y1="{acy}" x2="{ax2-8}" y2="{acy}" stroke="{color}" stroke-width="1.8" opacity="0.7"/>'
            f'<polygon points="{ax2-8},{acy-4} {ax2},{acy} {ax2-8},{acy+4}" fill="{color}" opacity="0.8"/>')

def tool_strip(ty, tools, color):
    """Tool strip — emoji replaced with colored text pills (safe for all SVG renderers)."""
    n  = len(tools)
    tw = 870 // n
    s  = f'<rect x="15" y="{ty}" width="870" height="26" rx="6" fill="{color}18" stroke="{color}50" stroke-width="1"/>'
    for i, (ico, name) in enumerate(tools):
        cx = 15 + i*tw + tw//2
        # Skip emoji, show only the name centered — cleaner and reliable
        fs = min(10, max(7, tw//9))
        s += f'<text x="{cx}" y="{ty+17}" text-anchor="middle" fill="{color}" font-size="{fs}" font-weight="700" font-family="Arial,sans-serif" letter-spacing="0.3">{x(clamp(name,tw//5))}</text>'
        if i < n-1:
            lx = 15+(i+1)*tw
            s += f'<line x1="{lx}" y1="{ty+4}" x2="{lx}" y2="{ty+22}" stroke="{BORDER2}" stroke-width="1"/>'
    return s

def status_row(ry, items):
    n  = len(items)
    iw = 870 // n
    s  = f'<rect x="15" y="{ry}" width="870" height="20" rx="10" fill="{BG3}" stroke="{BORDER2}" stroke-width="1"/>'
    for i, (label, color) in enumerate(items):
        cx = 15 + i*iw + iw//2
        lx = cx - len(label)*3 - 7
        s += f'<circle cx="{lx}" cy="{ry+10}" r="3.5" fill="{color}"/>'
        s += f'<text x="{lx+7}" y="{ry+14}" fill="{TEXT_MID}" font-size="{min(9,max(6,iw//10))}" font-weight="600" font-family="Arial,sans-serif">{x(label)}</text>'
    return s

def two_col(tx, ty, tw2, th, lbl1, col1, lbl2, col2, split=0.5):
    w1, w2 = int(tw2*split), tw2-int(tw2*split)
    s  = f'<rect x="{tx}" y="{ty}" width="{tw2}" height="{th}" rx="10" fill="{BG2}" stroke="{BORDER2}" stroke-width="1" stroke-dasharray="5,3"/>'
    lw1 = min(len(lbl1)*7+20, w1-20); lw2 = min(len(lbl2)*7+20, w2-20)
    s += f'<rect x="{tx+10}" y="{ty-10}" width="{lw1}" height="20" rx="10" fill="{col1}"/>'
    s += f'<text x="{tx+10+lw1//2}" y="{ty+4}" text-anchor="middle" fill="white" font-size="9" font-weight="700" font-family="Arial,sans-serif">{x(clamp(lbl1,lw1//6+2))}</text>'
    rx2 = tx+w1+10
    s += f'<rect x="{rx2}" y="{ty-10}" width="{lw2}" height="20" rx="10" fill="{col2}"/>'
    s += f'<text x="{rx2+lw2//2}" y="{ty+4}" text-anchor="middle" fill="white" font-size="9" font-weight="700" font-family="Arial,sans-serif">{x(clamp(lbl2,lw2//6+2))}</text>'
    s += f'<line x1="{tx+w1}" y1="{ty+12}" x2="{tx+w1}" y2="{ty+th-12}" stroke="{BORDER2}" stroke-width="1" stroke-dasharray="4,3"/>'
    return s

def cheatrow(ry, rh, label, color, items):
    lw = max(80, len(label)*8+16)
    s  = f'<rect x="15" y="{ry}" width="870" height="{rh}" rx="7" fill="{BG3}" stroke="{BORDER2}" stroke-width="1"/>'
    s += f'<rect x="15" y="{ry}" width="{lw}" height="{rh}" rx="7" fill="{color}28" stroke="{color}" stroke-width="1"/>'
    s += f'<rect x="{15+lw-7}" y="{ry}" width="7" height="{rh}" fill="{color}28"/>'
    s += f'<text x="{15+lw//2}" y="{ry+rh//2+4}" text-anchor="middle" fill="{color}" font-size="{min(10,max(7,lw//9))}" font-weight="700" font-family="Arial,sans-serif">{x(clamp(label,lw//6))}</text>'
    gx = 15+lw+6; avail = 880-gx; n = len(items); cw = max(50, avail//n-4)
    for i, item in enumerate(items):
        ico = item[0] if len(item)>0 else ""; title2 = item[1] if len(item)>1 else ""; sub = item[2] if len(item)>2 else ""
        cx2 = gx+i*(cw+4)
        s += f'<rect x="{cx2}" y="{ry+3}" width="{cw}" height="{rh-6}" rx="6" fill="{color}15" stroke="{color}40" stroke-width="1"/>'
        s += f'<text x="{cx2+cw//2}" y="{ry+rh//2+4}" text-anchor="middle" fill="{color}" font-size="{min(9,max(6,cw//8))}" font-weight="700" font-family="Arial,sans-serif">{x(clamp(title2,cw//5))}</text>'
        if sub and rh>=56: s += f'<text x="{cx2+cw//2}" y="{ry+rh-8}" text-anchor="middle" fill="{TEXT_MID}" font-size="{min(8,max(6,cw//9))}" font-family="Arial,sans-serif">{x(clamp(sub,cw//4))}</text>'
    return s

# ── WRAPPER ───────────────────────────────────────────────────────────────────
def wrap(content, title, subtitle, color, date_str):
    st = x(clamp(title.replace("&","and"), 52))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 580" width="900" height="580" style="overflow:hidden;display:block">
  <defs>
    <linearGradient id="hg" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0%" stop-color="{color}"/>
      <stop offset="100%" stop-color="{color}55"/>
    </linearGradient>
  </defs>
  <rect width="900" height="580" fill="{BG}"/>
  <!-- subtle grid -->
  <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
    <path d="M 30 0 L 0 0 0 30" fill="none" stroke="{BORDER}" stroke-width="0.5" opacity="0.5"/>
  </pattern>
  <rect width="900" height="580" fill="url(#grid)"/>
  <!-- header -->
  <rect x="0" y="0" width="900" height="60" fill="url(#hg)"/>
  <rect x="0" y="58" width="900" height="2" fill="{color}" opacity="0.5"/>
  <!-- category pill -->
  <rect x="15" y="14" width="{len(subtitle)*7+24}" height="18" rx="9" fill="rgba(255,255,255,0.15)" stroke="rgba(255,255,255,0.3)" stroke-width="1"/>
  <text x="27" y="26" fill="white" font-size="9" font-weight="700" font-family="Arial,sans-serif" letter-spacing="1.5">{x(subtitle.upper())}</text>
  <!-- title -->
  <text x="450" y="40" text-anchor="middle" fill="white" font-size="20" font-weight="800" font-family="Arial,sans-serif" letter-spacing="-0.5">{st}</text>
  <!-- content -->
  {content}
  <!-- footer -->
  <rect x="0" y="546" width="900" height="34" fill="{BG2}"/>
  <rect x="0" y="546" width="900" height="1" fill="{color}" opacity="0.4"/>
  <text x="20" y="568" fill="{TEXT_MID}" font-size="9" font-family="Arial,sans-serif">{x(date_str)}</text>
  <rect x="580" y="551" width="305" height="22" rx="11" fill="{color}" opacity="0.2"/>
  <rect x="580" y="551" width="305" height="22" rx="11" fill="none" stroke="{color}" stroke-width="1.5"/>
  <text x="732" y="566" text-anchor="middle" fill="white" font-size="11" font-weight="800" font-family="Arial,sans-serif" letter-spacing="1">AI (c) Komal Batra</text>
</svg>'''


# ── DIAGRAM FUNCTIONS ─────────────────────────────────────────────────────────

def make_system_design(C):
    s = tool_strip(70, [("","React/Next"),("","Nginx/ALB"),("","OAuth2"),("","K8s"),("","PostgreSQL"),("","Redis"),("","Grafana")], C[0])
    s += section(15, 98, 870, 46, "CLIENT LAYER", C[0])
    for i,t in enumerate(["Browser","Mobile","Desktop","3rd Party","IoT"]):
        cx = 15+i*174+87
        s += f'<text x="{cx}" y="{126}" text-anchor="middle" fill="{C[0]}" font-size="10" font-weight="700" font-family="Arial,sans-serif">{t}</text>'
    s += arrow_down(450, 144, 158, C[1])
    s += section(15, 168, 870, 40, "EDGE + AUTH", C[1])
    for i,(t,sub) in enumerate([("CDN","CloudFront"),("Load Balancer","layer-7"),("API Gateway","rate limit"),("Auth Service","OAuth2/JWT"),("WAF","L7 protect")]):
        s += card(22+i*172, 182, 164, 20, C[i%len(C)], t, sub)
    s += arrow_down(450, 208, 222, C[2])
    s += section(15, 232, 870, 64, "MICROSERVICES", C[2])
    for i,(t,sub) in enumerate([("User Svc","auth/profile"),("Order Svc","cart/checkout"),("Payment","Stripe/PCI"),("Notification","email/SMS"),("Search","Elasticsearch"),("Recommend","ML-powered"),("Analytics","events")]):
        s += card(20+i*124, 252, 118, 38, C[i%len(C)], t, sub)
    s += arrow_down(450, 296, 310, C[3])
    s += section(15, 320, 870, 40, "MESSAGE BROKER", C[3])
    for i,(t,sub) in enumerate([("Kafka","event stream"),("RabbitMQ","task queues"),("Redis PubSub","real-time"),("Dead Letter Q","failed msgs"),("EventBridge","event bus")]):
        s += card(22+i*172, 334, 164, 20, C[i%len(C)], t, sub)
    s += arrow_down(450, 360, 374, C[4])
    s += section(15, 384, 870, 58, "DATA LAYER", C[4])
    for i,(t,sub) in enumerate([("PostgreSQL","OLTP"),("Redis","cache"),("MongoDB","documents"),("S3","blobs"),("Elasticsearch","search"),("ClickHouse","analytics")]):
        s += card(22+i*143, 402, 137, 34, C[i%len(C)], t, sub)
    s += status_row(454, [("Load Balanced","#34D399"),("Auth Active","#A78BFA"),("Events flowing","#60A5FA"),("DB healthy","#34D399"),("Cache hit 94%","#FB923C")])
    return s, "System Architecture"

def make_lakehouse(C):
    s = tool_strip(70, [("","Spark"),("","Delta Lake"),("","Iceberg"),("","Flink"),("","dbt"),("","Trino"),("","Hive")], C[0])
    s += section(15, 98, 870, 64, "INGESTION", C[0])
    srcs=[("","Batch ETL","Airflow/Glue"),("","Streaming","Kafka/Kinesis"),("","CDC","Debezium"),
          ("","API Pull","REST/GraphQL"),("","File Drop","S3 trigger"),("","IoT","MQTT bridge"),("","App Events","SDK capture")]
    sw = 860 // len(srcs)
    for i,(ico,t,sub) in enumerate(srcs):
        s += flow_box(20+i*sw, 110, sw-4, 46, ico, t, sub, C[i%len(C)])
    s += arrow_down(450, 162, 176, C[1])
    s += section(15, 186, 870, 64, "OPEN TABLE FORMAT LAYER", C[1], dashed=True)
    for i,(t,sub) in enumerate([("Delta Lake","ACID + time travel"),("Apache Iceberg","schema evolution"),("Apache Hudi","upserts/deletes"),("Metadata Catalog","Glue/Hive Metastore")]):
        s += card(22+i*214, 208, 206, 36, C[i%len(C)], t, sub)
    s += arrow_down(450, 250, 264, C[2])
    s += section(15, 274, 870, 58, "COMPUTE ENGINE", C[2])
    for i,(t,sub) in enumerate([("Apache Spark","SQL/ML/streaming"),("Trino/Presto","interactive SQL"),("dbt","transform/test"),("Ray","ML distributed"),("Flink","stream proc")]):
        s += card(22+i*172, 292, 164, 34, C[i%len(C)], t, sub)
    s += arrow_down(450, 332, 346, C[3])
    s += section(15, 356, 870, 88, "CONSUMPTION LAYER", C[3], dashed=True)
    for i,(t,sub,col) in enumerate([("BI Tools","Tableau/Superset",C[3]),("ML Platform","SageMaker/Vertex",C[4]),
                                     ("Ad-hoc SQL","Athena/BigQuery",C[5]),("Dashboards","Grafana/Looker",C[0]),
                                     ("Data APIs","REST/GraphQL",C[1]),("Streaming","real-time feeds",C[2])]):
        s += card(20+i*144, 376, 138, 62, col, t, sub)
    s += status_row(456, [("Bronze","#B45309"),("Silver","#94A3B8"),("Gold","#D97706"),("Serving","#34D399"),("Governed","#A78BFA")])
    return s, "Data Architecture"

def make_kubernetes(C):
    s = tool_strip(70, [("","kubectl"),("","Helm"),("","Prometheus"),("","Jaeger"),("","RBAC"),("","Ingress")], C[0])
    s += section(15, 98, 870, 52, "CONTROL PLANE", C[0])
    for i,(t,sub) in enumerate([("API Server","entry point"),("Scheduler","node select"),("Controller Mgr","reconcile"),("etcd","state store"),("Cloud CM","cloud API")]):
        s += card(22+i*172, 116, 164, 28, C[i%len(C)], t, sub)
    s += arrow_down(450, 150, 164, C[1])
    s += section(15, 174, 870, 52, "WORKER NODES", C[1])
    for i,(t,sub) in enumerate([("Kubelet","node agent"),("kube-proxy","networking"),("Container RT","containerd"),("CNI Plugin","Calico/Cilium"),("Node Exporter","metrics")]):
        s += card(22+i*172, 192, 164, 28, C[i%len(C)], t, sub)
    s += arrow_down(450, 226, 240, C[2])
    s += section(15, 250, 870, 58, "WORKLOADS", C[2])
    for i,(t,sub) in enumerate([("Deployment","rolling update"),("StatefulSet","ordered pods"),("DaemonSet","per-node"),("CronJob","scheduled"),("HPA","autoscale"),("PDB","disruption budget")]):
        s += card(20+i*144, 268, 138, 34, C[i%len(C)], t, sub)
    s += arrow_down(450, 308, 322, C[3])
    s += two_col(15, 334, 870, 108, "NETWORKING + INGRESS", C[3], "STORAGE + CONFIG", C[4], 0.5)
    for i,(t,sub,col) in enumerate([("Ingress Ctrl","nginx/traefik",C[3]),("Service Mesh","Istio/Linkerd",C[5]),("NetworkPolicy","microseg",C[3]),("LoadBalancer","cloud LB",C[0])]):
        s += card(22+i*107, 358, 101, 76, col, t, sub)
    for i,(t,sub,col) in enumerate([("PersistentVol","dynamic prov",C[4]),("ConfigMap","env config",C[1]),("Secrets","encrypted kv",C[2]),("StorageClass","CSI driver",C[5])]):
        s += card(458+i*107, 358, 101, 76, col, t, sub)
    s += status_row(454, [("Nodes Ready","#34D399"),("Pods Running","#60A5FA"),("Services OK","#A78BFA"),("Storage Bound","#FB923C"),("Certs Valid","#34D399")])
    return s, "Cloud Architecture"

def make_llm(C):
    s = tool_strip(70, [("","Transformer"),("","LangChain"),("","vLLM"),("","RAG"),("","Guardrails"),("","API")], C[0])
    s += section(15, 98, 870, 44, "FOUNDATION MODELS", C[0])
    for i,(t,sub) in enumerate([("GPT-4o","OpenAI"),("Claude 3.5","Anthropic"),("Gemini 1.5","Google"),("Llama 3.1","Meta/OSS"),("Mistral","EU/OSS"),("Qwen 2.5","Alibaba")]):
        s += card(20+i*144, 114, 138, 22, C[i%len(C)], t, sub)
    s += arrow_down(450, 142, 156, C[1])
    s += section(15, 166, 870, 52, "CONTEXT + RETRIEVAL", C[1])
    for i,(t,sub) in enumerate([("Vector DB","Pinecone/Weaviate"),("Chunking","semantic split"),("Embeddings","text-embed-3"),("Reranker","cross-encoder"),("Cache","semantic sim")]):
        s += card(22+i*172, 182, 164, 30, C[i%len(C)], t, sub)
    s += arrow_down(450, 218, 232, C[2])
    s += section(15, 242, 870, 64, "AGENT + ORCHESTRATION", C[2])
    for i,(t,sub) in enumerate([("Agent Loop","ReAct/CoT"),("Tool Use","function call"),("Memory","episodic"),("Planner","task decomp"),("Critic","self-refine"),("Router","skill select")]):
        s += card(20+i*144, 260, 138, 40, C[i%len(C)], t, sub)
    s += arrow_down(450, 306, 320, C[3])
    s += two_col(15, 332, 870, 110, "INFERENCE + SERVING", C[3], "SAFETY + OPS", C[4], 0.55)
    for i,(t,sub,col) in enumerate([("vLLM","tensor parallel",C[3]),("TRT-LLM","NVIDIA opt",C[5]),("Batching","continuous",C[3]),("KV Cache","paged attn",C[0]),("Streaming","SSE/WS",C[1])]):
        s += card(22+i*106, 356, 100, 78, col, t, sub)
    for i,(t,sub,col) in enumerate([("Guardrails","PII/toxic",C[4]),("Evals","RAGAS/LLM",C[2]),("Traces","LangSmith",C[5])]):
        s += card(506+i*118, 356, 112, 78, col, t, sub)
    s += status_row(454, [("P50 420ms","#34D399"),("Tokens/s 1.2k","#60A5FA"),("Cache hit 64%","#A78BFA"),("Cost -38%","#34D399"),("Safety 99.1%","#FB923C")])
    return s, "AI Architecture"

def make_cicd(C):
    s = tool_strip(70, [("","Git"),("","GitHub Actions"),("","Docker"),("","K8s"),("","SonarQube"),("","Grafana")], C[0])
    phases = [("CODE","","git push","pre-commit"),("BUILD","","compile","unit tests"),
              ("TEST","","integration","DAST/SAST"),("SCAN","","CVE scan","SCA/SBOM"),
              ("PKG","","Docker","sign+push"),("STAGE","","deploy","smoke test"),("PROD","","blue/green","canary")]
    pw = 870 // len(phases)
    for i,(env,ico,phase,tools) in enumerate(phases):
        col = C[i%len(C)]; bx = 15+i*pw
        s += f'<rect x="{bx}" y="98" width="{pw-3}" height="184" rx="8" fill="{col}12" stroke="{col}" stroke-width="1.5" stroke-dasharray="6,3"/>'
        s += f'<rect x="{bx}" y="98" width="{pw-3}" height="24" rx="8" fill="{col}35"/>'
        s += f'<rect x="{bx}" y="110" width="{pw-3}" height="12" fill="{col}35"/>'
        s += f'<text x="{bx+(pw-3)//2}" y="{114}" text-anchor="middle" fill="white" font-size="9" font-weight="700" font-family="Arial,sans-serif" letter-spacing="0.8">{x(env)}</text>'
        s += f'<text x="{bx+(pw-3)//2}" y="{163}" text-anchor="middle" fill="{col}" font-size="22" font-weight="900" font-family="Arial,sans-serif">{i+1}</text>'
        s += f'<text x="{bx+(pw-3)//2}" y="{183}" text-anchor="middle" fill="white" font-size="9" font-weight="700" font-family="Arial,sans-serif">{x(clamp(phase,10))}</text>'
        s += f'<text x="{bx+(pw-3)//2}" y="{196}" text-anchor="middle" fill="{TEXT_MAIN}" font-size="8" font-family="Arial,sans-serif">{x(clamp(tools,12))}</text>'
        if i < len(phases)-1: s += arrow_right(bx+pw-3, bx+pw, 190, col)
    s += status_row(294, [("Build 2m14s","#34D399"),("Tests 97%","#60A5FA"),("CVEs 0 crit","#34D399"),("Image signed","#A78BFA"),("DORA Elite","#FB923C")])
    s += section(15, 326, 870, 110, "OBSERVABILITY PIPELINE", C[4], dashed=True)
    for i,(t,sub,col) in enumerate([("Metrics","Prometheus+Grafana",C[0]),("Logs","Loki/ELK",C[1]),("Traces","Tempo/Jaeger",C[2]),("Alerts","PagerDuty",C[3]),("SLO/SLA","error budget",C[4])]):
        s += card(22+i*172, 348, 164, 80, col, t, sub)
    s += status_row(448, [("Deploy freq: daily","#34D399"),("Lead time <1h","#60A5FA"),("MTTR <30min","#A78BFA"),("Change fail <5%","#34D399"),("Rollback <5min","#FB923C")])
    return s, "DevOps Pipeline"

def make_kafka(C):
    s = tool_strip(70, [("","Kafka"),("","Flink"),("","Spark"),("","ksqlDB"),("","Connect"),("","Schema Reg")], C[0])
    s += section(15, 98, 870, 68, "PRODUCERS", C[0])
    for i,(t,sub) in enumerate([("Microservices","REST/gRPC events"),("IoT Devices","MQTT bridge"),("DB CDC","Debezium"),("Clickstream","JS SDK"),("Mobile Apps","SDK"),("Batch Import","file ingest")]):
        s += card(22+i*143, 118, 137, 42, C[i%len(C)], t, sub)
    s += arrow_down(450, 166, 180, C[1])
    s += section(15, 190, 870, 96, "KAFKA CLUSTER", C[1])
    for i,(t,sub) in enumerate([("Broker 1","leader"),("Broker 2","replica"),("Broker 3","replica"),("ZooKeeper","coord"),("Schema Reg","Avro/JSON"),("Kafka UI","monitoring")]):
        s += card(22+i*143, 210, 137, 28, C[1], t, sub)
    for i,(t,sub) in enumerate([("orders","p=6 rf=3"),("events","p=12 rf=3"),("errors","DLQ"),("audit","immutable"),("users.cdc","CDC topic")]):
        s += card(22+i*172, 244, 164, 36, C[i%len(C)], t, sub)
    s += arrow_down(450, 286, 300, C[2])
    s += section(15, 310, 870, 52, "STREAM PROCESSING", C[2])
    for i,(t,sub) in enumerate([("Kafka Streams","in-process"),("Apache Flink","stateful"),("ksqlDB","SQL stream"),("Spark Struct.","micro-batch"),("Bytewax","Python")]):
        s += card(22+i*172, 328, 164, 28, C[i%len(C)], t, sub)
    s += arrow_down(450, 362, 376, C[3])
    s += section(15, 386, 870, 52, "CONSUMERS + SINKS", C[3])
    for i,(t,sub) in enumerate([("Elasticsearch","search index"),("ClickHouse","analytics"),("S3/GCS","data lake"),("PostgreSQL","OLTP sink"),("Redis","cache warm"),("Slack/PD","alerting")]):
        s += card(22+i*143, 402, 137, 30, C[i%len(C)], t, sub)
    s += status_row(450, [("Throughput 2M/s","#34D399"),("Lag 0","#60A5FA"),("Partitions 48","#A78BFA"),("Retention 7d","#FB923C"),("Replication 3x","#34D399")])
    return s, "Data Architecture"

def make_zero_trust(C):
    s = tool_strip(70, [("","mTLS"),("","OPA"),("","SIEM"),("","Vault"),("","ZTNA"),("","PAM")], C[0])
    s += section(15, 98, 870, 44, "IDENTITY + ACCESS", C[0])
    for i,(t,sub) in enumerate([("IdP/SSO","Okta/Azure AD"),("MFA","FIDO2/TOTP"),("PAM","just-in-time"),("Service ID","SPIFFE/SPIRE"),("Certificates","mTLS/PKI")]):
        s += card(22+i*172, 116, 164, 20, C[i%len(C)], t, sub)
    s += arrow_down(450, 142, 156, C[1])
    s += section(15, 166, 870, 42, "POLICY ENGINE (NEVER TRUST, ALWAYS VERIFY)", C[1])
    for i,(t,sub) in enumerate([("OPA/Rego","policy-as-code"),("ABAC","attribute-based"),("Context Aware","device posture"),("Time-based","lease expiry"),("Continuous","re-auth")]):
        s += card(22+i*172, 182, 164, 20, C[i%len(C)], t, sub)
    s += arrow_down(450, 208, 222, C[2])
    s += section(15, 232, 870, 64, "NETWORK SEGMENTS (MICRO-SEGMENTED)", C[2])
    for i,(t,sub) in enumerate([("Internet Zone","WAF/DDoS"),("DMZ","reverse proxy"),("App Zone","east-west mTLS"),("Data Zone","encrypted DB"),("Admin Zone","bastion/PAM"),("IoT Zone","MAC filtered")]):
        s += card(20+i*144, 252, 138, 38, C[i%len(C)], t, sub)
    s += arrow_down(450, 296, 310, C[3])
    s += two_col(15, 322, 870, 112, "DETECT + RESPOND", C[3], "DATA PROTECTION", C[4], 0.5)
    for i,(t,sub,col) in enumerate([("SIEM","Splunk/Sentinel",C[3]),("SOAR","auto-remediate",C[5]),("EDR","endpoint detect",C[3]),("Deception","honeypots",C[0])]):
        s += card(22+i*107, 346, 101, 80, col, t, sub)
    for i,(t,sub,col) in enumerate([("DLP","data loss prev",C[4]),("Encryption","AES-256/TLS1.3",C[1]),("Tokenization","PCI/PII",C[2]),("Key Mgmt","HashiCorp Vault",C[5])]):
        s += card(458+i*107, 346, 101, 80, col, t, sub)
    s += status_row(446, [("Zero Standing Priv","#34D399"),("mTLS 100%","#60A5FA"),("Posture Checked","#A78BFA"),("Least Privilege","#34D399"),("Audit Logged","#FB923C")])
    return s, "Security Architecture"

def make_aws(C):
    s = tool_strip(70, [("","VPC"),("","IAM"),("","ALB"),("","Lambda"),("","RDS"),("","CloudWatch")], C[0])
    s += section(15, 98, 870, 44, "EDGE + CDN LAYER", C[0])
    for i,(t,sub) in enumerate([("Route 53","DNS/health"),("CloudFront","CDN/WAF"),("ACM","SSL certs"),("Shield Adv","DDoS protect"),("API Gateway","REST/WS/GQL")]):
        s += card(22+i*172, 116, 164, 20, C[i%len(C)], t, sub)
    s += arrow_down(450, 142, 156, C[1])
    s += two_col(15, 166, 870, 112, "PUBLIC SUBNETS (AZ-a / AZ-b / AZ-c)", C[1], "PRIVATE SUBNETS", C[2], 0.5)
    for i,(t,sub,col) in enumerate([("ALB","layer-7 LB",C[1]),("NAT GW","outbound",C[5]),("Bastion","SSH jump",C[3])]):
        s += card(22+i*107+4, 192, 100, 78, col, t, sub)
    for i,(t,sub,col) in enumerate([("ECS/EKS","container",C[2]),("Lambda","serverless",C[0]),("EC2 ASG","VM fleet",C[4]),("ElastiCache","Redis/Memcached",C[5])]):
        s += card(458+i*104, 192, 98, 78, col, t, sub)
    s += arrow_down(450, 278, 292, C[3])
    s += section(15, 302, 870, 52, "DATA LAYER", C[3])
    for i,(t,sub) in enumerate([("RDS Aurora","Multi-AZ"),("DynamoDB","global tables"),("S3","11 9s durable"),("Redshift","analytics"),("Elasticsearch","search"),("SQS/SNS","messaging")]):
        s += card(22+i*143, 318, 137, 30, C[i%len(C)], t, sub)
    s += arrow_down(450, 354, 368, C[4])
    s += section(15, 378, 870, 60, "MONITORING + SECURITY", C[4])
    for i,(t,sub) in enumerate([("CloudWatch","metrics/logs"),("X-Ray","distributed trace"),("GuardDuty","threat detect"),("Config","compliance"),("CloudTrail","audit log"),("Security Hub","findings")]):
        s += card(22+i*143, 396, 137, 36, C[i%len(C)], t, sub)
    s += status_row(450, [("99.99% SLA","#34D399"),("Multi-AZ","#60A5FA"),("Auto Scaled","#A78BFA"),("Cost Optimized","#FB923C"),("Compliant","#34D399")])
    return s, "Cloud Architecture"

def make_mlops(C):
    s = tool_strip(70, [("","MLflow"),("","Kubeflow"),("","Evidently"),("","dbt"),("","S3"),("","Seldon")], C[0])
    s += section(15, 98, 870, 58, "DATA ENGINEERING", C[0])
    for i,(t,sub) in enumerate([("Feature Store","Feast/Tecton"),("Data Catalog","lineage track"),("Label Studio","annotation"),("DVC","data version"),("Great Expect","validation"),("dbt","transforms")]):
        s += card(20+i*144, 118, 138, 32, C[i%len(C)], t, sub)
    s += arrow_down(450, 156, 170, C[1])
    s += section(15, 180, 870, 58, "TRAINING + EXPERIMENTATION", C[1])
    for i,(t,sub) in enumerate([("MLflow","experiment track"),("Ray Train","distributed"),("Optuna","HPO"),("W&B","run tracking"),("Katib","AutoML"),("Kubeflow","pipeline")]):
        s += card(20+i*144, 200, 138, 32, C[i%len(C)], t, sub)
    s += arrow_down(450, 238, 252, C[2])
    s += section(15, 262, 870, 50, "MODEL REGISTRY + GOVERNANCE", C[2])
    for i,(t,sub) in enumerate([("MLflow Reg","versioning"),("Model Card","doc+bias"),("A/B Testing","champion/chal"),("Approval Gate","review"),("Lineage","input→output")]):
        s += card(22+i*172, 280, 164, 26, C[i%len(C)], t, sub)
    s += arrow_down(450, 312, 326, C[3])
    s += two_col(15, 338, 870, 100, "SERVING + INFERENCE", C[3], "MONITORING + FEEDBACK", C[4], 0.5)
    for i,(t,sub,col) in enumerate([("Seldon Core","k8s serving",C[3]),("Triton","GPU inference",C[5]),("TorchServe","PyTorch",C[3])]):
        s += card(22+i*144+2, 360, 138, 70, col, t, sub)
    for i,(t,sub,col) in enumerate([("Evidently","data drift",C[4]),("Prometheus","perf metrics",C[1]),("Retraining","auto trigger",C[2])]):
        s += card(460+i*128, 360, 122, 70, col, t, sub)
    s += status_row(450, [("Acc 96.2%","#34D399"),("Drift: None","#60A5FA"),("P99 87ms","#A78BFA"),("Retrain: weekly","#FB923C"),("Registry v2.4","#34D399")])
    return s, "AI Architecture"

def make_rag(C):
    s = tool_strip(70, [("","Embed"),("","VectorDB"),("","Chunking"),("","LangChain"),("","Reranker"),("","Guardrails")], C[0])
    s += section(15, 98, 870, 62, "DOCUMENT INGESTION PIPELINE", C[0])
    for i,(t,sub) in enumerate([("PDF/HTML","raw docs"),("Chunker","semantic split"),("Cleaner","PII strip"),("Embedder","text-embed-3"),("Metadata","tags+source"),("VectorDB","Pinecone/Weaviate")]):
        s += card(20+i*144, 118, 138, 36, C[i%len(C)], t, sub)
    s += arrow_down(450, 160, 174, C[1])
    s += section(15, 184, 870, 50, "RETRIEVAL STRATEGIES", C[1])
    for i,(t,sub) in enumerate([("Dense","cosine sim"),("Sparse","BM25/TF-IDF"),("Hybrid","RRF fusion"),("Reranker","cross-encoder"),("HyDE","hypothetical doc"),("Parent Doc","large chunk")]):
        s += card(22+i*143, 200, 137, 28, C[i%len(C)], t, sub)
    s += arrow_down(450, 234, 248, C[2])
    s += section(15, 258, 870, 62, "AUGMENTATION + GENERATION", C[2])
    for i,(t,sub) in enumerate([("Context Inject","top-k chunks"),("Prompt Tmpl","few-shot"),("LLM Call","GPT-4/Claude"),("Citation","source ref"),("Self-refine","critic loop"),("Output Parse","struct JSON")]):
        s += card(20+i*144, 278, 138, 36, C[i%len(C)], t, sub)
    s += arrow_down(450, 320, 334, C[3])
    s += two_col(15, 344, 870, 100, "EVALUATION SUITE", C[3], "PRODUCTION OPS", C[4], 0.5)
    for i,(t,sub,col) in enumerate([("RAGAS","faithfulness",C[3]),("Context Prec","recall",C[5]),("Answer Rel","semantic",C[3]),("Human Eval","RLHF",C[0])]):
        s += card(22+i*107, 366, 101, 70, col, t, sub)
    for i,(t,sub,col) in enumerate([("Caching","GPTCache",C[4]),("Rate Limit","token budget",C[1]),("Observ.","LangSmith",C[2]),("Feedback","thumbs",C[5])]):
        s += card(458+i*107, 366, 101, 70, col, t, sub)
    s += status_row(456, [("Faithfulness 92%","#34D399"),("Context Prec 87%","#60A5FA"),("Latency 1.1s","#A78BFA"),("Cache hit 41%","#FB923C"),("Cost -55%","#34D399")])
    return s, "AI Architecture"

def make_devsecops(C):
    s = tool_strip(70, [("","SAST/DAST"),("","Trivy"),("","Falco"),("","Semgrep"),("","OPA"),("","Splunk")], C[0])
    phases=[("IDE","","Pre-commit","git-secrets"),("SCM","","Review","SAST scan"),
            ("Build","","Compile","SCA/SBOM"),("Test","","Quality","DAST/ZAP"),
            ("Artifact","","Registry","Trivy+sign"),("Stage","","Deploy","IaC scan"),("Prod","","Runtime","Falco/eBPF")]
    pw = 870 // len(phases)
    for i,(env,ico,phase,tools) in enumerate(phases):
        col = C[i%len(C)]; bx = 15+i*pw
        s += f'<rect x="{bx}" y="98" width="{pw-3}" height="178" rx="8" fill="{col}12" stroke="{col}" stroke-width="1.5" stroke-dasharray="6,3"/>'
        s += f'<rect x="{bx}" y="98" width="{pw-3}" height="22" rx="8" fill="{col}35"/>'
        s += f'<rect x="{bx}" y="108" width="{pw-3}" height="12" fill="{col}35"/>'
        s += f'<text x="{bx+(pw-3)//2}" y="{113}" text-anchor="middle" fill="white" font-size="9" font-weight="700" font-family="Arial,sans-serif" letter-spacing="0.8">{x(env)}</text>'
        s += f'<text x="{bx+(pw-3)//2}" y="{160}" text-anchor="middle" fill="{col}" font-size="22" font-weight="900" font-family="Arial,sans-serif">{i+1}</text>'
        s += f'<text x="{bx+(pw-3)//2}" y="{174}" text-anchor="middle" fill="white" font-size="9" font-weight="700" font-family="Arial,sans-serif">{x(clamp(phase,10))}</text>'
        s += f'<text x="{bx+(pw-3)//2}" y="{188}" text-anchor="middle" fill="{TEXT_MAIN}" font-size="8" font-family="Arial,sans-serif">{x(clamp(tools,12))}</text>'
        if i < len(phases)-1: s += arrow_right(bx+pw-3, bx+pw, 186, col)
    s += status_row(288, [("Secrets Blocked","#F87171"),("CVE Free","#FB923C"),("Image Signed","#34D399"),("Policy Pass","#A78BFA"),("Runtime Watch","#60A5FA")])
    s += two_col(15, 320, 870, 122, "SIEM + INCIDENT RESPONSE", C[4], "COMPLIANCE + POLICY", C[1], 0.5)
    for i,(t,sub,col) in enumerate([("SIEM","Splunk/Sentinel",C[4]),("SOAR","auto-remediate",C[5]),("Threat Intel","IOC feeds",C[0])]):
        s += card(22+i*143, 344, 137, 90, col, t, sub)
    for i,(t,sub,col) in enumerate([("CIS Benchmarks","hardening",C[1]),("SOC2/ISO27K","audit",C[2]),("OPA/Rego","policy-as-code",C[3])]):
        s += card(456+i*143, 344, 137, 90, col, t, sub)
    s += status_row(454, [("NIST CSF","#34D399"),("ISO 27001","#60A5FA"),("SOC2 Type II","#A78BFA"),("GDPR","#FB923C"),("PCI-DSS","#F87171")])
    return s, "Security Architecture"

def make_docker(C):
    s = tool_strip(70, [("","Dockerfile"),("","Registry"),("","compose"),("","Trivy"),("","stats"),("","secrets")], C[0])
    rows=[("FROM / BASE",C[0],[("","Alpine","3.19"),("","Ubuntu","22.04 LTS"),("","Node","20-alpine"),("","Python","3.12-slim"),("","JDK","21-eclipse")]),
          ("BUILD",C[1],[("","COPY","src→workdir"),("","RUN","apt/pip install"),("","ARG","build-time var"),("","CACHE","layer reuse"),("","Multi-stage","slim final")]),
          ("CONFIGURE",C[2],[("","ENV","runtime vars"),("","WORKDIR","app dir"),("","USER","non-root"),("","VOLUME","mount points"),("","EXPOSE","port decl")]),
          ("RUNTIME",C[3],[("","CMD","default exec"),("","ENTRYPOINT","fixed cmd"),("","HEALTHCHECK","liveness"),("","LABEL","metadata"),("","STOPSIGNAL","graceful")])]
    y = 106
    for label,col,items in rows:
        s += cheatrow(y, 46, label, col, items); y += 52
    s += section(15, 318, 870, 40, "COMPOSE ESSENTIALS", C[4])
    for i,(t,sub) in enumerate([("services","container def"),("networks","bridge/overlay"),("volumes","named/bind"),("env_file","secrets"),("depends_on","start order"),("healthcheck","readiness")]):
        s += card(22+i*143, 334, 137, 18, C[i%len(C)], t, sub)
    s += section(15, 374, 870, 66, "SECURITY HARDENING", C[5])
    for i,(t,sub) in enumerate([("Distroless","minimal attack"),("Read-only FS","immutable"),("No root","USER 1001"),("Secrets","Docker secrets"),("Scan","Trivy/Snyk"),("Sign","cosign+SBOM")]):
        s += card(20+i*144, 394, 138, 40, C[i%len(C)], t, sub)
    s += status_row(452, [("Image <50MB","#34D399"),("0 CVE critical","#34D399"),("Non-root","#60A5FA"),("SBOM attached","#A78BFA"),("Signed","#FB923C")])
    return s, "DevOps Pipeline"

def make_git_workflow(C):
    s = tool_strip(70, [("","Git"),("","Merge"),("","Tag"),("","Review"),("","Actions"),("","Conventional")], C[0])
    branches=[("main","","protected","prod deploy",C[0]),("develop","","integration","staging deploy",C[1]),
              ("feature/*","","short-lived","PR target",C[2]),("release/*","","RC branch","freeze",C[3]),("hotfix/*","","critical fix","direct merge",C[4])]
    bw = 870 // len(branches)
    for i,(name,ico,role,deploy,col) in enumerate(branches):
        bx = 15+i*bw
        s += f'<rect x="{bx}" y="98" width="{bw-4}" height="166" rx="8" fill="{col}12" stroke="{col}" stroke-width="1.5" stroke-dasharray="6,3"/>'
        s += f'<text x="{bx+(bw-4)//2}" y="{134}" text-anchor="middle" fill="{col}" font-size="24" font-weight="900" font-family="Arial,sans-serif">{name[0].upper()}</text>'
        s += f'<text x="{bx+(bw-4)//2}" y="{150}" text-anchor="middle" fill="{col}" font-size="10" font-weight="700" font-family="Arial,sans-serif">{x(name)}</text>'
        s += f'<text x="{bx+(bw-4)//2}" y="{165}" text-anchor="middle" fill="{TEXT_MID}" font-size="8" font-family="Arial,sans-serif">{x(role)}</text>'
        s += f'<text x="{bx+(bw-4)//2}" y="{178}" text-anchor="middle" fill="{TEXT_MID}" font-size="8" font-family="Arial,sans-serif">{x(deploy)}</text>'
        s += card(bx+6, 186, bw-16, 22, col, "Protected" if i < 2 else "PR required", "")
    s += status_row(276, [("Signed commits","#34D399"),("DCO required","#60A5FA"),("Branch protect","#A78BFA"),("Linear history","#FB923C"),("Tag on release","#34D399")])
    s += section(15, 308, 870, 52, "CONVENTIONAL COMMITS", C[2])
    for i,(t,sub) in enumerate([("feat","new feature"),("fix","bug fix"),("docs","docs only"),("style","formatting"),("refactor","no logic change"),("test","tests"),("ci","CI config")]):
        s += card(20+i*124, 328, 118, 26, C[i%len(C)], t, sub)
    s += section(15, 376, 870, 64, "PR + REVIEW WORKFLOW", C[3])
    for i,(t,sub) in enumerate([("Branch","from develop"),("Commit","conventional"),("Push","trigger CI"),("PR Open","auto assign"),("Review","2 approvals"),("Merge","squash/rebase"),("Delete","clean branch")]):
        s += card(20+i*124, 396, 118, 38, C[i%len(C)], t, sub)
    s += status_row(452, [("PR coverage","#34D399"),("Avg review 4h","#60A5FA"),("Pass rate 94%","#A78BFA"),("Commits signed","#34D399"),("Releases tagged","#FB923C")])
    return s, "DevOps Pipeline"

def make_api_design(C):
    s = tool_strip(70, [("","REST"),("","GraphQL"),("","gRPC"),("","WebSocket"),("","OAuth2"),("","OpenAPI")], C[0])
    paradigms=[("REST","","HTTP/JSON","CRUD resources",C[0]),("GraphQL","","SDL schema","query/mutate",C[1]),
               ("gRPC","","Protobuf","streaming RPC",C[2]),("WebSocket","","ws://","bi-directional",C[3]),("Webhooks","","push events","async notify",C[4])]
    pw = 870 // len(paradigms)
    for i,(name,ico,proto,use,col) in enumerate(paradigms):
        bx = 15+i*pw
        s += f'<rect x="{bx}" y="98" width="{pw-3}" height="110" rx="8" fill="{col}15" stroke="{col}" stroke-width="1.5"/>'
        s += f'<text x="{bx+(pw-3)//2}" y="{130}" text-anchor="middle" fill="{col}" font-size="16" font-weight="900" font-family="Arial,sans-serif">{name[:4]}</text>'
        s += f'<text x="{bx+(pw-3)//2}" y="{151}" text-anchor="middle" fill="{col}" font-size="12" font-weight="700" font-family="Arial,sans-serif">{x(name)}</text>'
        s += f'<text x="{bx+(pw-3)//2}" y="{165}" text-anchor="middle" fill="{TEXT_MID}" font-size="8" font-family="Arial,sans-serif">{x(proto)}</text>'
        s += f'<text x="{bx+(pw-3)//2}" y="{178}" text-anchor="middle" fill="{TEXT_MID}" font-size="8" font-family="Arial,sans-serif">{x(use)}</text>'
        s += card(bx+6, 194, pw-15, 12, col, "OpenAPI / AsyncAPI", "")
    s += status_row(218, [("Versioned","#34D399"),("Rate Limited","#60A5FA"),("Auth required","#A78BFA"),("Documented","#FB923C"),("Monitored","#34D399")])
    s += section(15, 248, 870, 50, "SECURITY LAYER", C[2])
    for i,(t,sub) in enumerate([("OAuth2/OIDC","token auth"),("API Keys","service auth"),("JWT","stateless"),("mTLS","service mesh"),("Rate Limit","token bucket"),("IP Allowlist","network ACL")]):
        s += card(22+i*143, 266, 137, 26, C[i%len(C)], t, sub)
    s += section(15, 314, 870, 50, "GATEWAY PATTERNS", C[3])
    for i,(t,sub) in enumerate([("Load Balance","round-robin"),("Circuit Break","hystrix"),("Retry Logic","exp backoff"),("Caching","Redis/CDN"),("Transform","req/resp map"),("Aggregation","BFF pattern")]):
        s += card(22+i*143, 332, 137, 26, C[i%len(C)], t, sub)
    s += section(15, 380, 870, 60, "OBSERVABILITY", C[4])
    for i,(t,sub) in enumerate([("Struct. Logs","JSON+trace-id"),("Dist. Tracing","Jaeger/Tempo"),("Metrics","p50/p95/p99"),("Error Budget","SLO based"),("API Analytics","usage/cost"),("Alerting","PagerDuty")]):
        s += card(22+i*143, 400, 137, 34, C[i%len(C)], t, sub)
    s += status_row(452, [("OpenAPI 3.1","#34D399"),("Breaking change 0","#34D399"),("p95 < 200ms","#60A5FA"),("Uptime 99.9%","#A78BFA"),("Auth 100%","#FB923C")])
    return s, "System Architecture"

def make_solid(C):
    s = tool_strip(70, [("","SOLID"),("","Clean Arch"),("","DI"),("","TDD"),("","DDD"),("","Ports/Adapters")], C[0])
    principles=[("S","Single Resp","One reason to change"," UserService\n GodClass",C[0]),
                ("O","Open/Closed","Open extend, closed modify"," Strategy pattern\n if/elif chain",C[1]),
                ("L","Liskov Subst","Subtypes replace base"," Duck typing\n Override raises",C[2]),
                ("I","Interface Seg","Small focused interfaces"," Flyable+Swimmable\n Fat interface",C[3]),
                ("D","Dependency Inv","Depend on abstractions"," DI container\n new Dependency()",C[4])]
    pw = 870 // len(principles)
    for i,(letter,name,rule,example,col) in enumerate(principles):
        bx = 15+i*pw
        s += f'<rect x="{bx}" y="98" width="{pw-4}" height="220" rx="10" fill="{col}12" stroke="{col}" stroke-width="2"/>'
        s += f'<text x="{bx+(pw-4)//2}" y="{136}" text-anchor="middle" fill="{col}" font-size="32" font-weight="900" font-family="Arial,sans-serif">{letter}</text>'
        s += f'<text x="{bx+(pw-4)//2}" y="{156}" text-anchor="middle" fill="{col}" font-size="10" font-weight="700" font-family="Arial,sans-serif">{x(name)}</text>'
        words = rule.split(); line=""; lines_out=[]; ys=170
        for w in words:
            if len(line+" "+w) > (pw-4)//7: lines_out.append(line); line=w
            else: line=(line+" "+w).strip()
        if line: lines_out.append(line)
        for j,ln in enumerate(lines_out):
            s += f'<text x="{bx+(pw-4)//2}" y="{ys+j*13}" text-anchor="middle" fill="{TEXT_MID}" font-size="8" font-family="Arial,sans-serif">{x(ln)}</text>'
        for j,ln in enumerate(example.split("\n")):
            c2 = "#34D399" if ln.startswith("") else "#F87171" if ln.startswith("") else TEXT_MID
            s += f'<text x="{bx+(pw-4)//2}" y="{214+j*15}" text-anchor="middle" fill="{c2}" font-size="8" font-family="Arial,sans-serif">{x(ln)}</text>'
    s += status_row(330, [("Cohesion ↑","#34D399"),("Coupling ↓","#60A5FA"),("Testable","#A78BFA"),("Extensible","#FB923C"),("Readable","#34D399")])
    s += section(15, 362, 870, 78, "DESIGN PATTERNS (APPLY WITH SOLID)", C[2])
    for i,(t,sub,col) in enumerate([("Factory","object creation",C[0]),("Strategy","swappable algo",C[1]),("Observer","event pub/sub",C[2]),("Decorator","wrap behavior",C[3]),("Repository","data access",C[4]),("Command","encap requests",C[5])]):
        s += card(20+i*144, 384, 138, 50, col, t, sub)
    s += status_row(452, [("DRY","#34D399"),("YAGNI","#60A5FA"),("KISS","#A78BFA"),("Clean Code","#FB923C"),("Test First","#34D399")])
    return s, "System Architecture"

def make_generic(topic_name, C):
    s = tool_strip(70, [("","Architecture"),("","Services"),("","APIs"),("","Data"),("","Security"),("","Observability")], C[0])
    s += section(15, 98, 870, 62, "CORE ARCHITECTURE", C[0])
    words = topic_name.split()[:6]
    for i, w in enumerate(words[:6]):
        s += card(20+i*144, 118, 138, 36, C[i%len(C)], w, "component")
    s += arrow_down(450, 160, 174, C[1])
    s += section(15, 184, 870, 52, "KEY SERVICES", C[1])
    for i,(t,sub) in enumerate([("API Layer","REST/GraphQL"),("Business Logic","core rules"),("Data Access","ORM/queries"),("Cache Layer","Redis/CDN"),("Auth Service","JWT/OAuth2")]):
        s += card(22+i*172, 200, 164, 30, C[i%len(C)], t, sub)
    s += arrow_down(450, 236, 250, C[2])
    s += two_col(15, 260, 870, 100, "DATA + STORAGE", C[2], "INFRASTRUCTURE", C[3], 0.5)
    for i,(t,sub,col) in enumerate([("Primary DB","PostgreSQL",C[2]),("Cache","Redis",C[5]),("Object Store","S3/GCS",C[2]),("Search","Elasticsearch",C[0])]):
        s += card(22+i*107, 284, 101, 68, col, t, sub)
    for i,(t,sub,col) in enumerate([("Container","Docker/K8s",C[3]),("CI/CD","GitHub Actions",C[1]),("CDN","CloudFront",C[4]),("DNS","Route53",C[5])]):
        s += card(458+i*107, 284, 101, 68, col, t, sub)
    s += arrow_down(450, 360, 374, C[4])
    s += section(15, 384, 870, 52, "OBSERVABILITY + SECURITY", C[4])
    for i,(t,sub) in enumerate([("Metrics","Prometheus+Grafana"),("Logs","ELK/Loki"),("Traces","Jaeger/Tempo"),("Alerts","PagerDuty"),("Auth","mTLS+OAuth2"),("Audit","CloudTrail")]):
        s += card(22+i*143, 400, 137, 30, C[i%len(C)], t, sub)
    s += status_row(448, [("Scalable","#34D399"),("Resilient","#60A5FA"),("Secure","#A78BFA"),("Observable","#FB923C"),("Cost-Optimised","#34D399")])
    return s, "System Architecture"

# ── DISPATCH ──────────────────────────────────────────────────────────────────
def make_diagram(topic_name, topic_id, diagram_type=""):
    C   = get_pal(topic_id)
    now = datetime.now().strftime("%B %Y")
    tid = topic_id.lower()
    if   "kube"   in tid:                           content, sub = make_kubernetes(C)
    elif any(x2 in tid for x2 in ["llm","agent"]):  content, sub = make_llm(C)
    elif "cicd"   in tid:                           content, sub = make_cicd(C)
    elif "kafka"  in tid:                           content, sub = make_kafka(C)
    elif "zero"   in tid:                           content, sub = make_zero_trust(C)
    elif "aws"    in tid:                           content, sub = make_aws(C)
    elif "devsec" in tid:                           content, sub = make_devsecops(C)
    elif "system" in tid:                           content, sub = make_system_design(C)
    elif "mlops"  in tid:                           content, sub = make_mlops(C)
    elif any(x2 in tid for x2 in ["lake","data"]):  content, sub = make_lakehouse(C)
    elif "rag"    in tid:                           content, sub = make_rag(C)
    elif "docker" in tid:                           content, sub = make_docker(C)
    elif "git"    in tid:                           content, sub = make_git_workflow(C)
    elif "api"    in tid:                           content, sub = make_api_design(C)
    elif "solid"  in tid:                           content, sub = make_solid(C)
    else:                                           content, sub = make_generic(topic_name, C)
    return wrap(content, topic_name, sub, C[0], now)


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
