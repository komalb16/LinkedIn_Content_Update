import os
import sys
import re
import json
import random
import argparse
import copy
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from topic_manager import TopicManager
from diagram_generator import DiagramGenerator
from logger import get_logger
import notifier

log = get_logger("agent")
POST_MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".post_memory.json")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

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

# ─── NEWS SOURCES ─────────────────────────────────────────────────────────────
RSS_FEEDS = {
    "ai": [
        "https://venturebeat.com/category/ai/feed/",
        "https://techcrunch.com/category/artificial-intelligence/feed/",
    ],
    "tech": [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/tech/rss/index.xml",
    ],
    "layoffs": [
        "https://techcrunch.com/feed/",
        "https://news.ycombinator.com/rss",
    ],
    "tools": [
        "https://news.ycombinator.com/rss",
        "https://techcrunch.com/feed/",
    ],
}

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
- No corporate-speak. If you would not say it to a colleague, do not write it.
- ALWAYS end with 💬 + a genuine question + blank line + 5 to 7 hashtags
- Include exactly ONE fenced visual block that matches the planned diagram type
- If planned type is "Comparison Table", use a simple `left -> right` format
- For non-comparison topics, avoid forcing vendor-vs-vendor comparisons
- Do NOT add copyright, signature, or author name
- Never mention the current month or year
"""


NEWS_SYSTEM = """\
You are Komal Batra — a Staff Engineer reacting to breaking tech news on LinkedIn.
You have opinions. You pick a side. You back it with specifics.

