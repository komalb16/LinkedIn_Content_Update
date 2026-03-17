import json
import os
import random
from datetime import datetime
from logger import get_logger

log = get_logger("topics")

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".topic_history.json")

TOPICS = [
    {
        "id": "llm-architecture",
        "name": "LLM Architecture",
        "category": "AI",
        "prompt": "The internal architecture of Large Language Models — transformers, attention mechanisms, and what makes models like GPT-4, Gemini, and Claude different under the hood",
        "angle": "Technical deep-dive with practical implications for engineers building on top of LLMs",
        "diagram_subject": "Transformer Architecture: attention layers, feed-forward networks, tokenization, and inference pipeline",
        "diagram_type": "Architecture Diagram",
        "emoji": "🤖",
    },
    {
        "id": "ai-agents-2025",
        "name": "AI Agents in 2025",
        "category": "AI",
        "prompt": "The rise of autonomous AI agents — LangChain, AutoGen, CrewAI, and how multi-agent systems are changing software development workflows",
        "angle": "Practical frameworks, real production use cases, pitfalls to avoid",
        "diagram_subject": "Multi-Agent System Architecture: orchestrator, tool use, memory, planning and execution loop",
        "diagram_type": "Architecture Diagram",
        "emoji": "🤖",
        "hidden": True,   # superseded by ai-agents-2026
    },
    {
        "id": "ai-agents-2026",
        "name": "AI Agents in 2026",
        "category": "AI",
        "prompt": "The state of autonomous AI agents in 2026 — why simple chains failed and why LangGraph-style state machines won. Adopting the MCP protocol for tool use, and why human-in-the-loop is still the only way to achieve 99% reliability.",
        "angle": "Stop building simple agents. If your agent doesn't have a state machine and persistent memory, it's just a fancy script. Here is what 2026 engineering looks like.",
        "diagram_subject": "Modern Agentic Architecture: LangGraph nodes, state transitions, MCP tool servers, and human-in-the-loop validation gate",
        "diagram_type": "Architecture Diagram",
        "emoji": "🤖",
    },
    {
        "id": "mlops-pipeline",
        "name": "MLOps and Model Deployment",
        "category": "AI",
        "prompt": "Modern MLOps pipelines — from model training to production deployment with monitoring, drift detection, and CI/CD for ML",
        "angle": "What separates a POC from a production ML system",
        "diagram_subject": "End-to-end MLOps pipeline: data ingestion, training, evaluation, deployment, monitoring, retraining",
        "diagram_type": "Flow Chart",
        "emoji": "⚙️",
    },
    {
        "id": "rag-systems",
        "name": "RAG Systems",
        "category": "AI",
        "prompt": "Retrieval-Augmented Generation (RAG) — why it beats fine-tuning for most enterprise use cases, and how to build production RAG systems",
        "angle": "Vector databases, chunking strategies, re-ranking, and evaluation metrics",
        "diagram_subject": "RAG Architecture: document ingestion, chunking, embedding, vector search, context injection, LLM generation",
        "diagram_type": "Architecture Diagram",
        "emoji": "🔍",
    },
    {
        "id": "kubernetes-mastery",
        "name": "Kubernetes Deep Dive",
        "category": "Cloud",
        "prompt": "Kubernetes in production — pods, deployments, HPA, resource limits, and the real gotchas that take down clusters",
        "angle": "Hard-won lessons from running K8s at scale",
        "diagram_subject": "Kubernetes cluster architecture: nodes, pods, services, ingress, namespaces, and control plane components",
        "diagram_type": "Architecture Diagram",
        "emoji": "☸️",
    },
    {
        "id": "docker-cheatsheet",
        "name": "Docker Mastery",
        "category": "Cloud",
        "prompt": "Docker best practices for production — multi-stage builds, layer caching, security scanning, and the commands every engineer must know",
        "angle": "The 20% of Docker knowledge that covers 80% of daily use",
        "diagram_subject": "Docker essential commands cheat sheet: build, run, compose, exec, logs, prune",
        "diagram_type": "Cheat Sheet",
        "emoji": "🐳",
    },
    {
        "id": "aws-architecture",
        "name": "AWS Architecture Patterns",
        "category": "Cloud",
        "prompt": "Battle-tested AWS architecture patterns — serverless, microservices on ECS/EKS, and event-driven with SQS/SNS/EventBridge",
        "angle": "When to use which pattern and the cost implications of each",
        "diagram_subject": "AWS serverless architecture: API Gateway, Lambda, DynamoDB, S3, SQS, SNS, EventBridge, CloudWatch",
        "diagram_type": "Architecture Diagram",
        "emoji": "☁️",
    },
    {
        "id": "cicd-pipelines",
        "name": "CI/CD Best Practices",
        "category": "DevOps",
        "prompt": "Modern CI/CD pipelines — GitHub Actions, GitLab CI, and the practices that make deployments boring in the best way",
        "angle": "Pipeline patterns: testing strategy, parallelization, environment promotion, rollback",
        "diagram_subject": "CI/CD pipeline flow: code push, lint/test, build, security scan, staging deploy, integration tests, production deploy",
        "diagram_type": "Flow Chart",
        "emoji": "🚀",
    },
    {
        "id": "system-design",
        "name": "System Design Fundamentals",
        "category": "Engineering",
        "prompt": "System design principles every senior engineer must master — scalability, CAP theorem, load balancing, caching strategies, and database sharding",
        "angle": "How to approach a system design interview vs. building real systems",
        "diagram_subject": "Scalable web application architecture: CDN, load balancer, API servers, cache layer, primary/replica DB, message queue",
        "diagram_type": "Architecture Diagram",
        "emoji": "🏗️",
    },
    {
        "id": "api-design",
        "name": "API Design Principles",
        "category": "Engineering",
        "prompt": "REST vs GraphQL vs gRPC — when to use each, versioning strategies, rate limiting, and the API design mistakes that come back to haunt you",
        "angle": "Designing APIs that developers love and systems can scale with",
        "diagram_subject": "API design comparison: REST vs GraphQL vs gRPC — use cases, pros/cons, performance, tooling",
        "diagram_type": "Comparison Table",
        "emoji": "🔌",
    },
    {
        "id": "git-workflow",
        "name": "Git Workflow and Commands",
        "category": "Engineering",
        "prompt": "Git mastery — branching strategies (Gitflow vs trunk-based), the commands that save you in crises, and how senior engineers use git differently",
        "angle": "Commands and patterns that separate juniors from seniors",
        "diagram_subject": "Git essential commands cheat sheet: branch, merge, rebase, cherry-pick, stash, reset, reflog",
        "diagram_type": "Cheat Sheet",
        "emoji": "🌿",
    },
    {
        "id": "solid-principles",
        "name": "SOLID and Design Patterns",
        "category": "Engineering",
        "prompt": "SOLID principles and design patterns in modern software — with practical Python/TypeScript examples of when to apply them and when NOT to",
        "angle": "When design patterns help vs. when they are over-engineering",
        "diagram_subject": "SOLID principles visual guide: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion",
        "diagram_type": "Cheat Sheet",
        "emoji": "📐",
    },
    {
        "id": "zero-trust",
        "name": "Zero Trust Architecture",
        "category": "Security",
        "prompt": "Zero Trust security in 2025 — why never trust always verify is now a business requirement and how to implement it",
        "angle": "Practical implementation: identity-first, microsegmentation, continuous verification",
        "diagram_subject": "Zero Trust Architecture: identity provider, device trust, network microsegmentation, application access, data classification",
        "diagram_type": "Architecture Diagram",
        "emoji": "🔐",
    },
    {
        "id": "devsecops",
        "name": "DevSecOps Practices",
        "category": "Security",
        "prompt": "Shifting security left — DevSecOps tools and practices: SAST, DAST, SCA, secrets management, and container security scanning in CI/CD",
        "angle": "Making security a developer responsibility without slowing teams down",
        "diagram_subject": "DevSecOps pipeline: pre-commit hooks, SAST, dependency scan, container scan, DAST, compliance check, runtime monitoring",
        "diagram_type": "Flow Chart",
        "emoji": "🛡️",
    },
    {
        "id": "data-lakehouse",
        "name": "Data Lakehouse Architecture",
        "category": "Data",
        "prompt": "The data lakehouse pattern — why companies are moving from data warehouses and data lakes to a hybrid approach with Delta Lake, Iceberg, and Hudi",
        "angle": "Technical trade-offs and when this architecture makes and does not make sense",
        "diagram_subject": "Data Lakehouse architecture: ingestion layer, open table format, compute engines Spark/Trino, BI tools, ML platform",
        "diagram_type": "Architecture Diagram",
        "emoji": "📊",
    },
    {
        "id": "kafka-streaming",
        "name": "Apache Kafka and Streaming",
        "category": "Data",
        "prompt": "Apache Kafka in production — producers, consumers, partitioning strategy, consumer groups, and real-time streaming architecture patterns",
        "angle": "The operational realities of running Kafka at scale",
        "diagram_subject": "Kafka streaming architecture: producers, topics/partitions, consumer groups, stream processing Flink/Spark, sink connectors",
        "diagram_type": "Architecture Diagram",
        "emoji": "🌊",
    },
    {
        "id": "data-evolution",
        "name": "Data Architecture Evolution",
        "category": "Data",
        "prompt": "The evolution of data architecture into the 3-tier model (Sources -> Lakehouse -> Consumers) and why it's the industry standard.",
        "angle": "Why the lakehouse paradigm solves the problems of both data lakes and warehouses.",
        "diagram_subject": "3-Tier Data Architecture: Sources, Data Platform, and Consumers",
        "diagram_type": "Architecture Diagram",
        "emoji": "📊",
    },
    {
        "id": "ml-algorithms",
        "name": "Machine Learning Algorithms",
        "category": "Data Science",
        "prompt": "The taxonomy of Machine Learning algorithms every data scientist must know: Supervised, Unsupervised, and Reinforcement Learning.",
        "angle": "A structured breakdown of when to use which ML algorithm to solve real-world problems.",
        "diagram_subject": "Machine Learning Algorithms taxonomy tree: supervised, unsupervised, reinforcement",
        "diagram_type": "Taxonomy Tree",
        "emoji": "🌲",
    },
    {
        "id": "ai-disciplines",
        "name": "Comparing Major AI Disciplines",
        "category": "AI",
        "prompt": "Comparing the major AI disciplines: Artificial Intelligence vs Machine Learning vs Deep Learning vs Generative AI vs RAG vs AI Agents.",
        "angle": "Clearing up the buzzwords. How the progression of AI technologies stack upon each other.",
        "diagram_subject": "AI Disciplines layered comparison flow: AI -> ML -> DL -> GenAI -> RAG -> Agents",
        "diagram_type": "Conceptual Layers",
        "emoji": "🧠",
    },
    {
        "id": "rag-stack",
        "name": "Open Source RAG Stack",
        "category": "AI Tools",
        "prompt": "This stack brings together powerful tools to transform raw data into context-rich intelligence. It integrates ingestion pipelines, embeddings, retrieval, and vector databases into one cohesive system.",
        "angle": "How to layer components with LLM frameworks and models to enable scalable, trustworthy, and production-ready AI applications.",
        "diagram_subject": "Open Source RAG Stack ecosystem map: ingest, retrieval, embeddings, vector db, llm frameworks, llm, frontend",
        "diagram_type": "Ecosystem Tree",
        "emoji": "📚",
    },
    {
        "id": "ai-skills-map",
        "name": "AI Skills & Technologies Map",
        "category": "AI Learning",
        "prompt": "A comprehensive map of AI skills and technologies: Agentic AI, Generative AI, Deep Learning, Machine Learning, NLP, AI Ethics, Computer Vision, Robotics.",
        "angle": "Navigating the AI ecosystem: which skills to learn and which technologies to adopt for different subfields of AI.",
        "diagram_subject": "AI Skills mapping: honeycomb layout of domains connecting to specific skill and tech stacks",
        "diagram_type": "Honeycomb Map",
        "emoji": "🗺️",
    },
    {
        "id": "llm-vs-agentic",
        "name": "LLM vs Generative AI vs AI Agents Agentic AI",
        "category": "AI Workflows",
        "prompt": "The execution differences between standard LLMs, Generative AI models, basic AI Agents, and fully autonomous Agentic AI flows.",
        "angle": "Understanding the pipeline execution shifts from simple token prediction to complex autonomous reasoning and monitoring.",
        "diagram_subject": "Parallel execution pipelines comparing LLM sequences vs Agentic AI flows",
        "diagram_type": "Parallel Pipelines",
        "emoji": "🔄",
    },
    {
        "id": "genai-roadmap",
        "name": "Generative AI Learning Roadmap",
        "category": "AI Learning",
        "prompt": "Generative AI Learning Roadmap (Step-by-Step Guide): Start with Basics, Master Core Concepts, Foundation Models, Dev Stack, Model Training, AI Agents, Vision Models, Keep Learning.",
        "angle": "A step-by-step roadmap to guide a developer's journey from basics to building autonomous agentic systems.",
        "diagram_subject": "Winding step-by-step roadmap from 1 to 8 covering the GenAI journey",
        "diagram_type": "Winding Roadmap",
        "emoji": "🛣️",
    },
]

