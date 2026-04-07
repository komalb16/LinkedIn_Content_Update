#!/usr/bin/env python3
"""
trending_topics.py — Detect and integrate trending AI/Tech topics

Automatically discovers trending topics from:
- Twitter/X trending topics
- HackerNews top stories
- Reddit trending in r/MachineLearning, r/programming
- Google Trends (AI + Tech keywords)

Integrates with agent.py to post about trending topics dynamically.
"""

import os
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import deque

try:
    from logger import get_logger
    log = get_logger("trending_topics")
except ImportError:
    class _Logger:
        def info(self, m): print(f"[TRENDING] {m}")
        def warning(self, m): print(f"[TRENDING] WARN {m}")
        def error(self, m): print(f"[TRENDING] ERR {m}")
    log = _Logger()

# Trending topics cache file
TRENDING_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".trending_topics_cache.json")

# Keywords that indicate AI/Tech trending topics
AI_TECH_KEYWORDS = {
    "ai", "artificial intelligence", "machine learning", "llm", "gpt", "claude", "gemini",
    "rag", "agents", "agentic", "prompt", "guardrails", "vector", "embeddings",
    "data engineering", "mlops", "devops", "kubernetes", "docker", "aws", "azure", "gcp",
    "python", "rust", "golang", "typescript", "javascript", "react", "nextjs",
    "api", "graphql", "rest", "microservices", "architecture", "system design",
    "security", "cryptography", "zero trust", "authentication", "oauth",
    "cloud", "serverless", "lambda", "containers", "infrastructure", "terraform", "bicep",
    "monitoring", "observability", "logging", "traces", "metrics",
    "sql", "nosql", "postgres", "mongodb", "dynamodb", "redis",
    "github", "gitlab", "cicd", "github actions", "gitlab ci", "jenkins",
    "testing", "unit test", "integration test", "e2e test", "performance",
}

# Topics to avoid (too generic, not AI/tech focused)
EXCLUDE_KEYWORDS = {
    "crypto", "bitcoin", "ethereum", "nft", "metaverse",
    "finance", "stocks", "trading", "investment",
    "sports", "entertainment", "celebrity",
    "politics", "news", "world events",
}


