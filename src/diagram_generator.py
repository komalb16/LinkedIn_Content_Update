import os
from datetime import datetime
from pathlib import Path
from logger import get_logger

log = get_logger("diagrams")
OUTPUT_DIR = "diagrams"

def get_palette(topic_id):
    tid = topic_id.lower()
    if any(x in tid for x in ["llm", "rag", "agent", "mlops"]): 
        return {"bg":"#0D1117","p":"#00D4AA","s":"#7C3AED","a":"#F59E0B","d":"#EF4444","i":"#3B82F6","t":"#E2E8F0"}
    if any(x in tid for x in ["kube", "docker", "aws", "cicd"]): 
        return {"bg":"#0D1117","p":"#4ECDC4","s":"#2563EB","a":"#F59E0B","d":"#EF4444","i":"#8B5CF6","t":"#E2E8F0"}
    if any(x in tid for x in ["zero", "devsec"]): 
        return {"bg":"#0D1117","p":"#EF4444","s":"#F97316","a":"#FBBF24","d":"#DC2626","i":"#6366F1","t":"#E2E8F0"}
    if any(x in tid for x in ["kafka", "data", "lake"]): 
        return {"bg":"#0D1117","p":"#8B5CF6","s":"#06B6D4","a":"#10B981","d":"#F43F5E","i":"#3B82F6","t":"#E2E8F0"}
    return {"bg":"#0D1117","p":"#FFE66D","s":"#4ECDC4","a":"#A29BFE","d":"#FF6B6B","i":"#74B9FF","t":"#E2E8F0"}

def box(x,y,w,h,title,sub,color,rx=10):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="1.5"/>'
    s += f'<text x="{x+w//2}" y="{y+h//2-4}" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">{title}</text>'
    if sub:
        s += f'<text x="{x+w//2}" y="{y+h//2+11}" text-anchor="middle" fill="#94A3B8" font-size="9" font-family="Arial,sans-serif">{sub}</text>'
    return s

def section(x,y,w,h,title,color):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{color}" fill-opacity="0.06" stroke="{color}" stroke-width="1" stroke-opacity="0.5" stroke-dasharray="4,3"/>'
    s += f'<rect x="{x+8}" y="{y-10}" width="{len(title)*7+16}" height="18" rx="4" fill="{color}" fill-opacity="0.9"/>'
    s += f'<text x="{x+16}" y="{y+3}" fill="#0D1117" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{title}</text>'
    return s