# ─── DIAGRAM STRUCTURES ───────────────────────────────────────────────────────
DIAGRAM_STRUCTURES = {
    "llm-architecture": {
        "style": 1, "subtitle": "How LLMs Actually Work",
        "sections": [
            {"id":1,"label":"Tokenisation",   "desc":"Raw text split into sub-word tokens"},
            {"id":2,"label":"Embedding",      "desc":"Tokens mapped to dense vectors"},
            {"id":3,"label":"Attention",      "desc":"Multi-head self-attention mechanism"},
            {"id":4,"label":"Feed-Forward",   "desc":"Transform and project hidden states"},
            {"id":5,"label":"Output Layer",   "desc":"Project to vocabulary, sample token"},
        ]
    },
    "rag-systems": {
        "style": 16, "subtitle": "7 Patterns Every AI Engineer Must Know",
        "sections": [
            {"id":1,"label":"Naive RAG",           "desc":"Documents → Vector DB → LLM"},
            {"id":2,"label":"Retrieve-and-Rerank", "desc":"Reranker filters retrieved context"},
            {"id":3,"label":"Multimodal RAG",      "desc":"Text, images, audio, video"},
            {"id":4,"label":"Graph RAG",            "desc":"Knowledge graphs + vector search"},
            {"id":5,"label":"Hybrid RAG",           "desc":"Vector + structured retrieval"},
            {"id":6,"label":"Agentic RAG",          "desc":"Agent routes retrieval decisions"},
            {"id":7,"label":"Multi-Agent RAG",      "desc":"Specialised agents collaborate"},
        ]
    },
    "ai-agents-2026": {
        "style": 17, "subtitle": "What Real Agentic AI Looks Like",
        "sections": [
            {"id":1,"label":"NOT: LLM Chatbot", "desc":"Query → Prompt → LLM → Output"},
            {"id":2,"label":"NOT: RPA",          "desc":"Script trigger, no reasoning loop"},
            {"id":3,"label":"NOT: Basic RAG",    "desc":"Retrieval only, no planning"},
            {"id":4,"label":"IS: Agentic AI",    "desc":"Memory + Tools + Planning + Feedback"},
        ]
    },
    "mlops-pipeline": {
        "style": 0, "subtitle": "From Raw Data to Production",
        "sections": [
            {"id":1,"label":"Data Validation",     "desc":"Schema checks, dedup, quality gates"},
            {"id":2,"label":"Feature Engineering", "desc":"Feast feature store, versioning"},
            {"id":3,"label":"Training",            "desc":"Distributed GPU cluster training"},
            {"id":4,"label":"Experiment Tracking", "desc":"MLflow metrics and artefacts"},
            {"id":5,"label":"Model Registry",      "desc":"Versioned models, approval gate"},
            {"id":6,"label":"Serving + Monitor",   "desc":"Triton, drift detection, retraining"},
        ]
    },
    "kubernetes-mastery": {
        "style": 4, "subtitle": "Concepts Every K8s Engineer Must Know",
        "sections": [
            {"id":1,"label":"Pod",        "desc":"Smallest deployable unit"},
            {"id":2,"label":"Deployment", "desc":"Manages replica sets and rollouts"},
            {"id":3,"label":"Service",    "desc":"Stable network endpoint"},
            {"id":4,"label":"Ingress",    "desc":"HTTP routing and TLS termination"},
            {"id":5,"label":"HPA",        "desc":"Horizontal pod autoscaling"},
            {"id":6,"label":"RBAC",       "desc":"Role-based access control"},
        ]
    },
    "docker-cheatsheet": {
        "style": 19, "subtitle": "3 Players Behind Every docker build",
        "sections": [
            {"id":1,"label":"Docker Client", "desc":"CLI sends API requests to daemon"},
            {"id":2,"label":"Docker Host",   "desc":"Daemon builds layers, caches, stores image"},
            {"id":3,"label":"Docker Hub",    "desc":"Registry for sharing and deployment"},
        ]
    },
    "aws-architecture": {
        "style": 6, "subtitle": "Core Services Every Cloud Engineer Must Know",
        "sections": [
            {"id":1,"label":"Compute",  "desc":"EC2, Lambda, ECS, Fargate"},
            {"id":2,"label":"Storage",  "desc":"S3, EBS, EFS, Glacier"},
            {"id":3,"label":"Database", "desc":"RDS, DynamoDB, ElastiCache"},
            {"id":4,"label":"Network",  "desc":"VPC, ALB, CloudFront, Route53"},
            {"id":5,"label":"Security", "desc":"IAM, KMS, GuardDuty, Secrets Manager"},
        ]
    },
    "cicd-pipelines": {
        "style": 0, "subtitle": "From Commit to Production",
        "sections": [
            {"id":1,"label":"Code Commit",    "desc":"Pre-commit hooks, linting"},
            {"id":2,"label":"CI Build",       "desc":"Tests, SAST scan in parallel"},
            {"id":3,"label":"Image Build",    "desc":"Docker multi-stage, layer cache"},
            {"id":4,"label":"Security Scan",  "desc":"Trivy CVE, Snyk SCA, SBOM"},
            {"id":5,"label":"Stage Deploy",   "desc":"Helm upgrade, smoke tests"},
            {"id":6,"label":"Production",     "desc":"Blue/green, canary, feature flags"},
        ]
    },
    "system-design": {
        "style": 7, "subtitle": "Principles Every Senior Engineer Must Master",
        "sections": [
            {"id":1,"label":"Client Layer",   "desc":"Browser, mobile, desktop"},
            {"id":2,"label":"Edge + CDN",     "desc":"Cache at the network edge"},
            {"id":3,"label":"API Gateway",    "desc":"Rate limiting, auth, routing"},
            {"id":4,"label":"Microservices",  "desc":"Bounded domain services"},
            {"id":5,"label":"Data Layer",     "desc":"Primary DB and read replicas"},
            {"id":6,"label":"Observability",  "desc":"Metrics, traces, SLO alerts"},
        ]
    },
    "api-design": {
        "style": 5, "subtitle": "REST vs GraphQL vs gRPC vs WebSocket",
        "sections": [
            {"id":1,"label":"REST",      "desc":"Stateless, HTTP, JSON, OpenAPI"},
            {"id":2,"label":"GraphQL",   "desc":"Client-driven queries, single endpoint"},
            {"id":3,"label":"gRPC",      "desc":"Protobuf, bi-directional, fast"},
            {"id":4,"label":"WebSocket", "desc":"Full-duplex, real-time streams"},
            {"id":5,"label":"AsyncAPI",  "desc":"Event-driven, message brokers"},
        ]
    },
    "kafka-streaming": {
        "style": 5, "subtitle": "vs Other Streaming Platforms",
        "sections": [
            {"id":1,"label":"Kafka",         "desc":"Millions/s, configurable retention"},
            {"id":2,"label":"RabbitMQ",      "desc":"Task queue, 100k/s, no replay"},
            {"id":3,"label":"Redis Streams", "desc":"Low-latency, memory-first"},
            {"id":4,"label":"Kinesis",       "desc":"AWS-native, 7-day retention"},
            {"id":5,"label":"Pulsar",        "desc":"Multi-tenant, infinite retention"},
        ]
    },
    "zero-trust": {
        "style": 1, "subtitle": "Never Trust. Always Verify.",
        "sections": [
            {"id":1,"label":"Identity",      "desc":"IdP, MFA, PAM, SPIFFE certs"},
            {"id":2,"label":"Policy Engine", "desc":"OPA rules, ABAC, time-limits"},
            {"id":3,"label":"Network",       "desc":"Micro-segmentation, mTLS"},
            {"id":4,"label":"Device",        "desc":"Posture checks, EDR"},
            {"id":5,"label":"Data",          "desc":"DLP, encryption, Vault"},
        ]
    },
    "devsecops": {
        "style": 0, "subtitle": "Shift Security Left",
        "sections": [
            {"id":1,"label":"Pre-commit",     "desc":"gitleaks, detect-secrets hooks"},
            {"id":2,"label":"Pull Request",   "desc":"Semgrep SAST, CodeQL analysis"},
            {"id":3,"label":"Build Stage",    "desc":"SCA, Snyk, SBOM generation"},
            {"id":4,"label":"Container Scan", "desc":"Trivy, cosign signing"},
            {"id":5,"label":"Deploy Gate",    "desc":"tfsec, checkov, OPA policy"},
            {"id":6,"label":"Runtime",        "desc":"Falco, SIEM, SOAR remediate"},
        ]
    },
    "data-lakehouse": {
        "style": 2, "subtitle": "Why Companies Are Moving Here",
        "sections": [
            {"id":1,"label":"Raw Ingestion", "desc":"Batch, CDC, streaming, APIs"},
            {"id":2,"label":"Open Format",   "desc":"Delta Lake, Iceberg, Hudi"},
            {"id":3,"label":"Compute Layer", "desc":"Spark, Trino, Flink"},
            {"id":4,"label":"Governance",    "desc":"Catalog, lineage, quality checks"},
            {"id":5,"label":"Consumers",     "desc":"BI dashboards, ML models, data apps"},
        ]
    },
    "solid-principles": {
        "style": 2, "subtitle": "5 Principles Every Engineer Must Know",
        "sections": [
            {"id":1,"label":"S — SRP","desc":"One class, one responsibility"},
            {"id":2,"label":"O — OCP","desc":"Open to extend, closed to modify"},
            {"id":3,"label":"L — LSP","desc":"Subtypes must be substitutable"},
            {"id":4,"label":"I — ISP","desc":"No client forced onto unused methods"},
            {"id":5,"label":"D — DIP","desc":"Depend on abstractions, not concretions"},
        ]
    },
    "ai-disciplines": {
        "style": 10, "subtitle": "AI vs ML vs DL vs GenAI vs RAG vs Agents",
        "sections": [
            {"id":1,"label":"Artificial Intelligence","desc":"Broad field of intelligent systems"},
            {"id":2,"label":"Machine Learning",       "desc":"Learn from data without explicit rules"},
            {"id":3,"label":"Deep Learning",          "desc":"Neural networks with many layers"},
            {"id":4,"label":"Generative AI",          "desc":"Create new content from patterns"},
            {"id":5,"label":"RAG Systems",            "desc":"Ground LLMs in retrieved knowledge"},
            {"id":6,"label":"AI Agents",              "desc":"Autonomous tool-using reasoning loops"},
        ]
    },
    "data-evolution": {
        "style": 8, "subtitle": "Sources → Lakehouse → Consumers",
        "sections": [
            {"id":1,"label":"Data Sources",   "desc":"APIs, CDC, IoT, logs, events"},
            {"id":2,"label":"Data Lakehouse", "desc":"Ingestion, open format, compute"},
            {"id":3,"label":"Data Consumers", "desc":"BI, ML models, data apps"},
        ]
    },
    "agentic-ai": {
        "style": 18, "subtitle": "RAG vs Agentic RAG vs AI Memory",
        "sections": [
            {"id":1,"label":"RAG",          "desc":"Query → Embed → Vector → Context → LLM"},
            {"id":2,"label":"Agentic RAG",  "desc":"Agent routes: web search, DB, APIs"},
            {"id":3,"label":"AI Memory",    "desc":"Search + store memory across sessions"},
        ]
    },
    "git-workflow": {
        "style": 3, "subtitle": "Commands That Separate Juniors from Seniors",
        "sections": [
            {"id":1,"label":"Branch",    "desc":"main + develop + feature/* strategy"},
            {"id":2,"label":"Commit",    "desc":"Conventional commits, GPG signed"},
            {"id":3,"label":"PR Flow",   "desc":"2-reviewer gate, squash merge"},
            {"id":4,"label":"Rebase",    "desc":"Clean history, no merge noise"},
            {"id":5,"label":"Recovery",  "desc":"reset, reflog, cherry-pick"},
        ]
    },
}

