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

# Branding from environment
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

HOOK_STYLES = [
    "Start with a surprising personal observation or anecdote about this topic.",
    "Start with a provocative question that makes people stop scrolling.",
    "Start with a counterintuitive fact or statistic that challenges assumptions.",
    "Start with a relatable frustration that most engineers have experienced.",
    "Start with a bold, slightly controversial opinion.",
    "Start with a short anecdote: 'Last week I was debugging X and realized...'",
    "Start with a 'hot take' that goes against popular advice.",
    "Start with an observation from a real production incident or code review.",
    "Start with a rhetorical question like 'Why do we keep doing X when Y works better?'",
    "Start with 'Here is something nobody warned me about when I started...'",
    "Start with a brief story about a mistake or lesson learned.",
    "Start with a surprising comparison between two unrelated things.",
    "Start with a highly controversial technical opinion that triggers debate.",
    "Start with the biggest lie engineers are told about this topic.",
    "Start with a sharp contrast: 'Most people think X. The truth is Y.'",
    "Start with a shocking or surprising metric/statistic that defies logic.",
]

TONE_STYLES = [
    "conversational and friendly, like chatting with a colleague over coffee",
    "reflective and thoughtful, sharing hard-won wisdom",
    "slightly humorous and self-deprecating, keeping it real",
    "authoritative but approachable, like a senior mentor",
    "storytelling mode — weave the insight into a brief narrative",
]

# ── FORMAT A: STRUCTURED ──────────────────────────────────────────────────────
POST_SYSTEM_STRUCTURED = """You are a highly opinionated Staff Engineer and tech leader.
You write viral, scroll-stopping LinkedIn posts with rich formatting.

OUTPUT FORMAT:
Return a JSON object containing:
{
  "post": "The full post text with rich formatting (emojis, lists, etc.)",
  "diagram_query": "A search query to find a relevant High Quality diagram online (e.g. 'ByteByteGo system design for X')",
  "hook_variation": "A creative alternative hook for this same post"
}

HUMAN TOUCH & STRUCTURE BLEND:
- Follow the EXAMPLE structure — but add personal anecdotes/first-person views.
- Mix short punchy sentences with longer descriptive ones.
- Length: 250-350 words.

🚨 3 things nobody tells you about System Design

[Brief Personal Anecdote/Observation - 2-3 sentences max]

🚀 1. Scalability isn't about traffic.
[Insight]

🤔 2. The CAP Theorem isn't a choice.
[Insight]

⚡ 3. Caching & load balancing decide performance.
[Insight]

💬 What's the most overlooked system design principle?
#SystemDesign #Architecture #SoftwareEngineering
═══════════════ END EXAMPLE ═══════════════

BANNED: "robust", "crucial", "delve", "landscape", "realm", "ever-evolving", "foster", "tapestry", "seamless", "synergy", "paradigm", "unprecedented", "unpack", "dive deep", "game-changer", "leverage", "interplay", "navigating", "holistic".
"""

# ── FORMAT B: CONVERSATIONAL ──────────────────────────────────────────────────
POST_SYSTEM_CONVERSATIONAL = """You are a creative LinkedIn content assistant. Generate a human-like, engaging post.

OUTPUT FORMAT:
Return a JSON object:
{
  "post": "The full conversational post text (50-200 words)",
  "diagram_query": "Search query for a ByteByteGo-style diagram (e.g. 'ByteByteGo System Design pattern')",
  "hook_variation": "An alternative hook"
}

POST STYLE CONTENT:
- Tone: conversational, reflective, humorous, or authoritative.
- Include one personal anecdote, small insight, or rhetorical question.
- Avoid generic AI-sounding phrases.
- Length: 50–200 words.

BANNED WORDS: "robust", "crucial", "delve", "landscape", "realm", "ever-evolving", "foster", "tapestry", "seamless", "synergy", "paradigm", "unprecedented", "game-changer", "leverage", "navigating", "holistic".
"""

# ── NEWS SYSTEM ───────────────────────────────────────────────────────────────
NEWS_SYSTEM = """You are an opinionated Staff Engineer reacting to tech news.

OUTPUT FORMAT:
Return a JSON object:
{
  "post": "The post text (reaction to news, opinionated, human)",
  "diagram_query": "Search query for a diagram related to this news",
  "hook_variation": "An alternative punchy headline"
}

STYLE:
- Pick the most impactful story and give a genuine, opinionated reaction.
- Structure: Either a breakdown (Option A: 250-350 words) or a hot take (Option B: 50-200 words).
- Include one practical takeaway for engineers.
"""