class TrendingTopicDetector:
    """Detect and track trending AI/Tech topics."""

    def __init__(self, enable_trending: bool = False, cache_ttl_hours: int = 24):
        """
        Initialize trending topic detector.
        
        Args:
            enable_trending: Enable trending topic detection
            cache_ttl_hours: Cache time-to-live in hours (default: 24)
        """
        self.enable_trending = enable_trending
        self.cache_ttl_hours = cache_ttl_hours
        self.cache = self._load_cache()
        self.last_update = self.cache.get("last_update", 0)

    def _load_cache(self) -> Dict:
        """Load trending topics cache from disk."""
        if not os.path.exists(TRENDING_CACHE_FILE):
            return {"topics": [], "last_update": 0, "posted_topics": []}
        try:
            with open(TRENDING_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            log.warning(f"Could not load trending cache: {e}")
        return {"topics": [], "last_update": 0, "posted_topics": []}

    def _save_cache(self) -> None:
        """Save trending topics cache to disk."""
        try:
            with open(TRENDING_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            log.warning(f"Could not save trending cache: {e}")

    def is_ai_tech_topic(self, text: str) -> bool:
        """Check if topic is AI/Tech related."""
        text_lower = (text or "").lower()
        
        # Check if contains exclude keywords
        for exclude_kw in EXCLUDE_KEYWORDS:
            if exclude_kw in text_lower:
                return False
        
        # Check if contains AI/Tech keywords
        for kw in AI_TECH_KEYWORDS:
            if kw in text_lower:
                return True
        
        return False

    def get_cached_topics(self) -> List[Dict]:
        """Get cached trending topics if still valid."""
        if not self.cache.get("topics"):
            return []
        
        now = time.time()
        cache_age_hours = (now - self.last_update) / 3600
        
        if cache_age_hours < self.cache_ttl_hours:
            log.info(f"Using cached trending topics ({cache_age_hours:.1f}h old)")
            return self.cache["topics"]
        
        return []

    def discover_trending_topics(self) -> List[Dict]:
        """
        Discover trending AI/Tech topics.
        
        Returns list of {'topic': str, 'source': str, 'score': int, 'timestamp': float}
        """
        if not self.enable_trending:
            return []
        
        # Check cache first
        cached = self.get_cached_topics()
        if cached:
            return cached[:5]  # Return top 5 cached topics
        
        topics = []
        
        # Try to get trending topics from multiple sources
        try:
            topics.extend(self._get_twitter_trends())
        except Exception as e:
            log.warning(f"Twitter trends error: {e}")
        
        try:
            topics.extend(self._get_hackernews_trends())
        except Exception as e:
            log.warning(f"HackerNews trends error: {e}")
        
        try:
            topics.extend(self._get_reddit_trends())
        except Exception as e:
            log.warning(f"Reddit trends error: {e}")
        
        # Filter to AI/Tech topics
        ai_tech_topics = [t for t in topics if self.is_ai_tech_topic(t.get("topic", ""))]
        
        # Score and rank
        ai_tech_topics.sort(key=lambda t: t.get("score", 0), reverse=True)
        
        # Cache results
        if ai_tech_topics:
            self.cache["topics"] = ai_tech_topics[:10]  # Keep top 10
            self.cache["last_update"] = time.time()
            self._save_cache()
        
        return ai_tech_topics[:5]

    def _get_twitter_trends(self) -> List[Dict]:
        """Get trending topics from Twitter/X (requires API key)."""
        # This requires Twitter API v2 access token
        # For now, return empty list (user can provide their own token via env var)
        log.info("Twitter trends: Not implemented (requires API key)")
        return []

    def _get_hackernews_trends(self) -> List[Dict]:
        """Get trending topics from HackerNews top stories."""
        try:
            import requests
            
            # Get HackerNews top stories
            resp = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=5)
            if not resp.ok:
                return []
            
            top_story_ids = resp.json()[:30]  # Get top 30
            topics = []
            
            for story_id in top_story_ids[:10]:  # Process first 10
                story_resp = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=3)
                if not story_resp.ok:
                    continue
                
                story = story_resp.json()
                title = story.get("title", "")
                
                if self.is_ai_tech_topic(title):
                    topics.append({
                        "topic": title,
                        "source": "hackernews",
                        "score": story.get("score", 0),
                        "timestamp": time.time(),
                        "url": story.get("url", "")
                    })
            
            log.info(f"HackerNews trends: Found {len(topics)} AI/Tech topics")
            return topics
        except Exception as e:
            log.warning(f"HackerNews fetch error: {e}")
            return []

    def _get_reddit_trends(self) -> List[Dict]:
        """Get trending topics from Reddit (r/MachineLearning, r/programming)."""
        try:
            import requests
            
            subreddits = ["MachineLearning", "programming", "learnprogramming", "devops"]
            topics = []
            
            for subreddit in subreddits:
                try:
                    resp = requests.get(
                        f"https://www.reddit.com/r/{subreddit}/hot.json",
                        headers={"User-Agent": "LinkedIn-Content-Bot/1.0"},
                        timeout=3
                    )
                    if not resp.ok:
                        continue
                    
                    data = resp.json()
                    posts = data.get("data", {}).get("children", [])
                    
                    for post in posts[:5]:
                        title = post.get("data", {}).get("title", "")
                        score = post.get("data", {}).get("score", 0)
                        
                        if self.is_ai_tech_topic(title) and score > 100:
                            topics.append({
                                "topic": title,
                                "source": f"reddit-{subreddit}",
                                "score": score,
                                "timestamp": time.time(),
                                "url": "https://reddit.com" + post.get("data", {}).get("permalink", "")
                            })
                except Exception as e:
                    log.warning(f"Reddit/{subreddit} error: {e}")
                    continue
            
            log.info(f"Reddit trends: Found {len(topics)} AI/Tech topics")
            return topics
        except Exception as e:
            log.warning(f"Reddit fetch error: {e}")
            return []

    def get_topic_id_for_trending(self, topic_title: str) -> str:
        """Generate a topic ID for a trending topic."""
        # Convert title to slug: "ChatGPT 5 Release" -> "chatgpt-5-release"
        slug = topic_title.lower()
        slug = ''.join(c if c.isalnum() else '-' for c in slug)
        slug = '-'.join(word for word in slug.split('-') if word)
        
        # Truncate to 50 chars and add hash to ensure uniqueness
        topic_hash = hashlib.md5(topic_title.encode()).hexdigest()[:6]
        return f"trending-{slug[:40]}-{topic_hash}"

    def has_trending_topic_been_posted(self, topic_id: str) -> bool:
        """Check if trending topic has already been posted."""
        posted = self.cache.get("posted_topics", [])
        return topic_id in posted

    def mark_trending_topic_posted(self, topic_id: str) -> None:
        """Mark a trending topic as posted."""
        posted = self.cache.get("posted_topics", [])
        if topic_id not in posted:
            posted.append(topic_id)
            # Keep only last 100 posted topics
            self.cache["posted_topics"] = posted[-100:]
            self._save_cache()
        log.info(f"Marked trending topic as posted: {topic_id}")

    def get_trending_topic_for_posting(self) -> Optional[Dict]:
        """Get the next trending topic to post about."""
        if not self.enable_trending:
            return None
        
        topics = self.discover_trending_topics()
        
        for topic_data in topics:
            topic_id = self.get_topic_id_for_trending(topic_data["topic"])
            
            # Skip if already posted
            if self.has_trending_topic_been_posted(topic_id):
                continue
            
            return {
                "id": topic_id,
                "name": topic_data["topic"],
                "source": topic_data.get("source", "trending"),
                "url": topic_data.get("url", ""),
                "timestamp": topic_data.get("timestamp", time.time()),
                "is_trending": True
            }
        
        return None


# Main testing
if __name__ == "__main__":
    detector = TrendingTopicDetector(enable_trending=True, cache_ttl_hours=1)
    
    print("\n" + "="*70)
    print("TRENDING TOPIC DETECTOR TEST")
    print("="*70)
    
    print("\n[1] Discovering trending AI/Tech topics...")
    topics = detector.discover_trending_topics()
    
    if topics:
        print(f"\nFound {len(topics)} trending AI/Tech topics:\n")
        for i, topic in enumerate(topics, 1):
            print(f"{i}. {topic['topic']}")
            print(f"   Source: {topic['source']} | Score: {topic['score']}")
            print(f"   ID: {detector.get_topic_id_for_trending(topic['topic'])}\n")
    else:
        print("\n❌ No trending topics found (API issues or no internet)")
    
    print("\n[2] Testing topic ID generation...")
    test_topics = [
        "Claude 3.5 Sonnet Released",
        "RAG Best Practices 2026",
        "Distributed Systems Patterns"
    ]
    
    for topic_title in test_topics:
        topic_id = detector.get_topic_id_for_trending(topic_title)
        print(f"  '{topic_title}' → {topic_id}")
    
    print("\n[3] Testing topic tracking...")
    test_id = "trending-test-topic-abc123"
    print(f"  Before: posted={detector.has_trending_topic_been_posted(test_id)}")
    detector.mark_trending_topic_posted(test_id)
    print(f"  After:  posted={detector.has_trending_topic_been_posted(test_id)}")
    
    print("\n✓ Trending topic detector ready!\n")