DEFAULT_STRUCTURE = {
    "style": 7,
    "subtitle": "What Every Engineer Should Know",
    "sections": [
        {"id":1,"label":"The Problem",    "desc":"Why this matters right now"},
        {"id":2,"label":"Core Concept",   "desc":"The fundamental idea"},
        {"id":3,"label":"How It Works",   "desc":"The mechanism underneath"},
        {"id":4,"label":"Best Practices", "desc":"What production systems do"},
        {"id":5,"label":"Common Mistakes","desc":"What most engineers get wrong"},
        {"id":6,"label":"Key Takeaway",   "desc":"The one thing to remember"},
    ]
}

# topics_config.json lives in the root directory.
TOPICS_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "topics_config.json")


class TopicManager:
    def __init__(self):
        self.history = self._load_history()
        self.topics = self._load_topics()

    def _load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_history(self):
        with open(HISTORY_FILE, "w") as f:
            # Save last 50 entries
            history_list = list(self.history)
            json.dump(history_list[-100:], f, indent=2)

    def _load_topics(self):
        """Merge hardcoded TOPICS with topics_config.json overrides from the dashboard."""
        hidden_ids = set()
        custom_topics = []

        if os.path.exists(TOPICS_CONFIG_FILE):
            try:
                with open(TOPICS_CONFIG_FILE) as f:
                    cfg = json.load(f)
                hidden_ids = set(cfg.get("hidden_ids", []))
                custom_topics = cfg.get("custom_topics", [])
                if hidden_ids:
                    log.info(f"topics_config.json: hiding {len(hidden_ids)} topic(s): {hidden_ids}")
                if custom_topics:
                    log.info(f"topics_config.json: {len(custom_topics)} custom topic(s) added")
            except Exception as e:
                log.warning(f"Could not read topics_config.json (using defaults): {e}")

        # Built-in topics: also respect the hardcoded hidden flag, AND topics_config overrides
        active = [
            t for t in TOPICS
            if not t.get("hidden", False) and t["id"] not in hidden_ids
        ]

        # Custom topics from dashboard — provide defaults for missing fields
        for ct in custom_topics:
            if not ct.get("id"):
                continue
            active.append({
                "id":             ct["id"],
                "name":           ct.get("name", ct["id"]),
                "category":       ct.get("category", "Custom"),
                "prompt":         ct.get("prompt", f"Write an insightful post about {ct.get('name', ct['id'])} for senior engineers."),
                "angle":          ct.get("angle", "Practical insights and real-world implications"),
                "diagram_subject": ct.get("diagram_subject", ct.get("name", ct["id"]) + " architecture overview"),
                "diagram_type":   ct.get("diagram_type", "Architecture Diagram"),
                "emoji":          ct.get("emoji", "💡"),
            })

        log.info(f"Topic pool: {len(active)} active topic(s) (of {len(TOPICS)+len(custom_topics)} total)")
        return active

    def get_topic(self, topic_id):
        for t in self.topics:
            if t["id"] == topic_id:
                return t
        # Also search hidden built-ins in case --topic flag is used explicitly
        for t in TOPICS:
            if t["id"] == topic_id:
                log.warning(f"Topic '{topic_id}' is hidden but used via --topic flag")
                return t
        raise ValueError("Topic not found: " + topic_id)

    def get_next_topic(self):
        recent_ids = [h["topic_id"] for h in self.history[-35:]]
        available = [t for t in self.topics if t["id"] not in recent_ids]
        if not available:
            available = self.topics  # all have been used recently — full reset
        recent_categories = [h.get("category") for h in self.history[-5:]]
        prioritized = [t for t in available if t["category"] not in recent_categories]
        pool = prioritized if prioritized else available
        chosen = random.choice(pool)
        log.info(f"Selected topic: {chosen['name']} (category: {chosen['category']})")
        return chosen

    def get_diagram_type_for_topic(self, topic):
        return topic.get("diagram_type", "Architecture Diagram")

    def get_diagram_structure(self, topic):
        """Return diagram structure for this topic — matched sections for post + diagram."""
        tid = topic["id"]
        name_lower = topic["name"].lower()
        if tid in DIAGRAM_STRUCTURES:
            return DIAGRAM_STRUCTURES[tid]
        for key in DIAGRAM_STRUCTURES:
            if key in tid or tid in key:
                return DIAGRAM_STRUCTURES[key]
        for key in DIAGRAM_STRUCTURES:
            if key.replace("-", " ") in name_lower:
                return DIAGRAM_STRUCTURES[key]
        # Dynamic default using the topic's own name
        default = dict(DEFAULT_STRUCTURE)
        default["sections"] = [
            {"id":1,"label":"The Problem",    "desc":f"Why {topic['name']} matters now"},
            {"id":2,"label":"Core Concept",   "desc":"The fundamental idea"},
            {"id":3,"label":"How It Works",   "desc":"The mechanism underneath"},
            {"id":4,"label":"Best Practices", "desc":"What production systems do"},
            {"id":5,"label":"Common Mistakes","desc":"What most engineers get wrong"},
            {"id":6,"label":"Key Takeaway",   "desc":f"The one thing to remember"},
        ]
        return default

    def save_run_history(self, entry):
        self.history.append(entry)
        self._save_history()
        log.info("Run history saved (" + str(len(self.history)) + " total runs)")

    def list_topics(self):
        print("\n" + "-"*60)
        print("  LinkedIn Agent — Active Topic List  |  Komal Batra")
        print("-"*60)
        for t in self.topics:
            tag = " [custom]" if t.get("category") == "Custom" else ""
            print("  --topic " + str(t["id"]).ljust(28) + str(t["name"]) + tag)
        # Also show hidden ones for visibility
        hidden = [t for t in TOPICS if t.get("hidden", False)]
        if hidden:
            print("\n  Hidden (will not be auto-selected):")
            for t in hidden:
                print("  [hidden] " + str(t["id"]).ljust(25) + str(t["name"]))
        print("-"*60 + "\n")