def _pick_post_system():
    return random.choice([POST_SYSTEM_STRUCTURED, POST_SYSTEM_CONVERSATIONAL])

# ── DIAGRAM SOURCING ─────────────────────────────────────────────────────────

# Golden Seed URLs for common technical topics (ByteByteGo style)
DIAGRAM_LIBRARY = {
    "system design": "https://assets.bytebytego.com/diagrams/0324-system-design-blueprint.png",
    "microservices": "https://assets.bytebytego.com/diagrams/0396-typical-microservice-architecture.png",
    "api gateway": "https://substackcdn.com/image/fetch/f_auto,q_auto:good,fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2Fa5d572a6-c679-43d9-affa-54cc711a4b75_2250x2504.png",
    "load balancer": "https://assets.bytebytego.com/diagrams/0324-system-design-blueprint.png",
    "caching": "https://assets.bytebytego.com/diagrams/0324-system-design-blueprint.png",
    "azure": "https://assets.bytebytego.com/diagrams/0324-system-design-blueprint.png",
    "data engineering": "https://assets.bytebytego.com/diagrams/0324-system-design-blueprint.png",
    "architecture": "https://assets.bytebytego.com/diagrams/0324-system-design-blueprint.png"
}

def find_online_diagram(query):
    """Search online or library for a high quality diagram."""
    query_lower = query.lower()
    
    # Avoid explicitly branded searches if not requested
    if "bytebytego" in query_lower:
        log.info(f"Targeting ByteByteGo diagram for: {query}")
    else:
        log.info(f"Sourcing generic online diagram for: {query}")

    for keyword, url in DIAGRAM_LIBRARY.items():
        if keyword in query_lower:
            log.info(f"Matched seed library: {keyword}")
            return url
    return None

def download_image(url, topic_id):
    """Download image to a local file."""
    try:
        ext = ".png" if ".png" in url.lower() else ".jpg"
        path = f"assets/external_diagrams/{topic_id}{ext}"
        os.makedirs("assets/external_diagrams", exist_ok=True)
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            with open(path, "wb") as f:
                f.write(resp.content)
            return path
    except Exception as e:
        log.warning(f"Failed download: {e}")
    return None

# ── CORE FUNCTIONS ────────────────────────────────────────────────────────────

def call_ai(prompt, system):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY secret not set")
    headers = {"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "max_tokens": 1024,
        "temperature": 0.92
    }
    resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()
    
    # Robust JSON extraction via regex
    try:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            json_str = match.group(0)
            return json.loads(json_str)
        return json.loads(raw)
    except Exception as e:
        log.warning(f"Failed JSON extraction/parse: {e}")
        # Clean up potential markdown artifacts if raw is used
        clean_post = re.sub(r'^```json\s*|\s*```$', '', raw, flags=re.MULTILINE).strip()
        if clean_post.startswith('{'):
             try: return json.loads(clean_post)
             except: pass
        return {"post": clean_post, "diagram_query": "technical diagram", "hook_variation": "Check this out!"}

