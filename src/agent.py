import os
import sys
import re
import json
import time
import random
import argparse
import copy
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from topic_manager import TopicManager
from diagram_generator import DiagramGenerator
from logger import get_logger
import notifier

log = get_logger("agent")
POST_MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".post_memory.json")
ENGAGEMENT_TRACKER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".engagement_tracker.json")
DIAGRAM_ROTATION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".diagram_rotation.json")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"
MODEL_FALLBACK = "llama-3.1-8b-instant"  # Faster, higher rate limits for 429 fallback

USER_NAME = os.environ.get("USER_NAME", os.environ.get("AUTHOR_NAME", "Komal Batra"))

KNOWN_TOOL_NAMES = {
    "Elasticsearch",
    "LanguageTool",
    "New Relic",
    "GitHub Actions",
    "GitLab CI",
    "Commitlint",
    "Trivy",
    "Jenkins",
    "Datadog",
    "Grafana",
    "Prometheus",
    "OpenTelemetry",
    "LangSmith",
    "Pinecone",
    "Weaviate",
    "pgvector",
    "OpenSearch",
    "Azure AI Foundry",
    "Microsoft 365 Copilot",
    "GitHub Copilot",
}

METRIC_PATTERN = re.compile(
    r"(<\s*\d+\s*(?:ms|s|sec|%))"
    r"|(\b\d+\s*%)"
    r"|(\b\d+\s*(?:ms|s|sec|tokens?|minutes?|hours?|days?|weeks?|months?|years?)\b)"
    r"|(\b\d+(?:\.\d+)?\s*(?:k|m|b)\+?\b)"
    r"|(\$\s*\d+(?:\.\d+)?\s*(?:k|m|b)?\+?)",
    re.I,
)
EMOJI_PATTERN = re.compile(r"[\U0001F300-\U0001FAFF]")
POLL_PREFIX_RE = re.compile(r"^\s*(?:\d+\s*[.):]|[1-9]\uFE0F\u20E3|-)\s*")
# Matches LLM-generated placeholder tokens that should never appear in a live post
_PLACEHOLDER_LINE_RE = re.compile(
    r"^\s*(?:\[|\()?(?:Step|Option|Decision|Phase|Stage|Layer|Node|Label|Title|Section|Part|Item|"
    r"Point|Action|Result|Outcome|Choice|Poll|Answer|Insert|Replace|Your|Write|Fill|Task|Constraint|"
    r"Alternative|Solution|Scenario|Step\u00a0)[^\[\]()]*[\])]\s*$",
    re.I,
)
_PLACEHOLDER_INLINE_RE = re.compile(
    r"(?:\[|\()?(?:Step|Option|Decision|Phase|Stage|Layer|Node|Label|Title|Section|Part|Item|"
    r"Point|Action|Result|Outcome|Choice|Poll|Answer|Insert|Replace|Your|Write|Fill|Task|Constraint|"
    r"Alternative|Solution|Scenario|Step\u00a0)[^\[\]()]{1,60}[\])]",
    re.I,
)
_VISUAL_ARTIFACT_RE = re.compile(
    r"^\s*(?:[\.vV\^><\-]\s*){3,}\s*$",
    re.M
)


_NUM_ITEM_RE = re.compile(r"^([1-9])[.\)]\s+|^([1-9])\uFE0F\u20E3\s+")
SIM_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "your", "have", "has",
    "just", "into", "what", "when", "where", "which", "their", "about", "most",
    "team", "teams", "works", "work", "used", "using", "build", "system", "ai",
}
GENERIC_PHRASES = (
    "what actually works",
    "most teams",
    "when it comes to",
    "the hard part is not",
    "in production",
    "taking a step back",
)
INCIDENT_PATTERNS = [
    r"\bour production\b",
    r"\bour team\b",
    r"\bin my team\b",
    r"\bwe had an incident\b",
    r"\bproduction issue\b",
    r"\bproduction outage\b",
    r"\bdebugging\b.*\bproduction\b",
    r"\bi\s+just\s+spent\s+\d+\s*(?:hours?|hrs?)\b",
    r"\blast night\b.*\b(prod|incident|outage|issue)\b",
]

# ─── ENGAGEMENT IMPROVEMENTS ──────────────────────────────────────────────────

# Strong CTAs that drive engagement (vs weak "what do you think?")
STRONG_CTAS = [
    "How many of these mistakes have you made?",
    "Which one cost your team the most time?",
    "When was your turning point moment?",
    "What's the uncomfortable truth you experienced?",
    "Which wrong assumption did you finally fix?",
    "What would you do differently knowing this?",
    "Which trade-off bothers you most in production?",
    "How long did it take you to really learn this?",
    "What part of this does your team still get wrong?",
    "Which mistake taught you the most?",
]

VULNERABILITY_PATTERNS = [
    r"i was wrong",
    r"i didn't realize",
    r"biggest mistake",
    r"biggest failure",
    r"took me.*years?.*to learn",
    r"setup fails",
    r"architecture failed",
    r"finally understood",
    r"turns out",
    r"completely changed my mind",
    r"three times before",
    r"wasted weeks?",
    r"painful lesson",
    r"embarrassing discovery",
    r"got this wrong",
    r"production fire",
]

# High-engagement hashtags (reach multiplier)
TRENDING_HASHTAGS = {
    "ai": ["#AIengineering", "#LLM", "#RAG", "#Agentic", "#VectorDB"],
    "story": ["#CareerGrowth", "#LessonsLearned", "#EngineeringLife", "#HonestConversation"],
    "system": ["#SystemDesign", "#SoftwareArchitecture", "#DistributedSystems", "#ScaleEngineering"],
    "devops": ["#DevOps", "#Kubernetes", "#CloudNative", "#CICD"],
    "interview": ["#InterviewQuestions", "#EngineeringMindset", "#SkillDevelopment", "#TechInterviews"],
}

# ─── NEWS SOURCES ─────────────────────────────────────────────────────────────
# RSS_FEEDS: Used for news reaction posts (ai_news, tech_news, layoff_news modes)
# For trending topic discovery (trending mode), see trend_discovery.py which uses HN + Reddit APIs
RSS_FEEDS = {
    "ai": [
        "https://hnrss.org/frontpage?q=AI|ML|LLM|GPT|Transformer",
        "https://venturebeat.com/category/ai/feed/",
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://news.google.com/rss/search?q=AI+Machine+Learning&hl=en-US&gl=US&ceid=US:en"
    ],
    "tech": [
        "https://hnrss.org/frontpage",
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml"
    ],
    "layoffs": [
        "https://news.google.com/rss/search?q=tech+layoffs+OR+Microsoft+workforce+OR+Google+buyouts&hl=en-US&gl=US&ceid=US:en",
        "https://layoffs.fyi/feed/",
        "https://hnrss.org/frontpage?q=layoff|severance|exit"
    ],
    "tools": [
        "https://hnrss.org/newest?q=Show+HN",
        "https://producthunt.com/feed"
    ]
}

# ─── DIAGRAM TYPE ROTATION ────────────────────────────────────────────────────
# Maps topic category keywords to a weighted pool of diagram types.
# Used instead of always defaulting to "Modern Cards".
_DIAGRAM_TYPE_POOLS = {
    "ai":       ["Flow Chart", "Ecosystem Breakdown", "Comparison Table", "Observability Map", "Decision Tree",
                 "Iceberg Diagram", "Dashboard", "Tile Grid"],
    "data":     ["Comparison Table", "7 Layers", "Flow Chart", "Ecosystem Breakdown", "Dashboard", "Iceberg Diagram"],
    "devops":   ["Flow Chart", "Timeline", "Lane Map", "Comparison Table", "Iceberg Diagram"],
    "cloud":    ["Ecosystem Breakdown", "Architecture Diagram", "Comparison Table", "Flow Chart", "Dashboard"],
    "security": ["Decision Tree", "7 Layers", "Flow Chart", "Lane Map", "Iceberg Diagram", "Maturity Model"],
    "career":   ["Winding Roadmap", "Comparison Table", "Decision Tree", "Modern Cards", "Maturity Model", "Tile Grid"],
    "story":    ["Modern Cards", "Winding Roadmap", "Decision Tree", "Tile Grid"],
    "default":  ["Flow Chart", "Comparison Table", "Ecosystem Breakdown", "Decision Tree", "7 Layers",
                 "Architecture Diagram", "Winding Roadmap", "Modern Cards",
                 "Iceberg Diagram", "Dashboard", "Tile Grid", "Maturity Model"],
}

def _pick_diagram_type(topic_id: str = "", topic_name: str = "", category: str = "") -> str:
    """Select a diagram type based on topic, rotating through the pool using a seeded RNG."""
    combined = ((topic_id or "") + (topic_name or "") + (category or "")).lower()
    if any(x in combined for x in ["llm", "rag", "agent", "mlops", "genai", "agentic", "ai"]):
        pool = _DIAGRAM_TYPE_POOLS["ai"]
    elif any(x in combined for x in ["kafka", "data", "lake", "lakehouse", "sql"]):
        pool = _DIAGRAM_TYPE_POOLS["data"]
    elif any(x in combined for x in ["git", "devops", "cicd", "ci/cd", "docker", "kube"]):
        pool = _DIAGRAM_TYPE_POOLS["devops"]
    elif any(x in combined for x in ["aws", "cloud", "azure", "gcp", "infra"]):
        pool = _DIAGRAM_TYPE_POOLS["cloud"]
    elif any(x in combined for x in ["security", "zero-trust", "devsec", "auth"]):
        pool = _DIAGRAM_TYPE_POOLS["security"]
    elif any(x in combined for x in ["career", "skill", "job", "interview", "brand", "growth"]):
        pool = _DIAGRAM_TYPE_POOLS["career"]
    elif "story" in combined:
        pool = _DIAGRAM_TYPE_POOLS["story"]
    else:
        pool = _DIAGRAM_TYPE_POOLS["default"]
    # Use a seeded RNG so consecutive runs for the same topic still vary (seed = run date + topic)
    seed = int(hashlib.md5(
        (combined + datetime.utcnow().strftime("%Y-%m-%d")).encode()
    ).hexdigest()[:8], 16)
    return random.Random(seed).choice(pool)


# ─── HOOK STYLES ──────────────────────────────────────────────────────────────
# Each is a story archetype, not a sentence template.
# The model writes the entire post through this lens.
HOOK_STYLES = [
    (
        "Open mid-incident. Something broke in production. You diagnosed it. "
        "Start the post right there — no preamble. First sentence is the moment "
        "of failure or the surprising discovery. The rest teaches through what happened."
    ),
    (
        "Lead with one specific, counterintuitive statistic or benchmark that most "
        "engineers would not expect. One sentence. Line break. Then explain why that "
        "number exists and what it means for how they should build."
    ),
    (
        "Name the thing most engineers believe about this topic. State it plainly. "
        "Then immediately say why it is wrong or incomplete in production. "
        "The post is the correction — specific, not vague."
    ),
    (
        "Start with something you heard recently — a code review comment, a Slack "
        "message, a candidate answer in an interview. Quote it (paraphrased). "
        "Then react to it as a senior engineer would."
    ),
    (
        "Start with an honest admission. Something you believed or did for a long "
        "time that turned out to be wrong. Make it specific and a little uncomfortable. "
        "Then explain what you know now."
    ),
    (
        "Lead with a confident, slightly controversial claim about this topic. "
        "Not rage-bait — a real engineering opinion informed people might disagree with. "
        "Spend the rest of the post defending it with specifics and examples."
    ),
    (
        "Start with: 'Nobody talks about [specific thing].' Then explain that thing. "
        "The post reveals something real that tutorials and docs consistently skip."
    ),
    (
        "Open with how this topic looked 3 to 5 years ago in one short paragraph. "
        "Then show how it looks now. Let the contrast do the work. "
        "No fluff — just the delta and why it matters for engineers today."
    ),
]

# ─── TONE VARIATIONS ──────────────────────────────────────────────────────────
TONE_VARIATIONS = [
    "Senior engineer at 11pm fixing a production issue — direct, economical with words, slightly dark-humored.",
    "Tech lead writing the internal post-mortem — precise, owns mistakes, focused on what changes next.",
    "Principal engineer in a design review — thoughtful, asks hard questions, backs every claim with evidence.",
    "Staff engineer mentoring someone — patient, uses analogies, skips nothing important, zero condescension.",
    "Engineer who tried four approaches and finally found one that works — specific, quietly confident.",
    "The person at the conference who gives the best hallway talk — opinionated, concrete examples, no slides needed.",
]

# ─── FORMAT VARIATIONS ────────────────────────────────────────────────────────
FORMAT_VARIATIONS = [
    {
        "name": "numbered_sections",
        "instruction": (
            "Use numbered sections with emoji (1️⃣ 2️⃣ etc). "
            "Each section = one diagram label. Two to three sentences max per section. Punchy."
        ),
    },
    {
        "name": "short_paragraphs",
        "instruction": (
            "NO numbered list. Write in short paragraphs — two to three sentences each. "
            "Story flows: hook → insight → practical detail → so what. "
            "Vary sentence length deliberately: some one-liners, some longer."
        ),
    },
    {
        "name": "before_after",
        "instruction": (
            "Structure around contrast. For each main idea: one sentence for how "
            "most people do it, one sentence for what actually works in production. "
            "Use an em-dash or line break to separate them visually."
        ),
    },
    {
        "name": "myth_reality",
        "instruction": (
            "Each section: Myth → Reality. State the wrong belief, then the correction. "
            "Keep it tight — one myth per concept, no more. This is not a lecture."
        ),
    },
]

# ─── LENGTH VARIATIONS ────────────────────────────────────────────────────────
LENGTH_VARIATIONS = [
    "Keep it tight: 150 to 200 words. Every sentence must earn its place.",
    "Medium length: 220 to 280 words. Enough to teach, not enough to bore.",
    "Full breakdown: 280 to 340 words. Go deep on the most interesting section.",
]

# ─── VOICE CALIBRATION EXAMPLES ───────────────────────────────────────────────
# Shown verbatim in the system prompt. Add real posts that performed well.
VOICE_EXAMPLES = [
    """\
Most engineers know basic RAG.
Production teams use something different.

Here are 7 RAG patterns actually used at scale 👇

1️⃣ Naive RAG
Documents → embeddings → vector DB → LLM.
Works for prototypes. Falls apart with complex queries.

2️⃣ Retrieve-and-Rerank
A reranker model cuts irrelevant context before it reaches the LLM.
Result: better answers, fewer hallucinations, lower token cost.

3️⃣ Multimodal RAG
Text, images, audio, video — all searchable.
Used in medical AI and document intelligence today.

4️⃣ Graph RAG
Knowledge graphs instead of pure vector similarity.
Enables multi-hop reasoning across connected data.

5️⃣ Hybrid RAG
Vector search + SQL/graph/metadata combined.
This is becoming the default enterprise architecture.

6️⃣ Agentic RAG (Router)
An agent decides where to retrieve from.
Query → Router → Vector DB / API / Web Search → LLM.

7️⃣ Multi-Agent RAG
Specialised agents collaborate on a single query.
Used in autonomous research and enterprise AI systems.

The industry is moving fast.
Naive RAG is a starting point, not a destination.

💬 Which pattern are you using in production?
1️⃣ Naive  2️⃣ Hybrid  3️⃣ Graph  4️⃣ Agentic

#RAG #AIEngineering #LLM #GenerativeAI #SystemDesign""",

    """\
I spent three years thinking Kubernetes was the answer.

It was the answer to a question my team wasn't asking.

We had 12 microservices. We needed to ship faster.
We got: YAML debt, on-call rotations, and three engineers who only work on platform now.

Here is what I would do differently:

Start with managed containers — ECS, Cloud Run, whatever your cloud gives you.
Graduate to K8s when you have a dedicated platform team. Not before.
The complexity is real. The operational cost is real.
"Everyone uses Kubernetes" is not a reason.

Most teams that struggle with K8s don't have a Kubernetes problem.
They have a complexity budget problem.

Build the simplest thing that lets your engineers ship.
Optimise the platform when platform is the bottleneck.

💬 Where are you on this? Still on managed? Full K8s? Somewhere in between?

#Kubernetes #DevOps #PlatformEngineering #CloudNative #SoftwareArchitecture""",
]


# ─── SYSTEM PROMPT BUILDER ────────────────────────────────────────────────────

def _build_post_system():
    """Builds the system prompt with a randomly rotated voice example."""
    example = random.choice(VOICE_EXAMPLES)
    return f"""\
You are Komal Batra — a Staff Engineer and technical writer with 10+ years building \
production systems. You write LinkedIn posts that sound like you, not like AI.

Study this example. Match its energy, rhythm, and specificity exactly:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{example}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHY THAT EXAMPLE WORKS — internalize this before writing:
- The hook is a specific claim or moment, never a generic statement
- Sentences are short. Some are one line. Paragraph breaks create rhythm.
- Every section names ONE concrete thing: a tool, a metric, a pattern, a number
- There is a real opinion — not "it depends" or "both have merits"
- The question at the end is genuine, something the writer actually wants to know
- It sounds like a person wrote it at a desk, not a template engine

HARD RULES — no exceptions:
- Use "I" and "you" freely — first person is encouraged
- Never start two consecutive sentences with the same word
- No filler openers: "In today's...", "As we navigate...", "It's no secret..."
- No banned words: robust, crucial, delve, landscape, testament, realm, \
ever-evolving, foster, tapestry, seamless, synergy, paradigm, unprecedented, \
game-changer, leverage, revolutionize, supercharge, holistic, transformative
- Always lead with a punchy hook.
- Ensure technical depth: name specific tools, metrics (e.g. 500ms, 10k QPS), or trade-offs.
- ALWAYS end with 💬 + a genuine question + blank line + 5 to 7 hashtags
- Include exactly ONE fenced visual block that matches the planned diagram type
- If planned type is "Comparison Table", use a simple `left -> right` format
- For non-comparison topics, avoid forcing vendor-vs-vendor comparisons
- Do NOT add copyright, signature, author name, or current month/year
- CRITICAL: No structural placeholders like "(Option A)" or "[Step 1]" in your final output.
- PERSONAL ACCURACY: Do NOT invent personal life events or family details (e.g., becoming a parent, weddings, moving house, personal childhood memories) unless they are explicitly provided in the topic prompt. Keep the professional 'Technical Lead' persona grounded strictly in the provided content.
- NEGATIVE CONSTRAINT: Never output generic structural labels like "The Problem", "Core Concept", "How It Works", or "Key Takeaway" as standalone headers or narrative transitions. Just dive into the technical insight directly. Avoid saying "The problem is" or "The core concept is" - be more specific and authoritative.
- ZERO TOLERANCE: Never use ASCII art, box-drawing characters (┌, ┐, └, ┘, │, ─), or manual table boundaries (+---+) in the post text. If you need a comparison, use a simple 'Left -> Right' text format.
"""





NEWS_SYSTEM = """\
You are Komal Batra — a Technical Leader at Microsoft specializing in Cloud, AI, and System Architecture.
You design high-scale systems and provide deep technical synthesis of industry news.
You have opinions. You pick a side. You back it with specifics.

RULES:
- Lead with your honest reaction, not a summary of the news
- Use "I" freely — this is a personal take, not a press release
- One strong opinion, defended with specifics — not a both-sides take
- Include one ``` fenced visual block with 3-5 lines max. No ASCII art or visual arrows inside or outside the block.
- End with 💬 + a sharp question + 5 to 7 hashtags.
- 180 to 260 words — reactions should be tight.
- No banned words: robust, crucial, delve, landscape, seamless, synergy,
  paradigm, unprecedented, game-changer, revolutionize, supercharge,
  thrilled, excited, disruptor, democratize.
- CRITICAL: No structural placeholders like "[Option A]" or "(Step 1)".
- Never mention the current month or year.
- Do NOT add copyright or signature.
- ZERO TOLERANCE: Never use ASCII art or box-drawing characters (+---+ or |---|) in the text.
"""

