import os
import sys
import re
import json
import random
import argparse
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from topic_manager import TopicManager
from diagram_generator import DiagramGenerator
from logger import get_logger
import notifier

log = get_logger("agent")

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

METRIC_PATTERN = re.compile(r"(<\s*\d+\s*(?:ms|s|sec|%))|(\b\d+\s*%)|(\b\d+\s*(?:ms|s|sec|tokens?)\b)", re.I)

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
    return _cleanup_generated_post(call_ai(prompt, NEWS_SYSTEM))


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
- If the topic does not include a concrete metric, use qualitative language instead of numbers
- If the topic does not include named tools, keep examples generic instead of dropping in brand names
- Include exactly one fenced visual block that matches the planned diagram type
- Keep this to exactly one topic only; do not append or preview a second post
- The hook must be the very first line — no warming up, no preamble
- Never mention the current month or year
"""
    post_text = _cleanup_generated_post(call_ai(prompt, _build_post_system()))
    issues = _post_quality_issues(topic, post_text, structure, diagram_type)
    if issues:
        revision_prompt = (
            prompt
            + "\nRevision feedback:\n- "
            + "\n- ".join(issues[:5])
            + "\nRewrite the post from scratch and fix every issue above."
        )
        post_text = _cleanup_generated_post(call_ai(revision_prompt, _build_post_system()))
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

    allowed_tools = _detect_named_tools(topic_blob)
    unsupported_tools = sorted(_detect_named_tools(cleaned) - allowed_tools)
    if unsupported_tools:
        issues.append(
            "Remove unsupported named tool mentions that were not provided in the topic: "
            + ", ".join(unsupported_tools[:4])
        )

    if re.search(r"\bour production\b|\bour team\b|\bwe cut\b|\bI quickly diagnosed\b|\bjust failed\b", cleaned, re.I):
        issues.append("Do not invent a first-person incident or case study unless the topic explicitly includes one.")

    if re.search(r"\bnext post\b|\bthird post\b|\bpost 2\b|\banother post\b", cleaned, re.I):
        issues.append("Write exactly one post and remove any extra appended drafts.")

    if cleaned.count("📌") > 1:
        issues.append("Use a single title/topic marker only once.")

    hashtag_count = len(re.findall(r"(?<!\w)#\w+", cleaned))
    if hashtag_count > 8:
        issues.append("Use fewer hashtags (ideal range: 4 to 7).")

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


def _finalize_post_text(topic, post_text):
    finalized = _cleanup_generated_post(post_text or "")
    finalized = finalized.replace("hashtag#", "#").strip()
    if not finalized:
        return finalized
    return finalized


def _visual_coherence_issues(topic, diagram_type, structure=None):
    topic_blob = _topic_text_blob(topic).lower()
    issues = []
    if "observability" in topic_blob and diagram_type in {"Architecture Diagram", "Architecture"}:
        issues.append("Observability topics should not use the generic architecture diagram fallback.")
    if structure and structure.get("rows") and diagram_type in {"Architecture Diagram", "Architecture"}:
        issues.append("Structured notebook-style diagrams need a matching non-generic diagram type.")
    return issues


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
    for raw_line in (post_text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```") or line.startswith("#"):
            continue
        line = re.sub(r"^[\"'`•\-\s]+", "", line)
        line = re.sub(r"\s+", " ", line)
        if line.lower().startswith(weak_openers):
            continue
        if '"' in raw_line or "'" in raw_line:
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
            rows.append((label, [left[:22], right[:22]]))
            if len(rows) >= 4:
                break
        if len(rows) >= 4:
            break

    if not rows:
        rows = [
            ("Positioning", ["Established platform", "Emerging alternative"]),
            ("AI Approach", ["Add-on automation", "AI-native workflow"]),
            ("Best Fit", ["Enterprise breadth", "Developer speed"]),
            ("Trade-off", ["More control, more weight", "Simpler, less mature"]),
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
    if mode == "topic":
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
    rand = random.random()
    if rand < 0.05:
        return "ai_news"
    elif rand < 0.08:
        return "layoff_news"
    elif rand < 0.12:
        return "tools_news"
    elif rand < 0.15:
        return "tech_news"
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
        post_text = generate_topic_post(topic, structure, planned_diagram_type)
        post_text = _finalize_post_text(topic, post_text)

    # ── FALLBACK TOPIC for news posts ─────────────────────────────────────────
    if not topic:
        topic = topic_mgr.get_next_topic()
        structure = topic_mgr.get_diagram_structure(topic)
        log.info("Fallback topic for diagram/history: " + topic["name"])

    post_text = _finalize_post_text(topic, post_text)
    score_diagram_type = topic_mgr.get_diagram_type_for_topic(topic)
    score_structure = structure or topic_mgr.get_diagram_structure(topic)
    score_card = _score_post_candidate(topic, post_text, score_structure, score_diagram_type)
    if mode == "topic" and score_card["score"] < 75:
        log.warning(
            f"Low post quality score ({score_card['score']}/100). Regenerating once with the same topic."
        )
        regen_structure = score_structure
        regen_diagram_type = score_diagram_type
        post_text = generate_topic_post(topic, regen_structure, regen_diagram_type)
        post_text = _finalize_post_text(topic, post_text)
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
    log.info("Diagram saved: " + diagram_path)

    if dry_run:
        title_line = f"📌 {topic['name']}\n\n"
        full_post_text = (
            title_line + post_text
            if not post_text.strip().startswith("📌")
            else post_text
        )
        full_post_text = _finalize_post_text(topic, full_post_text)
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
        log.info("DRY RUN complete. Post saved.")
        return

    # ── POST TO LINKEDIN ───────────────────────────────────────────────────────
    title_line = f"📌 {topic['name']}\n\n"
    full_post_text = (
        title_line + post_text
        if not post_text.strip().startswith("📌")
        else post_text
    )
    full_post_text = _finalize_post_text(topic, full_post_text)

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
                        help="Force post mode: auto, topic, ai_news, layoff_news, tools_news, tech_news")
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
