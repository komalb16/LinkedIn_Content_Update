"""
Topic Manager — Handles topic selection, rotation, and history tracking.
© Komal Batra
"""

import json
import os
import random
from datetime import datetime, timedelta
from logger import get_logger

log = get_logger("topics")

TOPICS = [
    # ── AI & Machine Learning ──────────────────────────────────────────────
    {
        "id": "llm-architecture",
        "name": "LLM Architecture",
        "category": "AI",
        "prompt": "The internal architecture of Large Language Models — transformers, attention mechanisms, and what makes models like GPT-4, Gemini, and Claude different under the hood",
        "angle": "Technical deep-dive with practical implications for engineers building on top of LLMs",
        "diagram_subject": "Transformer Architecture: attention layers, feed-forward networks, tokenization, and inference pipeline",
        "diagram_type": "Architecture Diagram",
        "emoji": "🤖",
        "hashtags": ["#AI", "#LLM", "#MachineLearning", "#Transformers", "#GenerativeAI"],
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
        "hashtags": ["#AIAgents", "#LangChain", "#AutoGen", "#AI", "#MLOps"],
    },
    {
        "id": "mlops-pipeline",
        "name": "MLOps & Model Deployment",
        "category": "AI",
        "prompt": "Modern MLOps pipelines — from model training to production deployment with monitoring, drift detection, and CI/CD for ML",
        "angle": "What separates a POC from a production ML system",
        "diagram_subject": "End-to-end MLOps pipeline: data ingestion → training → evaluation → deployment → monitoring → retraining",
        "diagram_type": "Flow Chart",
        "emoji": "⚙️",
        "hashtags": ["#MLOps", "#MachineLearning", "#DevOps", "#ModelDeployment", "#AI"],
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
        "hashtags": ["#RAG", "#AI", "#VectorDB", "#LLM", "#EnterpriseAI"],
    },

    # ── Cloud & DevOps ─────────────────────────────────────────────────────
    {
        "id": "kubernetes-mastery",
        "name": "Kubernetes Deep Dive",
        "category": "Cloud",
        "prompt": "Kubernetes in production — pods, deployments, HPA, resource limits, and the real gotchas that take down clusters",
        "angle": "Hard-won lessons from running K8s at scale",
        "diagram_subject": "Kubernetes cluster architecture: nodes, pods, services, ingress, namespaces, and control plane components with kubectl commands",
        "diagram_type": "Architecture Diagram",
        "emoji": "☸️",
        "hashtags": ["#Kubernetes", "#K8s", "#DevOps", "#CloudNative", "#Containers"],
    },
    {
        "id": "docker-cheatsheet",
        "name": "Docker Mastery",
        "category": "Cloud",
        "prompt": "Docker best practices for production — multi-stage builds, layer caching, security scanning, and the commands every engineer must know",
        "angle": "The 20% of Docker knowledge that covers 80% of daily use",
        "diagram_subject": "Docker essential commands cheat sheet: build, run, compose, exec, logs, prune — organized by use case with flags and examples",
        "diagram_type": "Cheat Sheet",
        "emoji": "🐳",
        "hashtags": ["#Docker", "#DevOps", "#Containers", "#CloudNative", "#SoftwareEngineering"],
    },
    {
        "id": "aws-architecture",
        "name": "AWS Architecture Patterns",
        "category": "Cloud",
        "prompt": "Battle-tested AWS architecture patterns — serverless, microservices on ECS/EKS, and event-driven with SQS/SNS/EventBridge",
        "angle": "When to use which pattern and the cost implications of each",
        "diagram_subject": "AWS serverless architecture: API Gateway → Lambda → DynamoDB/S3 with SQS, SNS, EventBridge, CloudWatch monitoring",
        "diagram_type": "Architecture Diagram",
        "emoji": "☁️",
        "hashtags": ["#AWS", "#CloudArchitecture", "#Serverless", "#CloudNative", "#DevOps"],
    },
    {
        "id": "cicd-pipelines",
        "name": "CI/CD Best Practices",
        "category": "DevOps",
        "prompt": "Modern CI/CD pipelines — GitHub Actions, GitLab CI, and the practices that make deployments boring (in the best way)",
        "angle": "Pipeline patterns: testing strategy, parallelization, environment promotion, rollback",
        "diagram_subject": "CI/CD pipeline flow: code push → lint/test → build → security scan → staging deploy → integration tests → production deploy with rollback",
        "diagram_type": "Flow Chart",
        "emoji": "🚀",
        "hashtags": ["#CICD", "#DevOps", "#GitHubActions", "#Automation", "#SoftwareEngineering"],
    },

    # ── Software Engineering ───────────────────────────────────────────────
    {
        "id": "system-design",
        "name": "System Design Fundamentals",
        "category": "Engineering",
        "prompt": "System design principles every senior engineer must master — scalability, CAP theorem, load balancing, caching strategies, and database sharding",
        "angle": "How to approach a system design interview vs. building real systems",
        "diagram_subject": "Scalable web application architecture: CDN, load balancer, API servers, cache layer, primary/replica DB, message queue, background workers",
        "diagram_type": "Architecture Diagram",
        "emoji": "🏗️",
        "hashtags": ["#SystemDesign", "#SoftwareArchitecture", "#Engineering", "#Scalability", "#Backend"],
    },
    {
        "id": "api-design",
        "name": "API Design Principles",
        "category": "Engineering",
        "prompt": "REST vs GraphQL vs gRPC — when to use each, versioning strategies, rate limiting, and the API design mistakes that come back to haunt you",
        "angle": "Designing APIs that developers love and systems can scale with",
        "diagram_subject": "API design comparison cheat sheet: REST vs GraphQL vs gRPC — use cases, pros/cons, performance, tooling, and code examples",
        "diagram_type": "Comparison Table",
        "emoji": "🔌",
        "hashtags": ["#API", "#REST", "#GraphQL", "#gRPC", "#BackendEngineering"],
    },
    {
        "id": "git-workflow",
        "name": "Git Workflow & Commands",
        "category": "Engineering",
        "prompt": "Git mastery — branching strategies (Gitflow vs trunk-based), the commands that save you in crises, and how senior engineers use git differently",
        "angle": "Commands and patterns that separate juniors from seniors",
        "diagram_subject": "Git essential commands cheat sheet: branch, merge, rebase, cherry-pick, stash, reset, reflog — with real use-case examples and flags",
        "diagram_type": "Cheat Sheet",
        "emoji": "🌿",
        "hashtags": ["#Git", "#DevOps", "#SoftwareEngineering", "#VersionControl", "#Coding"],
    },
    {
        "id": "solid-principles",
        "name": "SOLID & Design Patterns",
        "category": "Engineering",
        "prompt": "SOLID principles and design patterns in modern software — with practical Python/TypeScript examples of when to apply them and when NOT to",
        "angle": "When design patterns help vs. when they're over-engineering",
        "diagram_subject": "SOLID principles visual guide: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion — with code examples",
        "diagram_type": "Cheat Sheet",
        "emoji": "📐",
        "hashtags": ["#SOLID", "#DesignPatterns", "#SoftwareEngineering", "#CleanCode", "#OOP"],
    },

    # ── Security ───────────────────────────────────────────────────────────
    {
        "id": "zero-trust",
        "name": "Zero Trust Architecture",
        "category": "Security",
        "prompt": "Zero Trust security in 2025 — why 'never trust, always verify' is now a business requirement, not a buzzword, and how to implement it",
        "angle": "Practical implementation: identity-first, microsegmentation, continuous verification",
        "diagram_subject": "Zero Trust Architecture: identity provider, device trust, network microsegmentation, application access, data classification layers",
        "diagram_type": "Architecture Diagram",
        "emoji": "🔐",
        "hashtags": ["#ZeroTrust", "#Cybersecurity", "#InfoSec", "#Security", "#CloudSecurity"],
    },
    {
        "id": "devsecops",
        "name": "DevSecOps Practices",
        "category": "Security",
        "prompt": "Shifting security left — DevSecOps tools and practices: SAST, DAST, SCA, secrets management, and container security scanning in CI/CD",
        "angle": "Making security a developer responsibility without slowing teams down",
        "diagram_subject": "DevSecOps pipeline: pre-commit hooks → SAST → dependency scan → container scan → DAST → compliance check → runtime monitoring",
        "diagram_type": "Flow Chart",
        "emoji": "🛡️",
        "hashtags": ["#DevSecOps", "#Cybersecurity", "#CICD", "#AppSec", "#DevOps"],
    },

    # ── Data Engineering ───────────────────────────────────────────────────
    {
        "id": "data-lakehouse",
        "name": "Data Lakehouse Architecture",
        "category": "Data",
        "prompt": "The data lakehouse pattern — why companies are moving from data warehouses and data lakes to a hybrid approach with Delta Lake, Iceberg, and Hudi",
        "angle": "Technical trade-offs and when this architecture makes (and doesn't make) sense",
        "diagram_subject": "Data Lakehouse architecture: ingestion layer, open table format, compute engines (Spark/Trino), BI tools, ML platform integration",
        "diagram_type": "Architecture Diagram",
        "emoji": "📊",
        "hashtags": ["#DataEngineering", "#DataLakehouse", "#Spark", "#BigData", "#Analytics"],
    },
    {
        "id": "kafka-streaming",
        "name": "Apache Kafka & Streaming",
        "category": "Data",
        "prompt": "Apache Kafka in production — producers, consumers, partitioning strategy, consumer groups, and real-time streaming architecture patterns",
        "angle": "The operational realities of running Kafka at scale",
        "diagram_subject": "Kafka streaming architecture: producers, topics/partitions, consumer groups, stream processing (Flink/Spark Streaming), sink connectors",
        "diagram_type": "Architecture Diagram",
        "emoji": "🌊",
        "hashtags": ["#Kafka", "#DataStreaming", "#DataEngineering", "#RealTime", "#BigData"],
    },
]

