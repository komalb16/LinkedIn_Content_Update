"""
trend_discovery.py — Fetch trending engineering topics from free public APIs.
Sources: Hacker News (no auth), Reddit (no auth), Dev.to (no auth)
"""

import re
import requests
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
]

BLACKLISTED_KEYWORDS = [
    "railway", "train", "transport", "shinkansen", "aviation", "maritime", 
    "logistics", "rails", "locomotive", "track", "transit",
    "game", "gaming", "esports", "sports", "athlete", "nba", "nfl", 
    "casino", "betting", "gambling", "travel", "tourism", "food",
    "fitness", "lifestyle", "marketing", "ads", "advertising",
]

ENGINEERING_SUBREDDITS = [
    "MachineLearning", "LocalLLaMA", "devops",
    "kubernetes", "programming", "softwarearchitecture",
]


def _is_relevant(title):
    """Check if a title is relevant to engineering/AI audience and not blacklisted."""
    lowered = (title or "").lower()
    # Must contain relevance, must NOT contain blacklist
    if any(bl in lowered for bl in BLACKLISTED_KEYWORDS):
        return False
    return any(kw in lowered for kw in RELEVANT_KEYWORDS)


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
                        "title": title,
                        "score": s.get("score", 0),
                        "url": s.get("url", ""),
                        "source": "hackernews",
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
                        "title": title,
                        "score": score,
                        "subreddit": sub,
                        "source": "reddit",
                        "url": f"https://reddit.com{d.get('permalink', '')}",
                    })
        except Exception as e:
            log.warning(f"Reddit fetch failed for r/{sub}: {e}")
            continue
    stories.sort(key=lambda x: x["score"], reverse=True)
    log.info(f"Reddit trending: {len(stories)} relevant stories")
    return stories[:max_items]


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
                    "title": a["title"],
                    "score": a.get("positive_reactions_count", 0),
                    "tags": list(tags),
                    "source": "devto",
                    "url": a.get("url", ""),
                })
        relevant.sort(key=lambda x: x["score"], reverse=True)
        log.info(f"Dev.to trending: {len(relevant)} relevant articles")
        return relevant[:max_items]
    except Exception as e:
        log.warning(f"Dev.to fetch failed: {e}")
        return []


def _title_similarity(a, b):
    """Simple word-overlap similarity between two titles."""
    stopwords = {"the", "a", "an", "is", "are", "for", "to", "of", "in", "and", "how", "why"}
    a_words = set(re.split(r"\W+", a.lower())) - stopwords
    b_words = set(re.split(r"\W+", b.lower())) - stopwords
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / len(a_words | b_words)


def discover_trending_topics(max_topics=12):
    """
    Combine all signals into a ranked, deduplicated topic list.
    Returns list of dicts ready to feed into trend_to_topic.py.
    """
    all_signals = []
    all_signals.extend(fetch_hn_trending(max_items=8))
    all_signals.extend(fetch_reddit_trending(max_items=6))
    all_signals.extend(fetch_devto_trending(max_items=5))

    # Sort by score descending
    all_signals.sort(key=lambda x: x.get("score", 0), reverse=True)

    # Deduplicate by title similarity
    seen_titles = []
    deduped = []
    for item in all_signals:
        title_lower = item["title"].lower()
        is_duplicate = any(
            _title_similarity(title_lower, seen) > 0.55
            for seen in seen_titles
        )
        if not is_duplicate:
            seen_titles.append(title_lower)
            deduped.append(item)

    log.info(f"Discovered {len(deduped)} unique trending topics from {len(all_signals)} raw signals")
    return deduped[:max_topics]