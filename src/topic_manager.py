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
        "prompt": "The state of autonomous AI agents heading into 2026 — Agentic frameworks like LangGraph, AutoGen v2, and CrewAI, MCP protocol adoption, multi-agent orchestration, and how agent reliability has evolved from research toy to production workload",
        "angle": "What changed in 12 months: better planning, tool use, memory, and the real failure modes still unsolved",
        "diagram_subject": "Multi-Agent System Architecture 2026: orchestrator, planner, sub-agents, MCP tool servers, memory store, human-in-the-loop",
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
]


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
            json.dump(list(self.history)[-50:], f, indent=2)

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
        recent_ids = [h["topic_id"] for h in self.history[-12:]]
        available = [t for t in self.topics if t["id"] not in recent_ids]
        if not available:
            available = self.topics  # all have been used recently — full reset
        recent_categories = [h.get("category") for h in self.history[-3:]]
        prioritized = [t for t in available if t["category"] not in recent_categories]
        pool = prioritized if prioritized else available
        chosen = random.choice(pool)
        log.info(f"Selected topic: {chosen['name']} (category: {chosen['category']})")
        return chosen

    def get_diagram_type_for_topic(self, topic):
        return topic.get("diagram_type", "Architecture Diagram")

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
