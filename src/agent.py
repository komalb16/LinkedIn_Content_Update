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

# ─── HOOK STYLES — varied, human-sounding openers ─────────────────────────────
HOOK_STYLES = [
    "Start with a specific number that surprises: e.g. '73% of RAG systems fail in production. Here is why.'",
    "Start with ONE short provocative sentence. Line break. Then: 'Here is what most engineers miss:'",
    "Start with a question engineers actually ask themselves at 2am debugging.",
    "Start mid-story: 'Last week a team showed me their ML pipeline. It had 6 single points of failure.'",
    "Start with a contrast: show what people think X is vs what X actually is in production.",
    "Start with the unpopular opinion — specific, defensible, slightly controversial.",
    "Start with a metric or benchmark that most engineers do not know about this topic.",
    "Start by naming a common mistake and immediately why it matters: 'Most teams do X. It is costing them Y.'",
    "Start with a short story about a production incident or a hard lesson learned.",
    "Start with a bold claim followed by 'Let me explain.' then actually explain it well.",
]

# ─── TONE VARIATIONS — changes writing voice per post ─────────────────────────
TONE_VARIATIONS = [
    "Write like a senior engineer sharing a hard production lesson — direct, slightly blunt, zero fluff.",
    "Write like someone who just saved a production system from failure — urgent, specific, battle-tested.",
    "Write like a tech lead explaining this to their team in a Slack message — clear, practical, example-driven.",
    "Write like someone who respectfully disagrees with the conventional wisdom — confident, backed by specifics.",
    "Write like an engineer who has seen this pattern fail 3 times and finally knows why — measured, honest.",
    "Write like the most knowledgeable person in the room who is also the most approachable.",
]

# ─── STRUCTURAL VARIATIONS — changes the post format ─────────────────────────
STRUCTURE_VARIATIONS = [
    "numbered list with emoji — each point is a section matching the diagram",
    "short punchy paragraphs — no numbered list, story flows naturally section to section",
    "before/after contrast — show the wrong way then the right way for each section",
    "common misconception followed by reality — one per section",
]

# ── WORD LIMIT NOTE ──────────────────────────────────────────────────────────
# LinkedIn hard limit = 3000 chars. Target 250-320 words.

POST_SYSTEM = """You are a highly experienced Staff Engineer and technical writer.
You write LinkedIn posts that feel like they were written by a real senior engineer — not by AI.

Study this EXAMPLE and reproduce its energy and structure:

═══════════════ EXAMPLE POST ═══════════════

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

#RAG #AIEngineering #LLM #GenerativeAI #SystemDesign

═══════════════ END EXAMPLE ═══════════════

RULES (non-negotiable):
- ALWAYS use ``` fenced blocks for flow diagrams and ASCII tables
- ALWAYS use 🟦🟩🟨🟥 emoji squares in flow diagrams with │ and ▼ connectors
- ALWAYS end with 💬 + engagement question + blank line + 5-7 hashtags
- STRICT LENGTH: 250-350 words. No more.
- Vary sentence length — mix short punchy lines with longer explanatory ones
- Mostly third-person but "most engineers", "production teams", "if you" is absolutely fine
- Never reference current month or year
- No banned words: "robust", "crucial", "delve", "landscape", "testament", "realm",
  "ever-evolving", "foster", "tapestry", "seamless", "synergy", "paradigm", "unprecedented",
  "game-changer", "leverage", "navigating", "holistic", "supercharge", "revolutionize"
- No corporate-speak. Write like a real engineer talking to another engineer.
- Do NOT add any copyright or signature
- When given a diagram structure, number your sections to MATCH it exactly
"""

