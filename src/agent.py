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

log = get_logger("agent")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

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

HOOK_STYLES = [
    "Start with a highly controversial technical opinion that triggers debate.",
    "Start with the biggest lie engineers are told about this topic.",
    "Start with: 'Unpopular opinion: [bold claim]'",
    "Start with a brutal, hard truth about the tech industry.",
    "Start with a sharp contrast: 'Most people think X. The truth is Y.'",
    "Start with a counterintuitive insight that makes people angry or intrigued.",
    "Start with: 'Stop doing [common practice]. Here is why.'",
    "Start with a shocking or surprising metric/statistic that defies logic.",
]

# ── WORD LIMIT NOTE ──────────────────────────────────────────────────────────
# LinkedIn hard limit = 3000 chars ≈ 420 words.
# Target 250-320 words so there is room for the prepended topic title.
# Both POST_SYSTEM and prompts enforce this consistently.

POST_SYSTEM = """You are a highly opinionated Staff Engineer and tech leader.
You write aggressive, viral, scroll-stopping LinkedIn posts that look exactly like the EXAMPLE below.
Study the structure and reproduce it for every post.

═══════════════ EXAMPLE POST (copy this structure exactly) ═══════════════

🚨 3 things nobody tells you about System Design

Most engineers learn system design through diagrams, theory, and interview prep.
But real-world systems teach very different lessons.

Here are 3 realities that experienced engineers eventually discover:

🚀 1. Scalability isn't about traffic.
It's about growth.
A system that works perfectly today may collapse tomorrow.

```
1K users     →   Single server
100K users   →   Load balancer + replicas
10M users    →   Distributed architecture
100M users   →   Microservices + sharding
```

Designing for scalability means thinking about how the system evolves, not just how it works today.

🤔 2. The CAP Theorem isn't a choice.
It's a trade-off.

Every architecture decision forces a pick:
• Consistency — every node sees the same data at the same time
• Availability — every request gets a response
• Partition Tolerance — the system survives network splits

Distributed systems cannot guarantee all three. Every decision prioritizes what matters most.

⚡ 3. Caching & load balancing decide performance.
Often the biggest wins come from the layer before the database.

```
User Request
     │
     ▼
🟦 Load Balancer
     │
     ▼
🟩 Application Servers
     │
     ▼
🟨 Cache Layer (Redis)
     │
     ▼
🟥 Database
```

A well-designed cache can reduce latency by 90% and cut database load dramatically.
But scaling further introduces complexity:
• Database sharding → data distribution challenges
• Query routing → consistency tradeoffs
• Replication → eventual consistency risk

💡 This is why engineers struggle with system design interviews.
It's not about memorizing architectures.
It's about understanding trade-offs, constraints, and how systems evolve.

💬 What's the most overlooked system design principle in real-world systems?

#SystemDesign #DistributedSystems #Scalability #SoftwareEngineering #TechArchitecture

═══════════════ END EXAMPLE ═══════════════

RULES (non-negotiable):
- ALWAYS use ``` fenced blocks for tables, flow diagrams, and ASCII art
- ALWAYS use 🟦🟩🟨🟥 emoji squares in flow diagrams with │ and ▼ connectors
- ALWAYS use numbered sections with emoji prefix (🚀 1., 🤔 2., ⚡ 3.)
- ALWAYS end with 💬 + engagement question + blank line + 5-7 hashtags
- STRICT LENGTH: 280-380 words. No more.
- Every paragraph is 1-3 sentences max. Frequent line breaks.
- Third-person perspective only. No "I", "me", "my", "we", "you", "your"
- Never reference current month or year
- No banned words: "robust", "crucial", "delve", "landscape", "testament", "realm",
  "ever-evolving", "foster", "tapestry", "seamless", "synergy", "paradigm", "unprecedented"
- Do NOT add any copyright or signature
"""

