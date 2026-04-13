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
from datetime import datetime, timedelta

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from topic_manager import TopicManager
from diagram_generator import DiagramGenerator
from diagram_rotation import DiagramRotation
from logger import get_logger
import notifier

log = get_logger("agent")
POST_MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".post_memory.json")
ENGAGEMENT_TRACKER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".engagement_tracker.json")
DIAGRAM_ROTATION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".diagram_rotation.json")

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
    {
        "id": "name-search-reputation-check",
        "name": "AI Name Search Reality Check",
        "prompt": "A personal moment: using an AI assistant for a simple recommendation, then searching your own name and realizing how public signals shape professional discovery.",
        "angle": "Tell it as a real story: one relatable trigger moment, one uncomfortable realization, then 3 specific profile/content actions.",
        "diagram_type": "Modern Cards",
        "diagram_subject": "Trigger moment -> self-search -> signal gaps -> profile fixes -> outcome",
    },
]

STORY_SYSTEM = """\
You are Komal Batra writing a personal story post for LinkedIn.

BANNED OPENERS — never use these:
- "I firmly believe", "I believe that", "In today's world"
- "Our online presence", "It's important", "As engineers"
- Any sentence starting with "I" followed by a belief statement

REQUIRED STRUCTURE:
1. Open with ONE specific moment — a scene, a number, a thing you clicked or read.
   Not a belief. A moment. Example: "I searched my own name in ChatGPT last week."
2. What you found (or didn't find) — be specific and a little uncomfortable.
3. Exactly 3 numbered actions (1️⃣ 2️⃣ 3️⃣) — concrete, specific, doable today.
4. One honest reflection — what this changed for you.
5. 💬 + genuine question + 4 to 7 hashtags.

FORMAT RULES:
- Each numbered action must be a COMPLETE sentence on its own line.
- Never truncate a thought mid-sentence.
- No fabricated metrics or salaries.
- Include one ``` fenced visual block with 3 to 5 lines showing the 3 actions.
- Do NOT mention the current month or year.
- 180 to 250 words total.
"""


# ─── HASHTAG OPTIMIZATION ─────────────────────────────────────────────────────

def optimize_hashtags_for_reach(post_text, post_type="topic"):
    """Replace generic hashtags with trending ones for better reach."""
    existing_tags = re.findall(r"(?<!\w)#\w+", post_text)
    
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
        if trending:
            new_tag = random.choice(trending)
            updatedText = updatedText.replace(old_tag, new_tag, 1)
    
    # Ensure 5-7 total hashtags (sweet spot for LinkedIn)
    final_tags = re.findall(r"(?<!\w)#\w+", updatedText)
    if len(final_tags) < 5 and trending:
        # Add missing tags
        for _ in range(5 - len(final_tags)):
            if trending:
                updatedText += f" {random.choice(trending)}"
    
    return updatedText


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

def _extract_story_sections(post_text, theme):
    """
    Extract actual numbered takeaways from a generated story post
    so the diagram labels match what was written, not generic placeholders.
    Falls back to theme-based sections if extraction fails.
    """
    lines = (post_text or "").splitlines()
    sections = []

    # Try to find numbered items (1️⃣ 2️⃣ or 1. 2. patterns)
    for line in lines:
        stripped = line.strip()
        # Match emoji numbers or plain numbers
        m = re.match(
            r"^(?:[1-9]\uFE0F\u20E3|[1-9][\.\)])\s+(.+)$",
            stripped
        )
        if m:
            label = m.group(1).strip()
            # Clean up — remove trailing punctuation, truncate
            label = re.sub(r"\s*[—:]\s*.*$", "", label).strip(" .")
            label = label[:40]
            if label and len(label) > 3:
                sections.append({
                    "id": len(sections) + 1,
                    "label": label,
                    "desc": "",
                })
        if len(sections) >= 5:
            break

    # If we found 3+ real sections, use them
    if len(sections) >= 3:
        return sections

    # Fallback: build from theme name + generic action labels
    theme_name = theme.get("name", "Key Insight")
    return [
        {"id": 1, "label": "The Moment", "desc": "What triggered this realization"},
        {"id": 2, "label": "The Insight", "desc": "What changed after this"},
        {"id": 3, "label": "Action 1", "desc": "First practical step"},
        {"id": 4, "label": "Action 2", "desc": "Second practical step"},
        {"id": 5, "label": "Action 3", "desc": "Third practical step"},
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
        "diagram_type": theme.get("diagram_type", "Modern Cards"),
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
            "diagram_type": "Modern Cards",
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

CRITICAL FORMATTING RULE: If using numbered sections (1️⃣ 2️⃣ etc), every section MUST be a complete sentence. Never end a line mid-thought with "—" followed by truncated text. Write the full description on the same line.

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


def _normalize_hashtags(text):
    cleaned = text or ""
    cleaned = cleaned.replace("hashtag#", "#")
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


def _finalize_post_text(topic, post_text, structure=None, diagram_type=""):
    finalized = _cleanup_generated_post(post_text or "")
    finalized = _normalize_hashtags(finalized).strip()
    if not finalized:
        return finalized
    finalized = _strip_work_incident_hook(finalized, topic.get("name", ""))
    finalized = _reduce_repetitive_copy(finalized)
    finalized = _remove_raw_flow_only_lines(finalized)
    finalized = _upgrade_weak_poll_options(finalized, structure=structure, diagram_type=diagram_type)
    finalized = _align_poll_with_structure(finalized, structure=structure, diagram_type=diagram_type)
    finalized = _enforce_numbered_poll_options(finalized)
    finalized = _tighten_poll_options(finalized)
    finalized = _normalize_hashtags(finalized)
    # Format post structure for better readability (NEW)
    finalized = _format_post_structure(finalized)
    # NEW: Optimize hashtags for better reach
    finalized = optimize_hashtags_for_reach(finalized, post_type=topic.get("category", "topic"))
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
        "Decision Tree": 9,
        "Comparison Table": 22,
        "Flow Chart": 0,
        "Lane Map": 0,
        "Signal vs Noise": 17,
        "7 Layers": 10,
        "Ecosystem Breakdown": 20,
        "Observability Map": 20,
        "Winding Roadmap": 15,
        "Architecture Diagram": 7,
        "Architecture": 7,
        "Modern Cards": 22,
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
    trending_prob  = _env_float("TREND_MODE_PROB",      0.20)  # NEW: trending topics
    ai_news_prob   = _env_float("AI_NEWS_MODE_PROB",    0.10)
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
    diagram_rotator = DiagramRotation()  # Initialize rotation system for diagram variety
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
                        draft = generate_topic_post(topic, structure, planned_diagram_type)
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
            draft = generate_topic_post(topic, structure, planned_diagram_type)
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

    write_github_output("POST_TOPIC",   topic.get("name", ""))
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
    
    # ── SELECT DIAGRAM STYLE USING SMART ROTATION ──────────────────────────────
    # NEW: Use smart rotation to cycle through all 23 available diagram styles
    selected_style = _select_smart_diagram_style(topic.get("id", ""))
    log.info(f"Selected diagram style {selected_style} from {len(ALL_DIAGRAM_STYLES)} available styles for visual variety")

    # Ensure diagram_structure is a dict and set the selected style
    if not isinstance(diagram_structure, dict):
        diagram_structure = {}
    diagram_structure_with_style = copy.deepcopy(diagram_structure)
    # Force the rotation style — this overrides diagram_generator's own style picking
    diagram_structure_with_style["style"] = selected_style

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
        None, topic["id"], diagram_title, diagram_type, structure=diagram_structure_with_style
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
