"""
trend_discovery.py — Fetch trending engineering topics from free public APIs.
Sources:
  - Hacker News (no auth)
  - Reddit (no auth)
  - Dev.to (no auth)
  - Tech Newsletters via RSS (ByteByteGo, TLDR, Pragmatic Engineer, etc.)  ← NEW
  - Google Trends via pytrends (optional — graceful fallback if not installed) ← NEW
"""

import re
import time
import random
import requests
import feedparser
from logger import get_logger

log = get_logger("trends")

RELEVANT_KEYWORDS = [
    "llm", "ai", "agent", "rag", "kubernetes", "docker", "devops",
    "api", "cloud", "ml", "gpt", "model", "engineer", "system",
    "architecture", "database", "python", "microservice", "platform",
    "monitoring", "security", "vector", "embedding", "inference",
    "training", "fine-tuning", "agentic", "transformer", "cuda", "gpu",
    "pytorch", "tensorflow", "mcp", "anthropic", "openai", "mistral",
    "layoff", "severance", "workforce", "hiring", "job", "career",
    "microsoft", "google", "amazon", "meta", "nvidia", "acquisition",
    "finops", "cost optimiz", "redis", "kafka", "postgres", "clickhouse",
    "grpc", "graphql", "observability", "opentelemetry", "platform eng",
    "langchain", "langgraph", "autogen", "huggingface", "pinecone",
]

BLACKLISTED_KEYWORDS = [
    # Transport/physical (avoid railway/train confusion)
    "railway", "train", "transport", "shinkansen", "aviation", "maritime",
    "logistics", "rails", "locomotive", "track", "transit",
    # Entertainment/lifestyle
    "game", "gaming", "esports", "sports", "athlete", "nba", "nfl",
    "casino", "betting", "gambling", "travel", "tourism", "food",
    "fitness", "lifestyle", "marketing", "ads", "advertising",
    # Finance/crypto
    "crypto", "bitcoin", "nft", "blockchain", "metaverse", "web3",
    "stock", "forex", "trading", "investment",
    # Politics
    "politics", "election", "government", "senate", "congress",
    # Frontend/CSS — off-brand for Staff Engineer persona
    "tailwind", "css framework", "stylesheet", "ui component",
    "design system", "frontend framework", "react component",
    "vue component", "angular", "svelte",
    # Privacy/VPN/browser — too consumer-focused
    "vpn", "mozilla", "firefox", "chrome extension", "browser privacy",
    "privacy tool", "ad blocker", "antivirus", "password manager",
    # Off-brand news
    "elon musk", "twitter", "x.com", "social media algorithm",
    "tiktok", "instagram", "facebook",
      # Promotional/course content
    "last call", "enrollment", "cohort", "sign up", "register now",
    "limited seats", "join now", "early bird", "discount",
    "course", "bootcamp", "certification",
    # Interview/podcast (not practical engineering)
    "with anders", "interview with", "podcast", "episode",
    "talking with", "conversation with", "chat with",
    # Opinion/drama (off-brand)
    "hostile to devs", "turned hostile", "drama", "controversy",
    "layoff", "severance", "fired",
]
ENGINEERING_SUBREDDITS = [
    "MachineLearning", "LocalLLaMA", "devops",
    "kubernetes", "programming", "softwarearchitecture",
    "mlops", "ExperiencedDevs",
]

# Newsletter RSS feeds — highest editorial signal
# Score = how much to weight this source vs HN/Reddit engagement scores
NEWSLETTER_FEEDS = [
    ("Pragmatic Engineer",     "https://newsletter.pragmaticengineer.com/feed",         600),
    ("ByteByteGo",             "https://blog.bytebytego.com/feed",                      580),
    ("TLDR AI",                "https://tldr.tech/ai/rss",                              520),
    ("Eugene Yan",             "https://eugeneyan.com/rss/",                            510),
    ("Architecture Notes",     "https://architecturenotes.co/rss",                     500),
    ("TLDR Tech",              "https://tldr.tech/tech/rss",                            490),
    ("The Batch deeplearning", "https://www.deeplearning.ai/the-batch/feed/",           480),
    ("MLOps Community",        "https://mlops.community/feed/",                        460),
    ("Simon Willison",         "https://simonwillison.net/atom/everything/",            440),
]

# Google Trends seed keywords — used to discover related rising queries
GOOGLE_TRENDS_SEEDS = [
    "LLM architecture",
    "AI agents production",
    "RAG system design",
    "Kubernetes",
    "platform engineering",
    "MLOps",
]


def _is_relevant(title):
    """Check if a title is relevant to engineering/AI audience and not blacklisted."""
    lowered = (title or "").lower()
    if any(bl in lowered for bl in BLACKLISTED_KEYWORDS):
        return False
    return any(kw in lowered for kw in RELEVANT_KEYWORDS)