NEWS_SYSTEM = """You are a highly opinionated Staff Engineer and tech leader.
You write aggressive, viral LinkedIn posts reacting to breaking tech news.
Study this EXAMPLE and reproduce its exact structure:

═══════════════ EXAMPLE POST ═══════════════

🚨 [Company] just [did something that changes everything].

Most engineers haven't processed what this actually means yet.

Here's the real breakdown:

🚀 1. What actually happened.
[2-3 sentences explaining the news clearly and specifically.]

```
Before           →   After
Old approach     →   New reality
Previous metric  →   New metric
```

🤔 2. Why this matters more than people think.
[2-3 punchy sentences on the deeper implication.]

The real shift:
• [Implication 1 for engineers]
• [Implication 2 for the industry]
• [Implication 3 for the future]

⚡ 3. What smart engineers should do right now.
[Concrete, specific action. One tool, one technique, one decision.]

```
🟦 Old Stack
     │
     ▼
🟩 New Capability Added
     │
     ▼
🟥 What Gets Replaced
```

💡 The bottom line: [One brutal, confident take.]
[One more punchy sentence.]

💬 [Engagement question about the news]?

#[Relevant] #[Hashtags] #[Here] #[5to7] #[Total]

═══════════════ END EXAMPLE ═══════════════

RULES (non-negotiable):
- ALWAYS use ``` fenced blocks for tables, comparisons, and flow diagrams
- ALWAYS use 🟦🟩🟨🟥 in flow diagrams with │ and ▼ connectors
- ALWAYS use numbered sections with emoji prefix
- ALWAYS end with 💬 + question + hashtags
- Be strongly opinionated — pick a side and defend it
- STRICT LENGTH: 280-380 words max
- Third-person only. No "I", "me", "my", "we", "you", "your"
- Never reference current month or year
- No banned words: "robust", "crucial", "delve", "landscape", "testament", "realm",
  "ever-evolving", "foster", "tapestry", "seamless", "synergy", "paradigm", "unprecedented"
- Do NOT add any copyright or signature
"""

# DIAGRAM_SYSTEM removed — diagrams are generated locally by DiagramGenerator.
# No LLM call is needed for diagram generation.


def call_ai(prompt, system):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY secret not set")
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
        "max_tokens": 1024,   # 250-320 words ≈ 400-500 tokens; 1024 is plenty
        "temperature": 0.85
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
    prompt = f"""Latest {news_type} tech news:
{news_text}

Hook style: {hook}

Pick the most impactful story and write a LinkedIn post reacting to it.
Follow the EXAMPLE structure from your system prompt exactly.
Requirements:
- Mention the actual company, product, or number from the news
- Include a ``` fenced comparison/before-after table using → arrows
- Include a ``` fenced flow diagram using 🟦🟩🟨🟥 with │ and ▼ connectors
- 3 numbered sections with emoji headers
- Strong, opinionated take — pick a side
- 280-380 words total"""

    return call_ai(prompt, NEWS_SYSTEM)


def generate_topic_post(topic):
    """Generate a post about a specific technical topic."""
    log.info("Generating post: " + topic["name"])
    hook = random.choice(HOOK_STYLES)
    prompt = f"""Write a LinkedIn post about: {topic["prompt"]}
Angle: {topic.get("angle", "practical insights")}

Hook style: {hook}

Requirements:
- Follow the EXAMPLE structure from your system prompt exactly
- Include a ``` fenced flow diagram using 🟦🟩🟨🟥 squares with │ and ▼ connectors
- Include a ``` fenced comparison table using → arrows
- Use 3 numbered sections with emoji headers (🚀 1., 🤔 2., ⚡ 3.)
- ONE specific real tool, metric, or example (e.g. "Redis cuts latency by 90%")
- Do NOT mention the current month or year
- 280-380 words total"""
    return call_ai(prompt, POST_SYSTEM)