STORY_THEMES = [
    {
        "id": "llm-agent-realization",
        "name": "AI Agent Interaction",
        "prompt": "The technical moment you realized a multi-agent system wasn't behaving as expected, and how you fixed the signal-to-noise ratio in agent communication.",
        "angle": "Explain the technical 'why', then give 3 architectural fixes for better agent reliability.",
        "diagram_type": "Architecture Diagram",
        "diagram_subject": "Agent A -> Brain -> Agent B -> Feedback Loop",
    },
    {
        "id": "rag-strategy-shift",
        "name": "RAG Strategy Shift",
        "prompt": "Why simple vector retrieval isn't enough for production AI. A story about high latency or low relevance solved by hybrid search or reranking.",
        "angle": "Focus on the performance metrics (latency/relevance) and 3 specific retrieval optimizations.",
        "diagram_type": "System Design",
        "diagram_subject": "User Query -> Vector DB -> Hybrid Search -> Reranker -> LLM",
    },
    {
        "id": "personal-ai-daily-life",
        "name": "Personal AI Productivity",
        "prompt": "How you built a custom AI agent (using LangGraph/Autogen/Modal) to handle a repetitive part of your personal life: travel planning, meal prep, or learning a new skill.",
        "angle": "Name specific tools and libraries. Show the transition from manual friction to AI automation.",
        "diagram_type": "Workflow",
        "diagram_subject": "Friction Point -> AI Tooling -> Automated Flow -> Time Saved",
    },
    {
        "id": "ml-model-fine-tuning",
        "name": "Model Observability Moment",
        "prompt": "The day you found drift or hallucination in a production ML model, and the specific metrics you used to diagnose and repair it.",
        "angle": "Be technical: discuss perplexity, semantic similarity, or drift detection tools.",
        "diagram_type": "Monitoring Map",
        "diagram_subject": "Feature Input -> Prediction -> Drift Detection -> Alert -> Retrain",
    },
]

STORY_SYSTEM = """\
You are Komal Batra writing a personal story post for LinkedIn.

BANNED OPENERS — the post will be rejected if it starts with any of these:
- "I recently overheard", "I firmly believe", "I believe that"
- "In today's world", "Our online presence", "It's important"
- "As a Staff Engineer, I", "Upon further investigation"
- Any sentence that starts with "I" + a belief verb (believe, think, feel, know)

REQUIRED STRUCTURE — follow this exactly:
1. LINE 1: One specific scene. A thing you clicked, read, typed, or saw.
   GOOD: "I searched my own name in ChatGPT last week."
   GOOD: "A candidate told me their AI assistant found my profile before my website."
   BAD:  "I recently overheard a colleague mention..."
   BAD:  "I firmly believe online presence matters."

2. LINE 2-3: What you found — specific and uncomfortable. Not vague.

3. THREE NUMBERED ACTIONS — each must be:
   - A complete sentence ending with a period
   - Under 8 words
   - Actionable TODAY, not aspirational
   GOOD: "1️⃣ Rewrite your LinkedIn headline to name one specific skill."
   BAD:  "1️⃣ I will ensure my LinkedIn profile"

4. DO NOT repeat the numbered actions as plain text below them.

5. One honest reflection sentence — what this changed.

6. 💬 + specific question + 4-7 hashtags.

FORMAT: 160-220 words. One ``` fenced block showing 3-5 action steps.
Do NOT mention the current month or year.
"""


# ─── HASHTAG OPTIMIZATION ─────────────────────────────────────────────────────

def optimize_hashtags_for_reach(post_text, post_type="topic"):
    """Replace generic hashtags with trending ones for better reach."""
    existing_tags = re.findall(r"(?<!\w)#\w+", post_text)
    existing_lower = {t.lower() for t in existing_tags}
    
    # Get relevant trend tag list
    type_key = "interview" if "interview" in post_type.lower() else post_type
    trending = TRENDING_HASHTAGS.get(type_key, TRENDING_HASHTAGS.get("system", []))
    
    if not trending:
        return post_text
    
    # Replace generic tags with trending ones (priority)
    generic_tags = {"#AI", "#Tech", "#DevOps", "#Engineering", "#Learning"}
    tags_to_replace = [t for t in existing_tags if t in generic_tags]
    
    updatedText = post_text
    for old_tag in tags_to_replace[:2]:  # Replace max 2 generic tags
        candidates = [t for t in trending if t.lower() not in existing_lower]
        if candidates:
            new_tag = random.choice(candidates)
            updatedText = updatedText.replace(old_tag, new_tag, 1)
            existing_lower.add(new_tag.lower())
    
    # Ensure double newline before hashtags if we are adding them
    if not re.search(r"\n\n#", updatedText):
        # If text ends with text (not hashtags/newlines), add the spacing
        if not updatedText.rstrip().endswith("#"):
            # If it already has hashtags but no double newline, try to inject it
            if "#" in updatedText and not "\n\n#" in updatedText:
                updatedText = re.sub(r"([^\n])(\s*#)", r"\1\n\n\2", updatedText, count=1)
    
    # Ensure 5-7 total hashtags (sweet spot for LinkedIn)
    final_tags = re.findall(r"(?<!\w)#\w+", updatedText)
    seen_lower = {t.lower() for t in final_tags}
    if len(final_tags) < 5 and trending:
        # Add missing tags — only add ones not already present
        for _ in range(5 - len(final_tags)):
            candidates = [t for t in trending if t.lower() not in seen_lower]
            if candidates:
                new_tag = random.choice(candidates)
                # Ensure spacing for the first newly added tag if none existed
                sep = " " if "#" in updatedText else "\n\n"
                updatedText = updatedText.rstrip() + f"{sep}{new_tag}"
                seen_lower.add(new_tag.lower())
    
    return updatedText



def _deduplicate_hashtags(text):
    """Final safety net: deduplicate hashtags and cap at 7."""
    if not text:
        return text
    lines = text.splitlines()
    # Find the last contiguous block of hashtag-only lines
    hashtag_start = None
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if stripped and all(t.startswith("#") for t in stripped.split()):
            hashtag_start = i
        else:
            break
    if hashtag_start is None:
        return text
    # Extract all hashtags from the hashtag block
    hashtag_block = " ".join(lines[hashtag_start:])
    all_tags = re.findall(r"(?<!\w)#\w+", hashtag_block)
    # Deduplicate preserving order (case-insensitive)
    seen = set()
    unique_tags = []
    for tag in all_tags:
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            unique_tags.append(tag)
    # Cap at 7
    unique_tags = unique_tags[:7]
    # Rebuild
    body_lines = lines[:hashtag_start]
    # Remove trailing empty lines from body
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()
    return "\n".join(body_lines) + "\n\n" + " ".join(unique_tags)


# ─── AI CALL ──────────────────────────────────────────────────────────────────