def fetch_rss_news(category="tech", max_items=5):
    articles = []
    feeds = RSS_FEEDS.get(category, RSS_FEEDS["tech"])
    for feed_url in feeds:
        try:
            resp = requests.get(feed_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200: continue
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item")[:max_items]:
                title = item.findtext("title", "").strip()
                desc = re.sub(r'<[^>]+>', '', item.findtext("description", ""))[:300]
                if title: articles.append({"title": title, "description": desc, "topic_id": "news"})
            if len(articles) >= max_items: break
        except: continue
    return articles[:max_items]

def generate_news_post(news_type="ai"):
    articles = fetch_rss_news(news_type)
    if not articles: return None
    news_text = "\n".join([f"- {a['title']}" for a in articles[:3]])
    prompt = f"News:\n{news_text}\n\nWrite a post reacting to the best story."
    return call_ai(prompt, NEWS_SYSTEM)

def generate_topic_post(topic):
    log.info(f"Generating post for: {topic['name']}")
    hook = random.choice(HOOK_STYLES)
    tone = random.choice(TONE_STYLES)
    system = _pick_post_system()
    
    prompt = f"""Topic: {topic['name']}
Angle: {topic.get('angle', 'practical engineering insights')}
Hook: {hook}
Tone: {tone}

Generate post."""
    return call_ai(prompt, system)

def get_post_mode():
    return "tech_news" if random.random() < 0.3 else "topic"

def write_github_output(key, value):
    gho = os.environ.get("GITHUB_OUTPUT")
    if gho:
        with open(gho, "a") as f: f.write(f"{key}={value}\n")

def write_github_summary(topic_name, mode, post_text, dry_run=False):
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(f"\n### {'🧪 Dry Run' if dry_run else '✅ Published'}: {topic_name}\nMode: {mode}\n\n```text\n{post_text}\n```\n")

def run_agent(manual_topic_id=None, dry_run=False, force_news=None, manual=False):
    log.info("Agent started (Komal Batra)")
    topic_mgr = TopicManager()
    diagram_gen = DiagramGenerator()
    
    # 1. Determine Mode & Generate
    mode = force_news or get_post_mode()
    data = None
    topic = None

    if mode in ["ai_news", "layoff_news", "tools_news", "tech_news"]:
        data = generate_news_post(mode.replace("_news", ""))
        if not data: mode = "topic"

    if mode == "topic" or not data:
        topic = topic_mgr.get_topic(manual_topic_id) if manual_topic_id else topic_mgr.get_next_topic()
        if topic:
            data = generate_topic_post(topic)
        else:
            log.error("No topic found")
            return

    if not data:
        log.error("Generation failed completely")
        return

    post_text = data.get("post", "No post generated")
    diagram_query = data.get("diagram_query", topic["name"] if topic else "tech concept")

    # 2. Diagram Logic
    diagram_path = None
    # Only try online sourcing 20% of the time to favor original generation
    if diagram_query and random.random() < 0.20:
        online_url = find_online_diagram(diagram_query)
        if online_url:
            diagram_path = download_image(online_url, topic.get("id", "news") if topic else "news")
            if diagram_path: log.info(f"External diagram: {diagram_path}")

    if not diagram_path:
        log.info("Local SVG generation fallback")
        d_type = topic_mgr.get_diagram_type_for_topic(topic) if topic else "vertical_flow"
        diagram_path = diagram_gen.save_svg(None, topic.get("id", "news") if topic else "news", topic["name"] if topic else "Tech", d_type)

    # 3. Output
    topic_name = topic["name"] if topic else "News"
    title_line = f"📌 {topic_name}\n\n" if topic else ""
    full_text = title_line + post_text
    
    # Pre-set some outputs for the dashboard/workflow
    write_github_output("POSTED_TOPIC", topic["id"] if topic else "news")
    write_github_output("POSTED_TITLE", topic_name)
    write_github_output("POSTED_DATE", datetime.now().strftime("%Y-%m-%d"))
    
    if dry_run:
        with open("dry_run_post.txt", "w", encoding="utf-8") as f: f.write(full_text)
        write_github_summary(topic["name"] if topic else "News", mode, full_text, dry_run=True)
        log.info("DRY RUN complete")
        return

    # 4. Post
    from linkedin_poster import LinkedInPoster
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    urn = os.environ.get("LINKEDIN_PERSON_URN")
    poster = LinkedInPoster(token, urn)
    result = poster.create_post_with_image(full_text, diagram_path, topic["name"] if topic else "News")
    
    if result.get("success"):
        log.info("Success!")
        post_url = result.get("post_url", "")
        if post_url:
            write_github_output("POSTED_URL", post_url)
            
        if topic:
            topic_mgr.save_run_history({"timestamp": datetime.now().isoformat(), "topic_id": topic["id"], "mode": mode, "status": "success"})
        write_github_summary(topic_name, mode, full_text, dry_run=False)
        
        # 5. Notify
        try:
            notifier.notify_all(topic_name, full_text, is_dry_run=False)
        except Exception as e:
            log.warning(f"Notification failed: {e}")
    else:
        log.error(f"Failed: {result.get('error')}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--news", default=None)
    args = parser.parse_args()
    run_agent(manual_topic_id=args.topic, dry_run=args.dry_run, force_news=args.news)