RULES:
- Lead with your honest reaction, not a summary of the news
- Use "I" freely — this is a personal take, not a press release
- One strong opinion, defended with specifics — not a both-sides take
- Include one ``` fenced visual block that fits the post
- End with 💬 + a sharp question + 5 to 7 hashtags
- 200 to 300 words — reactions should be tight
- No banned words: robust, crucial, delve, landscape, seamless, synergy,
  paradigm, unprecedented, game-changer, revolutionize, supercharge
- Never mention the current month or year
- Do NOT add copyright or signature
"""

STORY_THEMES = [
    {
        "id": "ai-discovery-moment",
        "name": "AI Discovery Moment",
        "prompt": "A personal but practical realization about how AI tools discover businesses, professionals, and expertise from public signals.",
        "angle": "Use one concrete moment, then extract 3 practical actions readers can apply to their own profile or workflow.",
        "diagram_type": "Modern Cards",
        "diagram_subject": "Moment -> Realization -> Actions -> Outcome",
    },
    {
        "id": "career-leverage-shift",
        "name": "Career Leverage Shift",
        "prompt": "How AI changes leverage at work: small teams shipping more by automating repetitive workflows.",
        "angle": "Ground it in practical examples and avoid fear language.",
        "diagram_type": "Modern Cards",
        "diagram_subject": "Old workflow vs AI workflow vs role shift",
    },
]

STORY_SYSTEM = """\
You are Komal Batra writing a personal story post for LinkedIn.

RULES:
- Start with a concrete moment (not a generic intro).
- Keep it honest, practical, and specific.
- Include exactly 3 actionable takeaways.
- No fabricated metrics, salaries, or sweeping claims unless explicitly provided.
- Include one ``` fenced visual block with 3 to 5 lines.
- End with 💬 and one genuine question plus 4 to 7 hashtags.
- Do NOT mention the current month or year.
"""


# ─── AI CALL ──────────────────────────────────────────────────────────────────

def call_ai(prompt, system):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY secret not set")
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 1024,
        "temperature": 0.92,
    }
    resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=30)
    if resp.status_code != 200:
        log.error("Groq error: " + resp.text)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


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
        "diagram_type": theme.get("diagram_type", "Modern Cards"),
    }
    return story_topic, post_text


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
    if diagram_type in {"Decision Tree", "Winding Roadmap", "Flow Chart", "Lane Map"}:
        return (
            "Include one ``` fenced flow block using plain ASCII connectors like `->` or `|`."
        )
    return (
        "Include one ``` fenced visual block (outline, framework, or mini-map) "
        "that mirrors the post structure."
    )


def generate_topic_post(topic, structure=None, diagram_type=""):
    log.info("Generating post: " + topic["name"])

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

    return text


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

    if re.search(r"\bnext post\b|\bthird post\b|\bpost 2\b|\banother post\b", cleaned, re.I):
        issues.append("Write exactly one post and remove any extra appended drafts.")
    if re.search(r"```+\s*mermaid|^\s*graph\s+(?:lr|td)|^\s*flowchart", cleaned, re.I | re.M):
        issues.append("Do not use Mermaid syntax; use plain-text visual blocks only.")

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


def _finalize_post_text(topic, post_text, structure=None, diagram_type=""):
    finalized = _cleanup_generated_post(post_text or "")
    finalized = finalized.replace("hashtag#", "#").strip()
    if not finalized:
        return finalized
    finalized = _strip_work_incident_hook(finalized, topic.get("name", ""))
    finalized = _upgrade_weak_poll_options(finalized, structure=structure, diagram_type=diagram_type)
    finalized = _align_poll_with_structure(finalized, structure=structure, diagram_type=diagram_type)
    finalized = _enforce_numbered_poll_options(finalized)
    return finalized


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
    entries = _load_post_memory()
    entries.append({
        "timestamp": datetime.now().isoformat(),
        "topic_id": topic.get("id", ""),
        "topic_name": topic.get("name", ""),
        "text": _cleanup_generated_post(text or "")[:2500],
    })
    _save_post_memory(entries)


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
        "Decision Tree": 21,
        "Comparison Table": 22,
        "Flow Chart": 21,
        "Lane Map": 21,
        "Signal vs Noise": 17,
        "7 Layers": 16,
        "Observability Map": 20,
        "Winding Roadmap": 16,
        "Architecture Diagram": 16,
        "Architecture": 16,
        "Modern Cards": 22,
    }
    return mapping.get(diagram_type, 16)


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
        score -= 6

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


def _pick_best_candidate(topic, candidates, structure, diagram_type, recent_posts, recent_hashes=None):
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
    strong_editorial = {"Decision Tree", "7 Layers", "Signal vs Noise", "Lane Map", "Observability Map"}
    if "decision tree" in text or "when not to use" in text or "should i" in text:
        return "Decision Tree"
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


def _resolve_visual_metadata(topic, post_text, mode, fallback_type, fallback_structure):
    if mode in {"topic", "story"}:
        return topic["name"], fallback_type, fallback_structure

    diagram_type = _infer_diagram_type_from_post(post_text, fallback_type)
    fallback_entities = [topic.get("name", topic.get("id", ""))]
    if topic.get("diagram_subject"):
        fallback_entities.extend(re.findall(r"\b[A-Z][A-Za-z0-9+.\-]{2,}\b", topic["diagram_subject"]))
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
    if os.environ.get("ENABLE_NEWS_MODES", "0").strip().lower() in {"1", "true", "yes"}:
        rand = random.random()
        if rand < 0.10:
            return "story"
        elif rand < 0.15:
            return "ai_news"
        elif rand < 0.18:
            return "layoff_news"
        elif rand < 0.22:
            return "tools_news"
        elif rand < 0.25:
            return "tech_news"
        else:
            return "topic"

    rand = random.random()
    if rand < 0.12:
        return "story"
    else:
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
    candidate_count = max(1, min(5, candidate_count))

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
    if mode == "ai_news":
        post_text = generate_news_post("ai")
        if not post_text:
            mode = "topic"

    elif mode == "layoff_news":
        articles = fetch_rss_news("layoffs", 5)
        layoff_articles = [a for a in articles if any(
            w in a["title"].lower()
            for w in ["layoff", "laid off", "cut", "job", "workforce", "redundan", "downsize"]
        )]
        if layoff_articles:
            news_text = "\n".join([
                f"- {a['title']}: {a['description'][:200]}"
                for a in layoff_articles[:3]
            ])
            hook   = random.choice(HOOK_STYLES)
            tone   = random.choice(TONE_VARIATIONS)
            length = random.choice(LENGTH_VARIATIONS)
            prompt = f"""Latest tech industry layoff news:
{news_text}