NEWS_SYSTEM = """You are a highly experienced Staff Engineer and technical writer.
You write LinkedIn posts that feel written by a real senior engineer reacting to breaking news.

RULES:
- ALWAYS use ``` fenced blocks for comparisons and flow diagrams
- ALWAYS use 🟦🟩🟨🟥 in flow diagrams with │ and ▼ connectors
- ALWAYS end with 💬 + question + hashtags
- Be strongly opinionated — pick a side, defend it with specifics
- STRICT LENGTH: 250-350 words
- Vary sentence length — short punchy lines mixed with longer ones
- Mostly third-person but "most engineers", "if you" is fine
- Never reference current month or year
- No banned words: "robust", "crucial", "delve", "landscape", "seamless", "synergy",
  "paradigm", "unprecedented", "game-changer", "revolutionize", "supercharge"
- Write like a real engineer, not a press release
- Do NOT add any copyright or signature
"""


def call_ai(prompt, system):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY secret not set")
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1024,
        "temperature": 0.88
    }
    resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=30)
    if resp.status_code != 200:
        log.error("Groq error: " + resp.text)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def fetch_rss_news(category="tech", max_items=5):
    """Fetch latest news from RSS feeds."""
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
                title = item.findtext("title", "").strip()
                desc = item.findtext("description", "").strip()
                link = item.findtext("link", "").strip()
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


def generate_news_post(news_type="ai"):
    """Fetch latest news and generate a post about it."""
    log.info("Fetching latest " + news_type + " news...")
    articles = fetch_rss_news(news_type, max_items=5)

    if not articles:
        log.warning("No news fetched, falling back to topic post")
        return None

    news_text = ""
    for i, a in enumerate(articles[:3]):
        news_text += f"\n{i+1}. {a['title']}\n   {a['description'][:200]}\n"

    log.info("Fetched " + str(len(articles)) + " news articles")

    hook = random.choice(HOOK_STYLES)
    tone = random.choice(TONE_VARIATIONS)

    prompt = f"""Latest {news_type} tech news:
{news_text}

Hook style: {hook}
Tone: {tone}

Pick the most impactful story and write a LinkedIn post reacting to it.
Requirements:
- Mention the actual company, product, or number from the news
- Include a ``` fenced comparison/before-after table using → arrows
- Include a ``` fenced flow diagram using 🟦🟩🟨🟥 with │ and ▼ connectors
- 3 sections with emoji headers
- Strong, opinionated take — pick a side
- 250-350 words total"""

    return call_ai(prompt, NEWS_SYSTEM)


def generate_topic_post(topic, structure=None):
    """Generate a post about a specific technical topic, matched to diagram structure."""
    log.info("Generating post: " + topic["name"])
    hook = random.choice(HOOK_STYLES)
    tone = random.choice(TONE_VARIATIONS)
    fmt  = random.choice(STRUCTURE_VARIATIONS)

    if structure and structure.get("sections"):
        sections = structure["sections"]
        n = len(sections)
        section_list = "\n".join(
            f"{s['id']}. {s['label']} — {s['desc']}"
            for s in sections
        )
        structure_block = f"""
The diagram for this post has exactly {n} sections:
{section_list}

Your numbered points MUST use these exact labels in this exact order.
Each section label must match the diagram label word-for-word.
End with a poll asking which of these {n} options the reader uses or prefers."""
    else:
        structure_block = ""

    prompt = f"""Write a LinkedIn post about: {topic["prompt"]}
Angle: {topic.get("angle", "practical insights")}

Hook style: {hook}
Tone: {tone}
Format: {fmt}
{structure_block}

Requirements:
- Follow the EXAMPLE structure from your system prompt
- Include a ``` fenced flow diagram using 🟦🟩🟨🟥 squares with │ and ▼ connectors
- Include a ``` fenced comparison table using → arrows
- ONE specific real tool, metric, or example per section
- Do NOT mention the current month or year
- 250-350 words total"""

    return call_ai(prompt, POST_SYSTEM)


def get_post_mode():
    """Randomly decide what type of post to generate."""
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


def write_github_output(key, value):
    """Write key=value to GITHUB_OUTPUT."""
    gho = os.environ.get("GITHUB_OUTPUT")
    if not gho:
        return
    try:
        with open(gho, "a") as f:
            f.write(f"{key}={value}\n")
    except Exception as e:
        log.warning(f"Could not write GITHUB_OUTPUT: {e}")