HISTORY_FILE = ".topic_history.json"


class TopicManager:
    def __init__(self):
        self.topics = TOPICS
        self.history = self._load_history()

    def _load_history(self) -> list:
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_history(self):
        with open(HISTORY_FILE, "w") as f:
            json.dump(self.history[-50:], f, indent=2)  # keep last 50 entries

    def get_topic(self, topic_id: str) -> dict:
        """Get topic by ID."""
        for t in self.topics:
            if t["id"] == topic_id:
                return t
        raise ValueError(f"Topic '{topic_id}' not found. Run with --list-topics to see options.")

    def get_next_topic(self) -> dict:
        """Smart rotation: pick least recently used topic, with some randomness."""
        recent_ids = [h["topic_id"] for h in self.history[-6:]]
        
        # Filter out recently used topics
        available = [t for t in self.topics if t["id"] not in recent_ids]
        if not available:
            available = self.topics  # reset if all used
        
        # Weight by category diversity
        recent_categories = [h.get("category") for h in self.history[-3:]]
        deprioritized = [t for t in available if t["category"] in recent_categories]
        prioritized = [t for t in available if t["category"] not in recent_categories]
        
        pool = prioritized if prioritized else deprioritized
        return random.choice(pool)

    def get_diagram_type_for_topic(self, topic: dict) -> str:
        """Get the diagram type specified for this topic."""
        return topic.get("diagram_type", "Architecture Diagram")

    def save_run_history(self, entry: dict):
        """Save run to history file."""
        self.history.append(entry)
        self._save_history()
        log.info(f"Run history saved ({len(self.history)} total runs)")

    def list_topics(self):
        """Print all available topics."""
        print(f"\n{'─'*60}")
        print(f"  LinkedIn Agent — Topic List  |  © Komal Batra")
        print(f"{'─'*60}")
        
        categories = {}
        for t in self.topics:
            cat = t["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(t)
        
        for cat, topics in categories.items():
            print(f"\n  {t['emoji']}  {cat.upper()}")
            for t in topics:
                print(f"     --topic {t['id']:<25} {t['name']}")
        
        print(f"\n{'─'*60}\n")
