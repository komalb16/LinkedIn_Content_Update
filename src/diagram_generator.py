import os
from datetime import datetime
from pathlib import Path
from logger import get_logger

log = get_logger("diagrams")
OUTPUT_DIR = "diagrams"

PALETTES = {
    "ai":      {"bg":"#0F172A","c":["#7C3AED","#2563EB","#0891B2","#059669","#D97706","#DC2626"]},
    "cloud":   {"bg":"#0F172A","c":["#1D4ED8","#0891B2","#047857","#B45309","#7C3AED","#BE185D"]},
    "security":{"bg":"#0F172A","c":["#DC2626","#D97706","#7C3AED","#0891B2","#047857","#1D4ED8"]},
    "data":    {"bg":"#0F172A","c":["#7C3AED","#1D4ED8","#0891B2","#047857","#D97706","#DC2626"]},
    "devops":  {"bg":"#0F172A","c":["#047857","#1D4ED8","#7C3AED","#D97706","#DC2626","#0891B2"]},
    "default": {"bg":"#0F172A","c":["#1D4ED8","#7C3AED","#047857","#D97706","#DC2626","#0891B2"]},
}

def get_pal(tid):
    t = tid.lower()
    if any(x in t for x in ["llm","rag","agent","mlops"]): return PALETTES["ai"]
    if any(x in t for x in ["kube","docker","aws","cicd"]): return PALETTES["cloud"]
    if any(x in t for x in ["zero","devsec"]): return PALETTES["security"]
    if any(x in t for x in ["kafka","data","lake"]): return PALETTES["data"]
    return PALETTES["default"]

def fb(x,y,w,h,color,title,sub="",rx=10):
    s  = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}"/>'
    s += f'<rect x="{x}" y="{y}" width="{w}" height="4" rx="{rx}" fill="white" opacity="0.18"/>'
    if sub:
        s += f'<text x="{x+w//2}" y="{y+h//2-4}" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">{title}</text>'
        s += f'<text x="{x+w//2}" y="{y+h//2+10}" text-anchor="middle" fill="rgba(255,255,255,0.72)" font-size="9" font-family="Arial,sans-serif">{sub}</text>'
    else:
        s += f'<text x="{x+w//2}" y="{y+h//2+4}" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">{title}</text>'
    return s

def sf(x,y,w,h,label,color):
    lw = len(label)*7+20
    s  = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{color}" fill-opacity="0.08" stroke="{color}" stroke-width="2"/>'
    s += f'<rect x="{x+12}" y="{y-12}" width="{lw}" height="22" rx="6" fill="{color}"/>'
    s += f'<text x="{x+12+lw//2}" y="{y+5}" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">{label}</text>'
    return s