def write_github_summary(topic_name, mode, post_preview, dry_run=False):
    """Write job summary to GitHub Actions step summary file."""
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


def run_agent(manual_topic_id=None, dry_run=False, force_news=None, manual=False):
    log.info("=" * 60)
    log.info("LinkedIn Agent — Komal Batra — " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("Mode: " + ("DRY RUN" if dry_run else "LIVE"))
    log.info("=" * 60)

    # ── CHECK SCHEDULE ────────────────────────────────────────────────────────
    try:
        from schedule_checker import check_and_wait
        check_and_wait(dry_run=dry_run, manual=manual)
    except SystemExit:
        raise
    except Exception as e:
        log.warning(f"schedule_checker error (non-fatal, continuing): {e}")

    topic_mgr  = TopicManager()
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

    # Determine post mode
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
            news_text = "\n".join([f"- {a['title']}: {a['description'][:200]}" for a in layoff_articles[:3]])
            hook = random.choice(HOOK_STYLES)
            tone = random.choice(TONE_VARIATIONS)
            prompt = f"""Latest tech industry layoff news:
{news_text}

Hook: {hook}
Tone: {tone}

Write an analytical LinkedIn post breaking down these layoffs.
What does this mean for tech workers, the industry, and AI's role?
Be empathetic but analytical. Share actionable advice.
Do NOT mention current month or year.
250-320 words total."""
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
            news_text = "\n".join([f"- {a['title']}: {a['description'][:200]}" for a in tool_articles[:3]])
            hook = random.choice(HOOK_STYLES)
            tone = random.choice(TONE_VARIATIONS)
            prompt = f"""Latest new tech tools and launches:
{news_text}

Hook: {hook}
Tone: {tone}

Write a LinkedIn post about one of these new tools/launches.
Expert breakdown: Is this significant? Who should care? What problem does it solve?
Include practical use cases.
Do NOT mention current month or year.
250-320 words total."""
            post_text = call_ai(prompt, NEWS_SYSTEM)
        if not post_text:
            mode = "topic"

    elif mode == "tech_news":
        post_text = generate_news_post("tech")
        if not post_text:
            mode = "topic"

    # ── RESOLVE TOPIC ─────────────────────────────────────────────────────────
    if mode == "topic" or not post_text:
        topic = topic_mgr.get_topic(manual_topic_id) if manual_topic_id else topic_mgr.get_next_topic()
        log.info("Topic selected: " + topic["name"])

        # Get diagram structure — drives both post numbering AND diagram layout
        structure = topic_mgr.get_diagram_structure(topic)
        log.info(f"Structure: '{structure['subtitle']}' ({len(structure['sections'])} sections)")

        post_text = generate_topic_post(topic, structure)

    # ── FALLBACK TOPIC for news posts ─────────────────────────────────────────
    if not topic:
        topic = topic_mgr.get_next_topic()
        structure = topic_mgr.get_diagram_structure(topic)
        log.info("Fallback topic for diagram/history: " + topic["name"])

    # ── SINGLE AUTHORITATIVE TOPIC OUTPUT ────────────────────────────────────
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
    full_post_text = title_line + post_text if not post_text.strip().startswith("📌") else post_text

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
            "status":     "success"
        })
        try:
            from notifier import notify_all
            notify_all(
                topic=topic["name"],
                post_preview=post_text,
                is_dry_run=dry_run
            )
        except Exception as e:
            log.warning("Notification error (non-fatal): " + str(e))
    else:
        log.error("Failed: " + str(result.get("error")))
        # Save history on failure too — prevents immediate re-pick of same topic
        topic_mgr.save_run_history({
            "timestamp":  datetime.now().isoformat(),
            "topic_id":   topic["id"],
            "topic_name": topic["name"],
            "mode":       mode,
            "status":     "failed"
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
    run_agent(manual_topic_id=args.topic, dry_run=args.dry_run,
              force_news=args.news, manual=args.manual)
