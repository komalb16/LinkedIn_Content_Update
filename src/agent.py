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
    "Start with a highly controversial technical opinion that triggers debate.",
    "Start with the biggest lie engineers are told about this topic.",
    "Start with: 'Unpopular opinion: [bold claim]'",
    "Start with a brutal, hard truth about the tech industry.",
    "Start with a sharp contrast: 'Most people think X. The truth is Y.'",
    "Start with a counterintuitive insight that makes people angry or intrigued.",
    "Start with: 'Stop doing [common practice]. Here is why.'",
    "Start with a shocking or surprising metric/statistic that defies logic.",
    "Start with a relatable frustration that most engineers have experienced.",
    "Start with an observation from a real production incident or code review.",
    "Start with 'Here is something nobody warned me about when I started...'",
    "Start with a surprising comparison between two unrelated things."
]

TONE_STYLES = [
    "conversational and friendly, like chatting with a colleague over coffee",
    "reflective and thoughtful, sharing hard-won wisdom",
    "slightly humorous and self-deprecating, keeping it real",
    "authoritative but approachable, like a senior mentor",
    "storytelling mode — weave the insight into a brief narrative",
]

# ── FORMAT A: STRUCTURED ──────────────────────────────────────────────────────
# ── POST SYSTEM (STAFF ENGINEER PERSONA) ─────────────────────────────────────
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

💬 What's the most overlooked system design principle in real-world systems?

#SystemDesign #Architecture #SoftwareEngineering #TechArchitecture #DistributedSystems

═══════════════ END EXAMPLE ═══════════════

WRITING PRINCIPLES:
1. PERSONA: You are Komal Batra. You speak from experience, not theory. You are authoritative and aggressive.
2. NO FLUFF: Zero "corporate speak". No "In today's ever-evolving landscape". Start with the point.
3. STRUCTURE: Use a clear 1., 2., 3. breakdown with specific emojis: 🚀 1., 🤔 2., ⚡ 3.
4. VISUALS: You MUST include at least one ASCII/Emoji diagram or comparison table inside the post content.
5. BANNED WORDS: "robust", "crucial", "delve", "landscape", "realm", "ever-evolving", "foster", "tapestry", "seamless", "synergy", "paradigm", "unprecedented", "game-changer", "leverage", "navigating", "holistic", "buckle up", "magic".
6. PERSPECTIVE: Third-person perspective only. No "I", "me", "my", "we", "you", "your".
7. LENGTH: 280-380 words. Frequent line breaks (1-3 sentences max per paragraph).
"""

# ── NEWS SYSTEM ───────────────────────────────────────────────────────────────
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

💬 [Engagement question about the news]?

#TechNews #Architecture #SoftwareEngineering #TechTrends

═══════════════ END EXAMPLE ═══════════════

WRITING PRINCIPLES:
- ALWAYS use ``` fenced blocks for tables, comparisons, and flow diagrams.
- ALWAYS use 🟦🟩🟨🟥 in flow diagrams with │ and ▼ connectors.
- Use 🚀 1., 🤔 2., ⚡ 3. headers.
- STRICT LENGTH: 280-380 words max.
- Be strongly opinionated — pick a side and defend it.
- Third-person only. No "I", "me", "my", "we", "you", "your".
- No banned words (same as POST_SYSTEM).
"""

def _pick_post_system():
    return POST_SYSTEM

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
            items = list(root.findall(".//item"))
            for i, item in enumerate(items):
                if i >= max_items: break
                title = item.findtext("title", "").strip()
                desc = re.sub(r'<[^>]+>', '', item.findtext("description", ""))[:300]
                if title: articles.append({"title": title, "description": desc, "topic_id": "news"})
            if len(articles) >= max_items: break
        except: continue
    return articles

def generate_news_post(news_type="ai"):
    articles = fetch_rss_news(news_type)
    if not articles: return None
    # Pick top 3 for context
    news_text = ""
    for i, a in enumerate(articles):
        if i >= 3: break
        news_text += f"- {a['title']}\n"
    
    hook_style = random.choice(HOOK_STYLES)
    prompt = f"{NEWS_SYSTEM}\n\nTOPIC: {articles[0]['title']}\nSUMMARY: {articles[0]['description']}\nHOOK STYLE: {hook_style}\n\nGenerate the viral post:"
    return call_ai(prompt, NEWS_SYSTEM)

def generate_topic_post(topic):
    log.info(f"Generating post for: {topic['name']}")
    hook_style = random.choice(HOOK_STYLES)
    prompt = f"""Write a LinkedIn post about: {topic['prompt']}
Angle: {topic.get('angle', 'practical engineering insights')}
Hook style: {hook_style}

Follow the MANDATORY STYLE EXAMPLE exactly.
Requirements:
- Third-person perspective only (No "I", "me", "my", "we", "you", "your").
- Include a technical ASCII diagram or comparison table in ``` blocks.
- Include a 🟦🟩🟨🟥 flow diagram.
- 280-380 words.
- No fluff. Focus on depth.
"""
    return call_ai(prompt, _pick_post_system())

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