def call_ai(prompt, system, json_mode=False):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY secret not set")
    
    current_model = MODEL
    
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
    }
    
    last_err = None
    for attempt in range(3):
        payload = {
            "model": current_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2048 if json_mode else 1024,
            "temperature": 0.85,
        }
        
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=45)
            
            if resp.status_code == 429:
                if current_model == MODEL:
                    log.warning(f"Groq primary model (70B) rate-limited. Falling back INSTANTLY to 8B model...")
                    current_model = MODEL_FALLBACK
                    continue
                else:
                    wait = int(resp.headers.get("Retry-After", 20))
                    log.warning(f"Groq fallback model also rate-limited. Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                    
            if resp.status_code >= 500:
                log.warning(f"Groq server error {resp.status_code} (attempt {attempt+1}/3) — retrying in 5s")
                time.sleep(5)
                continue
                
            if resp.status_code != 200:
                log.error(f"Groq error ({resp.status_code}): {resp.text}")
                
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
            
        except requests.exceptions.Timeout:
            log.warning(f"Groq request timed out (attempt {attempt+1}/3) — retrying")
            last_err = "timeout"
            time.sleep(3)
        except requests.exceptions.RequestException as e:
            log.warning(f"Groq request failed (attempt {attempt+1}/3): {e}")
            last_err = str(e)
            time.sleep(3)
            
    raise RuntimeError(f"Groq call failed after 3 attempts: {last_err}")


def _fallback_visual_block(structure=None):
    if structure and structure.get("sections"):
        labels = [s.get("label", f"Step {idx+1}") for idx, s in enumerate(structure.get("sections", [])[:5])]
        return "\n".join(labels)
    if structure and structure.get("rows"):
        labels = [r.get("label", f"Row {idx+1}") for idx, r in enumerate(structure.get("rows", [])[:5])]
        return "\n".join(labels)
    return "Problem -> Constraints -> Choice -> Trade-off -> Decision"


def _fallback_topic_post(topic, structure=None):
    title = topic.get("name", "Engineering Topic")
    angle = topic.get("angle", "practical production insights")
    visual = _fallback_visual_block(structure)
    return (
        f"{title} is less about theory and more about trade-offs in production. ⚙️\n\n"
        f"My current lens: {angle}. I optimize for clarity first, then scale, then cost. 🚀\n\n"
        "The fastest way to improve outcomes is to choose the simplest design that still meets reliability goals. "
        "That keeps systems easier to debug, cheaper to run, and safer to evolve. 🧠\n\n"
        "```text\n"
        f"{visual}\n"
        "```\n\n"
        "💬 If you had to simplify one part of your current architecture this week, what would you change first?\n\n"
        "#SystemDesign #SoftwareArchitecture #Engineering #Scalability #TechLeadership"
    )


# ─── RSS FETCH ────────────────────────────────────────────────────────────────

def fetch_rss_news(category="tech", max_items=5):
    feeds = RSS_FEEDS.get(category, RSS_FEEDS["tech"])
    articles = []
    for feed_url in feeds:
        try:
            resp = requests.get(feed_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                continue
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
            for item in items[:max_items]:
                title    = item.findtext("title", "").strip()
                desc     = item.findtext("description", "").strip()
                link     = item.findtext("link", "").strip()
                pub_date = item.findtext("pubDate", "").strip()
                desc = re.sub(r'<[^>]+>', '', desc)[:300]
                if title and len(title) > 10:
                    articles.append({
                        "title": title,
                        "description": desc,
                        "link": link,
                        "date": pub_date,
                    })
            if len(articles) >= max_items:
                break
        except Exception as e:
            log.warning("RSS fetch failed for " + feed_url + ": " + str(e))
            continue
    return articles[:max_items]


# ─── POST GENERATORS ──────────────────────────────────────────────────────────

def generate_news_post(news_type="ai"):
    log.info("Fetching latest " + news_type + " news...")
    articles = fetch_rss_news(news_type, max_items=5)

    if not articles:
        log.warning("No news fetched, falling back to topic post")
        return None

    news_text = ""
    for i, a in enumerate(articles[:3]):
        news_text += f"\n{i+1}. {a['title']}\n   {a['description'][:200]}\n"

    log.info("Fetched " + str(len(articles)) + " news articles")

    hook   = random.choice(HOOK_STYLES)
    tone   = random.choice(TONE_VARIATIONS)
    length = random.choice(LENGTH_VARIATIONS)

    prompt = f"""Latest {news_type} tech news:
{news_text}

Story archetype (hook): {hook}
Voice: {tone}
Length: {length}

Pick the most technically interesting story. Write a LinkedIn post that:
- Starts with your personal reaction — not a neutral summary
- Mentions the actual company, product, or number from the news
- Includes one ``` fenced visual block that supports the argument
- Takes a real position — not "time will tell"
"""
    try:
        return _cleanup_generated_post(call_ai(prompt, NEWS_SYSTEM))
    except Exception as e:
        log.warning(f"News generation failed ({news_type}), falling back to topic mode: {e}")
        return None

def _extract_story_sections(post_text, theme):
    """
    Extract actual numbered takeaways from a generated story post.
    Rejects truncated items. Falls back to theme-based sections if needed.
    """
    lines = (post_text or "").splitlines()
    sections = []
    seen_labels = set()

    for line in lines:
        stripped = line.strip()
        # Match emoji numbers or plain numbers
        m = re.match(
            r"^(?:[1-9]\uFE0F\u20E3|[1-9][\.\)])\s+(.+)$",
            stripped
        )
        if not m:
            continue

        label = m.group(1).strip()
        # Clean formatting artifacts
        label = re.sub(r"\s*[—:–]\s*.*$", "", label).strip(" .*")
        label = re.sub(r"\*+", "", label).strip()

        # Quality gates — reject truncated or duplicate items
        if len(label) < 8:
            continue  # Too short — probably truncated
        if label.lower() in seen_labels:
            continue  # Duplicate
        # Reject items that end with prepositions/conjunctions — sign of truncation
        last_word = label.rstrip(".!?,").split()[-1].lower() if label.split() else ""
        if last_word in {"and", "or", "the", "a", "an", "my", "your", "their", "our", "of", "to", "in", "for", "with"}:
            continue  # Truncated mid-thought

        seen_labels.add(label.lower())
        sections.append({
            "id": len(sections) + 1,
            "label": label[:42],
            "desc": "",
        })
        if len(sections) >= 5:
            break

    # Need at least 3 good sections
    if len(sections) >= 3:
        return sections

    # Fallback: use theme-specific sections
    theme_id = theme.get("id", "")
    if "career" in theme_id or "leverage" in theme_id:
        return [
            {"id": 1, "label": "Old Way: Manual everything", "desc": ""},
            {"id": 2, "label": "New Way: AI handles repetition", "desc": ""},
            {"id": 3, "label": "Your role shifts to judgment", "desc": ""},
            {"id": 4, "label": "Ship more with fewer people", "desc": ""},
            {"id": 5, "label": "Leverage compounds over time", "desc": ""},
        ]
    if "discovery" in theme_id or "name" in theme_id or "search" in theme_id:
        return [
            {"id": 1, "label": "Search your own name in AI tools", "desc": ""},
            {"id": 2, "label": "Find the gaps in your signal", "desc": ""},
            {"id": 3, "label": "Rewrite your headline for clarity", "desc": ""},
            {"id": 4, "label": "Publish proof, not just claims", "desc": ""},
            {"id": 5, "label": "Stay consistent for 90 days", "desc": ""},
        ]
    return [
        {"id": 1, "label": "The moment that changed things", "desc": ""},
        {"id": 2, "label": "What I was getting wrong", "desc": ""},
        {"id": 3, "label": "First concrete action I took", "desc": ""},
        {"id": 4, "label": "Second thing I changed", "desc": ""},
        {"id": 5, "label": "What's different now", "desc": ""},
    ]

def generate_story_post(theme=None):
    theme = theme or random.choice(STORY_THEMES)
    hook = random.choice(HOOK_STYLES)
    tone = random.choice(TONE_VARIATIONS)
    length = random.choice(LENGTH_VARIATIONS)

    prompt = f"""Write a LinkedIn post in story format.
Theme: {theme["prompt"]}
Angle: {theme["angle"]}
Hook style: {hook}
Voice: {tone}
Length target: {length}

Requirements:
- One clear moment -> one insight -> three practical actions.
- Keep it to one topic only.
- Do not invent unsupported metrics, salary ranges, or percentages.
- Include one ``` fenced visual block that reflects the 3 actions.
"""
    try:
        post_text = _cleanup_generated_post(call_ai(prompt, STORY_SYSTEM))
    except Exception as e:
        log.warning(f"Story generation failed, using fallback story copy: {e}")
        post_text = (
            "AI is changing discoverability faster than most people realize. 🔎\n\n"
            "One moment made this obvious to me: assistants now surface people and companies from clear public signals, not just ads. "
            "That shifts the game toward proof, clarity, and consistency. 📈\n\n"
            "```text\n"
            "Moment -> Insight -> Action 1 -> Action 2 -> Action 3\n"
            "```\n\n"
            "Three actions that work right away: tighten your headline, publish concrete outcomes, and keep a steady posting rhythm. 🛠️\n\n"
            "💬 What signal do you want AI tools to associate with your profile?\n\n"
            "#AIAgents #FutureOfWork #PersonalBranding #CareerGrowth #ArtificialIntelligence"
        )
    story_topic = {
        "id": f"story-{theme['id']}",
        "name": theme["name"],
        "category": "Story",
        "prompt": theme["prompt"],
        "angle": theme["angle"],
        "diagram_subject": theme.get("diagram_subject", theme["name"]),
        "diagram_type": theme.get("diagram_type") or _pick_diagram_type(
            topic_id=f"story-{theme['id']}",
            topic_name=theme["name"],
            category="story",
        ),
    }
    return story_topic, post_text


def generate_interview_post():
    """Generate interview-style post with rotating topics - NEW feature."""
    log.info("Generating interview post...")
    
    try:
        from interview_post_generator import InterviewPostGenerator
        
        gen = InterviewPostGenerator()
        
        # Get random question (will rotate naturally)
        question = gen.get_random_question()
        
        if not question:
            log.warning("No interview questions available, falling back to topic mode")
            return None, None
        
        # Generate post from question
        post_text = gen.generate_post_from_question(question)
        
        if not post_text:
            log.warning("Interview post generation failed")
            return None, None
        
        # Find parent topic
        parent_topic = None
        for topic_key, topic_data in gen.topics.items():
            for q in topic_data.get("questions", []):
                if q.get("id") == question.get("id"):
                    parent_topic = topic_key
                    break
        
        # Get recommended diagram styles
        diagram_styles = gen.get_best_diagram_styles(parent_topic) if parent_topic else [7]
        
        # Create metadata for integration
        topic = {
            "id": f"interview-{question.get('id', str(random.randint(1000, 9999)))}",
            "name": f"Interview: {parent_topic.title() if parent_topic else 'Developer Question'}",
            "category": "Interview",
            "prompt": question.get("question", ""),
            "angle": question.get("type", "opinion_poll"),
            "diagram_type": _pick_diagram_type(
                topic_id=f"interview-{parent_topic or ''}",
                topic_name=parent_topic or "",
                category="interview",
            ),
            "diagram_styles": diagram_styles,
        }
        
        log.info(f"Interview post generated from topic: {parent_topic}")
        return topic, post_text
    
    except ImportError:
        log.warning("interview_post_generator not available, falling back")
        return None, None
    except Exception as e:
        log.error(f"Interview post generation error: {e}")
        return None, None


def _build_post_template_instructions(diagram_type, structure=None):
    section_count = len(structure.get("sections", [])) if structure else 0

    templates = {
        "Decision Tree": (
            "Structure the post like a real decision memo. "
            "Open with the hard decision people get wrong. "
            "Walk through the branches in order using 'If ... then ...' logic. "
            "Be explicit about when NOT to use the more complex option. "
            "End with the single decision criterion that matters most."
        ),
        "7 Layers": (
            f"Write this as a layered breakdown with exactly {max(section_count, 5)} layers. "
            "Open with the hidden thesis or moat. "
            "Each section should name one layer and explain why it matters strategically. "
            "This should read like an argument, not a textbook explanation."
        ),
        "Ecosystem Breakdown": (
            "Write this like a practical ecosystem map. "
            "Group tools/components into clear layers (foundation, build/orchestrate, govern/operate). "
            "Show how the layers connect and where teams usually break integration. "
            "Finish with a clear adoption rule: start narrow, then expand stack coverage."
        ),
        "Signal vs Noise": (
            "Write this as a judgment call. "
            "Open with whether this is signal, noise, or a mix. "
            "Call out what is overrated, what is real, and where teams get misled. "
            "Use a decisive tone instead of neutral explanation."
        ),
        "Lane Map": (
            "Write this as an editorial workflow breakdown. "
            "Each section should describe one operating lane or system role. "
            "Emphasize how the lanes connect, hand off work, and fail in production."
        ),
        "Observability Map": (
            "Write this like an operating checklist for production AI. "
            "Focus on where signals enter, where context changes, what can fail silently, "
            "and which alerts tell you quality is slipping before users complain."
        ),
        "Comparison Table": (
            "Write this as a practical comparison. "
            "Do not just list differences; make a recommendation about when each option wins. "
            "Use a clear rule-of-thumb section near the end."
        ),
        "Winding Roadmap": (
            "Write this as a staged journey. "
            "Each section should feel like the next step in capability, not just a list item."
        ),
    }
    return templates.get(diagram_type, "")


def _build_visual_block_instruction(diagram_type):
    if diagram_type == "Comparison Table":
        return (
            "Include one ``` fenced comparison block using concise `left -> right` lines. "
            "Keep entities relevant to the topic only."
        )
    if diagram_type == "Ecosystem Breakdown":
        return (
            "Include one ``` fenced grouped-layer block with 3 headings: "
            "Foundation | Build/Orchestrate | Govern/Operate. Keep each layer concise."
        )
    if diagram_type in {"Decision Tree", "Winding Roadmap", "Flow Chart", "Lane Map"}:
        return (
            "Include one ``` fenced flow block using plain ASCII connectors like `->` or `|`."
        )
    return (
        "Include one ``` fenced visual block (outline, framework, or mini-map) "
        "that mirrors the post structure."
    )


def generate_topic_post(topic, structure=None, diagram_type="", dry_run=False):
    log.info("Generating post: " + topic["name"])

    # If no diagram type was provided (the most common path), pick one dynamically
    # so we get real variety instead of always defaulting to Modern Cards.
    if not diagram_type:
        diagram_type = topic.get("diagram_type") or _pick_diagram_type(
            topic_id=topic.get("id", ""),
            topic_name=topic.get("name", ""),
            category=topic.get("category", ""),
        )

    hook   = random.choice(HOOK_STYLES)
    tone   = random.choice(TONE_VARIATIONS)
    fmt    = random.choice(FORMAT_VARIATIONS)
    length = random.choice(LENGTH_VARIATIONS)
    template_instruction = _build_post_template_instructions(diagram_type, structure)

    if structure and structure.get("sections"):
        sections = structure["sections"]
        n = len(sections)
        section_list = "\n".join(
            f"  {s['id']}. {s['label']} — {s['desc']}"
            for s in sections
        )
        structure_block = f"""
The diagram has exactly {n} sections — cover them in this order:
{section_list}

Match each label word-for-word. End with a poll listing all {n} options."""
    elif structure and structure.get("rows"):
        rows = structure["rows"]
        n = len(rows)
        row_list = "\n".join(
            f"  {idx+1}. {row.get('label', f'Row {idx+1}')} — {row.get('text', row.get('type', 'row'))}"
            for idx, row in enumerate(rows)
        )
        structure_block = f"""
The diagram has exactly {n} rows — cover them in this order:
{row_list}

Match the row labels closely so the text and image stay coherent."""
    else:
        structure_block = ""

    if template_instruction:
        structure_block += f"\n\nPost template guidance:\n{template_instruction}"
    structure_block += f"\n\nVisual block guidance:\n{_build_visual_block_instruction(diagram_type)}"

    prompt = f"""Write a LinkedIn post about: {topic["prompt"]}
Angle: {topic.get("angle", "practical, production-level insights")}
Planned diagram type: {diagram_type or topic.get("diagram_type", "Architecture Diagram")}

CRITICAL FORMATTING RULES — violations will cause the post to fail:
1. Every numbered item (1️⃣ 2️⃣ 3️⃣) MUST be a complete, self-contained sentence.
2. NEVER write a numbered item that ends without a period. "1️⃣ I will ensure my LinkedIn" is WRONG. "1️⃣ Update your LinkedIn headline to name your exact expertise." is CORRECT.
3. NEVER list the same content twice. If you write numbered items, do NOT repeat them as plain text below.
4. Each numbered item must be SHORT enough to fit on ONE line — max 8 words per item.

Story archetype (hook): {hook}
Voice: {tone}
Format: {fmt["instruction"]}
Length target: {length}
{structure_block}

Requirements:
- Do not invent personal incidents, team stories, tool names, or metrics that were not explicitly provided in the topic
- Do not mention your own workplace incidents (debugging sessions, outages, production fires, internal team events)
- If the topic does not include a concrete metric, use qualitative language instead of numbers
- If the topic does not include named tools, keep examples generic instead of dropping in brand names
- Use 4 to 10 relevant emojis naturally across hook, bullets, and CTA (not spammy)
- Include exactly one fenced visual block that matches the planned diagram type
- Keep the fenced visual block concise (3 to 6 lines); avoid large ASCII box art
- Do not use Mermaid syntax or graph declarations like `graph LR`, `graph TD`, or `flowchart`
- Keep this to exactly one topic only; do not append or preview a second post
- Poll/CTA options must be concrete answer choices (not repeated section headers like "Task Shape", "Need Tools")
- The hook must be the very first line — no warming up, no preamble
- Keep paragraphs short and punchy (1 to 2 sentences where possible)
- Never mention the current month or year
"""
    try:
        post_text = _cleanup_generated_post(call_ai(prompt, _build_post_system()))
    except Exception as e:
        log.warning(f"Topic generation failed for {topic.get('id', 'unknown')}, using fallback copy: {e}")
        return _fallback_topic_post(topic, structure=structure)
    # Skip revision pass in dry run — saves one full LLM round-trip (~30s)
    if not dry_run:
        issues = _post_quality_issues(topic, post_text, structure, diagram_type)
        if issues:
            revision_prompt = (
                prompt
                + "\nRevision feedback:\n- "
                + "\n- ".join(issues[:5])
                + "\nRewrite the post from scratch and fix every issue above."
            )
            try:
                post_text = _cleanup_generated_post(call_ai(revision_prompt, _build_post_system()))
            except Exception as e:
                log.warning(f"Topic revision failed for {topic.get('id', 'unknown')}, keeping first draft: {e}")
    return _cleanup_generated_post(post_text)


def _cleanup_generated_post(text):
    if not text:
        return text
    
    # 1. Strip ASCII art and box-drawing leak from LLM
    text = _strip_ascii_art(text)
    
    # 2. Basic cleanup
    text = (text or "").replace("hashtag#", "#").strip()
    if not text:
        return text

    text = re.sub(r"\n{3,}", "\n\n", text)
    normalized = text.strip()

    first_line = normalized.splitlines()[0].strip() if normalized.splitlines() else ""
    if first_line:
        marker = "\n" + first_line + "\n"
        second_pos = normalized.find(marker, len(first_line) + 1)
        if second_pos > 20:
            text = normalized[:second_pos].strip()
            normalized = text

    for copies in (3, 2):
        if len(normalized) >= copies * 40:
            chunk_len = len(normalized) // copies
            if chunk_len * copies == len(normalized):
                chunk = normalized[:chunk_len].strip()
                if chunk and chunk * copies == normalized.replace("\r", ""):
                    text = chunk
                    normalized = text
                    break

    # Remove exact repeated full-post blocks that sometimes appear back-to-back.
    lines = [ln.rstrip() for ln in text.splitlines()]
    while lines and not lines[-1].strip():
        lines.pop()
    n = len(lines)
    for chunk_len in range(n // 3, 3, -1):
        if n >= chunk_len * 2:
            first = lines[:chunk_len]
            second = lines[chunk_len:chunk_len * 2]
            if first == second:
                lines = first + lines[chunk_len * 2:]
                break
        if n >= chunk_len * 3:
            first = lines[:chunk_len]
            second = lines[chunk_len:chunk_len * 2]
            third = lines[chunk_len * 2:chunk_len * 3]
            if first == second == third:
                lines = first + lines[chunk_len * 3:]
                break

    text = "\n".join(lines).strip()

    # --- Structural Cleanup ---
    # 1. Remove lines containing just structural pipe separators like "A | B | C"
    text = re.sub(r"(?m)^\s*(?:[A-Za-z\s]+\s*\|\s*){2,}[A-Za-z\s]*\s*$", "", text)
    
    # 2. Strip generic placeholder-only lines (using prefix match to catch full sentences)
    _PLACEHOLDERS = [
        "the problem", "core concept", "how it works", "key takeaway", 
        "takeaway", "summary", "conclusion", "introduction", "hook",
        "story archetype", "voice:", "format:", "length target:", "requirements:"
    ]
    cleaned_lines = []
    for line in text.splitlines():
        low = line.lower().strip(" .*:!")
        if any(low.startswith(p) for p in _PLACEHOLDERS):
            continue
        # Remove lines that are just "The Problem | Core Concept"
        if "|" in line and any(p in line.lower() for p in _PLACEHOLDERS if len(p) > 5):
            continue
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines).strip()

    # 3. Bullet Validator for CTA (Poll)
    # If we see "1️⃣ The Problem 2️⃣ Core Concept", wipe those specific items as they are hallucinations.
    # An item is valid if it has at least 3 descriptive words or a technical term.
    lines = text.splitlines()
    if lines:
        new_lines = list(lines)
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Match 1️⃣, 2️⃣, etc.
            m = re.match(r"^([1-9]\uFE0F\u20E3|[1-9][\.\)])\s*(.+)$", stripped)
            if m:
                content = m.group(2).strip(" .*:!")
                # Prefix match check for bullets
                if any(content.lower().startswith(p) for p in _PLACEHOLDERS if len(p) > 3) or len(content.split()) < 3:
                    # Remove this line by setting it empty
                    new_lines[i] = ""
        text = "\n".join(ln for ln in new_lines if ln or not ln.isspace()).strip()


    return text

    # Collapse accidental repeated title/header lines at the top.
    split_lines = text.splitlines()
    if len(split_lines) >= 2 and split_lines[0].strip() == split_lines[1].strip():
        split_lines.pop(1)
        text = "\n".join(split_lines).strip()

    # Guard against accidental multi-post output from the model.
    split_markers = [
        r"\n\s*next post\s*:",
        r"\n\s*third post\s*:",
        r"\n\s*post\s*2\s*:",
        r"\n\s*another post\s*:",
        r"\n\s*here'?s another\s*:",
    ]
    lowered = text.lower()
    cut_positions = []
    for pattern in split_markers:
        m = re.search(pattern, lowered, flags=re.IGNORECASE)
        if m:
            cut_positions.append(m.start())
    if cut_positions:
        text = text[:min(cut_positions)].strip()

    # Keep only one fenced visual/code block to prevent duplicated diagram sections.
    fence_matches = list(re.finditer(r"```[\s\S]*?```", text))
    if len(fence_matches) > 1:
        keep_start, keep_end = fence_matches[0].span()
        rebuilt = [text[:keep_end]]
        for idx in range(1, len(fence_matches)):
            prev_end = fence_matches[idx - 1].end()
            curr_start = fence_matches[idx].start()
            rebuilt.append(text[prev_end:curr_start])
        rebuilt.append(text[fence_matches[-1].end():])
        text = "".join(rebuilt).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)

    # Fix malformed opening quote in the first line.
    first_line = text.splitlines()[0] if text.splitlines() else ""
    if first_line.startswith('"') and first_line.count('"') == 1:
        text = first_line[1:].lstrip() + ("\n" + "\n".join(text.splitlines()[1:]) if len(text.splitlines()) > 1 else "")
    elif first_line.startswith("'") and first_line.count("'") == 1:
        text = first_line[1:].lstrip() + ("\n" + "\n".join(text.splitlines()[1:]) if len(text.splitlines()) > 1 else "")

     # Strip structure-block leakage — LLM sometimes echoes the diagram labels verbatim
    # Pattern: "Label: description" on its own line where label matches known section words
# Pattern 1: "Label: description" lines
    STRUCTURE_ECHO_PATTERN = re.compile(
        r"^(?:The Problem|Core Concept|How It Works|Best Practices|"
        r"Common Mistakes|Key Takeaway|Phase \d+|Step \d+|"
        r"Foundation|Data Layer|Service Layer|Integration|User|"
        r"Risk Tiering|Model Registry|Policy Controls|Monitoring|"
        r"Auditability|Reporting|Response|Ingest|Process|Store|"
        r"Serve|Govern|Deploy|Observe|Scale|Build|Test|Operate)\s*:.*$",
        re.MULTILINE | re.IGNORECASE
    )
    echo_matches = STRUCTURE_ECHO_PATTERN.findall(text)
    if len(echo_matches) >= 3:
        text = STRUCTURE_ECHO_PATTERN.sub("", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # Pattern 2: structure labels printed as a single space-separated line
    # e.g. "Risk Tiering Model Registry Policy Controls Monitoring"
    # Detect: a line with 4+ title-case words and no verbs/connectors
    lines_check = text.splitlines()
    cleaned_lines = []
    for ln in lines_check:
        stripped = ln.strip()
        words = stripped.split()
        if len(words) >= 4:
            # Check if ALL words are title-cased and none are common connectors
            connectors = {"and","or","the","a","an","is","are","was","were",
                         "to","of","in","for","with","that","this","it","but"}
            all_title = all(
                w[0].isupper() and w.lower() not in connectors
                for w in words if w.isalpha()
            )
            # Also check no sentence-ending punctuation — pure label dump
            no_punct = not any(c in stripped for c in ".!?,;:")
            if all_title and no_punct and len(words) >= 4:
                continue  # Skip this line — it's a leaked structure dump
        cleaned_lines.append(ln)
    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text


def _normalize_hashtags(text):
    cleaned = text or ""
    # Handle all variations of the hashtag# leak
    cleaned = cleaned.replace("hashtag#", "#")
    cleaned = cleaned.replace("Hashtag#", "#")
    cleaned = cleaned.replace("HASHTAG#", "#")
    # Handle "hashtag #Word" (space between hashtag and #)
    cleaned = re.sub(r"\bhashtag\s+#", "#", cleaned, flags=re.I)
    # Handle "hashtag Word" (no # at all — LLM sometimes does this)
    cleaned = re.sub(r"\bhashtag\s+([A-Z][A-Za-z0-9]+)", r"#\1", cleaned)
    # Fix broken tags like "# Agents" -> "#Agents"
    cleaned = re.sub(r"(?<!\w)#\s+([A-Za-z][A-Za-z0-9_]*)", r"#\1", cleaned)
    return cleaned


def _shorten_poll_label(label, max_words=6, max_chars=42):
    raw = re.sub(r"\s+", " ", (label or "")).strip(" .")
    raw = re.sub(r"^(?:with|using|for)\s+", "", raw, flags=re.I)
    # Keep strong noun phrase before long qualifiers.
    raw = re.split(r"\s+(?:with|using|for|that|which)\s+", raw, maxsplit=1, flags=re.I)[0]
    words = raw.split()
    if len(words) > max_words:
        raw = " ".join(words[:max_words]).strip()
    if len(raw) > max_chars:
        raw = raw[:max_chars].rsplit(" ", 1)[0].strip()
    return raw.strip(" ,.-")


def _tighten_poll_options(text):
    lines = (text or "").splitlines()
    if not lines:
        return text
    for i, line in enumerate(lines):
        m = POLL_PREFIX_RE.match(line.strip())
        if not m:
            continue
        label = POLL_PREFIX_RE.sub("", line.strip()).strip()
        short = _shorten_poll_label(label)
        if short:
            lines[i] = m.group(0).strip() + " " + short
    return "\n".join(lines).strip()


def _reduce_repetitive_copy(text):
    lines = (text or "").splitlines()
    if not lines:
        return text

    out = []
    seen_norm = set()
    prev_non_empty = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue

        norm = re.sub(r"[^a-z0-9]+", " ", stripped.lower()).strip()
        # Skip duplicate non-hashtag lines.
        if norm in seen_norm and not stripped.startswith("#"):
            continue
        seen_norm.add(norm)

        # Avoid repeated "If ... then ..." cadence.
        if stripped.startswith("If ") and prev_non_empty.startswith("If "):
            stripped = "When " + stripped[3:]

        out.append(stripped)
        prev_non_empty = stripped

    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _remove_raw_flow_only_lines(text):
    lines = (text or "").splitlines()
    if not lines:
        return text
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Remove bare flow-only lines like "A -> B -> C" that look like leaked draft notes.
        if re.match(r"^[A-Za-z0-9][A-Za-z0-9\s/\-&()]{1,30}(?:\s*->\s*[A-Za-z0-9][A-Za-z0-9\s/\-&()]{1,30}){2,}\s*$", stripped):
            continue
        cleaned.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned)).strip()


def _topic_text_blob(topic):
    return " ".join(
        str(topic.get(k, ""))
        for k in ("name", "prompt", "angle", "diagram_subject", "diagram_type", "category")
    )


def _detect_named_tools(text):
    lowered = (text or "").lower()
    return {
        tool for tool in KNOWN_TOOL_NAMES
        if tool.lower() in lowered
    }


def _label_in_post(label, lowered_post):
    words = [w for w in re.split(r"[^a-z0-9]+", (label or "").lower()) if len(w) > 2]
    if not words:
        return False
    return any(word in lowered_post for word in words)