def arr(x1,y1,x2,y2,color,label="",dashed=False):
    dash = 'stroke-dasharray="5,3"' if dashed else ''
    # determine direction for label placement
    mx = (x1+x2)//2
    my = (y1+y2)//2
    s = f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.5" {dash} marker-end="url(#arr{color.replace("#","")})"/>'
    if label:
        s += f'<rect x="{mx-len(label)*3}" y="{my-9}" width="{len(label)*6+8}" height="14" rx="3" fill="#1E293B"/>'
        s += f'<text x="{mx}" y="{my+2}" text-anchor="middle" fill="{color}" font-size="8" font-family="Arial,sans-serif">{label}</text>'
    return s

def curve(x1,y1,x2,y2,color,label="",dashed=False):
    dash = 'stroke-dasharray="5,3"' if dashed else ''
    mx,my = (x1+x2)//2, min(y1,y2)-40
    s = f'<path d="M{x1},{y1} Q{mx},{my} {x2},{y2}" fill="none" stroke="{color}" stroke-width="1.5" {dash} marker-end="url(#arr{color.replace("#","")})"/>'
    if label:
        lx,ly = mx,(y1+y2)//2-20
        s += f'<rect x="{lx-len(label)*3}" y="{ly-9}" width="{len(label)*6+8}" height="14" rx="3" fill="#1E293B"/>'
        s += f'<text x="{lx}" y="{ly+2}" text-anchor="middle" fill="{color}" font-size="8" font-family="Arial,sans-serif">{label}</text>'
    return s

def icon_node(x,y,r,icon,label,sub,color):
    s = f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="2"/>'
    s += f'<text x="{x}" y="{y+6}" text-anchor="middle" font-size="{r}" font-family="Arial,sans-serif">{icon}</text>'
    s += f'<text x="{x}" y="{y+r+14}" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{label}</text>'
    if sub:
        s += f'<text x="{x}" y="{y+r+26}" text-anchor="middle" fill="#64748B" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
    return s

def defs_block(colors):
    d = '<defs>'
    d += '<pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M 30 0 L 0 0 0 30" fill="none" stroke="white" stroke-width="0.2" opacity="0.08"/></pattern>'
    seen = set()
    for c in colors:
        if c not in seen:
            seen.add(c)
            cid = c.replace("#","")
            d += f'<marker id="arr{cid}" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="{c}"/></marker>'
    d += '</defs>'
    return d

def signature(c):
    return f'''
  <rect x="660" y="522" width="220" height="22" rx="11" fill="none" stroke="url(#sig)" stroke-width="1" opacity="0.7"/>
  <rect x="661" y="523" width="218" height="20" rx="10" fill="url(#sig)" fill-opacity="0.08"/>
  <text x="673" y="537" fill="#A29BFE" font-size="10" font-family="Arial,sans-serif">&#10022; AI &#183;</text>
  <text x="706" y="537" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif" letter-spacing="0.5">&#169; Komal Batra</text>'''

def wrap_svg(content, title, subtitle, color, now, all_colors):
    colors_list = list(set(all_colors + [color]))
    d = defs_block(colors_list)
    d += '<linearGradient id="sig" x1="0" x2="1" y1="0" y2="0"><stop offset="0%" stop-color="#00D4AA"/><stop offset="50%" stop-color="#A29BFE"/><stop offset="100%" stop-color="#FF6B6B"/></linearGradient>'
    d += f'<linearGradient id="topg" x1="0" x2="1" y1="0" y2="0"><stop offset="0%" stop-color="{color}"/><stop offset="100%" stop-color="{color}" stop-opacity="0.2"/></linearGradient>'
    safe = title.replace("&","and").replace("<","").replace(">","")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 550" width="900" height="550">
  {d}
  <rect width="900" height="550" fill="#0D1117"/>
  <rect width="900" height="550" fill="url(#grid)"/>
  <rect x="0" y="0" width="900" height="4" fill="url(#topg)"/>
  <circle cx="840" cy="80" r="120" fill="{color}" opacity="0.03"/>
  <circle cx="60" cy="480" r="80" fill="{color}" opacity="0.03"/>
  <text x="20" y="35" fill="{color}" font-size="10" font-weight="bold" font-family="Arial,sans-serif" opacity="0.8" letter-spacing="2">{subtitle.upper()}</text>
  <text x="450" y="65" text-anchor="middle" fill="white" font-size="20" font-weight="bold" font-family="Arial,sans-serif">{safe}</text>
  <line x1="20" y1="75" x2="880" y2="75" stroke="{color}" stroke-width="0.5" opacity="0.25"/>
  {content}
  <line x1="20" y1="515" x2="880" y2="515" stroke="{color}" stroke-width="0.5" opacity="0.2"/>
  <text x="20" y="533" fill="#334155" font-size="9" font-family="Arial,sans-serif">{now} &#183; Generated by AI</text>
  {signature(color)}
</svg>'''

# ─── KUBERNETES ───────────────────────────────────────────────────────────────
def make_kubernetes(p):
    c,s,a,d,i = p["p"],p["s"],p["a"],p["d"],p["i"]
    svg = ""
    # Control Plane
    svg += section(30,85,840,105,"CONTROL PLANE",s)
    svg += box(55,100,120,70,"API Server","entry point",s)
    svg += box(220,100,120,70,"Scheduler","filters/scores",a)
    svg += box(385,100,130,70,"Controller Mgr","reconciles state",a)
    svg += box(560,100,100,70,"etcd","key-value store",d)
    svg += box(700,100,150,70,"kubectl / UI","admin access",i)
    svg += arr(175,135,220,135,a,"schedules")
    svg += arr(340,135,385,135,a)
    svg += arr(515,135,560,135,a,"stores state",True)
    svg += arr(700,135,660,135,i,"requests")
    # Worker Node 1
    svg += section(30,205,390,165,"WORKER NODE 1",i)
    svg += box(50,230,110,50,"Kubelet","node agent",i)
    svg += box(185,230,110,50,"Kube-proxy","iptables/IPVS",i)
    svg += box(50,295,80,55,"Pod A","nginx:latest",c)
    svg += box(145,295,80,55,"Pod B","app:v2",c)
    svg += box(240,295,80,55,"Pod C","worker:v1",c)
    svg += box(335,295,70,55,"CNI","Calico",a)
    svg += arr(160,255,185,255,i,"manages")
    svg += arr(115,280,115,295,c,"runs",True)
    # Worker Node 2
    svg += section(440,205,430,165,"WORKER NODE 2",i)
    svg += box(460,230,110,50,"Kubelet","node agent",i)
    svg += box(595,230,110,50,"Kube-proxy","networking",i)
    svg += box(460,295,80,55,"Pod D","db:v3",c)
    svg += box(555,295,80,55,"Pod E","cache:v1",c)
    svg += box(650,295,80,55,"Pod F","api:v2",c)
    svg += box(745,295,100,55,"Ingress","NGINX controller",s)
    svg += arr(570,255,595,255,i,"manages")
    # Connections from Control Plane to Nodes
    svg += arr(115,170,115,205,s,"schedules pods",True)
    svg += arr(600,170,600,205,s,"schedules pods",True)
    # Bottom row
    svg += section(30,385,260,95,"STORAGE",a)
    svg += box(45,405,110,55,"PVC","volume claim",a)
    svg += box(165,405,110,55,"PersistentVol","StorageClass",a)
    svg += arr(155,432,165,432,a,"binds")
    svg += section(305,385,260,95,"AUTOSCALING",d)
    svg += box(320,405,105,55,"HPA","CPU/mem based",d)
    svg += box(440,405,110,55,"VPA","right-sizing",d)
    svg += arr(425,432,440,432,d)
    svg += section(580,385,290,95,"MONITORING",s)
    svg += box(595,405,120,55,"Prometheus","metrics scrape",s)
    svg += box(730,405,120,55,"Grafana","dashboards",s)
    svg += arr(715,432,730,432,s,"visualize")
    return svg, "Cluster Architecture"

# ─── LLM / AI AGENTS ─────────────────────────────────────────────────────────
def make_llm(p):
    c,s,a,d,i = p["p"],p["s"],p["a"],p["d"],p["i"]
    svg = ""
    # Input
    svg += section(20,85,140,340,"INPUT",i)
    svg += icon_node(90,130,22,"👤","User","query/prompt",i)
    svg += icon_node(90,220,"18","📄","Documents","context",i)
    svg += icon_node(90,305,"18","🔌","APIs","tools/data",a)
    # Orchestration
    svg += section(180,85,220,340,"ORCHESTRATION",s)
    svg += box(195,105,185,60,"Prompt Manager","template/vars/history",s)
    svg += box(195,183,185,60,"Memory Store","short+long term",s)
    svg += box(195,261,185,60,"Tool Router","function calling",a)
    svg += box(195,339,185,55,"Agent Loop","plan/act/observe",a)
    # LLM Core
    svg += section(420,85,240,340,"LLM CORE",c)
    svg += box(435,105,205,60,"Tokenizer","BPE encoding",c)
    svg += box(435,183,205,60,"Transformer","32 attn heads",c)
    svg += box(435,261,205,60,"FFN + Norm","feed-forward layers",c)
    svg += box(435,339,205,55,"Sampler","temp/top-p/top-k",c)
    # Outputs
    svg += section(680,85,200,340,"OUTPUT",d)
    svg += box(695,105,170,60,"Streaming","SSE / tokens",d)
    svg += box(695,183,170,60,"Structured","JSON / XML",d)
    svg += box(695,261,170,60,"Tool Calls","function results",a)
    svg += box(695,339,170,55,"Audit Log","trace/eval",i)
    # Arrows
    svg += arr(112,130,195,135,i,"prompt")
    svg += arr(112,220,195,213,i,"docs",True)
    svg += arr(112,305,195,291,a,"tools",True)
    svg += arr(380,135,435,135,s,"tokenize")
    svg += arr(380,213,435,213,s,"context")
    svg += arr(380,291,435,291,a,"tools")
    svg += arr(380,366,435,366,a,"plan")
    svg += arr(640,135,695,135,c,"stream")
    svg += arr(640,213,695,213,c,"parse")
    svg += arr(640,291,695,291,c,"execute")
    svg += arr(640,366,695,366,c,"log")
    # Internal LLM flow
    svg += arr(537,165,537,183,c)
    svg += arr(537,243,537,261,c)
    svg += arr(537,321,537,339,c)
    # RAG at bottom
    svg += section(20,440,860,60,"RAG LAYER",a)
    svg += box(40,453,150,38,"Vector DB","Pinecone/Weaviate",a)
    svg += box(210,453,150,38,"Chunker","512 tok/overlap",a)
    svg += box(380,453,150,38,"Embedder","text-embedding-3",a)
    svg += box(550,453,150,38,"Re-ranker","cross-encoder",a)
    svg += box(720,453,140,38,"Eval Metrics","RAGAS/faithfulness",i)
    svg += arr(190,472,210,472,a,"split")
    svg += arr(360,472,380,472,a,"embed")
    svg += arr(530,472,550,472,a,"rank")
    svg += arr(700,472,720,472,i,"eval")
    return svg, "Architecture Diagram"

# ─── CI/CD ───────────────────────────────────────────────────────────────────
def make_cicd(p):
    c,s,a,d,i = p["p"],p["s"],p["a"],p["d"],p["i"]
    svg = ""
    # Top pipeline flow
    stages = [
        (55, "💻","Code","git push",c),
        (170,"🔍","Lint+Test","pytest/jest",s),
        (285,"🏗️","Build","docker build",a),
        (400,"🛡️","Scan","trivy/snyk",d),
        (515,"📦","Artifact","ECR/registry",i),
        (630,"🚀","Deploy","helm upgrade",c),
        (745,"✅","Verify","smoke tests",s),
    ]
    for x,ico,lbl,sub,col in stages:
        svg += f'<circle cx="{x+45}" cy="155" r="36" fill="{col}" fill-opacity="0.12" stroke="{col}" stroke-width="2"/>'
        svg += f'<text x="{x+45}" y="148" text-anchor="middle" font-size="20" font-family="Arial,sans-serif">{ico}</text>'
        svg += f'<text x="{x+45}" y="166" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        svg += f'<text x="{x+45}" y="178" text-anchor="middle" fill="#64748B" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
        if x < 745:
            svg += arr(x+81,155,x+119,155,col)
    # Environments row
    svg += section(20,210,270,120,"ENVIRONMENTS",i)
    svg += box(35,230,115,40,"Development","feature branches",i)
    svg += box(35,280,115,40,"Staging","pre-production",a)
    svg += box(160,230,115,40,"Production","blue/green",c)
    svg += box(160,280,115,40,"DR","failover region",d)
    svg += arr(150,250,160,250,i)
    svg += arr(150,300,160,300,a)
    # Quality Gates
    svg += section(305,210,270,120,"QUALITY GATES",a)
    svg += box(320,230,110,40,"Coverage","greater 80 pct",c)
    svg += box(320,280,110,40,"Perf Budget","LCP less 2.5s",a)
    svg += box(445,230,110,40,"SAST/DAST","sec scan",d)
    svg += box(445,280,110,40,"Load Test","k6/Gatling",s)
    # Rollout strategies
    svg += section(590,210,290,120,"ROLLOUT STRATEGY",c)
    svg += box(605,230,120,40,"Canary","5 pct to 100 pct",c)
    svg += box(605,280,120,40,"Blue/Green","instant switch",s)
    svg += box(740,230,120,40,"Feature Flag","LaunchDarkly",a)
    svg += box(740,280,120,40,"A/B Test","traffic split",i)
    # Observability
    svg += section(20,348,860,90,"OBSERVABILITY AND ALERTING",d)
    tools = [("📊","Prometheus","metrics",50,d),("📈","Grafana","dashboards",180,s),
             ("🔍","Jaeger","tracing",310,i),("📋","ELK Stack","logs",440,a),
             ("🚨","PagerDuty","alerts",570,d),("💬","Slack","notify",700,c),("📝","JIRA","tickets",830,s)]
    for ico,lbl,sub,x,col in tools:
        svg += f'<text x="{x}" y="385" text-anchor="middle" font-size="16" font-family="Arial,sans-serif">{ico}</text>'
        svg += f'<text x="{x}" y="400" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        svg += f'<text x="{x}" y="413" text-anchor="middle" fill="#64748B" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
    # Rollback flow
    svg += section(20,450,860,48,"AUTO-ROLLBACK: Error rate greater 1pct  ➜  PagerDuty alert  ➜  Helm rollback  ➜  DNS failover  ➜  Incident ticket",d)
    return svg, "Pipeline Architecture"

# ─── RAG ─────────────────────────────────────────────────────────────────────
def make_rag(p):
    c,s,a,d,i = p["p"],p["s"],p["a"],p["d"],p["i"]
    svg = ""
    # Sources
    svg += section(15,85,145,340,"DATA SOURCES",s)
    sources = [(108,115,"📄","PDFs"),(108,170,"🌐","Web"),(108,225,"🗄️","Databases"),(108,280,"📧","Email"),(108,335,"🎥","Media")]
    for x,y,ico,lbl in sources:
        svg += f'<circle cx="{x}" cy="{y}" r="20" fill="{s}" fill-opacity="0.12" stroke="{s}" stroke-width="1.5"/>'
        svg += f'<text x="{x}" y="{y+5}" text-anchor="middle" font-size="14" font-family="Arial,sans-serif">{ico}</text>'
        svg += f'<text x="{x}" y="{y+32}" text-anchor="middle" fill="white" font-size="9" font-family="Arial,sans-serif">{lbl}</text>'
        svg += arr(128,y,165,y,s,"ingest")
    # Ingestion pipeline
    svg += section(165,85,220,340,"INGESTION",a)
    svg += box(178,105,190,60,"Chunker","512 tok, 50 overlap",a)
    svg += box(178,183,190,60,"Embedder","text-embed-3-large",a)
    svg += box(178,261,190,60,"Metadata","source/date/type",a)
    svg += box(178,339,190,55,"Dedup","hash-based",a)
    svg += arr(273,165,273,183,a)
    svg += arr(273,243,273,261,a)
    svg += arr(273,321,273,339,a)
    # Vector Store
    svg += section(400,85,170,340,"VECTOR STORE",c)
    svg += box(415,105,140,60,"Index","HNSW graph",c)
    svg += box(415,183,140,60,"Vector DB","Pinecone/Weaviate",c)
    svg += box(415,261,140,60,"BM25 Index","sparse vectors",c)
    svg += box(415,339,140,55,"Cache","query results",i)
    svg += arr(368,135,415,135,a,"store")
    svg += arr(368,213,415,213,a,"index")
    svg += arr(368,291,415,291,a,"sparse")
    # Retrieval
    svg += section(585,85,175,340,"RETRIEVAL",d)
    svg += box(600,105,145,60,"Query Analyzer","intent+expansion",d)
    svg += box(600,183,145,60,"HyDE","hypothetical doc",d)
    svg += box(600,261,145,60,"ANN Search","cosine similarity",d)
    svg += box(600,339,145,55,"Re-ranker","cross-encoder",d)
    svg += arr(555,135,600,135,c,"query")
    svg += arr(555,213,600,213,c,"expand")
    svg += arr(555,291,600,291,c,"search")
    svg += arr(555,366,600,366,c,"rank")
    svg += arr(672,165,672,183,d)
    svg += arr(672,243,672,261,d)
    svg += arr(672,321,672,339,d)
    # Generation
    svg += section(775,85,110,340,"GENERATION",i)
    svg += box(783,105,95,60,"LLM","GPT-4/Claude",i)
    svg += box(783,183,95,60,"Guardrails","safety filter",i)
    svg += box(783,261,95,60,"Citations","source refs",i)
    svg += box(783,339,95,55,"Feedback","RLHF loop",s)
    svg += arr(745,135,783,135,d,"context")
    svg += arr(745,213,783,213,d)
    svg += arr(745,291,783,291,d)
    svg += arr(745,366,783,366,d)
    # Eval bar
    svg += section(15,440,870,55,"EVALUATION: Faithfulness | Answer Relevance | Context Recall | RAGAS Score | Latency p95 | Hallucination Rate",c)
    return svg, "System Architecture"

# ─── KAFKA ───────────────────────────────────────────────────────────────────
def make_kafka(p):
    c,s,a,d,i = p["p"],p["s"],p["a"],p["d"],p["i"]
    svg = ""
    # Producers
    svg += section(15,85,155,180,"PRODUCERS",s)
    svg += box(25,105,130,40,"App Server","REST events",s)
    svg += box(25,155,130,40,"IoT Sensors","MQTT bridge",s)
    svg += box(25,205,130,40,"DB CDC","Debezium",a)
    for y in [125,175,225]:
        svg += arr(155,y,210,y,s,"produce")
    # Kafka Cluster
    svg += section(210,85,310,180,"KAFKA CLUSTER",c)
    svg += box(225,105,85,160,"Broker 1","leader",c)
    svg += box(320,105,85,160,"Broker 2","follower",c)
    svg += box(415,105,85,160,"Broker 3","follower",c)
    svg += f'<text x="365" y="220" text-anchor="middle" fill="{a}" font-size="9" font-weight="bold" font-family="Arial,sans-serif">Replication factor: 3</text>'
    svg += f'<text x="365" y="233" text-anchor="middle" fill="#475569" font-size="8" font-family="Arial,sans-serif">6 partitions | retention: 7d</text>'
    # Schema Registry
    svg += box(530,85,120,60,"Schema Reg","Avro/Protobuf",i)
    svg += box(530,155,120,60,"Kafka Connect","source/sink",i)
    svg += box(530,225,120,40,"Kafka UI","monitor",a)
    svg += arr(500,165,530,165,c,"validate")
    # Stream Processing
    svg += section(670,85,215,180,"STREAM PROCESSING",a)
    svg += box(685,105,185,50,"Apache Flink","stateful streaming",a)
    svg += box(685,165,185,50,"Spark Streaming","micro-batch 1s",a)
    svg += box(685,225,185,40,"KSQL","SQL on Kafka",i)
    svg += arr(660,135,685,135,c,"consume")
    svg += arr(660,190,685,190,c,"consume")
    # Consumers/Sinks
    svg += section(15,285,870,100,"CONSUMER GROUPS AND SINKS",d)
    sinks = [(60,"🏞️","Data Lake","S3/GCS",d),(190,"📊","ClickHouse","analytics",d),
             (320,"🔍","OpenSearch","full-text",s),(450,"🤖","ML Platform","features",a),
             (580,"📡","Real-time","dashboards",i),(710,"🚨","Alerting","PagerDuty",d),(840,"⚡","Cache","Redis",c)]
    for x,ico,lbl,sub,col in sinks:
        svg += f'<text x="{x}" y="315" text-anchor="middle" font-size="16" font-family="Arial,sans-serif">{ico}</text>'
        svg += f'<text x="{x}" y="333" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        svg += f'<text x="{x}" y="346" text-anchor="middle" fill="#64748B" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
        svg += arr(x,362,x,380,col,"",True)
    # Ops bar
    svg += section(15,400,870,90,"OPERATIONS",s)
    ops = [(100,"📊","Burrow","lag monitor"),(250,"🔐","mTLS","encryption"),(400,"📏","Quotas","throttle"),(550,"🔄","MirrorMaker","geo-replicate"),(700,"📋","Audit","compliance"),(830,"💰","Cost","optimization")]
    for x,ico,lbl,sub in ops:
        svg += f'<text x="{x}" y="430" text-anchor="middle" font-size="14">{ico}</text>'
        svg += f'<text x="{x}" y="448" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        svg += f'<text x="{x}" y="461" text-anchor="middle" fill="#64748B" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
    return svg, "Streaming Architecture"

# ─── ZERO TRUST ──────────────────────────────────────────────────────────────
def make_zero_trust(p):
    c,s,a,d,i = p["p"],p["s"],p["a"],p["d"],p["i"]
    svg = ""
    # Policy Engine center
    svg += f'<circle cx="450" cy="270" r="65" fill="{d}" fill-opacity="0.08" stroke="{d}" stroke-width="2" stroke-dasharray="6,3"/>'
    svg += f'<circle cx="450" cy="270" r="45" fill="{d}" fill-opacity="0.12" stroke="{d}" stroke-width="1.5"/>'
    svg += f'<text x="450" y="263" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">Policy</text>'
    svg += f'<text x="450" y="278" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">Engine</text>'
    svg += f'<text x="450" y="292" text-anchor="middle" fill="{d}" font-size="8" font-family="Arial,sans-serif">PDP / PEP</text>'
    # Surrounding nodes
    nodes = [
        (450,110,"🔑","Identity","SSO/MFA/RBAC",s,450,205),
        (700,175,"💻","Device Trust","MDM/posture check",a,515,235),
        (750,310,"🌐","Network","microsegmentation",i,515,280),
        (600,440,"📱","Workload","container/function",c,490,325),
        (300,440,"🔐","Data","classify/encrypt",a,410,325),
        (150,310,"⚔️","WAF/Firewall","L7 inspection",s,385,280),
        (200,175,"📡","Monitoring","SIEM/SOAR",i,385,235),
    ]
    for nx,ny,ico,lbl,sub,col,ax,ay in nodes:
        svg += f'<circle cx="{nx}" cy="{ny}" r="50" fill="{col}" fill-opacity="0.08" stroke="{col}" stroke-width="1.5"/>'
        svg += f'<text x="{nx}" y="{ny-8}" text-anchor="middle" font-size="20" font-family="Arial,sans-serif">{ico}</text>'
        svg += f'<text x="{nx}" y="{ny+10}" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        svg += f'<text x="{nx}" y="{ny+24}" text-anchor="middle" fill="#64748B" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
        svg += arr(ax,ay,450,270,col,"verify",True)
    # Banner
    svg += section(15,490,870,45,"PRINCIPLE: Never Trust, Always Verify   |   Least Privilege Access   |   Assume Breach   |   Continuous Monitoring",d)
    return svg, "Security Architecture"

# ─── AWS ─────────────────────────────────────────────────────────────────────
def make_aws(p):
    c,s,a,d,i = p["p"],p["s"],p["a"],p["d"],p["i"]
    svg = ""
    # Client
    svg += section(15,85,870,55,"CLIENT",i)
    for x,ico,lbl in [(80,"🌐","Browser"),(220,"📱","Mobile"),(360,"💻","CLI/SDK"),(500,"🤝","Partners"),(640,"🤖","IoT"),(780,"🔌","Webhooks")]:
        svg += f'<text x="{x}" y="108" text-anchor="middle" font-size="16">{ico}</text>'
        svg += f'<text x="{x}" y="126" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
    # Edge
    svg += section(15,150,870,65,"EDGE LAYER",s)
    svg += box(25,162,155,42,"CloudFront","global CDN / PoPs",s)
    svg += box(190,162,130,42,"Route 53","DNS + health check",s)
    svg += box(330,162,130,42,"WAF + Shield","DDoS L3/L7",d)
    svg += box(470,162,130,42,"ACM","TLS certificates",a)
    svg += box(610,162,150,42,"API Gateway","REST/WS/HTTP",s)
    svg += box(770,162,110,42,"Cognito","auth/federation",i)
    svg += arr(180,183,190,183,s)
    svg += arr(320,183,330,183,s)
    svg += arr(460,183,470,183,d)
    svg += arr(600,183,610,183,a)
    svg += arr(760,183,770,183,s)
    # Compute
    svg += section(15,228,430,130,"COMPUTE",c)
    svg += box(25,248,125,45,"Lambda","serverless FaaS",c)
    svg += box(160,248,130,45,"ECS/Fargate","containers",c)
    svg += box(300,248,135,45,"EKS","managed K8s",c)
    svg += box(25,303,125,45,"Step Functions","orchestration",a)
    svg += box(160,303,130,45,"App Runner","web services",a)
    svg += box(300,303,135,45,"Batch","job queues",a)
    # Messaging
    svg += section(455,228,435,130,"MESSAGING",s)
    svg += box(465,248,125,45,"SQS","queue/decouple",s)
    svg += box(600,248,120,45,"SNS","pub/sub",s)
    svg += box(730,248,145,45,"EventBridge","event bus",s)
    svg += box(465,303,125,45,"Kinesis","data streams",i)
    svg += box(600,303,120,45,"MSK","managed Kafka",i)
    svg += box(730,303,145,45,"SES","email service",a)
    svg += arr(450,275,465,275,c,"events")
    # Data
    svg += section(15,370,430,115,"DATA AND STORAGE",d)
    svg += box(25,388,95,42,"S3","object store",d)
    svg += box(130,388,100,42,"DynamoDB","NoSQL/DAX",d)
    svg += box(240,388,100,42,"RDS Aurora","MySQL/PG",d)
    svg += box(350,388,85,42,"ElastiCache","Redis",d)
    svg += box(25,438,95,38,"Redshift","warehouse",a)
    svg += box(130,438,100,38,"OpenSearch","search",a)
    svg += box(240,438,100,38,"Timestream","time series",a)
    svg += box(350,438,85,38,"Glue","ETL catalog",a)
    # Security
    svg += section(455,370,435,115,"SECURITY AND OBSERVABILITY",i)
    svg += box(465,388,95,42,"IAM","access ctrl",d)
    svg += box(570,388,95,42,"CloudWatch","metrics/logs",i)
    svg += box(675,388,95,42,"CloudTrail","audit",i)
    svg += box(780,388,100,42,"GuardDuty","threat detect",d)
    svg += box(465,438,95,38,"Secrets Mgr","creds rotate",a)
    svg += box(570,438,95,38,"X-Ray","tracing",i)
    svg += box(675,438,95,38,"Config","compliance",s)
    svg += box(780,438,100,38,"Macie","data security",a)
    return svg, "Cloud Architecture"

# ─── DEVSECOPS ────────────────────────────────────────────────────────────────
def make_devsecops(p):
    c,s,a,d,i = p["p"],p["s"],p["a"],p["d"],p["i"]
    svg = ""
    phases = [
        (50,"IDE","Pre-commit","git-secrets\ngit-leaks","💻",c),
        (175,"SCM","Code Review","SAST\nSemgrep","📝",s),
        (300,"Build","Compile","Dependency\nSCA check","🏗️",a),
        (425,"Test","Quality","DAST\nZAP scan","🧪",i),
        (550,"Artifact","Registry","Container\nScan: Trivy","📦",d),
        (675,"Staging","Deploy","IaC Scan\nTerraform","🚀",c),
        (800,"Prod","Monitor","Runtime\nFalco/SIEM","🛡️",s),
    ]
    for x,env,phase,tools,ico,col in phases:
        svg += f'<rect x="{x}" y="88" width="100" height="200" rx="10" fill="{col}" fill-opacity="0.06" stroke="{col}" stroke-width="1.5"/>'
        svg += f'<rect x="{x}" y="88" width="100" height="28" rx="8" fill="{col}" fill-opacity="0.3"/>'
        svg += f'<text x="{x+50}" y="106" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{env}</text>'
        svg += f'<text x="{x+50}" y="140" text-anchor="middle" font-size="24" font-family="Arial,sans-serif">{ico}</text>'
        svg += f'<text x="{x+50}" y="162" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{phase}</text>'
        for li,t in enumerate(tools.split("\n")):
            svg += f'<text x="{x+50}" y="{198+li*18}" text-anchor="middle" fill="{col}" font-size="9" font-family="Arial,sans-serif">{t}</text>'
        if x < 800:
            svg += arr(x+100,188,x+125,188,col)
    # Gates row
    svg += section(15,305,870,80,"SECURITY GATES — Fail pipeline on critical findings",d)
    gates = [(80,"🔴","Critical CVE","block merge"),(220,"🟠","Secrets","block build"),
             (360,"🟡","OWASP Top10","block deploy"),(500,"🔵","Compliance","block release"),
             (640,"🟢","Pen Test","quarterly"),(780,"⚪","Audit Log","always")]
    for x,ico,lbl,action in gates:
        svg += f'<text x="{x}" y="335" text-anchor="middle" font-size="16">{ico}</text>'
        svg += f'<text x="{x}" y="353" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        svg += f'<text x="{x}" y="368" text-anchor="middle" fill="#64748B" font-size="8" font-family="Arial,sans-serif">{action}</text>'
    # SIEM/Response
    svg += section(15,400,430,90,"SIEM AND INCIDENT RESPONSE",d)
    svg += box(25,420,120,55,"SIEM","Splunk/Sentinel",d)
    svg += box(155,420,120,55,"SOAR","auto-remediate",s)
    svg += box(285,420,120,55,"Threat Intel","feeds/IOCs",a)
    svg += box(415,420,20,55,"","",d)
    svg += arr(145,447,155,447,d,"correlate")
    svg += arr(275,447,285,447,s,"respond")
    svg += section(455,400,430,90,"COMPLIANCE AND POLICY",i)
    svg += box(465,420,120,55,"CIS Benchmarks","hardening",i)
    svg += box(595,420,120,55,"SOC2/ISO27001","audit ready",i)
    svg += box(725,420,145,55,"OPA/Rego","policy as code",a)
    return svg, "Security Pipeline"

# ─── SYSTEM DESIGN ────────────────────────────────────────────────────────────
def make_system_design(p):
    c,s,a,d,i = p["p"],p["s"],p["a"],p["d"],p["i"]
    svg = ""
    # Client
    svg += section(15,85,870,55,"CLIENTS",i)
    for x,lbl in [(100,"Web Browser"),(280,"Mobile App"),(460,"Desktop App"),(640,"Third-party API"),(820,"IoT Device")]:
        svg += f'<text x="{x}" y="118" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
    # CDN + LB
    svg += section(15,150,430,65,"EDGE",s)
    svg += box(25,163,200,42,"CDN","CloudFront/Akamai",s)
    svg += box(235,163,200,42,"Load Balancer","L7/health checks",s)
    svg += arr(225,184,235,184,s,"cache")
    svg += section(455,150,430,65,"AUTH",d)
    svg += box(465,163,190,42,"API Gateway","rate limit/route",d)
    svg += box(665,163,205,42,"Auth Service","OAuth2/JWT/SSO",d)
    svg += arr(655,184,665,184,d,"auth")
    # Services
    svg += section(15,228,870,120,"MICROSERVICES LAYER",c)
    services = [(40,"User Service","CRUD/profile"),(170,"Order Service","cart/checkout"),(300,"Payment Service","Stripe/PCI"),(430,"Notification","email/SMS/push"),(560,"Search Service","Elasticsearch"),(690,"Recommend","ML-powered"),(820,"Analytics","events/metrics")]
    for x,lbl,sub in services:
        svg += box(x,245,115,85,lbl,sub,c)
    for x in [155,285,415,545,675,805]:
        svg += arr(x,287,x+15,287,c)
    # Message Queue
    svg += section(15,362,870,60,"MESSAGE BROKER",a)
    svg += box(30,375,150,38,"Kafka","event streaming",a)
    svg += box(195,375,150,38,"RabbitMQ","task queues",a)
    svg += box(360,375,150,38,"Redis Pub/Sub","real-time events",i)
    svg += box(525,375,160,38,"Dead Letter Q","failed messages",d)
    svg += box(700,375,165,38,"Event Sourcing","audit stream",s)
    # Data
    svg += section(15,435,870,55,"DATA LAYER",d)
    data = [(65,"PostgreSQL","primary OLTP"),(200,"Redis","cache/session"),(335,"MongoDB","document store"),(470,"S3","blob/media"),(605,"Elasticsearch","search index"),(740,"ClickHouse","analytics OLAP"),(875,"Snowflake","data warehouse")]
    for x,lbl,sub in data:
        if x < 880:
            svg += f'<text x="{x}" y="458" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
            svg += f'<text x="{x}" y="472" text-anchor="middle" fill="{d}" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
    return svg, "System Architecture"

# ─── MLOPS ────────────────────────────────────────────────────────────────────
def make_mlops(p):
    c,s,a,d,i = p["p"],p["s"],p["a"],p["d"],p["i"]
    svg = ""
    # Data pipeline
    svg += section(15,85,870,100,"DATA PIPELINE",s)
    svg += box(25,100,140,65,"Data Sources","S3/DB/APIs",s)
    svg += box(180,100,140,65,"Feature Store","Feast/Tecton",s)
    svg += box(335,100,140,65,"Data Validation","Great Expectations",a)
    svg += box(490,100,140,65,"Feature Eng","Spark/dbt",a)
    svg += box(645,100,120,65,"Data Version","DVC/Delta",i)
    svg += box(780,100,100,65,"Monitoring","data drift",d)
    svg += arr(165,132,180,132,s,"ingest")
    svg += arr(320,132,335,132,s,"validate")
    svg += arr(475,132,490,132,a,"engineer")
    svg += arr(630,132,645,132,a,"version")
    svg += arr(765,132,780,132,i,"monitor")
    # Training
    svg += section(15,198,870,100,"TRAINING AND EXPERIMENTATION",c)
    svg += box(25,213,140,65,"Experiment","MLflow/W and B",c)
    svg += box(180,213,140,65,"Training","GPU cluster",c)
    svg += box(335,213,140,65,"Hyperparams","Optuna/Ray",c)
    svg += box(490,213,140,65,"Eval Metrics","F1/AUC/BLEU",a)
    svg += box(645,213,120,65,"Model Reg","MLflow/HF Hub",i)
    svg += box(780,213,100,65,"A/B Testing","champion/chall",d)
    svg += arr(165,245,180,245,c,"track")
    svg += arr(320,245,335,245,c,"tune")
    svg += arr(475,245,490,245,c,"evaluate")
    svg += arr(630,245,645,245,a,"register")
    svg += arr(765,245,780,245,i,"compare")
    # Serving
    svg += section(15,311,870,100,"MODEL SERVING",d)
    svg += box(25,326,140,65,"Online Serving","FastAPI/TorchServe",d)
    svg += box(180,326,140,65,"Batch Inference","Spark/Ray",d)
    svg += box(335,326,140,65,"Streaming","Kafka+Model",d)
    svg += box(490,326,140,65,"Edge Deploy","ONNX/TFLite",a)
    svg += box(645,326,120,65,"A/B Shadow","canary model",i)
    svg += box(780,326,100,65,"Rollback","auto revert",s)
    svg += arr(165,358,180,358,d,"serve")
    svg += arr(320,358,335,358,d)
    svg += arr(475,358,490,358,d)
    svg += arr(630,358,645,358,a)
    svg += arr(765,358,780,358,i)
    # Monitoring
    svg += section(15,424,870,65,"MONITORING AND FEEDBACK",i)
    mon = [(80,"Data Drift","PSI/KS test"),(220,"Model Perf","accuracy/F1"),(360,"Latency","p50/p95/p99"),
           (500,"Concept Drift","retraining trigger"),(640,"Explainability","SHAP/LIME"),(780,"Cost","GPU/token spend")]
    for x,lbl,sub in mon:
        svg += f'<text x="{x}" y="450" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        svg += f'<text x="{x}" y="464" text-anchor="middle" fill="{i}" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
    svg += curve(850,424,850,85,i,"retrain",True)
    return svg, "MLOps Pipeline"

# ─── DATA LAKEHOUSE ───────────────────────────────────────────────────────────
def make_lakehouse(p):
    c,s,a,d,i = p["p"],p["s"],p["a"],p["d"],p["i"]
    svg = ""
    svg += section(15,85,870,80,"INGESTION",s)
    sources = [(60,"📊","Batch ETL","Airflow/Glue"),(180,"🌊","Streaming","Kafka/Kinesis"),(300,"🔌","CDC","Debezium"),(420,"📡","API Pull","REST/GraphQL"),(540,"📂","File Drop","S3 trigger"),(660,"🤖","IoT","MQTT bridge"),(790,"📱","App Events","SDK capture")]
    for x,ico,lbl,sub in sources:
        svg += f'<text x="{x}" y="115" text-anchor="middle" font-size="18">{ico}</text>'
        svg += f'<text x="{x}" y="133" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        svg += f'<text x="{x}" y="147" text-anchor="middle" fill="{s}" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
        svg += arr(x,162,x,178,s,"",True)
    svg += section(15,178,870,100,"OPEN TABLE FORMAT LAYER",c)
    svg += box(30,193,200,70,"Delta Lake","ACID + time travel",c)
    svg += box(245,193,200,70,"Apache Iceberg","schema evolution",c)
    svg += box(460,193,200,70,"Apache Hudi","upserts/deletes",c)
    svg += box(675,193,200,70,"Metadata Catalog","Glue/Hive Metastore",a)
    svg += arr(230,228,245,228,c,"or")
    svg += arr(445,228,460,228,c,"or")
    svg += arr(660,228,675,228,a,"catalog")
    svg += section(15,292,870,100,"COMPUTE ENGINE",a)
    svg += box(30,307,190,70,"Apache Spark","SQL/ML/streaming",a)
    svg += box(235,307,170,70,"Trino/Presto","interactive SQL",a)
    svg += box(420,307,170,70,"dbt","transform/test",a)
    svg += box(605,307,170,70,"Ray","ML distributed",i)
    svg += box(790,307,90,70,"Flink","stream proc",i)
    svg += section(15,405,870,80,"CONSUMPTION LAYER",d)
    consumers = [(80,"📊","BI Tools","Tableau/Superset"),(230,"🤖","ML Platform","SageMaker/Vertex"),(380,"🔍","Ad-hoc SQL","Athena/BigQuery"),(530,"📈","Dashboards","Grafana/Looker"),(680,"📡","Data APIs","REST/GraphQL"),(820,"⚡","Streaming","real-time feeds")]
    for x,ico,lbl,sub in consumers:
        svg += f'<text x="{x}" y="433" text-anchor="middle" font-size="16">{ico}</text>'
        svg += f'<text x="{x}" y="451" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        svg += f'<text x="{x}" y="465" text-anchor="middle" fill="{d}" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
    return svg, "Data Architecture"

# ─── GENERIC FALLBACK ────────────────────────────────────────────────────────
def make_generic(topic_name, p):
    c,s,a,d,i = p["p"],p["s"],p["a"],p["d"],p["i"]
    svg = ""
    svg += section(15,85,870,60,"CLIENT AND EDGE",i)
    for x,lbl,sub in [(90,"Web/Mobile","React/Native"),(260,"CDN","CloudFront"),(430,"API Gateway","rate limit"),(600,"Auth","OAuth2/JWT"),(770,"DNS","Route 53")]:
        svg += box(x-70,98,140,38,lbl,sub,i)
        if x < 770: svg += arr(x+70,117,x+90,117,i)
    svg += section(15,160,430,130,"MICROSERVICES",c)
    for y,lbl,sub in [(178,"User Service","auth/profile"),(228,"Order Service","cart/payment"),(278,"Notification","email/SMS/push")]:
        svg += box(25,y,185,42,lbl,sub,c)
        svg += box(225,y,205,42,lbl.replace("Service","Worker"),"async processing",a)
        svg += arr(210,y+21,225,y+21,c,"async")
    svg += section(455,160,430,130,"DATA SERVICES",d)
    for y,lbl,sub in [(178,"Search","Elasticsearch"),(228,"Analytics","ClickHouse"),(278,"ML/AI","model serving")]:
        svg += box(465,y,195,42,lbl,sub,d)
        svg += box(670,y,200,42,sub.split("/")[0],"primary store",s)
        svg += arr(660,y+21,670,y+21,d,"query")
    svg += section(15,305,870,80,"MESSAGE LAYER",a)
    for x,lbl,sub in [(90,"Kafka","event stream"),(260,"RabbitMQ","task queue"),(430,"Redis","cache/pub-sub"),(600,"SQS","managed queue"),(770,"EventBridge","event bus")]:
        svg += box(x-70,320,140,52,lbl,sub,a)
        if x < 770: svg += arr(x+70,346,x+90,346,a)
    svg += section(15,400,870,90,"DATA STORES",d)
    for x,lbl,sub in [(90,"PostgreSQL","OLTP/primary"),(240,"Redis","sessions"),(390,"MongoDB","documents"),(540,"S3","blobs/media"),(690,"Redshift","analytics"),(830,"Cassandra","time-series")]:
        svg += box(x-65,415,130,65,lbl,sub,d)
    return svg, "System Architecture"

# ─── MAIN ────────────────────────────────────────────────────────────────────
def make_diagram(topic_name, topic_id, diagram_type):
    p = get_palette(topic_id)
    tid = topic_id.lower()
    now = datetime.now().strftime("%B %Y")

    if "kube" in tid: content, subtitle = make_kubernetes(p)
    elif "llm" in tid or "agent" in tid: content, subtitle = make_llm(p)
    elif "cicd" in tid: content, subtitle = make_cicd(p)
    elif "kafka" in tid: content, subtitle = make_kafka(p)
    elif "zero" in tid: content, subtitle = make_zero_trust(p)
    elif "aws" in tid: content, subtitle = make_aws(p)
    elif "devsec" in tid: content, subtitle = make_devsecops(p)
    elif "system" in tid: content, subtitle = make_system_design(p)
    elif "mlops" in tid: content, subtitle = make_mlops(p)
    elif "lake" in tid or "data" in tid: content, subtitle = make_lakehouse(p)
    elif "rag" in tid: content, subtitle = make_rag(p)
    else: content, subtitle = make_generic(topic_name, p)

    all_colors = [p["p"],p["s"],p["a"],p["d"],p["i"]]
    return wrap_svg(content, topic_name, subtitle, p["p"], now, all_colors)


class DiagramGenerator:
    def __init__(self):
        Path(OUTPUT_DIR).mkdir(exist_ok=True)
        log.info("Diagram output directory: " + OUTPUT_DIR + "/")

    def save_svg(self, svg_content, topic_id, topic_name="", diagram_type="Architecture Diagram"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = OUTPUT_DIR + "/" + topic_id + "_" + timestamp + ".svg"
        svg = make_diagram(topic_name or topic_id, topic_id, diagram_type)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(svg)
        size_kb = os.path.getsize(filename) / 1024
        log.info("Diagram saved: " + filename + " (" + str(round(size_kb, 1)) + " KB)")
        return filename