def _clean_html(text):
    """Strip HTML tags from text."""
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _title_similarity(a, b):
    """Simple word-overlap similarity between two titles."""
    stopwords = {"the", "a", "an", "is", "are", "for", "to", "of", "in", "and", "how", "why"}
    a_words = set(re.split(r"\W+", a.lower())) - stopwords
    b_words = set(re.split(r"\W+", b.lower())) - stopwords
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / len(a_words | b_words)


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 1 — HACKER NEWS (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_hn_trending(max_items=10):
    """Fetch top Hacker News stories filtered to engineering topics."""
    try:
        resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=10
        )
        resp.raise_for_status()
        story_ids = resp.json()[:40]
        stories = []
        for sid in story_ids:
            try:
                s = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                    timeout=5
                ).json()
                if not s or s.get("type") != "story":
                    continue
                title = s.get("title", "")
                if _is_relevant(title) and s.get("score", 0) > 50:
                    stories.append({
                        "title":    title,
                        "score":    s.get("score", 0),
                        "url":      s.get("url", ""),
                        "source":   "hackernews",
                        "comments": s.get("descendants", 0),
                    })
            except Exception:
                continue
            if len(stories) >= max_items:
                break
        log.info(f"HN trending: {len(stories)} relevant stories")
        return stories
    except Exception as e:
        log.warning(f"HN fetch failed: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 2 — REDDIT (unchanged + 2 new subreddits)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_reddit_trending(max_items=10):
    """Fetch top posts from engineering subreddits."""
    stories = []
    headers = {"User-Agent": "LinkedInBot/1.0 (by komalb16)"}
    for sub in ENGINEERING_SUBREDDITS:
        try:
            resp = requests.get(
                f"https://www.reddit.com/r/{sub}/hot.json?limit=5",
                headers=headers,
                timeout=10
            )
            if resp.status_code != 200:
                continue
            posts = resp.json().get("data", {}).get("children", [])
            for post in posts:
                d = post.get("data", {})
                title = d.get("title", "")
                score = d.get("score", 0)
                if score > 100 and _is_relevant(title):
                    stories.append({
                        "title":     title,
                        "score":     score,
                        "subreddit": sub,
                        "source":    "reddit",
                        "url":       f"https://reddit.com{d.get('permalink', '')}",
                    })
            time.sleep(0.3)
        except Exception as e:
            log.warning(f"Reddit fetch failed for r/{sub}: {e}")
            continue
    stories.sort(key=lambda x: x["score"], reverse=True)
    log.info(f"Reddit trending: {len(stories)} relevant stories")
    return stories[:max_items]


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 3 — DEV.TO (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_devto_trending(max_items=8):
    """Fetch trending engineering posts from Dev.to."""
    try:
        resp = requests.get(
            "https://dev.to/api/articles?top=7&per_page=20",
            timeout=10
        )
        resp.raise_for_status()
        articles = resp.json()
        RELEVANT_TAGS = {
            "ai", "machinelearning", "devops", "cloud", "kubernetes",
            "docker", "programming", "webdev", "architecture", "python",
            "llm", "opensource", "security",
        }
        relevant = []
        for a in articles:
            tags = {t.lower() for t in a.get("tag_list", [])}
            if RELEVANT_TAGS & tags:
                relevant.append({
                    "title":  a["title"],
                    "score":  a.get("positive_reactions_count", 0),
                    "tags":   list(tags),
                    "source": "devto",
                    "url":    a.get("url", ""),
                })
        relevant.sort(key=lambda x: x["score"], reverse=True)
        log.info(f"Dev.to trending: {len(relevant)} relevant articles")
        return relevant[:max_items]
    except Exception as e:
        log.warning(f"Dev.to fetch failed: {e}")
        return []

QUALITY_BLACKLIST = [
    "last call", "enrollment", "cohort", "sign up now", "register",
    "limited seats", "early bird", "join now", "discount", "% off",
    "interview with", "podcast ep", "episode ", " ep ", "ep2", "ep3", "ep4", "ep5",
"ep6", "ep7", "ep8", "ep9", "ep1", "ep0",
    "talking with", "conversation with",
    "the pulse:", "weekly update", "this week in",
    "advice for new", "notes to myself", "tips for new",
"how to get a job", "interview tips", "salary negotiation",
]

import re as _re

def _is_quality_content(title):
    """Rejects promos, podcasts, newsletter digests."""
    lowered = (title or "").lower()
    # Reject episode patterns like EP215, Ep12, ep 3
    if _re.search(r'\bep\s*\d+\b', lowered):
        return False
    return not any(q in lowered for q in QUALITY_BLACKLIST)

# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 4 — TECH NEWSLETTERS via RSS (NEW)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_newsletter_trending(max_items=12):
    """
    Fetch recent articles from top tech newsletters via RSS.
    These have strong editorial curation — highest signal source.
    Requires: pip install feedparser
    """
    results = []
    seen_titles = []

    for name, feed_url, base_score in NEWSLETTER_FEEDS:
        try:
            feed    = feedparser.parse(feed_url)
            entries = feed.entries[:5]

            for entry in entries:
                title   = getattr(entry, "title",   "").strip()
                summary = _clean_html(getattr(entry, "summary", ""))[:200]
                link    = getattr(entry, "link",    "")

                if not title or len(title) < 10:
                    continue
                if not _is_relevant(title + " " + summary):
                    continue
                if not _is_quality_content(title):
                    continue

                # Deduplicate
                is_dup = any(
                    _title_similarity(title.lower(), seen) > 0.55
                    for seen in seen_titles
                )
                if is_dup:
                    continue
                seen_titles.append(title.lower())

                results.append({
                    "title":   title,
                    "score":   base_score,
                    "source":  name,
                    "url":     link,
                    "summary": summary,
                })

        except Exception as e:
            log.debug(f"Newsletter '{name}' RSS failed: {e}")
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    log.info(f"Newsletters: {len(results)} relevant articles")
    return results[:max_items]


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 5 — GOOGLE TRENDS (NEW, optional)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_google_trends(max_items=6):
    """
    Fetch rising search queries from Google Trends.
    Requires: pip install pytrends
    Falls back gracefully if not installed — no error thrown.
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        log.info("pytrends not installed — skipping Google Trends (pip install pytrends to enable)")
        return []

    results = []
    seen    = set()

    try:
        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        seeds    = random.sample(GOOGLE_TRENDS_SEEDS, min(3, len(GOOGLE_TRENDS_SEEDS)))

        for seed in seeds:
            try:
                pytrends.build_payload(
                    [seed],
                    cat=13,           # Technology category
                    timeframe="now 7-d",
                    geo="US",
                )
                related = pytrends.related_queries()
                rising  = related.get(seed, {}).get("rising")

                if rising is not None and not rising.empty:
                    for _, row in rising.head(3).iterrows():
                        query = str(row.get("query", "")).strip()
                        value = int(row.get("value", 0))

                        if not query or len(query) < 5:
                            continue
                        if not _is_relevant(query):
                            continue

                        slug = re.sub(r"[^a-z0-9]+", "-", query.lower())
                        if slug in seen:
                            continue
                        seen.add(slug)

                        results.append({
                            "title":   query.title(),
                            "score":   min(60, int(value / 80)) + 25,
                            "source":  "google_trends",
                            "url":     f"https://trends.google.com/trends/explore?q={query}&cat=13",
                            "summary": f"Rising Google search in tech (breakout index: {value})",
                        })

                time.sleep(1.5)

            except Exception as e:
                log.debug(f"Google Trends seed '{seed}' failed: {e}")
                continue

    except Exception as e:
        log.warning(f"Google Trends overall failed: {e}")

    log.info(f"Google Trends: {len(results)} topics found")
    return results[:max_items]


# ══════════════════════════════════════════════════════════════════════════════
#  AGGREGATOR — same dedup logic as original, now with 5 sources
# ══════════════════════════════════════════════════════════════════════════════

def discover_trending_topics(max_topics=12):
    """
    Combine all signals into a ranked, deduplicated topic list.
    Returns list of dicts ready to feed into trend_to_topic.py.

    Source score ranges (higher wins ties):
      Pragmatic Engineer: 55 | ByteByteGo: 50 | TLDR AI: 45
      HN: variable (actual upvotes) | Reddit: variable | Dev.to: variable
      Google Trends: 25-85
    """
    all_signals = []

    # Newsletters first — highest editorial signal, best quality
    all_signals.extend(fetch_newsletter_trending(max_items=10))

    # Original sources
    all_signals.extend(fetch_hn_trending(max_items=8))
    all_signals.extend(fetch_reddit_trending(max_items=6))
    all_signals.extend(fetch_devto_trending(max_items=5))

    # Google Trends — optional, only fires if pytrends installed
    all_signals.extend(fetch_google_trends(max_items=5))

    # Sort by score descending
    all_signals.sort(key=lambda x: x.get("score", 0), reverse=True)

    # Deduplicate by title similarity — identical threshold to original (0.55)
    seen_titles = []
    deduped     = []
    for item in all_signals:
        title_lower  = item["title"].lower()
        is_duplicate = any(
            _title_similarity(title_lower, seen) > 0.55
            for seen in seen_titles
        )
        if not is_duplicate:
            seen_titles.append(title_lower)
            deduped.append(item)

    log.info(
        f"Discovered {len(deduped)} unique trending topics "
        f"from {len(all_signals)} raw signals "
        f"(newsletters + HN + Reddit + Dev.to + Google Trends)"
    )

    for i, t in enumerate(deduped[:5]):
        log.info(f"  #{i+1} [{t['score']}] {t['title']} ({t['source']})")

    return deduped[:max_topics]