Hook: {hook}
Voice: {tone}
Length: {length}

Write a LinkedIn post that:
- Leads with your honest reaction — not a neutral summary
- Breaks down what this actually signals about the industry
- Gives one piece of actionable advice for engineers affected
- Is empathetic but analytical — not motivational-poster language
- Does NOT mention the current month or year
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
    elif mode == "story":
        chosen_theme = random.choice(STORY_THEMES)
        story_candidates = []
        story_meta = []
        for _ in range(candidate_count):
            st_topic, st_text = generate_story_post(theme=chosen_theme)
            st_structure = {
                "style": 22,
                "subtitle": "Moment -> Insight -> Action",
                "sections": [
                    {"id": 1, "label": "Moment", "desc": "The trigger event that changed perspective"},
                    {"id": 2, "label": "Insight", "desc": "What the moment reveals about AI discovery"},
                    {"id": 3, "label": "Action 1", "desc": "Immediate profile or workflow update"},
                    {"id": 4, "label": "Action 2", "desc": "Signal quality and clarity improvements"},
                    {"id": 5, "label": "Action 3", "desc": "Consistent content and positioning cadence"},
                ],
            }
            st_text = _finalize_post_text(st_topic, st_text, structure=st_structure, diagram_type="Modern Cards")
            story_candidates.append(st_text)
            story_meta.append((st_topic, st_structure))
        pick = _pick_best_candidate(
            story_meta[0][0], story_candidates, story_meta[0][1], "Modern Cards", recent_posts, recent_hashes=recent_hashes
        )
        topic, structure = story_meta[pick["index"]]
        post_text = story_candidates[pick["index"]]

    # ── RESOLVE TOPIC ─────────────────────────────────────────────────────────
    if mode == "topic" or not post_text:
        topic = (
            topic_mgr.get_topic(manual_topic_id)
            if manual_topic_id
            else topic_mgr.get_next_topic()
        )
        log.info("Topic selected: " + topic["name"])
        structure = topic_mgr.get_diagram_structure(topic)
        planned_diagram_type = topic_mgr.get_diagram_type_for_topic(topic)
        structure_items = structure.get("sections") or structure.get("rows") or []
        log.info(f"Structure: '{structure['subtitle']}' ({len(structure_items)} items)")
        log.info(f"Planned topic diagram type: {planned_diagram_type}")
        topic_candidates = []
        for _ in range(candidate_count):
            draft = generate_topic_post(topic, structure, planned_diagram_type)
            topic_candidates.append(_finalize_post_text(topic, draft, structure=structure, diagram_type=planned_diagram_type))
        pick = _pick_best_candidate(
            topic, topic_candidates, structure, planned_diagram_type, recent_posts, recent_hashes=recent_hashes
        )
        post_text = topic_candidates[pick["index"]]

    # ── FALLBACK TOPIC for news posts ─────────────────────────────────────────
    if not topic:
        topic = topic_mgr.get_next_topic()
        structure = topic_mgr.get_diagram_structure(topic)
        log.info("Fallback topic for diagram/history: " + topic["name"])

    post_text = _finalize_post_text(topic, post_text, structure=structure, diagram_type=topic_mgr.get_diagram_type_for_topic(topic))
    score_diagram_type = topic_mgr.get_diagram_type_for_topic(topic)
    score_structure = structure or topic_mgr.get_diagram_structure(topic)
    score_card = _score_post_candidate(topic, post_text, score_structure, score_diagram_type)
    if mode in {"topic", "story"} and score_card["score"] < 75:
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
        regen_pick = _pick_best_candidate(
            topic, regen_candidates, regen_structure, regen_diagram_type, recent_posts, recent_hashes=recent_hashes
        )
        post_text = regen_candidates[regen_pick["index"]]
        score_card = _score_post_candidate(topic, post_text, regen_structure, regen_diagram_type)

    log.info(
        f"Quality score: {score_card['score']}/100 | "
        f"words={score_card['word_count']} | hashtags={score_card['hashtag_count']}"
    )
    if score_card["issues"]:
        log.warning("Quality notes: " + " | ".join(score_card["issues"][:5]))

    write_github_output("POST_TOPIC",   topic.get("name", ""))
    write_github_output("POSTED_TOPIC", topic.get("name", ""))
    write_github_output("POST_TOPIC_ID", topic.get("id", ""))
    write_github_output("POST_QUALITY_SCORE", str(score_card["score"]))
    log.info(f"Final topic resolved: {topic['name']} (mode: {mode})")
    log.info("POST:\n" + post_text)

    # ── GENERATE DIAGRAM ──────────────────────────────────────────────────────
    fallback_diagram_type = topic_mgr.get_diagram_type_for_topic(topic)
    diagram_title, diagram_type, diagram_structure = _resolve_visual_metadata(
        topic, post_text, mode, fallback_diagram_type, structure
    )
    visual_issues = _visual_coherence_issues(topic, diagram_type, diagram_structure)
    if visual_issues:
        log.warning("Visual coherence override: " + " | ".join(visual_issues))
        diagram_type = fallback_diagram_type
        diagram_structure = topic_mgr.get_diagram_structure(topic)
    log.info(f"Visual metadata: title='{diagram_title}', type='{diagram_type}'")
    diagram_path = diagram_gen.save_svg(
        None, topic["id"], diagram_title, diagram_type, structure=diagram_structure
    )
    alignment = _diagram_alignment_score(diagram_path, diagram_structure)
    log.info(f"Diagram/Text alignment score: {alignment:.2f}")

    if alignment < 0.45 and diagram_structure:
        fallback_style = _fallback_style_for_diagram(diagram_type, diagram_structure)
        forced_structure = copy.deepcopy(diagram_structure)
        forced_structure["style"] = fallback_style
        log.warning(
            f"Low diagram/text alignment ({alignment:.2f}). Regenerating diagram with style {fallback_style}."
        )
        diagram_path = diagram_gen.save_svg(
            None, topic["id"], diagram_title, diagram_type, structure=forced_structure
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
        with open("output_post_" + topic["id"] + ".txt", "w", encoding="utf-8") as f:
            f.write(full_post_text)
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
                "quality_score": score_card["score"],
                "quality_notes": score_card["issues"],
            }, f, indent=2)
        write_github_summary(topic["name"], mode, full_post_text, dry_run=True, score_card=score_card)
        _remember_post(topic, full_post_text)
        topic_mgr.save_run_history({
            "timestamp":  datetime.now().isoformat(),
            "topic_id":   topic["id"],
            "topic_name": topic["name"],
            "category":   topic.get("category", ""),
            "mode":       mode,
            "status":     "dry_run",
        })
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

    result = poster.create_post_with_image(
        text=full_post_text,
        image_path=diagram_path,
        title=topic["name"],
    )
    if result.get("success"):
        log.info("Posted! ID: " + str(result.get("post_id")))
        write_github_output("POSTED_TITLE", topic.get("name", ""))
        write_github_output("POSTED_DATE",  datetime.now().strftime("%Y-%m-%d"))
        write_github_output("POSTED_URL",   result.get("post_url", ""))
        write_github_summary(topic["name"], mode, full_post_text, dry_run=False, score_card=score_card)
        _remember_post(topic, full_post_text)
        topic_mgr.save_run_history({
            "timestamp":  datetime.now().isoformat(),
            "topic_id":   topic["id"],
            "topic_name": topic["name"],
            "category":   topic.get("category", ""),
            "mode":       mode,
            "status":     "success",
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
                        help="Force post mode: auto, topic, story, ai_news, layoff_news, tools_news, tech_news")
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