def get_post_mode():
    """Randomly decide what type of post to generate for variety."""
    # 40% news posts, 60% technical topic posts
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
    """Write key=value to GITHUB_OUTPUT for use in subsequent workflow steps."""
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
        with open(summary_file, "a") as f:
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
        raise  # clean skip — propagate so GH Actions marks as success
    except Exception as e:
        log.warning(f"schedule_checker error (non-fatal, continuing): {e}")

    topic_mgr = TopicManager()
    diagram_gen = DiagramGenerator()

    if not dry_run:
        from linkedin_poster import LinkedInPoster
        poster = LinkedInPoster(
            access_token=os.environ.get("LINKEDIN_ACCESS_TOKEN"),
            person_urn=os.environ.get("LINKEDIN_PERSON_URN"),
        )

    post_text = None
    topic = None

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
            prompt = f"""Latest tech industry layoff news:
{news_text}

{hook}

Write an analytical LinkedIn post breaking down these layoffs.
What does this mean for tech workers, the industry, and AI's role?
Be empathetic but also analytical. Share actionable advice.
Do NOT mention current month or year.
STRICT: 250-320 words total."""
            post_text = call_ai(prompt, NEWS_SYSTEM)
        if not post_text:
            mode = "topic"

    elif mode == "tools_news":
        articles = fetch_rss_news("tools", 5)
        tool_articles = [a for a in articles if any(
            w in a["title"].lower()
            for w in ["launch", "release", "new", "introduce", "tool", "platform", "open source", "github", "api", "model"]
        )]
        if tool_articles:
            news_text = "\n".join([f"- {a['title']}: {a['description'][:200]}" for a in tool_articles[:3]])
            hook = random.choice(HOOK_STYLES)
            prompt = f"""Latest new tech tools and launches:
{news_text}

{hook}

Write a LinkedIn post about one of these new tools/launches.
Provide an expert breakdown: Is this a game-changer? Who should care? What problem does it solve?
Include practical use cases.
Do NOT mention current month or year.
STRICT: 250-320 words total."""
            post_text = call_ai(prompt, NEWS_SYSTEM)
        if not post_text:
            mode = "topic"

    elif mode == "tech_news":
        post_text = generate_news_post("tech")
        if not post_text:
            mode = "topic"

    if mode == "topic" or not post_text:
        topic = topic_mgr.get_topic(manual_topic_id) if manual_topic_id else topic_mgr.get_next_topic()

    if topic:
        write_github_output("POST_TOPIC", topic.get("name", ""))
        log.info("Topic: " + topic["name"])
        post_text = generate_topic_post(topic)

    log.info("POST:\n" + post_text)

    # ── GENERATE DIAGRAM (local — no LLM call needed) ─────────────────────────
    if not topic:
        topic = topic_mgr.get_next_topic()

    diagram_type = topic_mgr.get_diagram_type_for_topic(topic)
    diagram_path = diagram_gen.save_svg(None, topic["id"], topic["name"], diagram_type)
    log.info("Diagram saved: " + diagram_path)

    if dry_run:
        with open("output_post_" + topic["id"] + ".txt", "w", encoding="utf-8") as f:
            f.write(post_text)
        write_github_summary(topic["name"], mode, post_text, dry_run=True)
        log.info("DRY RUN complete. Post saved.")
        return

    # ── POST TO LINKEDIN ───────────────────────────────────────────────────────
    # Always write POST_TOPIC before posting (covers news modes where topic resolved late)
    write_github_output("POST_TOPIC", topic.get("name", mode))

    # Prepend topic title as visible first line — build full text BEFORE truncation
    # so linkedin_poster._truncate_text() accounts for the title too
    title_line = f"📌 {topic['name']}\n\n"
    full_post_text = title_line + post_text if not post_text.strip().startswith("📌") else post_text

    result = poster.create_post_with_image(
        text=full_post_text,
        image_path=diagram_path,
        title=topic["name"],
    )
    if result.get("success"):
        log.info("Posted! ID: " + str(result.get("post_id")))
        write_github_summary(topic["name"], mode, full_post_text, dry_run=False)
        topic_mgr.save_run_history({
            "timestamp": datetime.now().isoformat(),
            "topic_id": topic["id"],
            "mode": mode,
            "status": "success"
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
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--manual", action="store_true", help="Manual trigger: skip schedule sleep, run immediately")
    parser.add_argument("--news", type=str, default=None, help="Force news mode: ai_news, layoff_news, tools_news, tech_news")
    parser.add_argument("--list-topics", action="store_true")
    args = parser.parse_args()
    if args.list_topics:
        TopicManager().list_topics()
        sys.exit(0)
    run_agent(manual_topic_id=args.topic, dry_run=args.dry_run, force_news=args.news, manual=args.manual)