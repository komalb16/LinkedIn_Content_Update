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
    "Start with a shocking or surprising statistic relevant to the topic.",
    "Start with a bold controversial opinion that challenges conventional wisdom.",
    "Start with a short story or personal scenario (2 sentences max) that illustrates the problem.",
    "Start with a direct question that makes the reader stop and think.",
    "Start with a counterintuitive insight that most people get wrong.",
    "Start with a 'hot take' that is provocative but defensible.",
    "Start with a numbered insight like '3 things nobody tells you about...'",
    "Start with an analogy comparing the tech concept to everyday life.",
]

POST_SYSTEM = """You are a LinkedIn content strategist for Komal Batra, a senior tech leader and AI practitioner.

STRICT RULES:
- NEVER start with "As we dive into", "In today's", "In the world of", or any month/year reference
- NEVER use generic openings — be bold, specific, provocative
- Write 150-250 words maximum
- Use emojis strategically (3-5 max, not at every line)
- Add 3-5 hashtags at the end using ONLY the # symbol like #AI #DevOps
- Do NOT add any copyright or signature
- Write in first person occasionally ("I've seen", "In my experience")
- Include ONE specific data point, tool name, or real example
- End with a punchy question to drive comments
"""

NEWS_SYSTEM = """You are a LinkedIn content strategist for Komal Batra, a senior tech leader.

STRICT RULES:
- NEVER start with "As we dive into", "In today's", "In the world of"
- Write a reaction/commentary post about the news provided
- Be opinionated — share a clear perspective on what this means for the industry
- 150-250 words maximum
- Use emojis strategically (3-5 max)
- Add 3-5 relevant hashtags using ONLY # symbol like #AI #Tech
- Do NOT add any copyright or signature
- Write in first person: "This is what I think...", "Here's my take..."
- End with a question to drive engagement
"""

DIAGRAM_SYSTEM = """You are a technical SVG diagram creator for Komal Batra.
Return ONLY raw SVG code starting with <svg and ending with </svg>.
Dark background #0D1117. Professional technical architecture diagram."""


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
        "max_tokens": 1024,
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
                # Clean HTML from description
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

    # Format news for prompt
    news_text = ""
    for i, a in enumerate(articles[:3]):
        news_text += f"\n{i+1}. {a['title']}\n   {a['description'][:200]}\n"

    log.info("Fetched " + str(len(articles)) + " news articles")

    hook = random.choice(HOOK_STYLES)
    prompt = f"""Here are the latest {news_type} tech news stories from today:
{news_text}

{hook}

Write a LinkedIn post reacting to ONE of these news stories (pick the most interesting/impactful one).
Share your expert perspective on what this means for engineers, the industry, and the future.
Be specific — mention the actual news, companies, or numbers involved.
Make it feel timely and urgent."""

    return call_ai(prompt, NEWS_SYSTEM)


def generate_topic_post(topic):
    """Generate a post about a specific technical topic."""
    log.info("Generating post: " + topic["name"])
    hook = random.choice(HOOK_STYLES)
    prompt = f"""Write a LinkedIn post about: {topic["prompt"]}
Angle: {topic.get("angle", "practical insights")}

{hook}

Make it feel like insider knowledge from someone who has actually built these systems.
Include ONE specific real tool, metric, or example.
Do NOT mention the current month or year."""
    return call_ai(prompt, POST_SYSTEM)


def generate_diagram(topic, diagram_type):
    log.info("Generating diagram: " + diagram_type)
    prompt = "Create a " + diagram_type + " SVG about: " + topic["diagram_subject"] + "\nReturn ONLY raw SVG code, nothing else."
    result = call_ai(prompt, DIAGRAM_SYSTEM)
    match = re.search(r"<svg[\s\S]*?<\/svg>", result, re.IGNORECASE)
    return match.group(0) if match else result


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
            # Multiline safe delimiter format
            f.write(f"{key}={value}\n")
    except Exception as e:
        log.warning(f"Could not write GITHUB_OUTPUT: {e}")

def write_github_summary(topic_name, mode, post_preview, dry_run=False):
    """Write job summary to GitHub Actions step summary file."""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return  # not running in GitHub Actions
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
    # Reads schedule_config.json. Exits cleanly if today is paused/skipped.
    # Sleeps until configured IST time if triggered before scheduled time.
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

    # Generate post based on mode
    if mode == "ai_news":
        post_text = generate_news_post("ai")
        if not post_text:
            mode = "topic"

    elif mode == "layoff_news":
        articles = fetch_rss_news("layoffs", 5)
        # Filter for layoff-related articles
        layoff_articles = [a for a in articles if any(w in a["title"].lower() for w in ["layoff", "laid off", "cut", "job", "workforce", "redundan", "downsize"])]
        if layoff_articles:
            news_text = "\n".join([f"- {a['title']}: {a['description'][:200]}" for a in layoff_articles[:3]])
            hook = random.choice(HOOK_STYLES)
            prompt = f"""Latest tech industry layoff news:
{news_text}

{hook}

Write a LinkedIn post sharing your perspective on these layoffs.
What does this mean for tech workers, the industry, and AI's role?
Be empathetic but also analytical. Share actionable advice.
Do NOT mention current month or year."""
            post_text = call_ai(prompt, NEWS_SYSTEM)
        if not post_text:
            mode = "topic"

    elif mode == "tools_news":
        articles = fetch_rss_news("tools", 5)
        # Filter for tool/product launches
        tool_articles = [a for a in articles if any(w in a["title"].lower() for w in ["launch", "release", "new", "introduce", "tool", "platform", "open source", "github", "api", "model"])]
        if tool_articles:
            news_text = "\n".join([f"- {a['title']}: {a['description'][:200]}" for a in tool_articles[:3]])
            hook = random.choice(HOOK_STYLES)
            prompt = f"""Latest new tech tools and launches:
{news_text}

{hook}

Write a LinkedIn post about one of these new tools/launches.
Share your expert take: Is this a game-changer? Who should care? What problem does it solve?
Include practical use cases.
Do NOT mention current month or year."""
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
        write_github_output("POST_TOPIC", topic.get("name",""))
        log.info("Topic: " + topic["name"])
        post_text = generate_topic_post(topic)

    log.info("POST:\n" + post_text)

    # Generate diagram (always use topic-based diagram)
    if not topic:
        topic = topic_mgr.get_next_topic()

    diagram_type = topic_mgr.get_diagram_type_for_topic(topic)
    svg_content = generate_diagram(topic, diagram_type)
    diagram_path = diagram_gen.save_svg(svg_content, topic["id"], topic["name"], diagram_type)
    log.info("Diagram saved: " + diagram_path)

    if dry_run:
        with open("output_post_" + topic["id"] + ".txt", "w") as f:
            f.write(post_text)
        write_github_summary(topic["name"], mode, post_text, dry_run=True)
        log.info("DRY RUN complete. Post saved.")
        return

    # Post to LinkedIn
    # Prepend topic title as visible first line on LinkedIn
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
        # Send notifications (email / WhatsApp / Telegram)
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
