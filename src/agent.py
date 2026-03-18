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
- ALWAYS include a ``` fenced flow diagram using 🟦🟩🟨🟥 with │ and ▼ connectors
- ALWAYS include a ``` fenced comparison or table using → arrows
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
- Include a ``` fenced comparison or flow diagram
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
- Includes a ``` fenced comparison table using → arrows
- Includes a ``` fenced flow diagram using 🟦🟩🟨🟥 with │ and ▼ connectors
- Takes a real position — not "time will tell"
"""
    return call_ai(prompt, NEWS_SYSTEM)


def generate_topic_post(topic, structure=None):
    log.info("Generating post: " + topic["name"])

    hook   = random.choice(HOOK_STYLES)
    tone   = random.choice(TONE_VARIATIONS)
    fmt    = random.choice(FORMAT_VARIATIONS)
    length = random.choice(LENGTH_VARIATIONS)

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
    else:
        structure_block = ""

    prompt = f"""Write a LinkedIn post about: {topic["prompt"]}
Angle: {topic.get("angle", "practical, production-level insights")}

Story archetype (hook): {hook}
Voice: {tone}
Format: {fmt["instruction"]}
Length target: {length}
{structure_block}

Requirements:
- ONE real tool, metric, or named example per section — no generic descriptions
- Include a ``` fenced flow diagram using 🟦🟩🟨🟥 squares with │ and ▼ connectors
- Include a ``` fenced comparison or before/after table using → arrows
- The hook must be the very first line — no warming up, no preamble
- Never mention the current month or year
"""
    return call_ai(prompt, _build_post_system())


# ─── POST MODE ────────────────────────────────────────────────────────────────

def get_post_mode():
    rand = random.random()
    if rand < 0.15:
        return "ai_news"
    elif rand < 0.25:
        return "layoff_news"
    elif rand < 0.35:
        return "tools_news"
    elif rand < 0.40:
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


def write_github_summary(topic_name, mode, post_preview, dry_run=False):
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
            f"",
            f"### Post Preview",
            f"> {preview}",
        ]
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        log.info("GitHub step summary written")
    except Exception as e:
        log.warning(f"Could not write step summary: {e}")


# ─── MAIN AGENT ───────────────────────────────────────────────────────────────

def run_agent(manual_topic_id=None, dry_run=False, force_news=None, manual=False):
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

    if manual_topic_id:
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
        log.info(f"Structure: '{structure['subtitle']}' ({len(structure['sections'])} sections)")
        post_text = generate_topic_post(topic, structure)

    # ── FALLBACK TOPIC for news posts ─────────────────────────────────────────
    if not topic:
        topic = topic_mgr.get_next_topic()
        structure = topic_mgr.get_diagram_structure(topic)
        log.info("Fallback topic for diagram/history: " + topic["name"])

    write_github_output("POST_TOPIC",   topic.get("name", ""))
    write_github_output("POSTED_TOPIC", topic.get("name", ""))
    log.info(f"Final topic resolved: {topic['name']} (mode: {mode})")
    log.info("POST:\n" + post_text)

    # ── GENERATE DIAGRAM ──────────────────────────────────────────────────────
    diagram_type = topic_mgr.get_diagram_type_for_topic(topic)
    diagram_path = diagram_gen.save_svg(
        None, topic["id"], topic["name"], diagram_type, structure=structure
    )
    log.info("Diagram saved: " + diagram_path)

    if dry_run:
        with open("output_post_" + topic["id"] + ".txt", "w", encoding="utf-8") as f:
            f.write(post_text)
        write_github_summary(topic["name"], mode, post_text, dry_run=True)
        log.info("DRY RUN complete. Post saved.")
        return

    # ── POST TO LINKEDIN ───────────────────────────────────────────────────────
    title_line = f"📌 {topic['name']}\n\n"
    full_post_text = (
        title_line + post_text
        if not post_text.strip().startswith("📌")
        else post_text
    )

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
        write_github_summary(topic["name"], mode, full_post_text, dry_run=False)
        topic_mgr.save_run_history({
            "timestamp":  datetime.now().isoformat(),
            "topic_id":   topic["id"],
            "topic_name": topic["name"],
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
    )