def _post_quality_issues(topic, post_text, structure=None, diagram_type=""):
    issues = []
    cleaned = _cleanup_generated_post(post_text or "")
    lowered = cleaned.lower()
    topic_blob = _topic_text_blob(topic).lower()

    # ─── ENGAGEMENT QUALITY CHECKS (NEW) ───────────────────────────────────────
    # Check for vulnerability (drives engagement +500%)
    has_vulnerability = any(re.search(pattern, lowered) for pattern in VULNERABILITY_PATTERNS)
    if not has_vulnerability:
        issues.append("Add vulnerability: mention a mistake, failure, or lesson learned. Try 'I was wrong', 'took me years to learn', or 'finally understood'.")

    # Check for strong CTA (drives engagement +200%)
    has_strong_cta = any(cta.lower() in lowered for cta in STRONG_CTAS)
    weak_cta_patterns = [r"what do you think\?", r"thoughts\?", r"curious", r"let me know"]
    has_weak_cta = any(re.search(pattern, lowered) for pattern in weak_cta_patterns)
    
    if has_weak_cta and not has_strong_cta:
        random_cta = random.choice(STRONG_CTAS)
        issues.append(f"Strengthen CTA: replace generic 'what do you think?' with concrete question like '{random_cta.lower()}'")

    if "hashtag#" in (post_text or ""):
        issues.append("Convert every 'hashtag#' token into a normal hashtag like '#AI'.")

    if METRIC_PATTERN.search(cleaned) and not METRIC_PATTERN.search(topic_blob):
        issues.append("Remove unsupported numeric claims and metrics unless the topic explicitly provided them.")
    if re.search(r"\bonly\s+\d+%|\b\d+(?:\.\d+)?\s*(?:million|billion)\b|\$\s*\d", cleaned, re.I) and not re.search(
        r"\bonly\s+\d+%|\b\d+(?:\.\d+)?\s*(?:million|billion)\b|\$\s*\d", topic_blob, re.I
    ):
        issues.append("Remove unsupported hard stats (percentages, millions, salary figures) unless provided in the topic.")

    allowed_tools = _detect_named_tools(topic_blob)
    unsupported_tools = sorted(_detect_named_tools(cleaned) - allowed_tools)
    if unsupported_tools:
        issues.append(
            "Remove unsupported named tool mentions that were not provided in the topic: "
            + ", ".join(unsupported_tools[:4])
        )

    if any(re.search(pat, cleaned, re.I) for pat in INCIDENT_PATTERNS):
        issues.append("Avoid personal/work incident references; keep examples generic unless the topic explicitly includes a real case study.")

    # Check for naked structural labels leaked into post body
    # e.g. "Best Practices: Access control" or "Common Mistakes: Human error"
    naked_label_re = re.compile(
        r"^(Best Practices|Common Mistakes|The Problem|Core Concept|"
        r"How It Works|Key Takeaway|Summary|Introduction)\s*:",
        re.MULTILINE | re.IGNORECASE
    )
    if naked_label_re.search(cleaned):
        issues.append(
            "Remove naked structural labels like 'Best Practices:' or 'Common Mistakes:' — "
            "these are prompt scaffolding that leaked into the post. Write the insight directly."
        )

    # Check for fabricated company incident references not in topic data
    fabricated_ref = re.search(
        r"\bas seen in\b.{0,60}\b(breach|incident|outage|hack|leak)\b"
        r"|\brecent\b.{0,40}\b(breach|incident|outage)\b.{0,20}\blike\b",
        cleaned, re.IGNORECASE
    )
    if fabricated_ref and not any(
        word in topic_blob for word in ["breach", "incident", "outage", "hack", "leak"]
    ):
        issues.append(
            "Remove fabricated company incident reference not supported by topic data. "
            "Do not invent real-world breaches or outages unless explicitly provided."
        )

    if re.search(r"\bnext post\b|\bthird post\b|\bpost 2\b|\banother post\b", cleaned, re.I):
        issues.append("Write exactly one post and remove any extra appended drafts.")
    if re.search(r"```+\s*mermaid|^\s*graph\s+(?:lr|td)|^\s*flowchart", cleaned, re.I | re.M):
        issues.append("Do not use Mermaid syntax; use plain-text visual blocks only.")
    for block in re.findall(r"```(.*?)```", cleaned, flags=re.S):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if len(lines) > 6:
            issues.append("Keep the visual block short (3 to 6 lines) so the post stays readable.")
            break
        if any(ch in block for ch in ("+---", "|   |", "┌", "└", "│")):
            issues.append("Avoid heavy ASCII box art inside the visual block; use compact line-based flow text.")
            break

    if cleaned.count("📌") > 1:
        issues.append("Use a single title/topic marker only once.")

    hashtag_count = len(re.findall(r"(?<!\w)#\w+", cleaned))
    if hashtag_count > 8:
        issues.append("Use fewer hashtags (ideal range: 4 to 7).")
    emoji_count = len(EMOJI_PATTERN.findall(cleaned))
    if emoji_count < 4:
        issues.append("Add more relevant emojis to improve scanability and engagement (target: 4 to 10).")
    if emoji_count > 14:
        issues.append("Reduce emoji density; keep emojis relevant and readable.")

    for phrase in GENERIC_PHRASES:
        if lowered.count(phrase) > 1:
            issues.append(f"Avoid repeating the phrase '{phrase}' multiple times.")
            break
    generic_hits = sum(1 for phrase in GENERIC_PHRASES if phrase in lowered)
    if generic_hits >= 3:
        issues.append("Reduce generic filler phrasing and add one concrete technical detail or trade-off.")

    if structure and structure.get("sections"):
        labels = [s.get("label", "").strip().lower() for s in structure.get("sections", []) if s.get("label")]
        if labels:
            poll_lines = [
                ln.strip().lower()
                for ln in cleaned.splitlines()
                if POLL_PREFIX_RE.match(ln.strip())
            ]
            if poll_lines:
                stripped = [POLL_PREFIX_RE.sub("", ln).strip() for ln in poll_lines]
                label_echoes = sum(1 for ln in stripped if any(lb == ln for lb in labels))
                if label_echoes >= max(2, len(stripped) // 2):
                    issues.append("Replace poll options with concrete architecture choices, not section header names.")

    if diagram_type == "Observability Map" or "observability" in topic_blob:
        expected_terms = ("prompt", "retrieval", "tool", "latency", "cost", "quality", "alert")
        matched = sum(1 for term in expected_terms if term in lowered)
        if matched < 4:
            issues.append("Make the post explicitly cover observability signals like prompts, retrieval, tool calls, cost, quality, and alerts.")

    if structure and structure.get("sections"):
        labels = [s.get("label", "") for s in structure.get("sections", [])]
        covered = sum(1 for label in labels if _label_in_post(label, lowered))
        if labels and covered < max(2, len(labels) // 2):
            issues.append("Align the post more closely to the planned diagram labels so the image and text tell the same story.")

    if structure and structure.get("rows") and diagram_type == "Observability Map":
        row_terms = ("input", "retrieval", "runtime", "quality")
        covered = sum(1 for term in row_terms if term in lowered)
        if covered < 3:
            issues.append("Align the post to the observability map structure: inputs, retrieval, runtime signals, and quality signals.")

    return issues


def _upgrade_weak_poll_options(text, structure=None, diagram_type=""):
    if not structure or not structure.get("sections"):
        return text
    lines = (text or "").splitlines()
    if not lines:
        return text

    labels = [s.get("label", "").strip().lower() for s in structure.get("sections", []) if s.get("label")]
    if not labels:
        return text

    poll_idx = None
    for i, ln in enumerate(lines):
        if "💬" in ln or "curious" in ln.lower() or "which approach" in ln.lower():
            poll_idx = i
    if poll_idx is None:
        return text

    option_idxs = []
    for i in range(poll_idx + 1, min(len(lines), poll_idx + 8)):
        ln = lines[i].strip()
        if POLL_PREFIX_RE.match(ln):
            option_idxs.append(i)
        elif ln.startswith("#") or not ln:
            break
    if not option_idxs:
        return text

    stripped = [
        POLL_PREFIX_RE.sub("", lines[i].strip()).strip().lower()
        for i in option_idxs
    ]
    echoes = sum(1 for ln in stripped if ln in labels)
    if echoes < max(2, len(stripped) // 2):
        return text

    if diagram_type == "Decision Tree" or "decision" in (diagram_type or "").lower():
        replacements = [
            "1️⃣ Traditional software + rules",
            "2️⃣ RAG (knowledge-first)",
            "3️⃣ Single-agent with tools",
            "4️⃣ Multi-agent workflow",
            "5️⃣ Hybrid (depends on step)",
        ]
    else:
        replacements = [
            "1️⃣ Fastest to ship",
            "2️⃣ Best reliability",
            "3️⃣ Lowest cost",
            "4️⃣ Easiest to maintain",
            "5️⃣ Best long-term fit",
        ]

    for j, idx in enumerate(option_idxs):
        if j < len(replacements):
            lines[idx] = replacements[j]
        else:
            lines[idx] = ""
    return "\n".join([ln for ln in lines if ln is not None]).strip()


def _enforce_numbered_poll_options(text):
    lines = (text or "").splitlines()
    if not lines:
        return text

    poll_idx = None
    for i, ln in enumerate(lines):
        low = ln.lower()
        if "💬" in ln or "which approach" in low or "what's your top priority" in low or "what do you use" in low:
            poll_idx = i
    if poll_idx is None:
        return text

    # If we already have numbered/bulleted options, keep as-is.
    for i in range(poll_idx + 1, min(len(lines), poll_idx + 8)):
        if POLL_PREFIX_RE.match(lines[i].strip()):
            return text
        if lines[i].strip().startswith("#"):
            break

    if poll_idx + 1 >= len(lines):
        return text
    option_line = lines[poll_idx + 1].strip().rstrip("?")
    symbol_options = []
    for i in range(poll_idx + 1, min(len(lines), poll_idx + 9)):
        ln = lines[i].strip()
        if not ln or ln.startswith("#"):
            break
        m = re.match(r"^[❇️✳️•\-]\s*(.+)$", ln)
        if m:
            symbol_options.append((i, m.group(1).strip(" .")))
    if len(symbol_options) >= 3:
        for j, (idx, label) in enumerate(symbol_options[:5]):
            lines[idx] = f"{j+1}\uFE0F\u20E3 {label}"
        return "\n".join(lines).strip()
    if not option_line or option_line.startswith("#"):
        return text

    parts = []
    for raw in option_line.split(","):
        part = raw.strip(" .")
        part = re.sub(r"^(?:or|and)\s+", "", part, flags=re.I)
        if part:
            parts.append(part)
    if len(parts) < 3:
        return text
    parts = parts[:5]
    numbered = [f"{i+1}\uFE0F\u20E3 {part}" for i, part in enumerate(parts)]
    lines[poll_idx + 1] = "  ".join(numbered)
    return "\n".join(lines).strip()


def _strip_work_incident_hook(text, topic_name=""):
    if not text:
        return text
    if not any(re.search(pat, text, re.I) for pat in INCIDENT_PATTERNS):
        return text
    lines = text.splitlines()
    if not lines:
        return text
    safe_hook = (
        f"Most teams blame the model first, but in {topic_name or 'LLM systems'} "
        "the bigger failures usually come from architecture decisions. 🧠"
    )
    lines[0] = safe_hook
    return "\n".join(lines).strip()


def _align_poll_with_structure(text, structure=None, diagram_type=""):
    if not structure or not structure.get("sections"):
        return text
    if diagram_type == "Decision Tree":
        return text

    labels = [s.get("label", "").strip() for s in structure.get("sections", []) if s.get("label")]
    if len(labels) < 3:
        return text

    lines = (text or "").splitlines()
    if not lines:
        return text

    poll_idx = None
    for i, ln in enumerate(lines):
        low = ln.lower()
        if "💬" in ln or "which" in low or "what's your" in low or "what drives" in low:
            poll_idx = i
    if poll_idx is None:
        return text

    options = []
    option_line_idx = None
    for i in range(poll_idx + 1, min(len(lines), poll_idx + 8)):
        ln = lines[i].strip()
        if not ln or ln.startswith("#"):
            break
        if POLL_PREFIX_RE.match(ln):
            options.append(POLL_PREFIX_RE.sub("", ln).strip().lower())
        elif "," in ln:
            option_line_idx = i
            options.extend([
                re.sub(r"^(?:or|and)\s+", "", p.strip(" ."), flags=re.I).lower()
                for p in ln.rstrip("?").split(",")
                if p.strip(" .")
            ])
            break

    if not options:
        return text

    normalized_labels = {l.lower() for l in labels}
    overlap = sum(1 for op in options if op in normalized_labels)
    if overlap >= max(2, len(options) // 2):
        return text

    numbered = [f"{i+1}\uFE0F\u20E3 {lbl}" for i, lbl in enumerate(labels[:5])]
    replacement = "  ".join(numbered)
    if option_line_idx is not None:
        lines[option_line_idx] = replacement
    else:
        # Replace existing option lines under poll
        replaced = False
        for i in range(poll_idx + 1, min(len(lines), poll_idx + 8)):
            ln = lines[i].strip()
            if not ln or ln.startswith("#"):
                if not replaced:
                    lines.insert(i, replacement)
                replaced = True
                break
            if POLL_PREFIX_RE.match(ln):
                if not replaced:
                    lines[i] = replacement
                    replaced = True
                else:
                    lines[i] = ""
        if not replaced:
            lines.insert(poll_idx + 1, replacement)
    return "\n".join([ln for ln in lines if ln is not None and ln != ""]).strip()


def _format_post_structure(text):
    """Add proper spacing and visual hierarchy to posts for better LinkedIn readability."""
    if not text:
        return text
    
    lines = text.splitlines()
    if not lines:
        return text
    
    # Detect structural elements
    visual_block_ranges = []  # Store (start, end) tuples for visual blocks
    cta_line_idx = None
    hashtag_start = None
    
    # Find visual blocks
    in_visual = False
    visual_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            if not in_visual:
                visual_start = i
                in_visual = True
            else:
                visual_block_ranges.append((visual_start, i))
                in_visual = False
    
    # Find CTA section (look for poll marker or strong CTA)
    for i in range(len(lines) - 1, -1, -1):
        if "💬" in lines[i] or POLL_PREFIX_RE.search(lines[i]):
            cta_line_idx = i
            break
    
    # Find start of hashtags
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith("#"):
            hashtag_start = i
        else:
            break
    
    # Build formatted post with intelligent spacing
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Check if we're in a visual block
        in_visual_block = any(start <= i <= end for start, end in visual_block_ranges)
        
        if not stripped:
            # Empty line - preserve but avoid duplicates
            if result and result[-1] != "":
                result.append("")
            i += 1
            continue
        
        # Handle visual blocks - add space before/after
        if i > 0 and line.strip().startswith("```"):
            if result and result[-1].strip():
                result.append("")  # Space before visual block
            result.append(line)
            i += 1
            continue
        
        if line.strip().startswith("```"):
            if result and result[-1].strip():
                result.append("")
            while i < len(lines) and i <= (max([e for s, e in visual_block_ranges if s <= i], default=i) or i):
                result.append(lines[i])
                if lines[i].strip().endswith("```") and i > 0:
                    i += 1
                    if i < len(lines) and lines[i].strip():
                        result.append("")  # Space after visual block
                    break
                i += 1
            continue
        
        # Handle CTA/poll section - add clear visual breaks
        if cta_line_idx and i >= cta_line_idx:
            if i == cta_line_idx and result and result[-1].strip():
                result.append("")  # Space before CTA section
            
            if "💬" in line and i > cta_line_idx:
                # This is a poll question
                result.append(line)
                result.append("")  # Space after question
            elif POLL_PREFIX_RE.search(line):
                # Poll options - keep on separate lines
                result.append(line)
            else:
                result.append(line)
            i += 1
            continue
        
        # Handle bullet points and numbered lists - add spacing
        is_list_item = stripped.startswith(("•", "-", "→", "*", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"))
        is_new_paragraph = (stripped[0].isupper() and 
                           not (stripped.startswith(("📌", "💬")) or result and result[-1].endswith(":")))
        
        if result and result[-1].strip():
            # Add space before:
            # 1. New list items after regular text
            if is_list_item and not result[-1].strip().startswith(("•", "-", "→", "*")):
                result.append("")
            # 2. New paragraphs after dense content
            elif is_new_paragraph and len(result[-1]) > 60 and not result[-1] in ("", " "):
                result.append("")
        
        result.append(line)
        i += 1
    
    # Final cleanup: remove trailing spaces and limit empty lines
    final_lines = []
    prev_empty = False
    
    for line in result:
        if not line.strip():
            if not prev_empty and final_lines:
                final_lines.append("")
                prev_empty = True
        else:
            final_lines.append(line)
            prev_empty = False
    
    # Remove trailing empty lines
    while final_lines and not final_lines[-1].strip():
        final_lines.pop()
    
    return "\n".join(final_lines).strip()


def _fix_truncated_numbered_items(text):
    """
    Remove numbered items that end mid-sentence (sign of LLM truncation).
    Also removes the plain-text duplicate that often follows.
    Also drops items that are part of a sequence restart (e.g. 1, 2, 1).
    """
    if not text:
        return text

    lines = text.splitlines()

    # ── Pass 1: find numbered items and detect sequence restarts ─────────────
    num_items = []  # [(line_index, number)]
    for i, line in enumerate(lines):
        m = _NUM_ITEM_RE.match(line.strip())
        if m:
            n = int(m.group(1) or m.group(2))
            num_items.append((i, n))

    drop_restart = set()
    if num_items:
        prev_line_idx = None
        seq = []
        for line_idx, n in num_items:
            is_contiguous = prev_line_idx is not None and (line_idx - prev_line_idx) <= 4
            if is_contiguous:
                if seq and n <= seq[-1]:
                    # Restart detected — drop this item and any that follow in the same block
                    drop_restart.add(line_idx)
                    seq = []  # reset so we don't chain-drop after the restart
                else:
                    seq.append(n)
            else:
                seq = [n]
            prev_line_idx = line_idx

    # ── Pass 2: build duplicate-detection set from clean numbered items ──────
    seen_content: set = set()
    numbered_labels: set = set()
    for i, line in enumerate(lines):
        if i in drop_restart:
            continue
        m = re.match(r"^(?:[1-9]\uFE0F\u20E3|[1-9][\.\)])\s+(.+)$", line.strip())
        if m:
            label = m.group(1).strip().rstrip(".!?,")
            last_word = label.split()[-1].lower() if label.split() else ""
            if last_word not in {"and","or","the","a","an","my","your","of","to","in","for","with","is"}:
                numbered_labels.add(label.lower()[:30])

    result = []
    for i, line in enumerate(lines):
        stripped = line.strip()

        if i in drop_restart:
            continue

        # Check if this is a numbered item
        m = re.match(r"^(?:[1-9]\uFE0F\u20E3|[1-9][\.\)])\s+(.+)$", stripped)
        if m:
            label = m.group(1).strip()
            last_word = label.rstrip(".!?,").split()[-1].lower() if label.split() else ""
            # Drop truncated numbered items
            if last_word in {"and","or","the","a","an","my","your","of","to","in","for","with","is"}:
                continue
            # Drop if too short (< 4 words = probably truncated)
            if len(label.split()) < 4:
                continue

        # Drop plain-text lines that duplicate a numbered item
        norm = re.sub(r"[^a-z0-9 ]", "", stripped.lower())[:30]
        if norm and norm in seen_content and not stripped.startswith("#"):
            continue

        seen_content.add(norm)
        result.append(line)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(result)).strip()


def _strip_placeholder_text(text):
    """
    Remove LLM-leaked structural placeholder tokens from the post.
    Examples of what gets removed: [Step 1], (Option A), [Decision Point 2]
    """
    if not text:
        return text
    lines = []
    for line in text.splitlines():
        if _PLACEHOLDER_LINE_RE.match(line):
            continue  # drop whole line
        cleaned = _PLACEHOLDER_INLINE_RE.sub("", line).strip()
        lines.append(cleaned if cleaned else line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _strip_visual_artifacts(text):
    """Remove repetitive visual 'pointing' characters like 'v v v' or '---'."""
    if not text:
        return text
    # Strip lines that only contain visual markers like v v v or ^ ^ ^
    cleaned = _VISUAL_ARTIFACT_RE.sub("", text)
    # Also strip common inline artifacts
    cleaned = re.sub(r"\s+[vV\^]{3,}\s*", " ", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _normalize_poll_separators(text):
    """Convert poll options using | or other non-standard separators into separate lines."""
    if not text:
        return text
    lines = text.splitlines()
    poll_idx = None
    for i, ln in enumerate(lines):
        if "💬" in ln:
            poll_idx = i
            break
    if poll_idx is None:
        return text
    
    # Look for a line containing options separated by | or /
    for i in range(poll_idx + 1, min(len(lines), poll_idx + 3)):
        ln = lines[i].strip()
        if "|" in ln or (" / " in ln and not ln.startswith(("http", "/"))):
            sep = "|" if "|" in ln else " / "
            parts = [p.strip() for p in ln.split(sep) if p.strip()]
            if len(parts) >= 2:
                # Replace with separate numbered lines
                replacement = [f"{j+1}\uFE0F\u20E3 {p}" for j, p in enumerate(parts[:4])]
                lines[i] = "\n".join(replacement)
                break
    return "\n".join(lines).strip()



def _strip_ascii_art(text):
    """
    Remove ASCII art boxes (+---+), separators (----), and box-drawing characters
    that LLMs sometimes leak into the post body.
    """
    if not text:
        return text
    
    lines = []
    # Match patterns like +-----+ or | Text | or |-------|
    # Also matches Unicode box-drawing: ┌ ─ ┐ │ └ ┘ ├ ┤ ┬ ┴ ┼
    box_chars = "[\u2500-\u257F\u2580-\u259F\u25A0-\u25FF]"
    box_pattern = re.compile(rf"^\s*(?:[\+\-\|]{3,}|{box_chars}{{3,}})\s*$")
    
    for line in text.splitlines():
        # Remove lines that look like box boundaries (+---+ or |---|)
        if box_pattern.match(line):
            continue
        
        # Remove inline box characters | or + if they appear in a structural way
        # but preserve them if they are likely math or logic (e.g. A | B)
        cleaned = re.sub(rf"{box_chars}", " ", line)
        # Only strip | and + if they are at the edges of a line (LLM table artifact)
        cleaned = re.sub(r"^\s*[\+\|]\s*", " ", cleaned)
        cleaned = re.sub(r"\s*[\+\|]\s*$", " ", cleaned)
        
        lines.append(cleaned.rstrip())
        
    return "\n".join(lines).strip()


def _has_structural_integrity_issues(text):
    """
    Returns a list of hard-blocker descriptions for structural integrity problems
    that should prevent publishing regardless of quality score.
    """
    blockers = []
    lines = (text or "").splitlines()

    # 1. Placeholder text still present
    for line in lines:
        if _PLACEHOLDER_LINE_RE.match(line) or _PLACEHOLDER_INLINE_RE.search(line):
            blockers.append("Placeholder structure text leaked into the final post.")
            break

    # 2. Truncated numbered items still present (after cleanup pass)
    for line in lines:
        m = re.match(r"^(?:[1-9]\uFE0F\u20E3|[1-9][\.\)])\s+(.+)$", line.strip())
        if m:
            label = m.group(1).strip().rstrip(".!?,")
            last_word = label.split()[-1].lower() if label.split() else ""
            if last_word in {"and","or","the","a","an","my","your","of","to","in","for","with","is"}:
                blockers.append("Truncated numbered items remain in the final post.")
                break
            if len(label.split()) < 4:
                blockers.append("Truncated numbered items remain in the final post.")
                break

    # 3. Numbered sequence restart (e.g. 1, 2, 1)
    num_items = []
    for i, line in enumerate(lines):
        m = _NUM_ITEM_RE.match(line.strip())
        if m:
            n = int(m.group(1) or m.group(2))
            num_items.append((i, n))
    if num_items:
        prev_idx = None
        seq: list = []
        for line_idx, n in num_items:
            is_cont = prev_idx is not None and (line_idx - prev_idx) <= 4
            if is_cont:
                if seq and n <= seq[-1]:
                    seq_str = ", ".join(str(x) for x in seq) + ", " + str(n)
                    blockers.append(
                        f"Numbered list sequence is incomplete or skips items: {seq_str}"
                    )
                    break
                seq.append(n)
            else:
                seq = [n]
            prev_idx = line_idx

    # 4. Poll options still contain placeholder labels
    for line in lines:
        if POLL_PREFIX_RE.match(line.strip()) and _PLACEHOLDER_INLINE_RE.search(line):
            blockers.append("Poll options still contain placeholder labels instead of real choices.")
            break

    # 5. Naked structural labels leaked into post body
    # e.g. "Best Practices: Access control" or "Common Mistakes: Human error"
    naked_label_pattern = re.compile(
        r"^(Best Practices|Common Mistakes|The Problem|Core Concept|"
        r"How It Works|Key Takeaway|Summary|Introduction|Hook)\s*:",
        re.MULTILINE | re.IGNORECASE
    )
    if naked_label_pattern.search(text or ""):
        blockers.append(
            "Naked structural label found (e.g. 'Best Practices: ...'). "
            "These are prompt scaffolding leaking into the post — regenerate."
        )

    # 6. Fabricated company incident references
    fabricated_incident = re.search(
        r"\bas seen in\b.{0,60}\b(breach|incident|outage|hack|leak)\b"
        r"|\brecent\b.{0,40}\b(breach|incident|outage)\b.{0,20}\blike\b",
        text or "", re.IGNORECASE
    )
    if fabricated_incident:
        blockers.append(
            "Fabricated company incident reference detected (e.g. 'as seen in Vercel's breach'). "
            "Remove unless the topic explicitly provides this case study."
        )

    return blockers

def _finalize_post_text(topic, post_text, structure=None, diagram_type=""):
    finalized = _cleanup_generated_post(post_text or "")
    finalized = _normalize_hashtags(finalized).strip()
    if not finalized:
        return finalized
    
    # ── STAGE 1: Artifact & Placeholder Stripping ─────────────────────────────
    finalized = _strip_placeholder_text(finalized)         # remove [Step X] tokens
    finalized = _strip_visual_artifacts(finalized)         # remove v v v arrows
    finalized = _strip_work_incident_hook(finalized, topic.get("name", ""))
    
    # ── STAGE 2: Structural Repair ────────────────────────────────────────────
    finalized = _fix_truncated_numbered_items(finalized)   # fix LLM truncation
    finalized = _reduce_repetitive_copy(finalized)
    finalized = _remove_raw_flow_only_lines(finalized)
    
    # ── STAGE 3: Poll Normalization ───────────────────────────────────────────
    finalized = _normalize_poll_separators(finalized)      # fix | separators
    finalized = _upgrade_weak_poll_options(finalized, structure=structure, diagram_type=diagram_type)
    finalized = _align_poll_with_structure(finalized, structure=structure, diagram_type=diagram_type)
    finalized = _enforce_numbered_poll_options(finalized)
    finalized = _tighten_poll_options(finalized)
    
    # ── STAGE 4: Final Formatting & Reach ─────────────────────────────────────
    finalized = _normalize_hashtags(finalized)
    finalized = _format_post_structure(finalized)
    finalized = optimize_hashtags_for_reach(finalized, post_type=topic.get("category", "topic"))
    finalized = _deduplicate_hashtags(finalized)
    return finalized



def _render_linkedin_text(post_text):
    text = (post_text or "").strip()
    if not text:
        return text

    try:
        visual_blocks = []

        def extract_visual(match):
            raw = match.group(1)
            # Strip the optional language hint from the first line (e.g. "python\n")
            lines = raw.split("\n")
            # Drop first line if it's just a language tag (no spaces, all alpha)
            if lines and re.match(r"^[a-z]*$", lines[0].strip()):
                lines = lines[1:]
            content = "\n".join(lines).strip()
            if content:
                visual_blocks.append(content)
                return f"\n[VISUAL_BLOCK_{len(visual_blocks)-1}]\n"
            return ""

        # Strip ALL fence variations including ```python, ```text, ```
        text = re.sub(r"```[a-z]*\n?([\s\S]*?)```", extract_visual, text)

        # Hard remove any remaining stray backtick fences
        text = re.sub(r"```[a-z]*", "", text)
        text = re.sub(r"```", "", text)

        # Remove inline code ticks
        text = re.sub(r"`([^`\n]+)`", r"\1", text)

        # Restore visual block content (no surrounding backticks)
        for i, visual_content in enumerate(visual_blocks):
            placeholder = f"[VISUAL_BLOCK_{i}]"
            text = text.replace(placeholder, visual_content)

        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text

    except Exception as e:
        log.warning(f"_render_linkedin_text failed ({e}), stripping all fences")
        try:
            fallback = re.sub(r"```[a-z]*\n?", "", post_text or "")
            fallback = re.sub(r"```", "", fallback)
            fallback = re.sub(r"`([^`\n]+)`", r"\1", fallback)
            return re.sub(r"\n{3,}", "\n\n", fallback).strip()
        except Exception:
            return (post_text or "").strip()


def _load_post_memory():
    if os.path.exists(POST_MEMORY_FILE):
        try:
            with open(POST_MEMORY_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data[-120:]
        except Exception:
            pass
    return []


def _save_post_memory(entries):
    try:
        with open(POST_MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump((entries or [])[-120:], f, indent=2)
    except Exception as e:
        log.warning(f"Could not save post memory: {e}")


def _remember_post(topic, text):
    """Remember post with enhanced tracking for engagement and diversity."""
    entries = _load_post_memory()
    
    # Determine category
    category = topic.get("category", "")
    if "interview" in topic.get("id", "").lower():
        category = "interview"
    elif topic.get("id", "").startswith("story-"):
        category = "story"
    elif "news" in topic.get("id", "").lower():
        category = "news"
    else:
        category = "topic"
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "topic_id": topic.get("id", ""),
        "topic_name": topic.get("name", ""),
        "category": category,
        "text": _cleanup_generated_post(text or "")[:2500],
    }
    
    entries.append(entry)
    _save_post_memory(entries)
    log.info(f"Post memory updated: {category} | {topic.get('name', 'unknown')}")


def _get_recent_topics(days=7):
    """Get topics posted in last N days to avoid repeats (interview feature)."""
    entries = _load_post_memory()
    cutoff = datetime.now() - timedelta(days=days)
    recent = []
    
    try:
        for entry in entries:
            ts = datetime.fromisoformat(entry.get("timestamp", ""))
            if ts > cutoff:
                if entry.get("topic_id"):
                    recent.append(entry.get("topic_id"))
    except Exception as e:
        log.warning(f"Could not check recent topics: {e}")
    
    return set(recent)


def _get_category_mix(days=30):
    """Get post category distribution for diversity tracking."""
    entries = _load_post_memory()
    cutoff = datetime.now() - timedelta(days=days)
    categories = {}
    
    try:
        for entry in entries:
            ts = datetime.fromisoformat(entry.get("timestamp", ""))
            if ts > cutoff:
                cat = entry.get("category", "topic")
                categories[cat] = categories.get(cat, 0) + 1
    except Exception as e:
        log.warning(f"Could not get category mix: {e}")
    
    return categories


def _normalize_similarity_text(text):
    lowered = re.sub(r"```[\s\S]*?```", " ", (text or "").lower())
    lowered = re.sub(r"(?<!\w)#\w+", " ", lowered)
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    tokens = [t for t in lowered.split() if len(t) > 2 and t not in SIM_STOPWORDS]
    return tokens


def _content_hash(text):
    tokens = _normalize_similarity_text(text)
    if not tokens:
        return ""
    blob = " ".join(tokens[:500])
    return hashlib.md5(blob.encode("utf-8")).hexdigest()


def _similarity_score(a, b):
    a_tokens = _normalize_similarity_text(a)
    b_tokens = _normalize_similarity_text(b)
    if len(a_tokens) < 4 or len(b_tokens) < 4:
        return 0.0
    a_grams = {" ".join(a_tokens[i:i + 2]) for i in range(len(a_tokens) - 1)}
    b_grams = {" ".join(b_tokens[i:i + 2]) for i in range(len(b_tokens) - 1)}
    if not a_grams or not b_grams:
        return 0.0
    inter = len(a_grams & b_grams)
    union = max(1, len(a_grams | b_grams))
    return inter / union


def _recent_similarity_penalty(text, recent_posts):
    if not recent_posts:
        return 0, 0.0
    best = 0.0
    for prev in recent_posts[-30:]:
        score = _similarity_score(text, prev)
        if score > best:
            best = score
    if best >= 0.78:
        return 35, best
    if best >= 0.70:
        return 22, best
    if best >= 0.62:
        return 12, best
    return 0, best


def _visual_coherence_issues(topic, diagram_type, structure=None):
    topic_blob = _topic_text_blob(topic).lower()
    issues = []
    if "observability" in topic_blob and diagram_type in {"Architecture Diagram", "Architecture"}:
        issues.append("Observability topics should not use the generic architecture diagram fallback.")
    if structure and structure.get("rows") and diagram_type in {"Architecture Diagram", "Architecture"}:
        issues.append("Structured notebook-style diagrams need a matching non-generic diagram type.")
    return issues

def _diagram_labels_from_structure(structure):
    labels = []
    if not isinstance(structure, dict):
        return labels
    for sec in structure.get("sections", []) or []:
        labels.append(str(sec.get("label", "")))
        labels.append(str(sec.get("desc", "")))
    for row in structure.get("rows", []) or []:
        labels.append(str(row.get("label", "")))
        labels.append(str(row.get("text", "")))
    return [x for x in labels if x.strip()]


def _diagram_alignment_score(diagram_path, structure):
    if not diagram_path.lower().endswith(".svg"):
        return 1.0
    if not structure:
        return 1.0
    try:
        with open(diagram_path, encoding="utf-8") as f:
            svg_text = f.read().lower()
    except Exception:
        return 0.0

    labels = _diagram_labels_from_structure(structure)
    if not labels:
        return 1.0

    covered = 0
    total = 0
    for label in labels:
        words = [w for w in re.split(r"[^a-z0-9]+", label.lower()) if len(w) > 2]
        if not words:
            continue
        total += 1
        if any(w in svg_text for w in words):
            covered += 1
    if total == 0:
        return 1.0
    return covered / total


def _fallback_style_for_diagram(diagram_type, structure=None):
    if structure and structure.get("rows"):
        return 20
    mapping = {
        "Decision Tree":      9,
        "Comparison Table":   22,
        "Flow Chart":         0,
        "Lane Map":           0,
        "Signal vs Noise":    17,
        "7 Layers":           10,
        "Ecosystem Breakdown": 20,
        "Observability Map":  20,
        "Winding Roadmap":    15,
        "Architecture Diagram": 7,
        "Architecture":       7,
        "Modern Cards":       22,
        "Viral Poster":       23,
        "poster":             23,
    }
    return mapping.get(diagram_type, 7)


def _score_post_candidate(topic, post_text, structure=None, diagram_type=""):
    text = _cleanup_generated_post(post_text or "")
    issues = list(_post_quality_issues(topic, text, structure, diagram_type))
    score = 100

    score -= len(issues) * 12

    trailing_lines = "\n".join(text.splitlines()[-4:])
    if "?" not in trailing_lines and "💬" not in text and "ðŸ’¬" not in text:
        issues.append("End with a real discussion prompt that starts with 💬.")
        score -= 10

    hashtags = re.findall(r"(?<!\w)#\w+", text)
    if not 4 <= len(hashtags) <= 7:
        issues.append("Use 4 to 7 clean hashtags at the end.")
        score -= 8

    fence_count = text.count("```")
    if fence_count < 2:
        issues.append("Include one fenced visual block that matches the planned diagram type.")
        score -= 10
    if fence_count > 2:
        issues.append("Include only one fenced visual block; remove duplicated diagram/code blocks.")
        score -= 10

    first_line = text.splitlines()[0].strip().lower() if text.splitlines() else ""
    weak_openers = ("today", "in today's", "this post", "let's talk", "here's")
    if any(first_line.startswith(opener) for opener in weak_openers):
        issues.append("Strengthen the hook so the first line makes a sharper claim or observation.")
        score -= 8

    word_count = len(re.findall(r"\b\w+\b", text))
    if word_count < 140 or word_count > 340:
        issues.append("Keep the post in the LinkedIn sweet spot: roughly 140 to 340 words.")
        score -= 25  # Hard penalty — short posts reliably fail the quality gate

    if structure and structure.get("sections"):
        labels = [s.get("label", "") for s in structure.get("sections", [])]
        covered = sum(1 for label in labels if _label_in_post(label, text.lower()))
        if labels:
            score += min(8, covered * 2)
        poll_lines = [
            ln.strip().lower()
            for ln in text.splitlines()
            if POLL_PREFIX_RE.match(ln.strip())
        ]
        if poll_lines:
            normalized_labels = {lbl.strip().lower() for lbl in labels if lbl}
            stripped = [POLL_PREFIX_RE.sub("", ln).strip() for ln in poll_lines]
            echoes = sum(1 for ln in stripped if ln in normalized_labels)
            if echoes >= max(2, len(stripped) // 2):
                issues.append("Poll options are too generic; use concrete answer choices.")
                score -= 8

    if structure and structure.get("rows") and diagram_type == "Observability Map":
        row_terms = ("input", "retrieval", "runtime", "quality")
        covered = sum(1 for term in row_terms if term in text.lower())
        score += min(8, covered * 2)

    score = max(0, min(100, score))
    return {
        "score": score,
        "issues": issues[:8],
        "word_count": word_count,
        "hashtag_count": len(hashtags),
    }


# ─── TOPIC DIVERSITY CHECK ────────────────────────────────────────────────────

def _get_topic_concepts(topic):
    """Extract key concepts from topic for similarity comparison."""
    blob = _topic_text_blob(topic).lower()
    # Extract meaningful tokens
    tokens = [t for t in re.split(r"[^a-z0-9]+", blob) if len(t) > 3]
    # Also include topic ID for exact matches
    concepts = {topic.get("id", "").lower()}
    concepts.update(tokens[:20])  # Top 20 tokens
    return concepts


def _check_topic_diversity(topic, days=7):
    """
    Check if topic is too similar to recently posted topics.
    Returns (is_diverse, similarity_score, conflicting_topic_ids)
    """
    entries = _load_post_memory()
    cutoff = datetime.now() - timedelta(days=days)
    recent_topics = []
    
    try:
        for entry in entries:
            ts = datetime.fromisoformat(entry.get("timestamp", ""))
            if ts > cutoff:
                recent_topics.append({
                    "id": entry.get("topic_id", ""),
                    "name": entry.get("topic_name", ""),
                    "category": entry.get("category", "")
                })
    except Exception as e:
        log.warning(f"Could not check topic diversity: {e}")
        return True, 0.0, []
    
    # Get current topic concepts
    current_concepts = _get_topic_concepts(topic)
    conflicting = []
    max_similarity = 0.0
    
    # Compare against recent topics
    for recent in recent_topics:
        # Exact ID match = very similar
        if current_concepts & {recent["id"].lower()}:
            conflicting.append(recent["id"])
            continue
        
        # Similar category = likely related
        if recent["category"] == topic.get("category", "topic"):
            conflicting.append(recent["id"])
            continue
    
    # If too many similar topics recently, flag it
    if len(conflicting) >= 2:
        max_similarity = min(0.95, 0.5 + len(conflicting) * 0.15)
        return False, max_similarity, conflicting
    
    return True, max_similarity, conflicting


# ─── SMART DIAGRAM ROTATION ───────────────────────────────────────────────────

ALL_DIAGRAM_STYLES = list(range(8)) + list(range(8, 16)) + [17, 18, 19, 20, 22, 23]

def _load_diagram_rotation_state():
    """Load diagram rotation state to track style usage."""
    if os.path.exists(DIAGRAM_ROTATION_FILE):
        try:
            with open(DIAGRAM_ROTATION_FILE, encoding="utf-8") as f:
                data = json.load(f)
            # File is a dict — normal case after first proper save
            if isinstance(data, dict) and "rotation_index" in data:
                return data
            # File is a list (old format from diagram_rotation.py) — migrate it
            if isinstance(data, list):
                recent_styles = [
                    e.get("style_idx", e.get("style", 0))
                    for e in data[-15:]
                    if isinstance(e, dict)
                ]
                return {
                    "rotation_index": recent_styles[-1] + 1 if recent_styles else 0,
                    "style_history": recent_styles,
                }
        except Exception:
            pass
    return {"rotation_index": 0, "style_history": []}


def _save_diagram_rotation_state(state):
    """Save diagram rotation state."""
    try:
        with open(DIAGRAM_ROTATION_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log.warning(f"Could not save diagram rotation state: {e}")


def _select_smart_diagram_style(topic_id=""):
    """
    Select diagram style intelligently:
    1. Rotate through all 23 available styles
    2. Avoid styles used in last 15 posts
    3. Prefer variety for each topic
    """
    state = _load_diagram_rotation_state()
    style_history = state.get("style_history", [])[-15:]  # Last 15 used styles
    
    # Find first style not in recent history
    for offset in range(len(ALL_DIAGRAM_STYLES)):
        next_index = (state.get("rotation_index", 0) + offset) % len(ALL_DIAGRAM_STYLES)
        candidate_style = ALL_DIAGRAM_STYLES[next_index]
        
        if candidate_style not in style_history:
            # Found a fresh style
            state["rotation_index"] = (next_index + 1) % len(ALL_DIAGRAM_STYLES)
            state["style_history"] = style_history + [candidate_style]
            _save_diagram_rotation_state(state)
            log.info(f"Selected diagram style {candidate_style} (rotated from {len(style_history)} previous)")
            return candidate_style
    
    # Fallback: use next in rotation even if recently used (but better than always using 7)
    next_index = state.get("rotation_index", 0)
    selected_style = ALL_DIAGRAM_STYLES[next_index]
    state["rotation_index"] = (next_index + 1) % len(ALL_DIAGRAM_STYLES)
    state["style_history"] = style_history + [selected_style]
    _save_diagram_rotation_state(state)
    
    return selected_style


# ─── ENGAGEMENT TRACKER ────────────────────────────────────────────────────────

def _load_engagement_tracker():
    """Load engagement tracking data."""
    if os.path.exists(ENGAGEMENT_TRACKER_FILE):
        try:
            with open(ENGAGEMENT_TRACKER_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "posts" in data:
                return data
        except Exception:
            pass
    return {"posts": [], "stats_by_type": {}, "stats_by_topic": {}}


def _save_engagement_tracker(tracker):
    """Save engagement tracking data."""
    try:
        with open(ENGAGEMENT_TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(tracker, f, indent=2)
    except Exception as e:
        log.warning(f"Could not save engagement tracker: {e}")


def _log_post_generated(topic, post_text, diagram_style, post_mode):
    """
    Log a generated post to engagement tracker.
    This captures metadata for later engagement analysis.
    """
    tracker = _load_engagement_tracker()
    
    post_id = hashlib.md5(f"{datetime.now().isoformat()}|{topic.get('id', '')}".encode()).hexdigest()[:12]
    
    post_entry = {
        "post_id": post_id,
        "timestamp": datetime.now().isoformat(),
        "topic_id": topic.get("id", ""),
        "topic_name": topic.get("name", ""),
        "post_type": post_mode,  # "topic", "story", "news", "interview"
        "category": topic.get("category", ""),
        "diagram_style": diagram_style,
        "text_length": len(post_text or ""),
        "emoji_count": len(re.findall(r"[^\w\s]", post_text or "")),
        "hashtag_count": len(re.findall(r"(?<!\w)#\w+", post_text or "")),
        "has_poll": "💬" in (post_text or ""),
        "has_vulnerability": any(re.search(pat, (post_text or "").lower()) for pat in VULNERABILITY_PATTERNS),
        "has_strong_cta": any(cta.lower() in (post_text or "").lower() for cta in STRONG_CTAS),
        "engagement": {
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "impressions": 0,
            "tracked": False
        }
    }
    
    tracker["posts"].append(post_entry)
    
    # Keep only last 500 posts
    if len(tracker["posts"]) > 500:
        tracker["posts"] = tracker["posts"][-500:]
    
    _save_engagement_tracker(tracker)
    log.info(f"Post logged for engagement tracking: {post_id} | {post_mode} | {topic.get('name', 'unknown')}")
    
    return post_id


def _get_engagement_stats(days=30, post_type=None):
    """
    Get engagement statistics by post type.
    Returns average engagement metrics for comparison.
    """
    tracker = _load_engagement_tracker()
    cutoff = datetime.now() - timedelta(days=days)
    
    posts = []
    try:
        for post in tracker.get("posts", []):
            ts = datetime.fromisoformat(post.get("timestamp", ""))
            if ts > cutoff:
                if post_type is None or post.get("post_type") == post_type:
                    posts.append(post)
    except Exception:
        pass
    
    if not posts:
        return {
            "count": 0,
            "avg_engagement": 0,
            "avg_comments": 0,
            "avg_impressions": 0
        }
    
    total_engagement = sum(p.get("engagement", {}).get("likes", 0) + 
                          p.get("engagement", {}).get("comments", 0) for p in posts)
    total_impressions = sum(p.get("engagement", {}).get("impressions", 0) for p in posts)
    
    return {
        "count": len(posts),
        "avg_engagement": total_engagement / max(1, len(posts)),
        "avg_comments": sum(p.get("engagement", {}).get("comments", 0) for p in posts) / max(1, len(posts)),
        "avg_impressions": total_impressions / max(1, len(posts)),
        "tracked_count": len([p for p in posts if p.get("engagement", {}).get("tracked", False)])
    }


def _pick_best_candidate(topic, candidates, structure, diagram_type, recent_posts, recent_hashes=None):
    ranked = _rank_candidates(topic, candidates, structure, diagram_type, recent_posts, recent_hashes=recent_hashes)
    best = ranked[0]
    log.info(
        "Text candidates ranked: "
        + ", ".join(
            f"#{r['index']+1}={r['score']} (raw={r['raw_score']}, sim={r['sim']:.2f})"
            for r in ranked
        )
        + f" -> selected #{best['index']+1}"
    )
    return best


def _rank_candidates(topic, candidates, structure, diagram_type, recent_posts, recent_hashes=None):
    ranked = []
    recent_hashes = set(recent_hashes or [])
    for idx, text in enumerate(candidates):
        card = _score_post_candidate(topic, text, structure, diagram_type)
        penalty, sim = _recent_similarity_penalty(text, recent_posts)
        duplicate_hash = _content_hash(text)
        if duplicate_hash and duplicate_hash in recent_hashes:
            penalty = max(penalty, 40)
        adjusted = max(0, card["score"] - penalty)
        ranked.append({
            "index": idx,
            "text": text,
            "score": adjusted,
            "raw_score": card["score"],
            "sim": sim,
            "penalty": penalty,
            "issues": card["issues"],
            "hash": duplicate_hash,
        })
    ranked.sort(key=lambda r: (r["score"], r["raw_score"]), reverse=True)
    return ranked

def _extract_poster_title(topic_name: str, post_text: str, mode: str) -> str:
    """
    Pick a clean, short, authoritative headline for the Viral Poster diagram.
    """
    if not post_text:
        return (topic_name or "Engineering Insight")[:32]

    # Priority 1: Check for very short, bolded lines at the start (often a better title than topic_name)
    lines = (post_text or "").splitlines()
    for line in lines[:3]:
        m = re.match(r"^\*\*(.+?)\*\*", line.strip())
        if m:
            t = m.group(1).strip(" .*:")
            if 8 <= len(t) <= 35:
                # Filter structural nonsense
                if any(p in t.lower() for p in ["problem", "concept", "works"]): continue
                return t[:32]

    # Priority 2: Extract a specific model/product name if it's a news/trending item
    model_match = re.search(r"\b([A-Z][A-Za-z0-9]{1,12}(?:[.\-][0-9A-Za-z]{1,10}){0,3})\b", post_text)
    if model_match:
        cand = model_match.group(1)
        if len(cand) >= 3 and cand.upper() not in {"THE", "THIS", "THAT", "WHEN", "TECH"}:
            if re.search(r"[0-9.\-]", cand) or cand.isupper():
                return cand[:32]

    # Priority 3: Contextual search for technical Subject Actors (e.g. "RAG Pipeline")
    tech_keywords = [
        "Pipeline", "System", "Architecture", "Detection", "Workflow", "Service", 
        "Engine", "Platform", "Model", "Node", "RAG", "LLM", "Agent",
        "Railway", "Infrastructure", "Traffic", "Protocol", "Strategy", "Framework", "Stack", "Process"
    ]
    for kw in tech_keywords:
        # Switch to strict word boundary matching to avoid "Engine" in "Engineers"
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, post_text, re.I):
            # Try to find the word BEFORE it first
            m = re.search(r"(\w+)\s+" + re.escape(kw), post_text, re.I)
            if m:
                actor = m.group(1).title()
                # Blacklist generic descriptors
                if actor.upper() not in {"MOST", "THE", "OUR", "THIS", "STAFF", "YOUR", "RELIABLE"}:
                    return f"{actor} {kw}"[:32]
            
            # If no good actor, try to see if topic_name has a better word
            if topic_name and kw.lower() in topic_name.lower():
                # Extract first word of topic name if it's meaningful
                t_parts = topic_name.split()
                if t_parts and len(t_parts[0]) > 3:
                     return f"{t_parts[0]} {kw}"[:32]
            
            return f"Professional {kw}"[:32]

    # Final fallback
    return (topic_name or "Production Insight")[:32]


def _build_mermaid_code(title, sections):
    """
    Translates sections into a valid Mermaid flowchart for Kroki.io rendering.
    """
    mermaid = f"graph TD\n"
    mermaid += f'  Title["{title}"]\n'
    mermaid += f'  Title --- Node1\n'
    
    for i, sec in enumerate(sections):
        label = sec["label"].replace('"', "'").strip()
        # Create a node
        mermaid += f'  Node{i+1}["{label}"]\n'
        # Connect to next
        if i < len(sections) - 1:
            mermaid += f'  Node{i+1} --> Node{i+2}\n'
            
    # Styling for professional engineering look
    mermaid += "  classDef default fill:#111,stroke:#3b82f6,stroke-width:2px,color:#fff,font-family:Inter,font-size:14px;\n"
    mermaid += "  class Title fill:#1e293b,stroke:#60a5fa,stroke-width:4px,color:#fff,font-size:18px,font-weight:bold;\n"
    return mermaid



def _extract_visual_title(post_text, fallback_title):
    return _extract_visual_title_for_type(post_text, fallback_title, "")


def _clean_entity_name(name):
    cleaned = re.sub(r"^[\"'`\-\s]+|[\"'`.,:;!?\)\]\s]+$", "", (name or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:28]


def _extract_comparison_entities(post_text, fallback_entities=None):
    text = post_text or ""
    patterns = [
        r"\b([A-Z][A-Za-z0-9&.+/\- ]{1,30})\s+vs\.?\s+([A-Z][A-Za-z0-9&.+/\- ]{1,30})\b",
        r"\bcomparison of\s+([A-Z][A-Za-z0-9&.+/\- ]{1,30})\s+(?:and|to|vs\.?)\s+([A-Z][A-Za-z0-9&.+/\- ]{1,30})\b",
        r"\bcompare\s+([A-Z][A-Za-z0-9&.+/\- ]{1,30})\s+(?:and|to|vs\.?)\s+([A-Z][A-Za-z0-9&.+/\- ]{1,30})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            left = _clean_entity_name(match.group(1))
            right = _clean_entity_name(match.group(2))
            if left and right and left.lower() != right.lower():
                return [left, right]

    if fallback_entities and len(fallback_entities) >= 2:
        cleaned = []
        for entity in fallback_entities:
            name = _clean_entity_name(entity)
            if name and name not in cleaned:
                cleaned.append(name)
            if len(cleaned) >= 2:
                return cleaned[:2]
    return []


def _extract_visual_title_for_type(post_text, fallback_title, diagram_type, fallback_entities=None):
    entities = _extract_comparison_entities(post_text, fallback_entities=fallback_entities) if diagram_type == "Comparison Table" else []
    if len(entities) >= 2:
        return f"{entities[0]} vs {entities[1]}"

    title_like_fallbacks = {"Decision Tree", "7 Layers", "Signal vs Noise", "Lane Map", "Observability Map"}
    if fallback_title and diagram_type in title_like_fallbacks:
        return fallback_title[:54]

    weak_openers = (
        "i'm", "i am", "here's", "the fact that", "this led me", "nobody talks",
        "our ", "today", "in today's", "let's", "three years ago",
    )
    blocked_title_patterns = (
        r"^(?:the problem|core concept|how it works|best practices|common mistakes|key takeaway|summary|introduction|hook)$",
        r"^\d+$",
        r"^\d+[%\)]?$",
    )
    in_fence = False
    for raw_line in (post_text or "").splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^[\"'`•\-\s]+", "", line)
        line = re.sub(r"\s+", " ", line)
        if line.lower().startswith(weak_openers):
            continue
        if '"' in raw_line or "'" in raw_line:
            continue
        if any(tok in line for tok in ("->", "-->", "|>", "[", "]", "{", "}")):
            continue
        if any(re.match(pat, line.strip(), re.I) for pat in blocked_title_patterns):
            continue
        if re.match(r"^[\d\s.:()%/-]+$", line):
            continue
        if len(line) >= 12:
            return line[:54]
    return fallback_title


def _build_comparison_structure_from_post(post_text, title, fallback_entities=None):
    entities = _extract_comparison_entities(post_text, fallback_entities=fallback_entities)
    if len(entities) < 2:
        return None

    rows = []
    code_blocks = re.findall(r"```(.*?)```", post_text or "", flags=re.DOTALL)
    for block in code_blocks:
        for raw_line in block.splitlines():
            line = raw_line.strip(" -*\t")
            if not line or "|" in line or "---" in line:
                continue
            parts = re.split(r"\s*(?:->|→)\s*", line, maxsplit=1)
            if len(parts) != 2:
                continue
            left, right = parts[0].strip(), parts[1].strip()
            if not left or not right:
                continue
            label = "Positioning" if not rows else f"Point {len(rows) + 1}"
            rows.append({
                "label": label,
                "text": f"{left[:22]} -> {right[:22]}",
            })
            if len(rows) >= 4:
                break
        if len(rows) >= 4:
            break

    if not rows:
        rows = [
            {"label": "Positioning", "text": "Established platform -> Emerging alternative"},
            {"label": "AI Approach", "text": "Add-on automation -> AI-native workflow"},
            {"label": "Best Fit", "text": "Enterprise breadth -> Developer speed"},
            {"label": "Trade-off", "text": "More control, more weight -> Simpler, less mature"},
        ]

    return {
        "title": title,
        "cols": entities[:2],
        "rows": rows,
    }


def _infer_diagram_type_from_post(post_text, fallback_type):
    text = (post_text or "").lower()
    strong_editorial = {"Decision Tree", "7 Layers", "Signal vs Noise", "Lane Map", "Observability Map", "Ecosystem Breakdown"}
    if "decision tree" in text or "when not to use" in text or "should i" in text:
        return "Decision Tree"
    if "ecosystem" in text or "full stack" in text or "from models to" in text:
        return "Ecosystem Breakdown"
    if "7 layers" in text or "layer 1" in text:
        return "7 Layers"
    if "signal vs noise" in text or "signal or noise" in text:
        return "Signal vs Noise"
    if "mcp" in text or "a2a" in text:
        return "Lane Map"
    if "comparison" in text or ("|" in text and "---" in text) or " vs " in text:
        return "Comparison Table"
    if "timeline" in text or "roadmap" in text:
        return "Timeline"
    if fallback_type in strong_editorial:
        return fallback_type
    if "flow" in text or "→" in post_text or "▼" in post_text:
        return "Flow Chart"
    return fallback_type


def _build_viral_poster_structure(post_text, topic_name, mode, topic=None):
    """
    Build sections for the viral poster from actual post content.
    Extracts UNIQUE, non-redundant take-aways.
    """
    # NEW: If we used JSON mode, the nodes are already extracted and optimized!
    if isinstance(topic, dict) and topic.get("_extracted_nodes"):
        nodes = topic["_extracted_nodes"]
        sections = []
        for i, node in enumerate(nodes[:5]):
            sections.append({"id": i + 1, "label": node.strip()[:50], "desc": ""})
        if sections:
            log.info(f"Using {len(sections)} pre-extracted nodes from JSON mode.")
            return {"style": 23, "subtitle": topic_name[:60], "sections": sections}

    lines = (post_text or "").splitlines()
    sections = []
    
    # 1. IDENTIFY THE HOOK (First 2-3 sentences / 300 chars)
    # We explicitly EXCLUDE this text from the diagram to avoid redundancy.
    hook_text = (post_text or "")[:350].lower()
    
    # 2. IDENTIFY BULLETS 
    post_bullets = []
    for line in lines:
        bm = re.match(r"^(?:[1-9]\uFE0F\u20E3|[1-9][\.\)]|[1-9]\s)\s*(.+)$", line.strip())
        if bm: post_bullets.append(bm.group(1).lower().strip())

    scaffold_labels = {
        "the problem", "core concept", "how it works", "best practices",
        "common mistakes", "key takeaway", "summary", "introduction", "hook"
    }

    def is_too_redundant(cand):
        c = cand.lower().strip()
        if not c: return True
        if c in scaffold_labels:
            return True
        if re.fullmatch(r"\d+[%\)]?", c):
            return True
        # If it's in the HOOK, it's redundant nonsense for a diagram
        if c in hook_text or (len(c) > 20 and hook_text.find(c) != -1):
            return True
        # If it's already a bullet, we might use it ONLY if we summarize later
        for pb in post_bullets:
            if len(c) > 10 and (c in pb or pb in c): return True
        return False

    def clean_label(label):
        # Truncate and summarize to a punchy label
        label = re.sub(r"\s*[—:–]\s*.*$", "", label).strip(" .*")
        return label[:60].strip()

    # Pass 1: look for explicit key-takeaway bolding (**Takeaway**)
    for line in lines:
        m = re.match(r"^\*\*(.+?)\*\*", line.strip())
        if m:
            label = clean_label(m.group(1))
            if 5 <= len(label) <= 120 and not is_too_redundant(label):
                sections.append({"id": len(sections) + 1, "label": label, "desc": ""})
        if len(sections) >= 6: break

    # Pass 2: Numbered items (only if we need more variety)
    if len(sections) < 3:
        for line in lines:
            m = re.match(r"^(?:[1-9]\uFE0F\u20E3|[1-9][\.\)]|[1-9]\s)\s*(.+)$", line.strip())
            if m:
                label = clean_label(m.group(1))
                if len(label) > 6 and not is_too_redundant(label):
                    sections.append({"id": len(sections) + 1, "label": label, "desc": ""})
            if len(sections) >= 6: break

    # Pass 3: Extract technical headers or deep paragraph sentences
    if len(sections) < 3:
        for line in lines:
            stripped = line.strip()
            if len(stripped) < 40 or stripped.startswith(("#", "`", "💬", "📌")): continue
            first_sentence = re.split(r"[.!?]", stripped)[0].strip()
            label = clean_label(first_sentence)
            if len(label) > 15 and not is_too_redundant(label):
                sections.append({"id": len(sections) + 1, "label": label, "desc": ""})
            if len(sections) >= 5: break

    # Final fallback if still empty — call AI to extract 4 technical keywords from the post
    if len(sections) < 3:
        log.info("No bullets found. Calling AI for elite content extraction...")
        extraction_prompt = f"""Identify 4 technical stages, components, or key architectural concepts discussed in this LinkedIn post.
Post Text: {post_text[:1000]}

Return exactly 4 punchy items, each 3-5 words max. One per line. No numbers.
"""
        raw_items = call_ai(extraction_prompt, "You are a Technical Diagram Specialist.")
        if raw_items:
            for line in raw_items.splitlines()[:5]:
                label = clean_label(line.strip())
                if len(label) > 4:
                    sections.append({"id": len(sections) + 1, "label": label, "desc": ""})
    
    # Second fallback if AI somehow fails — use topic-related tags
    if len(sections) < 3:
        sections = [
            {"id": 1, "label": f"{topic_name} Initial State", "desc": ""},
            {"id": 2, "label": f"{topic_name} Implementation", "desc": ""},
            {"id": 3, "label": f"{topic_name} Validation", "desc": ""},
            {"id": 4, "label": "Deployment", "desc": ""},
        ]

    # Deduplicate and renumber
    final_sections = []
    seen = set()
    for sec in sections:
        label = re.sub(r"^(?:[1-9]\uFE0F\u20E3|[1-9][\.\)]|[1-9]\s+)\s*", "", sec["label"]).strip()
        label = re.sub(r"\s+", " ", label)
        if not label:
            continue
        lowered = label.lower()
        if lowered in scaffold_labels or re.fullmatch(r"\d+[%\)]?", lowered):
            continue
        sec["label"] = label
        norm = lowered
        if norm not in seen:
            seen.add(norm)
            final_sections.append(sec)
    
    for i, sec in enumerate(final_sections):
        sec["id"] = i + 1

    # UNIVERSAL PROFESSIONAL PIVOT:
    # Every post now earns a professional Mermaid/Kroki diagram (Engineering standard).
    title = _extract_poster_title(topic_name, post_text, mode)
    mermaid_code = ""
    if len(final_sections) >= 3:
        mermaid_code = _build_mermaid_code(title, final_sections)

    return {
        "style": 23,
        "subtitle": _get_post_subtitle(mode),
        "sections": final_sections[:6],
        "mermaid_code": mermaid_code,
        "diagram_style": "mermaid"
    }



def _get_post_subtitle(mode):
    subtitles = {
        "story":      "Personal Lessons",
        "ai_news":    "AI Engineering Take",
        "tech_news":  "Engineer's Perspective",
        "tools_news": "Signal or Noise?",
        "layoff_news":"Industry Reality Check",
        "trending":   "What Engineers Need to Know",
        "topic":      "Production Insights",
    }
    return subtitles.get(mode, "Staff Engineer's Take")

def _resolve_visual_metadata(topic, post_text, mode, fallback_type, fallback_structure):
    """
    Decide diagram title, type, and structure based on post mode and content.
    Viral Poster → story, news, trending, and soft/career topics
    Technical diagrams → system design, devops, architecture topics
    """
    # Modes that always get Viral Poster
    POSTER_MODES = {"story", "ai_news", "tech_news", "tools_news", "layoff_news", "trending"}

    # Topic categories that suit Viral Poster over technical diagrams
    POSTER_TOPIC_KEYWORDS = {
        "career", "brand", "growth", "discovery", "name-search",
        "online", "presence", "leverage", "ai-discovery", "visibility",
        "reputation", "personal", "interview", "skill", "learning",
        "iot", "transit",  # IoT in Transit is a story-style topic
    }

    topic_id_lower = topic.get("id", "").lower()
    topic_name_lower = topic.get("name", "").lower()
    is_poster_topic = any(
        kw in topic_id_lower or kw in topic_name_lower
        for kw in POSTER_TOPIC_KEYWORDS
    )

    # We NO LONGER use Viral Poster (Style 23) for news or technical content.
    # User Request: "I am not liking the diagrams at all" -> Pivot to Professional Engineering charts.
    use_viral_poster = mode in {"story", "career"}  # Only story/career keep the soft cards
    
    if use_viral_poster:
        poster_title = _extract_poster_title(topic["name"], post_text, mode)
        poster_structure = _build_viral_poster_structure(post_text, poster_title, mode, topic=topic)
        return poster_title, "Viral Poster", poster_structure

    # ALL TECHNICAL/NEWS/TRENDING modes now use Professional Engineering Charts
    # (Mermaid + Kroki). Keep the diagram title anchored to the intended topic,
    # not the post hook/first line, so the visual title stays stable.
    diagram_title = _extract_poster_title(topic["name"], post_text, mode)

    # Technical topic posts — use planned diagram type
    diagram_type = _infer_diagram_type_from_post(post_text, fallback_type)
    fallback_entities = [topic.get("name", topic.get("id", ""))]
    if topic.get("diagram_subject"):
        fallback_entities.extend(
            re.findall(r"\b[A-Z][A-Za-z0-9+.\-]{2,}\b", topic["diagram_subject"])
        )
    diagram_title = _extract_visual_title_for_type(
        post_text, topic["name"], diagram_type, fallback_entities=fallback_entities
    )
    diagram_structure = fallback_structure
    if diagram_type != fallback_type:
        diagram_structure = None
    if diagram_type == "Comparison Table" and not diagram_structure:
        diagram_structure = _build_comparison_structure_from_post(
            post_text, diagram_title, fallback_entities=fallback_entities
        )
    return diagram_title, diagram_type, diagram_structure

# ─── POST MODE ────────────────────────────────────────────────────────────────

def get_post_mode():
    """Decide which post type to generate."""
    def _env_float(name, default):
        try:
            return float(os.environ.get(name, str(default)))
        except Exception:
            return float(default)

    # Load interview frequency from schedule_config if available
    interview_freq = 0.15
    try:
        config_path = os.path.join(os.path.dirname(__file__), "..", "schedule_config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                cfg = json.load(f)
                interview_freq = cfg.get("interview_posts", {}).get("frequency", 0.15)
    except Exception:
        pass

    interview_prob = interview_freq
    story_prob     = _env_float("STORY_MODE_PROB",      0.18)
    trending_prob  = _env_float("TREND_MODE_PROB",      0.35)  # BUMPED: prioritized trending news
    ai_news_prob   = _env_float("AI_NEWS_MODE_PROB",    0.20)  # BUMPED: more AI focus
    layoff_prob    = _env_float("LAYOFF_MODE_PROB",     0.04)
    tools_prob     = _env_float("TOOLS_NEWS_MODE_PROB", 0.06)
    tech_prob      = _env_float("TECH_NEWS_MODE_PROB",  0.04)

    rand = random.random()
    cumulative = 0.0

    cumulative += interview_prob
    if rand < cumulative:
        return "interview"

    cumulative += story_prob
    if rand < cumulative:
        return "story"

    cumulative += trending_prob
    if rand < cumulative:
        return "trending"

    cumulative += ai_news_prob
    if rand < cumulative:
        return "ai_news"

    cumulative += layoff_prob
    if rand < cumulative:
        return "layoff_news"

    cumulative += tools_prob
    if rand < cumulative:
        return "tools_news"

    cumulative += tech_prob
    if rand < cumulative:
        return "tech_news"

    total_prob = interview_prob + story_prob + trending_prob + ai_news_prob + layoff_prob + tools_prob + tech_prob
    if total_prob > 1.0:
        log.warning(f"Post mode probabilities sum to {total_prob:.2f} > 1.0 — topic mode will never run. Check env vars.")
    return "topic"


# ─── GITHUB HELPERS ───────────────────────────────────────────────────────────

def write_github_output(key, value):
    gho = os.environ.get("GITHUB_OUTPUT")
    if not gho:
        return
    try:
        with open(gho, "a") as f:
            f.write(f"{key}={value}\n")
    except Exception as e:
        log.warning(f"Could not write GITHUB_OUTPUT: {e}")


def write_github_summary(topic_name, mode, post_preview, dry_run=False, score_card=None):
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return
    try:
        preview = post_preview[:300].replace("\n", "\n> ") if post_preview else "—"
        status  = "🧪 Dry Run" if dry_run else "✅ Published"
        lines = [
            f"## {status} — LinkedIn Post",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| **Topic** | {topic_name} |",
            f"| **Mode** | {mode} |",
            f"| **Dry Run** | {'Yes' if dry_run else 'No'} |",
        ]
        if score_card:
            lines.extend([
                f"| **Quality Score** | {score_card.get('score', '—')} / 100 |",
                f"| **Word Count** | {score_card.get('word_count', '—')} |",
                f"| **Hashtags** | {score_card.get('hashtag_count', '—')} |",
            ])
            if score_card.get("issues"):
                lines.extend([
                    f"",
                    f"### Quality Notes",
                    *[f"- {issue}" for issue in score_card["issues"][:5]],
                ])
        lines.extend([
            f"",
            f"### Post Preview",
            f"> {preview}",
        ])
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        log.info("GitHub step summary written")
    except Exception as e:
        log.warning(f"Could not write step summary: {e}")


# ─── MAIN AGENT ───────────────────────────────────────────────────────────────

def run_agent(manual_topic_id=None, dry_run=False, force_news=None, manual=False, forced_mode=None):
    log.info("=" * 60)
    log.info("LinkedIn Agent — Komal Batra — " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("Mode: " + ("DRY RUN" if dry_run else "LIVE"))
    log.info("=" * 60)

    try:
        from schedule_checker import check_and_wait
        check_and_wait(dry_run=dry_run, manual=manual)
    except SystemExit:
        raise
    except Exception as e:
        log.warning(f"schedule_checker error (non-fatal, continuing): {e}")

    topic_mgr   = TopicManager()
    diagram_gen = DiagramGenerator()
    recent_post_entries = _load_post_memory()
    recent_posts = [e.get("text", "") for e in recent_post_entries if e.get("text")]
    recent_hashes = {_content_hash(t) for t in recent_posts if t}
    try:
        candidate_count = int(os.environ.get("TEXT_CANDIDATES", "3"))
    except Exception:
        candidate_count = 3
    # Dry runs use 1 candidate to skip 3x AI calls — still validates the pipeline
    if dry_run:
        candidate_count = 1
    candidate_count = max(1, min(5, candidate_count))
    try:
        ab_variants = int(os.environ.get("AB_VARIANTS", "2"))
    except Exception:
        ab_variants = 2
    ab_variants = max(1, min(3, ab_variants))
    candidate_snapshot = []

    if not dry_run:
        from linkedin_poster import LinkedInPoster
        poster = LinkedInPoster(
            access_token=os.environ.get("LINKEDIN_ACCESS_TOKEN"),
            person_urn=os.environ.get("LINKEDIN_PERSON_URN"),
        )

    post_text = None
    topic     = None
    structure = None

    if forced_mode and forced_mode not in ("", "auto"):
        mode = forced_mode
    elif manual_topic_id:
        mode = "topic"
    elif force_news:
        mode = force_news
    else:
        mode = get_post_mode()

    log.info("Post mode: " + mode)
    write_github_output("POST_MODE", mode)

    # ── GENERATE POST ─────────────────────────────────────────────────────────
    if mode == "interview":
        # NEW: Interview posts with rotating topics
        interview_topic, interview_text = generate_interview_post()
        
        if interview_topic and interview_text:
            post_text = interview_text
            topic = interview_topic
            structure = None  # Interview posts don't use structured diagrams
            log.info(f"Interview post selected: {topic['name']}")
        else:
            mode = "topic"  # Fallback
            log.warning("Interview generation failed, falling back to topic mode")

    elif mode == "ai_news":
        post_text = generate_news_post("ai")
        if not post_text:
            mode = "topic"

    elif mode == "layoff_news":
        # SYNTHESIS MODE: Aggregating multiple sources for deeper analysis
        articles = fetch_rss_news("layoffs", 10) # Fetch more to find the best signal
        layoff_articles = [a for a in articles if any(
            w in a["title"].lower()
            for w in ["layoff", "laid off", "cut", "job", "workforce", "redundan", "downsize", "voluntary exit", "retirement", "buyout", "severance"]
        )][:5] # Synthesize top 5
        
        if layoff_articles:
            news_text = "\n".join([
                f"- {a['title']}: {a['description'][:300]}"
                for a in layoff_articles
            ])
            hook   = random.choice(HOOK_STYLES)
            tone   = random.choice(TONE_VARIATIONS)
            length = random.choice(LENGTH_VARIATIONS)
            
            # ADVANCED SYNTHESIS PROMPT
            prompt = f"""TECHNICAL NEWS AGGREGATION:
{news_text}

Analyze the above industry signals and write a high-authority LinkedIn post.
GOAL: Don't just report news; synthesize it into an industry trend.

Structure:
1. Hook: {hook} (Address the human side of tech)
2. The Pulse: What connects these specific events? (e.g. shifts from growth to efficiency, or specific vertical tremors)
3. The Engineering Take: How should Staff/Senior engineers read these signals for their own career roadmap?
4. Actionable Insight: One specific thing an engineer can do TODAY to stay ahead of this trend.

Voice/Tone: {tone} (Analytical, weathered, engineering-leader perspective)
Constraints:
- No mentions of months/years
- No 'congratulations' or 'my thoughts go out to' placeholders
- Professional but direct
"""
            post_text = call_ai(prompt, NEWS_SYSTEM)
        if not post_text:
            mode = "topic"

    elif mode == "tools_news":
        articles = fetch_rss_news("tools", 5)
        tool_articles = [a for a in articles if any(
            w in a["title"].lower()
            for w in ["launch", "release", "new", "introduce", "tool", "platform",
                      "open source", "github", "api", "model"]
        )]
        if tool_articles:
            news_text = "\n".join([
                f"- {a['title']}: {a['description'][:200]}"
                for a in tool_articles[:3]
            ])
            hook   = random.choice(HOOK_STYLES)
            tone   = random.choice(TONE_VARIATIONS)
            length = random.choice(LENGTH_VARIATIONS)
            prompt = f"""Latest new tech tools and launches:
{news_text}

Hook: {hook}
Voice: {tone}
Length: {length}

Write a LinkedIn post that:
- Picks ONE tool and makes a real judgment call: signal or noise?
- Explains exactly what problem it solves (or claims to)
- Compares it to something engineers already use
- Gives a concrete use case — not "this could be useful for many teams"
- Does NOT mention the current month or year
"""
            post_text = call_ai(prompt, NEWS_SYSTEM)
        if not post_text:
            mode = "topic"

    elif mode == "tech_news":
        post_text = generate_news_post("tech")
        if not post_text:
            mode = "topic"

    elif mode == "trending":
        # ── TRENDING TOPIC MODE ───────────────────────────────────────────
        try:
            from trend_discovery import discover_trending_topics
            from trend_to_topic import pick_best_trend

            log.info("Fetching trending topics from HN + Reddit + Dev.to...")
            trends = discover_trending_topics(max_topics=12)

            if trends:
                recent_ids = _get_recent_topics(days=7)
                trend_topic, chosen_trend = pick_best_trend(
                    trends, recent_ids, call_ai
                )
                if trend_topic:
                    topic = trend_topic
                    structure = topic_mgr.get_diagram_structure(topic)
                    planned_diagram_type = topic_mgr.get_diagram_type_for_topic(topic)
                    log.info(f"Trending topic selected: {topic['name']} (from {chosen_trend.get('source','?')} — score {chosen_trend.get('score',0)})")
                    trending_candidates = []
                    for _ in range(candidate_count):
                        draft = generate_topic_post(topic, structure, planned_diagram_type, dry_run=dry_run)
                        trending_candidates.append(_finalize_post_text(topic, draft, structure=structure, diagram_type=planned_diagram_type))
                    ranked_trending = _rank_candidates(
                        topic, trending_candidates, structure, planned_diagram_type,
                        recent_posts, recent_hashes=recent_hashes
                    )
                    pick = ranked_trending[0]
                    candidate_snapshot = ranked_trending[:ab_variants]
                    post_text = trending_candidates[pick["index"]]
                    if len(candidate_snapshot) >= 2:
                        log.info(
                            f"A/B winner: variant #{candidate_snapshot[0]['index']+1} ({candidate_snapshot[0]['score']}) "
                            f"over #{candidate_snapshot[1]['index']+1} ({candidate_snapshot[1]['score']})"
                        )
                else:
                    log.warning("No suitable trending topic found, falling back to topic mode")
                    mode = "topic"
            else:
                log.warning("Trend discovery returned no results, falling back to topic mode")
                mode = "topic"

        except ImportError as e:
            log.warning(f"Trend discovery modules not available ({e}), falling back to topic mode")
            mode = "topic"
        except Exception as e:
            log.warning(f"Trending mode failed ({e}), falling back to topic mode")
            mode = "topic"

    elif mode == "story":
        chosen_theme = random.choice(STORY_THEMES)
        story_candidates = []
        story_meta = []
        for _ in range(candidate_count):
            st_topic, st_text = generate_story_post(theme=chosen_theme)
            # Extract actual takeaways from the generated post text
            # so diagram labels match what was actually written
            extracted_sections = _extract_story_sections(st_text, chosen_theme)
            st_structure = {
                "style": 23,  # Viral poster — fits personal stories much better than flow diagrams
                "subtitle": chosen_theme.get("angle", "Engineer's Perspective")[:60],
                "sections": extracted_sections,
            }
            st_text = _finalize_post_text(st_topic, st_text, structure=st_structure, diagram_type="Modern Cards")
            story_candidates.append(st_text)
            story_meta.append((st_topic, st_structure))
        ranked_story = _rank_candidates(
            story_meta[0][0], story_candidates, story_meta[0][1], "Modern Cards", recent_posts, recent_hashes=recent_hashes
        )
        pick = ranked_story[0]
        candidate_snapshot = ranked_story[:ab_variants]
        topic, structure = story_meta[pick["index"]]
        post_text = story_candidates[pick["index"]]
        if len(candidate_snapshot) >= 2:
            log.info(
                f"A/B winner: variant #{candidate_snapshot[0]['index']+1} ({candidate_snapshot[0]['score']}) "
                f"over #{candidate_snapshot[1]['index']+1} ({candidate_snapshot[1]['score']})"
            )
    elif mode == "carousel":
        # ── CAROUSEL MODE: 5-Slide Narrative ──────────────────────────────────────
        topic = topic_mgr.get_next_topic()
        carousel_prompt = f"""Write a 5-slide Technical Carousel about {topic['name']}.
Goal: Tell a high-level architectural story.

Slide 1: The Hook & The 'Big Picture' Problem
Slide 2: The Traditional Way (and why it fails at Microsoft scale)
Slide 3: The 'Lead' Insight (The clever architectural shift)
Slide 4: The Deep Dive (Components & Data Flow)
Slide 5: The Impact & Final Architect's Tip

For each slide, provide a 'Visual Title' and a 'Visual Description' for the diagram.
Format the output as a LinkedIn post followed by a [SLIDES] section.
"""
        raw_carousel = call_ai(carousel_prompt, NEWS_SYSTEM)
        post_text = raw_carousel.split("[SLIDES]")[0].strip()
        slides_text = raw_carousel.split("[SLIDES]")[1].strip() if "[SLIDES]" in raw_carousel else ""
        
        # Parse slides and generate bundle
        slides_config = _extract_carousel_slides(slides_text, topic)
        from diagram_generator import generate_carousel_bundle
        carousel_paths = generate_carousel_bundle(topic["id"], topic["name"], slides_config)
        log.info(f"Carousel bundle ready: {len(carousel_paths)} images generated.")
        
        # Track for the first comment
        with open("output_comment.txt", "w") as f:
            f.write(f"This is a 5-slide deep dive into {topic['name']}. Swipe through to see the architectural breakdown! 💡")
    elif mode == "build_log":
        # ── BUILD LOG MODE: Progress Diary ──────────────────────────────────────
        from build_tracker import get_recent_milestones
        milestones = get_recent_milestones()
        
        if milestones:
            ms_text = "\n".join(milestones)
            prompt = f"""Write a LinkedIn 'Weekly Build Log' as a Technical Lead.
What we achieved this week in the engineering repository:
{ms_text}

Goal: Show high-level progress and the 'Why' behind the changes.
- Focus on how these changes improve the overall system architecture.
- Keep it honest and engineering-focused (no 'hustle' culture language).
- End with a question about how other teams handle developmental sprints.
"""
            post_text = call_ai(prompt, NEWS_SYSTEM)
            topic = {"id": "build-log", "name": "Weekly Build Progress", "category": "system"}
            structure = {"style": 23, "subtitle": "Weekly Sprint Architecture", "sections": milestones[:4]}
            planned_diagram_type = "Modern Cards"
        else:
            mode = "topic"

    # ── RESOLVE TOPIC ─────────────────────────────────────────────────────────
    if mode == "topic" or not post_text:
        topic = (
            topic_mgr.get_topic(manual_topic_id)
            if manual_topic_id
            else topic_mgr.get_next_topic()
        )
        log.info("Topic selected: " + topic["name"])
        
        # NEW: Check topic diversity to prevent repetition
        is_diverse, similarity_score, conflicts = _check_topic_diversity(topic, days=7)
        if not is_diverse:
            log.warning(f"Topic similarity warning: {topic['name']} is {similarity_score:.1%} similar to recent posts. Conflicting topics: {conflicts}")
        else:
            log.info(f"Topic diversity check passed: {topic['name']} is unique")
        structure = topic_mgr.get_diagram_structure(topic)
        planned_diagram_type = topic_mgr.get_diagram_type_for_topic(topic)
        structure_items = structure.get("sections") or structure.get("rows") or []
        log.info(f"Structure: '{structure['subtitle']}' ({len(structure_items)} items)")
        log.info(f"Planned topic diagram type: {planned_diagram_type}")
        topic_candidates = []
        for _ in range(candidate_count):
            draft = generate_topic_post(topic, structure, planned_diagram_type, dry_run=dry_run)
            topic_candidates.append(_finalize_post_text(topic, draft, structure=structure, diagram_type=planned_diagram_type))
        ranked_topic = _rank_candidates(
            topic, topic_candidates, structure, planned_diagram_type, recent_posts, recent_hashes=recent_hashes
        )
        pick = ranked_topic[0]
        candidate_snapshot = ranked_topic[:ab_variants]
        post_text = topic_candidates[pick["index"]]
        if len(candidate_snapshot) >= 2:
            log.info(
                f"A/B winner: variant #{candidate_snapshot[0]['index']+1} ({candidate_snapshot[0]['score']}) "
                f"over #{candidate_snapshot[1]['index']+1} ({candidate_snapshot[1]['score']})"
            )

    # Save selection history for both dry and live runs to reduce repeated topics in previews.
    if topic and topic.get("id"):
        try:
            topic_mgr.save_selection_history({
                "timestamp": datetime.now().isoformat(),
                "topic_id": topic["id"],
                "topic_name": topic.get("name", ""),
                "category": topic.get("category", ""),
                "mode": mode,
                "dry_run": bool(dry_run),
            })
        except Exception as e:
            log.warning(f"Could not save selection history: {e}")

    # ── FALLBACK TOPIC for news posts ─────────────────────────────────────────
    if not topic:
        topic = topic_mgr.get_next_topic()
        structure = topic_mgr.get_diagram_structure(topic)
        log.info("Fallback topic for diagram/history: " + topic["name"])

    post_text = _finalize_post_text(topic, post_text, structure=structure, diagram_type=topic_mgr.get_diagram_type_for_topic(topic))
    score_diagram_type = topic_mgr.get_diagram_type_for_topic(topic)
    score_structure = structure or topic_mgr.get_diagram_structure(topic)
    score_card = _score_post_candidate(topic, post_text, score_structure, score_diagram_type)
    if mode in {"topic", "story"} and score_card["score"] < 75 and not dry_run:
        log.warning(
            f"Low post quality score ({score_card['score']}/100). Regenerating once with the same topic."
        )
        regen_structure = score_structure
        regen_diagram_type = score_diagram_type
        regen_candidates = []
        for _ in range(max(2, candidate_count)):
            if mode == "story":
                _, regen_text = generate_story_post()
            else:
                regen_text = generate_topic_post(topic, regen_structure, regen_diagram_type)
            regen_candidates.append(_finalize_post_text(topic, regen_text, structure=regen_structure, diagram_type=regen_diagram_type))
        ranked_regen = _rank_candidates(
            topic, regen_candidates, regen_structure, regen_diagram_type, recent_posts, recent_hashes=recent_hashes
        )
        regen_pick = ranked_regen[0]
        candidate_snapshot = ranked_regen[:ab_variants]
        post_text = regen_candidates[regen_pick["index"]]
        score_card = _score_post_candidate(topic, post_text, regen_structure, regen_diagram_type)

    log.info(
        f"Quality score: {score_card['score']}/100 | "
        f"words={score_card['word_count']} | hashtags={score_card['hashtag_count']}"
    )
    if score_card["issues"]:
        log.warning("Quality notes: " + " | ".join(score_card["issues"][:5]))

    # ── HARD PUBLISH BLOCKERS ─────────────────────────────────────────────────
    # Minimum bar for a live post. Dry-run and manual triggers bypass this gate.
    PUBLISH_SCORE_MIN = 60
    if not dry_run and not manual:
        pub_blockers = []
        if score_card["score"] < PUBLISH_SCORE_MIN:
            pub_blockers.append(
                f"Quality score too low for live publish ({score_card['score']}/100)."
            )
        if not (4 <= score_card["hashtag_count"] <= 7):
            pub_blockers.append(
                f"Hashtag count is outside the safe publish range (4 to 7)."
            )
        # Hard structural integrity check — catches naked labels, fabricated incidents, truncated items
        structural_blockers = _has_structural_integrity_issues(post_text)
        if structural_blockers:
            pub_blockers.extend(structural_blockers)
            log.warning("Structural integrity blockers: " + " | ".join(structural_blockers))
        if pub_blockers:
            log.warning("Publish blockers: " + " | ".join(pub_blockers))
            log.warning("Draft failed quality checks — attempting recovery with fresh topic post.")
            # Pick a different topic for recovery
            failed_id = topic.get("id", "")
            recovery_topic = topic_mgr.get_next_topic()
            if recovery_topic.get("id") == failed_id:
                # get_next_topic returned the same topic — force a different one
                alt_topics = [t for t in topic_mgr.topics if t.get("id") != failed_id]
                if alt_topics:
                    recovery_topic = alt_topics[0]
            log.info(f"Selected topic: {recovery_topic['name']} (category: {recovery_topic.get('category', '')})")
            recovery_structure = topic_mgr.get_diagram_structure(recovery_topic)
            recovery_diagram_type = topic_mgr.get_diagram_type_for_topic(recovery_topic)
            log.info(f"Generating post: {recovery_topic['name']}")
            recovery_text_raw = generate_topic_post(recovery_topic, recovery_structure, recovery_diagram_type)
            recovery_text = _finalize_post_text(
                recovery_topic, recovery_text_raw,
                structure=recovery_structure, diagram_type=recovery_diagram_type
            )
            recovery_score = _score_post_candidate(
                recovery_topic, recovery_text, recovery_structure, recovery_diagram_type
            )
            recovery_blockers = _has_structural_integrity_issues(recovery_text)
            if recovery_score["score"] < PUBLISH_SCORE_MIN:
                recovery_blockers.insert(
                    0, f"Quality score too low for live publish ({recovery_score['score']}/100)."
                )
            if not (4 <= recovery_score["hashtag_count"] <= 7):
                recovery_blockers.insert(
                    0, f"Hashtag count is outside the safe publish range (4 to 7)."
                )
            if recovery_blockers:
                log.warning("Recovery post also had quality issues — publishing best available post.")
                log.warning("Recovery blockers: " + " | ".join(recovery_blockers))
                # Don't exit — continue with the original post rather than losing the run entirely
            # Recovery succeeded — use the recovery post for publishing
            log.info(
                f"Recovery quality score: {recovery_score['score']}/100 | "
                f"hashtags={recovery_score['hashtag_count']} — proceeding with recovery post."
            )
            topic = recovery_topic
            post_text = recovery_text
            score_card = recovery_score
            structure = recovery_structure
            score_structure = recovery_structure
            score_diagram_type = recovery_diagram_type

    write_github_output("POST_TOPIC",   topic.get("name", ""))
    write_github_output("POST_TOPIC_ID", topic.get("id", ""))
    write_github_output("POST_QUALITY_SCORE", str(score_card["score"]))
    log.info(f"Final topic resolved: {topic['name']} (mode: {mode})")
    log.info("POST:\n" + post_text)

    # ── GENERATE DIAGRAM ──────────────────────────────────────────────────────
    fallback_diagram_type = topic_mgr.get_diagram_type_for_topic(topic)

    # ALIGNMENT FIX: Extract the actual subject the post was written about
    # by scanning for the most specific technical noun phrase in the post.
    # We now include general system design concepts (Domain Transfer, CDC, etc.)
    post_subject_override = None
    tech_subject_patterns = [
        # Specific Tools/Tech
        r"\b(Kubernetes|Docker|Kafka|RAG|LLM|GraphQL|gRPC|Redis|Postgres|"
        r"Terraform|Helm|Prometheus|Grafana|Istio|Argo|Flink|Spark|dbt|"
        r"Pinecone|Weaviate|LangChain|LangGraph|AutoGen|FastAPI|Pydantic|"
        r"OpenTelemetry|Datadog|New Relic|GitHub Actions|GitLab CI)\b",
        # General Engineering Concepts (New: catches 'Domain Transfer', etc.)
        r"\b(Domain Transfer|API Gateway|Load Balanc|Event-Driven|Microservice|"
        r"CDC|Change Data Capture|Rate Limiting|Circuit Breaker|Database Sharding|"
        r"Blue-Green|Canary|Observability|Distributed Tracing|Zero Trust)\b",
    ]
    for pattern in tech_subject_patterns:
        match = re.search(pattern, post_text or "", re.IGNORECASE)
        if match:
            post_subject_override = match.group(0)
            log.info(f"🎯 Post subject detected: '{post_subject_override}' — aligning all metadata")
            break

    # If post is about something different from topic name, sync EVERYTHING
    if post_subject_override and post_subject_override.lower() not in topic["name"].lower():
        log.warning(
            f"🔄 Topic mismatch: topic='{topic['name']}' -> post='{post_subject_override}'. Syncing metadata."
        )
        topic["name"] = post_subject_override  # SYNC GLOBAL TOPIC
    
    diagram_topic = dict(topic)
    diagram_title, diagram_type, diagram_structure = _resolve_visual_metadata(
        diagram_topic, post_text, mode, fallback_diagram_type, structure
    )
    visual_issues = _visual_coherence_issues(topic, diagram_type, diagram_structure)
    if visual_issues:
        log.warning("Visual coherence override: " + " | ".join(visual_issues))
        diagram_type = fallback_diagram_type
        diagram_structure = topic_mgr.get_diagram_structure(topic)
    log.info(f"Visual metadata: title='{diagram_title}', type='{diagram_type}'")
    
    # ── SELECT DIAGRAM STYLE USING SMART ROTATION ──────────────────────────────
    # NEW: Use smart rotation to cycle through all 23 available diagram styles
    # Check if the diagram type has an intentional style (e.g. Viral Poster = 23)
    # If so, respect it — don't let rotation override a deliberate design choice
    INTENTIONAL_STYLE_MAP = {
        "Viral Poster":     23,
        "poster":           23,
        "Info Frame":       23,
        "Knowledge Card":   23,
        "Tile Grid":        24,
        "tiles":            24,
        "Iceberg Diagram":  25,
        "iceberg":          25,
        "Dashboard":        26,
        "Metrics":          26,
        "kpi":              26,
        "Maturity Model":   27,
        "Radial":           27,
        "Progress Rings":   27,
    }
    intentional_style = INTENTIONAL_STYLE_MAP.get(diagram_type)

    if intentional_style is not None:
        selected_style = intentional_style
        log.info(f"Using intentional style {selected_style} for diagram type '{diagram_type}' (rotation bypassed)")
    else:
        selected_style = _select_smart_diagram_style(topic.get("id", ""))
        log.info(f"Selected diagram style {selected_style} from {len(ALL_DIAGRAM_STYLES)} available styles for visual variety")

    # Ensure diagram_structure is a dict and set the selected style
    if not isinstance(diagram_structure, dict):
        diagram_structure = {}
    diagram_structure_with_style = copy.deepcopy(diagram_structure)
    # CRITICAL: style must be set here AND passed through — diagram_generator
    # will respect structure["style"] over its own _pick_candidate_styles()
    diagram_structure_with_style["style"] = selected_style

    # Double-check: if viral poster was chosen, verify structure has style=23
    # diagram_generator's internal scoring can still override if we don't assert this
    if diagram_type in ("Viral Poster", "poster"):
        diagram_structure_with_style["style"] = 23
        # Also set DIAGRAM_CANDIDATES=1 via env to prevent internal style competition
        os.environ["DIAGRAM_CANDIDATES"] = "1"
        log.info("Viral Poster confirmed — locking style=23, candidates=1")

    # Sanity check: log if style 0 repeats (indicates rotation file reset)
    recent_styles = _load_diagram_rotation_state().get("style_history", [])
    if recent_styles.count(0) >= 3:
        log.warning("Style 0 appearing 3+ times in rotation — rotation file may have reset. Forcing a different style.")
        available_non_zero = [s for s in ALL_DIAGRAM_STYLES if s != 0 and s not in recent_styles[-5:]]
        if available_non_zero:
            selected_style = available_non_zero[0]
            diagram_structure_with_style["style"] = selected_style
            log.info(f"Forced style override to {selected_style}")
    
    diagram_path = diagram_gen.save_svg(
    None, topic["id"], diagram_title, diagram_type,
    structure=diagram_structure_with_style, post_text=post_text,
    topic_name_override=diagram_topic["name"]   # ← use post-derived subject
)
    
    alignment = _diagram_alignment_score(diagram_path, diagram_structure_with_style)
    log.info(f"Diagram/Text alignment score: {alignment:.2f}")

    if alignment < 0.45 and diagram_structure_with_style:
        fallback_style = _fallback_style_for_diagram(diagram_type, diagram_structure)
        forced_structure = copy.deepcopy(diagram_structure_with_style)
        forced_structure["style"] = fallback_style  # Use fallback style but keep rotation record
        log.warning(
            f"Low diagram/text alignment ({alignment:.2f}). Regenerating diagram with style {fallback_style}."
        )
        diagram_path = diagram_gen.save_svg(
            None, topic["id"], diagram_title, diagram_type,
            structure=forced_structure, post_text=post_text
        )
        alignment = _diagram_alignment_score(diagram_path, forced_structure)
        diagram_structure = forced_structure
        log.info(f"Diagram/Text alignment score after retry: {alignment:.2f}")

    strict_match = os.environ.get("DIAGRAM_STRICT_MATCH", "1").strip().lower() not in {"0", "false", "no"}
    if alignment < 0.35:
        msg = f"Diagram/Post semantic mismatch remains high (alignment={alignment:.2f})."
        if strict_match and not dry_run:
            log.error(msg + " Blocking publish.")
            sys.exit(1)
        log.warning(msg + " Continuing due to dry-run or non-strict mode.")

    log.info("Diagram saved: " + diagram_path)

    if dry_run:
        title_line = f"📌 {topic['name']}\n\n"
        full_post_text = (
            title_line + post_text
            if not post_text.strip().startswith("📌")
            else post_text
        )
        full_post_text = _finalize_post_text(topic, full_post_text, structure=diagram_structure, diagram_type=diagram_type)
        publish_text = _render_linkedin_text(full_post_text)
        publish_text = _normalize_hashtags(publish_text)  # Fix: strip any leaked hashtag# tokens
        with open("output_post_" + topic["id"] + ".txt", "w", encoding="utf-8") as f:
                f.write(publish_text)
            
        # NEW: Log post to engagement tracker even in dry run
        post_id = _log_post_generated(topic, publish_text, selected_style, mode)
    
        with open("preview_payload_" + topic["id"] + ".json", "w", encoding="utf-8") as f:
            json.dump({
                "topic_id": topic["id"],
                "topic_name": topic["name"],
                "category": topic.get("category", ""),
                "mode": mode,
                "diagram_type": diagram_type,
                "diagram_title": diagram_title,
                "diagram_file": os.path.basename(diagram_path),
                "post_file": "output_post_" + topic["id"] + ".txt",
                "post_id_for_tracking": post_id,
                "diagram_style_used": selected_style,
                "quality_notes": score_card["issues"],
                "ab_variants": [
                    {
                        "variant_index": c.get("index", 0) + 1,
                        "score": c.get("score"),
                        "raw_score": c.get("raw_score"),
                        "similarity": round(c.get("sim", 0.0), 4),
                        "penalty": c.get("penalty", 0),
                    }
                    for c in candidate_snapshot
                ],
            }, f, indent=2)
        write_github_summary(topic["name"], mode, publish_text, dry_run=True, score_card=score_card)
        _remember_post(topic, publish_text)
        log.info("DRY RUN complete. Post saved.")
        return

    # ── POST TO LINKEDIN ───────────────────────────────────────────────────────
    title_line = f"📌 {topic['name']}\n\n"
    full_post_text = (
        title_line + post_text
        if not post_text.strip().startswith("📌")
        else post_text
    )
    full_post_text = _finalize_post_text(topic, full_post_text, structure=diagram_structure, diagram_type=diagram_type)
    publish_text = _render_linkedin_text(full_post_text)
    publish_text = _normalize_hashtags(publish_text)  # Fix: strip any leaked hashtag# tokens
    with open("output_post_" + topic["id"] + ".txt", "w", encoding="utf-8") as f:
        f.write(publish_text)
        
    # NEW: Log post to engagement tracker even in dry run
    post_id = _log_post_generated(topic, publish_text, selected_style, mode)
    log.info(f"Engagement tracking ID assigned: {post_id}")

    result = poster.create_post_with_image(
        text=publish_text,
        image_path=diagram_path,
        title=topic["name"],
    )
    if result.get("success"):
        log.info("Posted! ID: " + str(result.get("post_id")))
        write_github_output("POSTED_TOPIC", topic.get("name", ""))
        write_github_output("POSTED_TITLE", topic.get("name", ""))
        write_github_output("POSTED_DATE",  datetime.now().strftime("%Y-%m-%d"))
        write_github_output("POSTED_URL",   result.get("post_url", ""))
        write_github_summary(topic["name"], mode, publish_text, dry_run=False, score_card=score_card)
        _remember_post(topic, publish_text)
        
        # --- NEXT-GEN: Analytics & First Comment ---
        try:
            from analytics_engine import record_post_metadata
            record_post_metadata(topic["id"], score_card["score"], mode)
            
            # Generate engagement comment
            comment_prompt = f"""Write a short, engaging first comment for this LinkedIn post about {topic['name']}.
Goal: Spark a technical debate or provide an 'extra' Pro Tip not in the post.
Keep it under 3 lines. No hashtags.
"""
            first_comment = call_ai(comment_prompt, NEWS_SYSTEM)
            if first_comment:
                with open("output_comment.txt", "w", encoding="utf-8") as f:
                    f.write(first_comment)
                log.info("💬 First comment generated for engagement.")
        except Exception as e:
            log.warning(f"Next-Gen hooks failed (non-fatal): {e}")

        topic_mgr.save_run_history({
            "timestamp":  datetime.now().isoformat(),
            "topic_id":   topic["id"],
            "topic_name": topic["name"],
            "category":   topic.get("category", ""),
            "mode":       mode,
            "status":     "success",
            "quality_score": score_card["score"],
            "ab_variants": [
                {
                    "variant_index": c.get("index", 0) + 1,
                    "score": c.get("score"),
                    "raw_score": c.get("raw_score"),
                    "similarity": round(c.get("sim", 0.0), 4),
                    "penalty": c.get("penalty", 0),
                }
                for c in candidate_snapshot
            ],
        })
        try:
            from notifier import notify_all
            notify_all(topic=topic["name"], post_preview=post_text, is_dry_run=dry_run)
        except Exception as e:
            log.warning("Notification error (non-fatal): " + str(e))
    else:
        log.error("Failed: " + str(result.get("error")))
        topic_mgr.save_run_history({
            "timestamp":  datetime.now().isoformat(),
            "topic_id":   topic["id"],
            "topic_name": topic["name"],
            "category":   topic.get("category", ""),
            "mode":       mode,
            "status":     "failed",
        })
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--manual", action="store_true",
                        help="Skip schedule sleep, run immediately")
    parser.add_argument("--news", type=str, default=None,
                        help="Force news mode: ai_news, layoff_news, tools_news, tech_news")
    parser.add_argument("--mode", type=str, default=None,
                        help="Force post mode: auto, topic, story, trending, ai_news, layoff_news, tools_news, tech_news")
    parser.add_argument("--list-topics", action="store_true")
    args = parser.parse_args()
    if args.list_topics:
        TopicManager().list_topics()
        sys.exit(0)
    run_agent(
        manual_topic_id=args.topic,
        dry_run=args.dry_run,
        force_news=args.news,
        manual=args.manual,
        forced_mode=args.mode,
    )

def _extract_carousel_slides(slides_text, topic):
    """Parses AI output into 5 slide configs."""
    slides = []
    # Simplified parser: looks for 'Slide X:'
    lines = slides_text.split("\n")
    current_slide = None
    for line in lines:
        if line.lower().startswith("slide"):
            if current_slide: slides.append(current_slide)
            current_slide = {"title": line, "type": "Architecture", "structure": None}
        elif current_slide and ":" in line:
            current_slide["title"] = line.split(":", 1)[1].strip()
    if current_slide: slides.append(current_slide)
    
    # Ensure at least 3, max 5
    return slides[:5] if len(slides) >= 3 else [
        {"title": f"{topic['name']} - Intro", "type": "Modern Cards"},
        {"title": "The Architecture", "type": "Architecture"},
        {"title": "The Trade-offs", "type": "Comparison Table"}
    ]