def ar(x1,y1,x2,y2,color="white",label="",dashed=False):
    dash='stroke-dasharray="6,4"' if dashed else ''
    cid=color.replace("#","").replace("(","").replace(")","").replace(",","")[:8]
    uid=f"{cid}{abs(x1)}{abs(y1)}"
    mx,my=(x1+x2)//2,(y1+y2)//2
    s =f'<defs><marker id="m{uid}" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="{color}"/></marker></defs>'
    s+=f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2" {dash} marker-end="url(#m{uid})"/>'
    if label:
        bw=len(label)*5+8
        s+=f'<rect x="{mx-bw//2}" y="{my-8}" width="{bw}" height="14" rx="4" fill="#1E293B" stroke="{color}" stroke-width="0.5"/>'
        s+=f'<text x="{mx}" y="{my+3}" text-anchor="middle" fill="{color}" font-size="8" font-family="Arial,sans-serif">{label}</text>'
    return s

def ic(cx,cy,r,icon,label,sub,color):
    s =f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>'
    s+=f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="white" stroke-width="1.5" opacity="0.2"/>'
    s+=f'<text x="{cx}" y="{cy+int(r*0.35)}" text-anchor="middle" font-size="{int(r*0.7)}" font-family="Arial,sans-serif">{icon}</text>'
    s+=f'<text x="{cx}" y="{cy+r+16}" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">{label}</text>'
    if sub:
        s+=f'<text x="{cx}" y="{cy+r+29}" text-anchor="middle" fill="#94A3B8" font-size="9" font-family="Arial,sans-serif">{sub}</text>'
    return s

def wrap(content,title,subtitle,accent,date_str):
    st=title.replace("&","and").replace("<","").replace(">","")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 550" width="900" height="550">
  <defs>
    <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M 32 0 L 0 0 0 32" fill="none" stroke="white" stroke-width="0.3" opacity="0.05"/></pattern>
    <linearGradient id="hdr" x1="0" x2="1"><stop offset="0%" stop-color="{accent}"/><stop offset="100%" stop-color="{accent}" stop-opacity="0.2"/></linearGradient>
    <linearGradient id="sig" x1="0" x2="1"><stop offset="0%" stop-color="#0EA5E9"/><stop offset="50%" stop-color="#8B5CF6"/><stop offset="100%" stop-color="#EC4899"/></linearGradient>
  </defs>
  <rect width="900" height="550" fill="#0F172A"/>
  <rect width="900" height="550" fill="url(#grid)"/>
  <rect x="0" y="0" width="900" height="5" fill="url(#hdr)"/>
  <circle cx="820" cy="100" r="180" fill="{accent}" opacity="0.04"/>
  <text x="20" y="36" fill="{accent}" font-size="10" font-weight="bold" font-family="Arial,sans-serif" letter-spacing="2" opacity="0.85">{subtitle.upper()}</text>
  <text x="450" y="68" text-anchor="middle" fill="white" font-size="22" font-weight="bold" font-family="Arial,sans-serif">{st}</text>
  <line x1="20" y1="78" x2="880" y2="78" stroke="white" stroke-width="0.5" opacity="0.1"/>
  {content}
  <line x1="20" y1="515" x2="880" y2="515" stroke="white" stroke-width="0.5" opacity="0.08"/>
  <text x="20" y="533" fill="#334155" font-size="9" font-family="Arial,sans-serif">{date_str}</text>
  <rect x="660" y="522" width="220" height="22" rx="11" fill="url(#sig)" fill-opacity="0.15" stroke="url(#sig)" stroke-width="1"/>
  <text x="750" y="537" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif" letter-spacing="0.5">&#10022; AI &#169; Komal Batra</text>
</svg>'''

def make_kubernetes(p):
    C=p["c"]; s=""
    s+=sf(20,88,860,110,"CONTROL PLANE",C[0])
    s+=fb(35,102,150,80,C[0],"API Server","entry point")
    s+=fb(200,102,150,80,C[1],"Scheduler","filters/scores")
    s+=fb(365,102,180,80,C[2],"Controller Mgr","reconciles state")
    s+=fb(560,102,120,80,C[3],"etcd","key-value store")
    s+=fb(695,102,170,80,C[4],"kubectl / UI","admin access")
    s+=ar(185,142,200,142,"white","schedules")
    s+=ar(350,142,365,142,"white")
    s+=ar(540,142,560,142,"#94A3B8","stores",True)
    s+=ar(695,142,665,142,"#94A3B8","request")
    s+=sf(20,210,415,180,"WORKER NODE 1",C[1])
    s+=fb(35,228,125,55,C[1],"Kubelet","node agent")
    s+=fb(175,228,130,55,C[2],"Kube-proxy","iptables/IPVS")
    s+=fb(35,295,90,82,C[0],"Pod A","nginx:latest")
    s+=fb(140,295,90,82,C[3],"Pod B","app:v2")
    s+=fb(245,295,90,82,C[4],"Pod C","worker:v1")
    s+=fb(350,295,75,82,C[5],"CNI","Calico")
    s+=ar(160,255,175,255,"white","manages")
    s+=ar(110,282,110,295,"#94A3B8","runs",True)
    s+=sf(450,210,430,180,"WORKER NODE 2",C[2])
    s+=fb(465,228,125,55,C[1],"Kubelet","node agent")
    s+=fb(605,228,130,55,C[2],"Kube-proxy","networking")
    s+=fb(465,295,90,82,C[0],"Pod D","db:v3")
    s+=fb(565,295,90,82,C[3],"Pod E","cache:v1")
    s+=fb(665,295,90,82,C[4],"Pod F","api:v2")
    s+=fb(770,295,95,82,C[5],"Ingress","NGINX LB")
    s+=ar(590,255,605,255,"white","manages")
    s+=ar(110,182,110,210,"#94A3B8","",True)
    s+=ar(665,182,665,210,"#94A3B8","",True)
    s+=sf(20,404,270,95,"STORAGE",C[3])
    s+=fb(30,420,120,68,C[3],"PVC","volume claim")
    s+=fb(158,420,120,68,C[4],"PersistentVol","StorageClass")
    s+=ar(150,454,158,454,"white","binds")
    s+=sf(305,404,265,95,"AUTOSCALING",C[4])
    s+=fb(315,420,115,68,C[4],"HPA","CPU/mem based")
    s+=fb(445,420,115,68,C[5],"VPA","right-sizing")
    s+=ar(430,454,445,454,"white")
    s+=sf(585,404,295,95,"MONITORING",C[0])
    s+=fb(595,420,130,68,C[0],"Prometheus","metrics scrape")
    s+=fb(740,420,130,68,C[2],"Grafana","dashboards")
    s+=ar(730,454,740,454,"white","visualize")
    return s,"Cluster Architecture"

def make_llm(p):
    C=p["c"]; s=""
    s+=sf(15,88,145,340,"INPUT",C[1])
    s+=ic(87,135,28,"👤","User","queries",C[1])
    s+=ic(87,225,24,"📄","Documents","context",C[2])
    s+=ic(87,310,24,"🔌","APIs","tools/data",C[3])
    s+=sf(175,88,220,340,"ORCHESTRATION",C[0])
    s+=fb(188,108,190,62,C[0],"Prompt Manager","template/vars/history")
    s+=fb(188,185,190,62,C[1],"Memory Store","short+long term")
    s+=fb(188,263,190,62,C[2],"Tool Router","function calling")
    s+=fb(188,342,190,56,C[3],"Agent Loop","plan/act/observe")
    for y in [139,216,294,370]: s+=ar(163,y,188,y,"white")
    s+=sf(410,88,240,340,"LLM CORE",C[4])
    s+=fb(422,108,210,62,C[4],"Tokenizer","BPE encoding")
    s+=fb(422,185,210,62,C[5],"Transformer","32 attn heads")
    s+=fb(422,263,210,62,C[0],"FFN + Norm","feed-forward layers")
    s+=fb(422,342,210,56,C[1],"Sampler","temp/top-p/top-k")
    for y in [139,216,294,370]: s+=ar(378,y,422,y,"#94A3B8")
    for y in [170,247,325]: s+=ar(527,y,527,y+15,"#60A5FA","",True)
    s+=sf(665,88,215,340,"OUTPUT",C[2])
    s+=fb(675,108,190,62,C[2],"Streaming","SSE / tokens")
    s+=fb(675,185,190,62,C[3],"Structured","JSON / XML")
    s+=fb(675,263,190,62,C[4],"Tool Calls","function results")
    s+=fb(675,342,190,56,C[5],"Audit Log","trace/eval")
    for y in [139,216,294,370]: s+=ar(632,y,675,y,"white")
    s+=sf(15,442,865,58,"RAG LAYER",C[3])
    for i,(lbl,sub,col) in enumerate([("Vector DB","Pinecone",C[3]),("Chunker","512 tok",C[4]),("Embedder","text-embed-3",C[5]),("Re-ranker","cross-encoder",C[0]),("Eval","RAGAS",C[1])]):
        x=20+i*172
        s+=fb(x,454,162,36,col,lbl,sub,6)
    for x in [182,354,526,698]: s+=ar(x,472,x+10,472,"white")
    return s,"Architecture Diagram"

def make_cicd(p):
    C=p["c"]; s=""
    stages=[(75,"💻","Code","git push",C[0]),(195,"🔍","Lint+Test","pytest/jest",C[1]),(315,"🏗️","Build","docker build",C[2]),(435,"🛡️","Scan","trivy/snyk",C[3]),(555,"📦","Artifact","ECR/registry",C[4]),(675,"🚀","Deploy","helm upgrade",C[5]),(795,"✅","Verify","smoke tests",C[0])]
    for x,ico,lbl,sub,col in stages:
        s+=f'<circle cx="{x}" cy="155" r="38" fill="{col}"/>'
        s+=f'<circle cx="{x}" cy="155" r="38" fill="none" stroke="white" stroke-width="2" opacity="0.2"/>'
        s+=f'<text x="{x}" y="148" text-anchor="middle" font-size="22" font-family="Arial,sans-serif">{ico}</text>'
        s+=f'<text x="{x}" y="166" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        s+=f'<text x="{x}" y="179" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
        if x<795: s+=ar(x+38,155,x+82,155,"white")
    s+=sf(20,205,280,125,"ENVIRONMENTS",C[1])
    s+=fb(30,222,125,46,C[1],"Development","feature branches")
    s+=fb(30,276,125,46,C[2],"Staging","pre-production")
    s+=fb(165,222,125,46,C[0],"Production","blue/green")
    s+=fb(165,276,125,46,C[3],"DR Region","failover")
    s+=sf(315,205,270,125,"QUALITY GATES",C[2])
    s+=fb(325,222,115,46,C[2],"Coverage",">80% req")
    s+=fb(325,276,115,46,C[3],"Perf Budget","LCP < 2.5s")
    s+=fb(450,222,125,46,C[4],"SAST/DAST","sec scan")
    s+=fb(450,276,125,46,C[5],"Load Test","k6/Gatling")
    s+=sf(600,205,280,125,"ROLLOUT STRATEGY",C[4])
    s+=fb(610,222,125,46,C[4],"Canary","5% to 100%")
    s+=fb(610,276,125,46,C[0],"Blue/Green","instant switch")
    s+=fb(745,222,125,46,C[1],"Feature Flag","LaunchDarkly")
    s+=fb(745,276,125,46,C[5],"A/B Test","traffic split")
    s+=sf(20,345,860,95,"OBSERVABILITY AND ALERTING",C[3])
    obs=[("📊","Prometheus","metrics",C[3]),("📈","Grafana","dashboards",C[0]),("🔍","Jaeger","tracing",C[1]),("📋","ELK Stack","logs",C[2]),("🚨","PagerDuty","alerts",C[3]),("💬","Slack","notify",C[4]),("📝","JIRA","tickets",C[5])]
    w=860//len(obs)
    for i,(ico,lbl,sub,col) in enumerate(obs):
        cx=20+i*w+w//2
        s+=f'<text x="{cx}" y="380" text-anchor="middle" font-size="18" font-family="Arial,sans-serif">{ico}</text>'
        s+=f'<text x="{cx}" y="398" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        s+=f'<text x="{cx}" y="412" text-anchor="middle" fill="#94A3B8" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
    s+=f'<rect x="20" y="452" width="860" height="38" rx="8" fill="{C[3]}" opacity="0.15" stroke="{C[3]}" stroke-width="1.5"/>'
    s+=f'<text x="450" y="476" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">AUTO-ROLLBACK: Error &gt; 1%  &#8594;  Alert  &#8594;  Helm rollback  &#8594;  DNS failover  &#8594;  Incident</text>'
    return s,"Pipeline Architecture"

def make_kafka(p):
    C=p["c"]; s=""
    s+=sf(15,88,155,195,"PRODUCERS",C[1])
    s+=fb(25,106,130,50,C[1],"App Server","REST events")
    s+=fb(25,166,130,50,C[2],"IoT Sensors","MQTT bridge")
    s+=fb(25,226,130,50,C[3],"DB CDC","Debezium")
    for y in [131,191,251]: s+=ar(155,y,205,y,"white","produce")
    s+=sf(205,88,305,195,"KAFKA CLUSTER",C[0])
    for i,(lbl,role) in enumerate([("Broker 1","leader"),("Broker 2","follower"),("Broker 3","follower")]):
        s+=fb(215+i*97,106,87,165,C[i],lbl,role)
    s+=f'<text x="357" y="288" text-anchor="middle" fill="#94A3B8" font-size="9" font-family="Arial,sans-serif">RF:3 | 6 partitions | 7d retention</text>'
    s+=sf(525,88,145,195,"SCHEMA+CONNECT",C[4])
    s+=fb(535,106,125,70,C[4],"Schema Reg","Avro/Protobuf")
    s+=fb(535,185,125,70,C[5],"Kafka Connect","source+sink")
    s+=ar(510,140,535,140,"white","validate")
    s+=ar(510,220,535,220,"white","stream")
    s+=sf(685,88,200,195,"STREAM PROC",C[2])
    s+=fb(695,106,180,55,C[2],"Apache Flink","stateful streaming")
    s+=fb(695,170,180,55,C[3],"Spark Streaming","micro-batch 1s")
    s+=fb(695,233,180,42,C[4],"KSQL","SQL on Kafka")
    s+=ar(670,140,695,140,"white","consume")
    s+=ar(670,200,695,200,"white","consume")
    s+=sf(15,297,865,105,"CONSUMER GROUPS AND SINKS",C[3])
    sinks=[("🏞️","Data Lake","S3/GCS",C[3]),("📊","ClickHouse","analytics",C[4]),("🔍","OpenSearch","full-text",C[5]),("🤖","ML Platform","features",C[0]),("📡","Real-time","dashboards",C[1]),("🚨","Alerting","PagerDuty",C[2]),("⚡","Cache","Redis",C[3])]
    w=860//len(sinks)
    for i,(ico,lbl,sub,col) in enumerate(sinks):
        cx=20+i*w+w//2
        s+=f'<text x="{cx}" y="326" text-anchor="middle" font-size="18" font-family="Arial,sans-serif">{ico}</text>'
        s+=fb(cx-50,340,100,48,col,lbl,sub,7)
    s+=sf(15,415,865,80,"OPERATIONS",C[5])
    ops=[("📊","Burrow","lag"),("🔐","mTLS","encrypt"),("📏","Quotas","throttle"),("🔄","MirrorMaker","geo-rep"),("📋","Audit","compliance"),("💰","Cost","optimize")]
    w2=860//len(ops)
    for i,(ico,lbl,sub) in enumerate(ops):
        cx=20+i*w2+w2//2
        s+=f'<text x="{cx}" y="447" text-anchor="middle" font-size="16" font-family="Arial,sans-serif">{ico}</text>'
        s+=f'<text x="{cx}" y="463" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        s+=f'<text x="{cx}" y="477" text-anchor="middle" fill="#94A3B8" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
    return s,"Streaming Architecture"

def make_zero_trust(p):
    C=p["c"]; s=""; cx,cy=450,275
    s+=f'<circle cx="{cx}" cy="{cy}" r="70" fill="{C[0]}"/>'
    s+=f'<circle cx="{cx}" cy="{cy}" r="70" fill="none" stroke="white" stroke-width="2" opacity="0.25"/>'
    s+=f'<text x="{cx}" y="{cy-10}" text-anchor="middle" fill="white" font-size="13" font-weight="bold" font-family="Arial,sans-serif">Policy</text>'
    s+=f'<text x="{cx}" y="{cy+8}" text-anchor="middle" fill="white" font-size="13" font-weight="bold" font-family="Arial,sans-serif">Engine</text>'
    s+=f'<text x="{cx}" y="{cy+26}" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-size="9" font-family="Arial,sans-serif">PDP / PEP</text>'
    nodes=[(450,108,"🔑","Identity","SSO/MFA/RBAC",C[1],450,205),(710,170,"💻","Device Trust","MDM/posture",C[2],522,238),(755,310,"🌐","Network","microsegment",C[3],520,282),(605,435,"📱","Workload","containers",C[4],492,330),(295,435,"🔐","Data","classify+encrypt",C[5],408,330),(145,310,"⚔️","WAF","L7 inspect",C[1],380,282),(200,170,"📡","Monitoring","SIEM/SOAR",C[2],378,238)]
    for nx,ny,ico,lbl,sub,col,ax,ay in nodes:
        s+=f'<circle cx="{nx}" cy="{ny}" r="52" fill="{col}"/>'
        s+=f'<circle cx="{nx}" cy="{ny}" r="52" fill="none" stroke="white" stroke-width="1.5" opacity="0.2"/>'
        s+=f'<text x="{nx}" y="{ny-8}" text-anchor="middle" font-size="20" font-family="Arial,sans-serif">{ico}</text>'
        s+=f'<text x="{nx}" y="{ny+10}" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        s+=f'<text x="{nx}" y="{ny+24}" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-size="8" font-family="Arial,sans-serif">{sub}</text>'
        s+=ar(ax,ay,cx-12,cy-12,"#94A3B8","verify",True)
    s+=f'<rect x="15" y="495" width="865" height="40" rx="8" fill="{C[0]}" opacity="0.15" stroke="{C[0]}" stroke-width="1.5"/>'
    s+=f'<text x="450" y="520" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">Never Trust, Always Verify | Least Privilege | Assume Breach | Continuous Monitoring</text>'
    return s,"Security Architecture"

def make_aws(p):
    C=p["c"]; s=""
    s+=sf(15,88,865,55,"CLIENT LAYER",C[1])
    for x,ico,lbl in [(80,"🌐","Browser"),(210,"📱","Mobile"),(340,"💻","CLI/SDK"),(470,"🤝","Partners"),(600,"🤖","IoT"),(730,"🔌","Webhooks")]:
        s+=f'<text x="{x}" y="110" text-anchor="middle" font-size="16" font-family="Arial,sans-serif">{ico}</text>'
        s+=f'<text x="{x}" y="128" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
    s+=sf(15,155,865,55,"EDGE LAYER",C[0])
    for i,(x,lbl,sub,col) in enumerate([(30,"CloudFront","CDN/PoPs",C[0]),(185,"Route 53","DNS+health",C[1]),(330,"WAF+Shield","DDoS L3/L7",C[3]),(475,"ACM","TLS certs",C[2]),(620,"API Gateway","REST/WS",C[4]),(765,"Cognito","auth/federation",C[5])]):
        s+=fb(x,162,145,40,col,lbl,sub,7)
    for x in [175,320,465,610,755]: s+=ar(x,182,x+10,182,"white")
    s+=sf(15,222,425,115,"COMPUTE",C[2])
    for i,(x,lbl,sub,col) in enumerate([(25,"Lambda","serverless",C[2]),(165,"ECS/Fargate","containers",C[0]),(305,"EKS","managed K8s",C[1]),(25,"Step Func","orchestrate",C[3]),(165,"App Runner","web svcs",C[4]),(305,"Batch","job queues",C[5])]):
        s+=fb(x,238 if i<3 else 285,130,40,col,lbl,sub,7)
    s+=sf(450,222,430,115,"MESSAGING",C[4])
    for i,(x,lbl,sub,col) in enumerate([(460,"SQS","queues",C[4]),(595,"SNS","pub/sub",C[5]),(730,"EventBridge","event bus",C[0]),(460,"Kinesis","streaming",C[1]),(595,"MSK","Kafka",C[2]),(730,"SES","email",C[3])]):
        s+=fb(x,238 if i<3 else 285,125,40,col,lbl,sub,7)
    s+=sf(15,350,425,130,"DATA AND STORAGE",C[3])
    for i,(x,lbl,sub,col) in enumerate([(25,"S3","object store",C[3]),(130,"DynamoDB","NoSQL",C[4]),(235,"RDS Aurora","MySQL/PG",C[5]),(340,"ElastiCache","Redis",C[0]),(25,"Redshift","warehouse",C[1]),(130,"OpenSearch","search",C[2]),(235,"Timestream","time-series",C[3]),(340,"Glue","ETL",C[4])]):
        s+=fb(x,365 if i<4 else 410,100,40,col,lbl,sub,6)
    s+=sf(450,350,430,130,"SECURITY AND OBS",C[5])
    for i,(x,lbl,sub,col) in enumerate([(460,"IAM","access ctrl",C[5]),(570,"CloudWatch","metrics",C[0]),(680,"CloudTrail","audit",C[1]),(790,"GuardDuty","threats",C[2]),(460,"Secrets Mgr","creds",C[3]),(570,"X-Ray","tracing",C[4]),(680,"Config","compliance",C[5]),(790,"Macie","data sec",C[0])]):
        s+=fb(x,365 if i<4 else 410,100,40,col,lbl,sub,6)
    return s,"Cloud Architecture"

def make_mlops(p):
    C=p["c"]; s=""
    rows=[
        ("DATA PIPELINE",C[0],[("Data Sources","S3/DB/APIs",C[0]),("Feature Store","Feast/Tecton",C[1]),("Validation","Great Expect",C[2]),("Feature Eng","Spark/dbt",C[3]),("Data Version","DVC/Delta",C[4]),("Data Monitor","drift detect",C[5])]),
        ("TRAINING",C[1],[("Experiment","MLflow/W&B",C[1]),("Training","GPU cluster",C[2]),("Hyperparam","Optuna/Ray",C[3]),("Eval Metrics","F1/AUC/BLEU",C[4]),("Model Reg","HuggingFace",C[5]),("A/B Testing","champion/chall",C[0])]),
        ("SERVING",C[2],[("Online Serve","FastAPI/Triton",C[2]),("Batch Infer","Spark/Ray",C[3]),("Streaming","Kafka+Model",C[4]),("Edge Deploy","ONNX/TFLite",C[5]),("Shadow Test","canary model",C[0]),("Rollback","auto revert",C[1])]),
        ("MONITORING",C[3],[("Data Drift","PSI/KS test",C[3]),("Model Perf","accuracy/F1",C[4]),("Latency","p50/p95/p99",C[5]),("Concept Drift","retrain trig",C[0]),("Explainability","SHAP/LIME",C[1]),("Cost","GPU/token $",C[2])]),
    ]
    for ri,(label,col,items) in enumerate(rows):
        y=88+ri*107
        s+=sf(15,y,865,95,label,col)
        for ci,(lbl,sub,ic) in enumerate(items):
            s+=fb(20+ci*143,y+14,133,68,ic,lbl,sub,8)
        for x in [153,296,439,582,725]: s+=ar(x,y+48,x+10,y+48,"white")
    return s,"MLOps Pipeline"

def make_lakehouse(p):
    C=p["c"]; s=""
    s+=sf(15,88,865,75,"INGESTION SOURCES",C[0])
    srcs=[("📊","Batch ETL","Airflow",C[0]),("🌊","Streaming","Kafka/Kinesis",C[1]),("🔌","CDC","Debezium",C[2]),("📡","API Pull","REST",C[3]),("📂","File Drop","S3 trigger",C[4]),("🤖","IoT","MQTT",C[5]),("📱","App Events","SDK",C[0])]
    w=860//len(srcs)
    for i,(ico,lbl,sub,col) in enumerate(srcs):
        s+=fb(20+i*w,95,w-8,60,col,f"{ico} {lbl}",sub,8)
    for x in [140,262,384,506,628,750]: s+=ar(x,125,x+8,125,"white")
    s+=sf(15,175,865,80,"OPEN TABLE FORMAT",C[1])
    s+=fb(20,188,200,58,C[1],"Delta Lake","ACID + time travel")
    s+=fb(235,188,200,58,C[2],"Apache Iceberg","schema evolution")
    s+=fb(450,188,200,58,C[3],"Apache Hudi","upserts/deletes")
    s+=fb(665,188,200,58,C[4],"Metadata Catalog","Glue/Hive Metastore")
    for x in [220,435,650]: s+=ar(x,217,x+15,217,"white","or")
    s+=sf(15,267,865,80,"COMPUTE ENGINE",C[2])
    s+=fb(20,280,195,58,C[2],"Apache Spark","SQL/ML/streaming")
    s+=fb(230,280,180,58,C[3],"Trino/Presto","interactive SQL")
    s+=fb(425,280,180,58,C[4],"dbt","transform/test")
    s+=fb(620,280,175,58,C[5],"Ray","ML distributed")
    s+=fb(810,280,60,58,C[0],"Flink","stream")
    for x in [215,410,605,795]: s+=ar(x,309,x+15,309,"white")
    s+=sf(15,360,865,75,"CONSUMPTION LAYER",C[3])
    cons=[("📊","BI Tools","Tableau",C[3]),("🤖","ML Platform","SageMaker",C[4]),("🔍","Ad-hoc SQL","Athena/BQ",C[5]),("📈","Dashboards","Grafana",C[0]),("📡","Data APIs","REST",C[1]),("⚡","Streaming","real-time",C[2])]
    w2=860//len(cons)
    for i,(ico,lbl,sub,col) in enumerate(cons):
        s+=fb(20+i*w2,372,w2-10,55,col,f"{ico} {lbl}",sub,8)
    s+=f'<rect x="15" y="447" width="865" height="45" rx="10" fill="{C[4]}" opacity="0.12" stroke="{C[4]}" stroke-width="1.5"/>'
    s+=f'<text x="450" y="475" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">GOVERNANCE: Data Catalog | Column Lineage | Row-level Security | GDPR | Cost Optimization</text>'
    return s,"Data Architecture"

def make_devsecops(p):
    C=p["c"]; s=""
    phases=[("IDE","💻","Pre-commit","git-secrets",C[0]),("SCM","📝","Code Review","SAST/Semgrep",C[1]),("Build","🏗️","Compile","Dep SCA check",C[2]),("Test","🧪","Quality","DAST/ZAP scan",C[3]),("Artifact","📦","Registry","Container Trivy",C[4]),("Staging","🚀","Deploy","IaC/Terraform",C[5]),("Prod","🛡️","Monitor","Falco/SIEM",C[0])]
    pw=120
    for i,(env,ico,phase,tools,col) in enumerate(phases):
        x=15+i*(pw+5)
        s+=f'<rect x="{x}" y="88" width="{pw}" height="215" rx="10" fill="{col}" fill-opacity="0.1" stroke="{col}" stroke-width="2"/>'
        s+=f'<rect x="{x}" y="88" width="{pw}" height="28" rx="8" fill="{col}"/>'
        s+=f'<text x="{x+pw//2}" y="107" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">{env}</text>'
        s+=f'<text x="{x+pw//2}" y="148" text-anchor="middle" font-size="24" font-family="Arial,sans-serif">{ico}</text>'
        s+=f'<text x="{x+pw//2}" y="168" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{phase}</text>'
        s+=f'<text x="{x+pw//2}" y="200" text-anchor="middle" fill="{col}" font-size="9" font-family="Arial,sans-serif">{tools}</text>'
        if i<len(phases)-1: s+=ar(x+pw,195,x+pw+5+2,195,"white")
    s+=sf(15,316,865,75,"SECURITY GATES",C[3])
    gates=[("🔴","Critical CVE","block merge",C[3]),("🟠","Secrets","block build",C[4]),("🟡","OWASP","block deploy",C[5]),("🔵","Compliance","block release",C[0]),("🟢","Pen Test","quarterly",C[1]),("⚪","Audit Log","always",C[2])]
    gw=860//len(gates)
    for i,(ico,lbl,action,col) in enumerate(gates):
        cx=20+i*gw+gw//2
        s+=f'<text x="{cx}" y="345" text-anchor="middle" font-size="18" font-family="Arial,sans-serif">{ico}</text>'
        s+=f'<text x="{cx}" y="363" text-anchor="middle" fill="white" font-size="9" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
        s+=f'<text x="{cx}" y="377" text-anchor="middle" fill="#94A3B8" font-size="8" font-family="Arial,sans-serif">{action}</text>'
    s+=sf(15,403,420,85,"SIEM AND RESPONSE",C[4])
    s+=fb(25,418,120,58,C[4],"SIEM","Splunk/Sentinel")
    s+=fb(155,418,120,58,C[5],"SOAR","auto-remediate")
    s+=fb(285,418,140,58,C[0],"Threat Intel","feeds/IOCs")
    s+=ar(145,447,155,447,"white","correlate")
    s+=ar(275,447,285,447,"white","respond")
    s+=sf(445,403,435,85,"COMPLIANCE",C[1])
    s+=fb(455,418,125,58,C[1],"CIS Benchmarks","hardening")
    s+=fb(590,418,130,58,C[2],"SOC2/ISO27001","audit ready")
    s+=fb(730,418,140,58,C[3],"OPA/Rego","policy as code")
    return s,"Security Pipeline"

def make_rag(p):
    C=p["c"]; s=""
    s+=sf(15,88,140,340,"SOURCES",C[1])
    for cx,cy,ico,lbl in [(87,118,"📄","PDFs"),(87,178,"🌐","Web"),(87,238,"🗄️","DB"),(87,298,"📧","Email"),(87,355,"🎥","Media")]:
        s+=f'<circle cx="{cx}" cy="{cy}" r="22" fill="{C[1]}"/>'
        s+=f'<text x="{cx}" y="{cy+6}" text-anchor="middle" font-size="14" font-family="Arial,sans-serif">{ico}</text>'
        s+=f'<text x="{cx}" y="{cy+36}" text-anchor="middle" fill="white" font-size="9" font-family="Arial,sans-serif">{lbl}</text>'
        s+=ar(109,cy,158,cy,"white","ingest")
    s+=sf(158,88,200,340,"INGESTION",C[2])
    s+=fb(168,108,178,68,C[2],"Chunker","512 tok, 50 overlap")
    s+=fb(168,190,178,68,C[3],"Embedder","text-embed-3-large")
    s+=fb(168,272,178,68,C[4],"Metadata","source/date/type")
    s+=fb(168,354,178,62,C[5],"Dedup","hash-based filter")
    for y in [176,258,340]: s+=ar(257,y,257,y+14,"white")
    s+=sf(372,88,170,340,"VECTOR STORE",C[0])
    s+=fb(382,108,150,68,C[0],"HNSW Index","graph ANN")
    s+=fb(382,190,150,68,C[1],"Vector DB","Pinecone/Weaviate")
    s+=fb(382,272,150,68,C[2],"BM25 Index","sparse vectors")
    s+=fb(382,354,150,62,C[3],"Query Cache","result caching")
    for y in [142,224,306]: s+=ar(457,y,457,y+14,"white")
    for y in [142,224,306,385]: s+=ar(346,y,382,y,"white","store")
    s+=sf(556,88,165,340,"RETRIEVAL",C[4])
    s+=fb(566,108,145,68,C[4],"Query Analyzer","intent + expand")
    s+=fb(566,190,145,68,C[5],"HyDE","hypothetical doc")
    s+=fb(566,272,145,68,C[0],"ANN Search","cosine similarity")
    s+=fb(566,354,145,62,C[1],"Re-ranker","cross-encoder")
    for y in [142,224,306]: s+=ar(638,y,638,y+14,"white")
    for y in [142,224,306,385]: s+=ar(532,y,566,y,"white","query")
    s+=sf(735,88,145,340,"GENERATION",C[5])
    s+=fb(745,108,125,68,C[5],"LLM","GPT-4/Claude")
    s+=fb(745,190,125,68,C[0],"Guardrails","safety filter")
    s+=fb(745,272,125,68,C[1],"Citations","source refs")
    s+=fb(745,354,125,62,C[2],"Feedback","RLHF loop")
    for y in [142,224,306,385]: s+=ar(721,y,745,y,"white","ctx")
    s+=f'<rect x="15" y="440" width="865" height="50" rx="10" fill="{C[3]}" opacity="0.12" stroke="{C[3]}" stroke-width="1.5"/>'
    s+=f'<text x="450" y="470" text-anchor="middle" fill="white" font-size="11" font-weight="bold" font-family="Arial,sans-serif">EVALUATION: Faithfulness | Answer Relevance | Context Recall | RAGAS Score | Hallucination Rate</text>'
    return s,"System Architecture"

def make_system_design(p):
    C=p["c"]; s=""
    s+=sf(15,88,865,50,"CLIENTS",C[0])
    for x,lbl in [(100,"Web Browser"),(280,"Mobile App"),(460,"Desktop"),(640,"Third-party API"),(820,"IoT Device")]:
        s+=f'<text x="{x}" y="118" text-anchor="middle" fill="white" font-size="10" font-weight="bold" font-family="Arial,sans-serif">{lbl}</text>'
    s+=sf(15,150,865,55,"EDGE AND AUTH",C[1])
    for i,(x,lbl,sub,col) in enumerate([(20,"CDN","CloudFront",C[1]),(180,"Load Balancer","L7/health",C[2]),(340,"API Gateway","rate limit",C[3]),(500,"Auth Service","OAuth2/JWT",C[4]),(660,"WAF","L7 protect",C[0]),(800,"Rate Limiter","throttle",C[5])]):
        s+=fb(x,158,150,38,col,lbl,sub,7)
    for x in [170,330,490,650,790]: s+=ar(x,177,x+10,177,"white")
    s+=sf(15,218,865,105,"MICROSERVICES",C[2])
    for x,lbl,sub,col in [(20,"User Service","CRUD/profile",C[2]),(145,"Order Service","cart/checkout",C[3]),(270,"Payment","Stripe/PCI",C[4]),(395,"Notification","email/SMS",C[5]),(520,"Search","Elasticsearch",C[0]),(645,"Recommend","ML-powered",C[1]),(770,"Analytics","events",C[2])]:
        s+=fb(x,232,120,80,col,lbl,sub)
    for x in [140,265,390,515,640,765]: s+=ar(x,272,x+5,272,"white")
    s+=sf(15,336,865,55,"MESSAGE BROKER",C[3])
    for x,lbl,sub,col in [(20,"Kafka","event stream",C[3]),(190,"RabbitMQ","task queues",C[4]),(360,"Redis PubSub","real-time",C[5]),(530,"Dead Letter Q","failed msgs",C[0]),(700,"Event Source","audit stream",C[1])]:
        s+=fb(x,344,160,38,col,lbl,sub,7)
    s+=sf(15,405,865,85,"DATA LAYER",C[4])
    for x,lbl,sub,col in [(20,"PostgreSQL","OLTP",C[4]),(165,"Redis","cache",C[5]),(310,"MongoDB","documents",C[0]),(455,"S3","blob/media",C[1]),(600,"Elasticsearch","search",C[2]),(745,"ClickHouse","analytics",C[3])]:
        s+=fb(x,416,140,65,col,lbl,sub)
    return s,"System Architecture"

def make_generic(topic_name,p):
    C=p["c"]; s=""
    s+=sf(15,88,865,55,"CLIENT AND EDGE",C[0])
    for x,lbl,sub,col in [(20,"Web/Mobile","React/Native",C[0]),(185,"CDN","CloudFront",C[1]),(350,"API Gateway","rate limit",C[2]),(515,"Auth","OAuth2/JWT",C[3]),(680,"DNS","Route 53",C[4])]:
        s+=fb(x,96,155,38,col,lbl,sub,7)
    for x in [175,340,505,670]: s+=ar(x,115,x+10,115,"white")
    s+=sf(15,155,430,120,"MICROSERVICES",C[1])
    for y,lbl,sub,col in [(170,"User Service","auth/profile",C[1]),(220,"Order Service","cart/payment",C[2]),(270,"Notification","email/SMS/push",C[3])]:
        s+=fb(25,y,190,42,col,lbl,sub,7)
        s+=fb(225,y,210,42,lbl+" Worker","async processing",C[4])
        s+=ar(215,y+21,225,y+21,"white","async")
    s+=sf(455,155,425,120,"DATA SERVICES",C[2])
    for y,lbl,sub,col in [(170,"Search","Elasticsearch",C[2]),(220,"Analytics","ClickHouse",C[3]),(270,"ML/AI","model serving",C[4])]:
        s+=fb(465,y,195,42,col,lbl,sub,7)
        s+=fb(670,y,200,42,sub.split("/")[0],"primary store",C[5])
        s+=ar(660,y+21,670,y+21,"white","query")
    s+=sf(15,288,865,65,"MESSAGE LAYER",C[3])
    for x,lbl,sub,col in [(20,"Kafka","event stream",C[3]),(195,"RabbitMQ","task queue",C[4]),(370,"Redis","cache/pub-sub",C[5]),(545,"SQS","managed queue",C[0]),(720,"EventBridge","event bus",C[1])]:
        s+=fb(x,298,165,46,col,lbl,sub,7)
    s+=sf(15,366,865,120,"DATA STORES",C[4])
    for x,lbl,sub,col in [(20,"PostgreSQL","OLTP",C[4]),(165,"Redis","sessions",C[5]),(310,"MongoDB","documents",C[0]),(455,"S3","blobs",C[1]),(600,"Redshift","analytics",C[2]),(745,"Cassandra","time-series",C[3])]:
        s+=fb(x,378,140,95,col,lbl,sub)
    return s,"System Architecture"

def make_diagram(topic_name,topic_id,diagram_type):
    p=get_pal(topic_id)
    now=datetime.now().strftime("%B %Y")
    accent=p["c"][0]
    tid=topic_id.lower()
    if "kube" in tid:        content,subtitle=make_kubernetes(p)
    elif any(x in tid for x in ["llm","agent"]): content,subtitle=make_llm(p)
    elif "cicd" in tid:      content,subtitle=make_cicd(p)
    elif "kafka" in tid:     content,subtitle=make_kafka(p)
    elif "zero" in tid:      content,subtitle=make_zero_trust(p)
    elif "aws" in tid:       content,subtitle=make_aws(p)
    elif "devsec" in tid:    content,subtitle=make_devsecops(p)
    elif "system" in tid:    content,subtitle=make_system_design(p)
    elif "mlops" in tid:     content,subtitle=make_mlops(p)
    elif any(x in tid for x in ["lake","data"]): content,subtitle=make_lakehouse(p)
    elif "rag" in tid:       content,subtitle=make_rag(p)
    else:                    content,subtitle=make_generic(topic_name,p)
    return wrap(content,topic_name,subtitle,accent,now)

class DiagramGenerator:
    def __init__(self):
        Path(OUTPUT_DIR).mkdir(exist_ok=True)
        log.info("Diagram output dir: "+OUTPUT_DIR+"/")
    def save_svg(self,svg_content,topic_id,topic_name="",diagram_type="Architecture Diagram"):
        timestamp=datetime.now().strftime("%Y%m%d_%H%M%S")
        filename=OUTPUT_DIR+"/"+topic_id+"_"+timestamp+".svg"
        svg=make_diagram(topic_name or topic_id,topic_id,diagram_type)
        with open(filename,"w",encoding="utf-8") as f: f.write(svg)
        size_kb=os.path.getsize(filename)/1024
        log.info("Diagram saved: "+filename+" ("+str(round(size_kb,1))+" KB)")
        return filename
