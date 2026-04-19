#!/usr/bin/env python3
"""
trending_topics_enhanced.py — Multi-category trending topics detector

Supports:
- AI/Tech Trends (70%)
- Industry News (15%)
- Personal Stories (10%)
- Tips & Lessons (5%)

Usage:
    detector = TrendingTopicDetectorEnhanced(enabled_categories=['ai_tech', 'news', 'stories'])
    topic = detector.get_trending_topic_for_category('ai_tech')
    topic = detector.get_trending_topic_for_category('personal_stories')
"""

import os
import json
import random
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional

try:
    from logger import get_logger
    log = get_logger("trending_enhanced")
except ImportError:
    class _Logger:
        def info(self, m): print(f"[TRENDING+] {m}")
        def warning(self, m): print(f"[TRENDING+] WARN {m}")
        def error(self, m): print(f"[TRENDING+] ERR {m}")
    log = _Logger()


# ═════════════════════════════════════════════════════════════════════════════
# KEYWORDS BY CATEGORY
# ═════════════════════════════════════════════════════════════════════════════

KEYWORDS = {
    "ai_tech": {
        # LLMs & AI Core
        "llm", "large language model", "gpt", "claude", "gemini", "mistral", "qwen",
        "transformer", "attention", "embedding", "token", "context window",
        
        # AI Applications
        "rag", "agents", "agentic", "prompt", "prompt engineering", "fine-tuning",
        "retrieval", "augmented generation", "vector", "semantic search",
        
        # ML & Data
        "machine learning", "deep learning", "neural network", "backprop",
        "data engineering", "mlops", "feature store", "pipeline",
        
        # Infrastructure & DevOps
        "kubernetes", "docker", "container", "microservices", "cicd", "devops",
        "serverless", "lambda", "faas", "infrastructure as code", "terraform",
        "bicep", "ansible", "vagrant",
        
        # Cloud
        "aws", "azure", "gcp", "cloud", "compute", "storage", "database",
        "scaling", "vertical", "horizontal", "load balancing",
        
        # Programming & Tools
        "python", "rust", "golang", "typescript", "javascript", "reactjs",
        "nodejs", "fastapi", "django", "flask", "api", "rest", "graphql",
        
        # Concepts
        "system design", "architecture", "scalability", "performance",
        "optimization", "caching", "redis", "postgresql", "mongodb",
        "sql", "nosql", "database", "distributed", "consensus",
        
        # Security & Compliance
        "security", "cryptography", "oauth", "jwt", "authentication",
        "authorization", "zero trust", "encryption", "ssl",
    },
    
    "industry_news": {
        # Tech Giants
        "microsoft", "google", "amazon", "meta", "apple", "nvidia",
        "anthropic", "openai", "deepmind", "databricks", "huggingface",
        
        # News Indicators
        "announced", "launched", "released", "unveiled", "introduces",
        "partnership", "collaboration", "integration", "acquisition",
        "funding", "raises", "series", "investment", "startup",
        
        # Product/Release News
        "new", "beta", "alpha", "release", "version", "update",
        "feature", "available", "now available", "open source",
        
        # Metrics/Milestones
        "billion", "million", "valuation", "round", "series a", "series b",
        "ipo", "milestone", "growth", "expansion", "enterprise",
    },
    
    "personal_story": {
        # Journey Keywords
        "journey", "experience", "learned", "lesson", "story", "my",
        "i ", "we ", "went from", "started", "beginning", "chapter",
        
        # Challenge Keywords
        "challenge", "struggled", "failed", "mistake", "broke", "bug",
        "issue", "problem", "solved", "breakthrough", "aha moment",
        "difficult", "hard", "tough", "almost quit", "wanted to quit",
        
        # Growth Keywords
        "growth", "progress", "improvement", "better", "increase",
        "learned", "realized", "discovered", "insight", "revelation",
        "transformation", "pivot", "changed", "shift",
        
        # Personal Language
        "my experience", "i discovered", "i found", "i realized",
        "i learned", "i struggled", "i failed", "i won", "i achieved",
        "first time", "first project", "my first", "back then",
    },
    
    "tips_lessons": {
        # Prescriptive Keywords
        "tip", "trick", "hack", "secret", "best practice", "pattern",
        "anti-pattern", "gotcha", "warning", "note", "remember",
        "always", "never", "avoid", "mistake to avoid",
        
        # How-To Keywords
        "how to", "how i", "5 ways", "3 steps", "guide", "tutorial",
        "example", "use case", "scenario", "here's how",
        
        # Lesson Keywords
        "lesson", "learned", "takeaway", "key", "important", "critical",
        "essential", "fundamental", "must know", "should know",
        
        # Analysis Keywords
        "why", "reason", "because", "advantage", "disadvantage",
        "pro", "con", "trade-off", "tradeoff", "when to use",
    }
}

# Topics to completely exclude
EXCLUDE_KEYWORDS = {
    "crypto", "bitcoin", "ethereum", "nft", "blockchain", "web3",
    "finance", "stock", "trading", "forex", "investment", "portfolio",
    "sports", "athlete", "game", "gaming", "esports",
    "celebrity", "actor", "musician", "entertainment",
    "political", "politics", "election", "vote", "government",
}


class TrendingTopicDetectorEnhanced:
    """Multi-category trending topic detector."""
    
    def __init__(self, enabled_categories: List[str] = None, cache_file: str = None):
        """
        Initialize enhanced trending detector.
        
        Args:
            enabled_categories: Categories to detect. Defaults to all.
                Options: 'ai_tech', 'industry_news', 'personal_story', 'tips_lessons'
            cache_file: Path to cache file (default: .trending_cache_enhanced.json)
        """
        self.enabled_categories = enabled_categories or list(KEYWORDS.keys())
        self.cache_file = cache_file or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            ".trending_cache_enhanced.json"
        )
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cache from disk."""
        if not os.path.exists(self.cache_file):
            return {"topics": {}, "posted": []}
        try:
            with open(self.cache_file, "r") as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"Could not load cache: {e}")
        return {"topics": {}, "posted": []}
    
    def _save_cache(self) -> None:
        """Save cache to disk."""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            log.warning(f"Could not save cache: {e}")
    
    def categorize_topic(self, title: str, text: str = "") -> Optional[str]:
        """
        Detect topic category.
        
        Args:
            title: Topic/article title
            text: Optional additional text (description, body, etc.)
        
        Returns:
            Category name or None if excluded/no match
        """
        combined = (f"{title} {text}").lower()
        
        # Check exclusions first
        for exclude_kw in EXCLUDE_KEYWORDS:
            if exclude_kw in combined:
                return None  # Excluded
        
        # Score each enabled category
        scores = {}
        for category in self.enabled_categories:
            category_keywords = KEYWORDS.get(category, set())
            matches = sum(1 for kw in category_keywords if kw in combined)
            if matches > 0:
                scores[category] = matches
        
        if not scores:
            return None
        
        # Return highest scoring category
        return max(scores.items(), key=lambda x: x[1])[0]
    
    def get_trending_topic_for_category(self, category: str) -> Optional[Dict]:
        """
        Get trending topic for specific category.
        
        Args:
            category: One of 'ai_tech', 'industry_news', 'personal_story', 'tips_lessons'
        
        Returns:
            Topic dict or None if not found
        """
        if category not in self.cache.get("topics", {}):
            return None
        
        topics = self.cache["topics"][category]
        posted_ids = set(self.cache.get("posted", []))
        
        # Get unposted topics
        available = [t for t in topics if t.get("id") not in posted_ids]
        
        if not available:
            log.warning(f"No unposted topics in category: {category}")
            return None
        
        # Pick random from available
        topic = random.choice(available)
        
        # Mark as posted
        posted_ids.add(topic.get("id"))
        self.cache["posted"] = list(posted_ids)
        self._save_cache()
        
        log.info(f"Selected {category} topic: {topic.get('title', 'Unknown')[:50]}")
        return topic
    
    def add_topic_to_cache(self, category: str, topic: Dict) -> None:
        """Add topic to cache."""
        if category not in self.cache["topics"]:
            self.cache["topics"][category] = []
        
        # Don't add duplicates
        existing_ids = {t.get("id") for t in self.cache["topics"][category]}
        if topic.get("id") not in existing_ids:
            self.cache["topics"][category].append(topic)
            self._save_cache()
            log.info(f"Added {category} topic: {topic.get('title', 'Unknown')[:50]}")
    
    def refresh_from_sources(self) -> Dict[str, int]:
        """
        Refresh trending topics from all enabled sources.
        
        Returns:
            Count of topics added per category: {'ai_tech': 5, 'news': 3, ...}
        """
        counts = {}
        
        for category in self.enabled_categories:
            if category == "ai_tech":
                count = self._fetch_ai_tech_topics()
            elif category == "industry_news":
                count = self._fetch_industry_news()
            elif category == "personal_story":
                count = self._fetch_personal_story_topics()
            elif category == "tips_lessons":
                count = self._fetch_tips_lessons_topics()
            else:
                count = 0
            
            counts[category] = count
            log.info(f"{category}: {count} topics added")
        
        return counts
    
    def _fetch_ai_tech_topics(self) -> int:
        """Fetch AI/Tech topics from HackerNews."""
        try:
            # HN Top Stories
            res = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10)
            if res.status_code != 200: return 0
            
            story_ids = res.json()[:40] # Check top 40 items
            count = 0
            for sid in story_ids:
                s_res = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5)
                if s_res.status_code == 200:
                    story = s_res.json()
                    title = story.get("title", "")
                    category = self.categorize_topic(title)
                    if category == "ai_tech":
                        topic = {
                            "id": f"hn-{sid}",
                            "title": title,
                            "url": story.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                            "score": story.get("score", 0),
                            "timestamp": datetime.now().isoformat()
                        }
                        self.add_topic_to_cache("ai_tech", topic)
                        count += 1
            return count
        except Exception as e:
            log.warning(f"Failed to fetch HN topics: {e}")
            return 0

    def _fetch_industry_news(self) -> int:
        """Fetch industry news topics from Google News RSS."""
        try:
            # Google News RSS for AI and Tech
            url = "https://news.google.com/rss/search?q=AI+Machine+Learning+Technology&hl=en-US&gl=US&ceid=US:en"
            res = requests.get(url, timeout=10)
            if res.status_code != 200: return 0
            
            root = ET.fromstring(res.text)
            count = 0
            for item in root.findall(".//item")[:15]:
                title = item.find("title").text if item.find("title") is not None else ""
                url = item.find("link").text if item.find("link") is not None else ""
                
                category = self.categorize_topic(title)
                if category == "industry_news":
                    topic = {
                        "id": hashlib.md5(url.encode()).hexdigest(),
                        "title": title,
                        "url": url,
                        "timestamp": datetime.now().isoformat()
                    }
                    self.add_topic_to_cache("industry_news", topic)
                    count += 1
            return count
        except Exception as e:
            log.warning(f"Failed to fetch Google News topics: {e}")
            return 0

    def _fetch_personal_story_topics(self) -> int:
        """Fetch personal story topics from Medium/Dev.to RSS."""
        # Using a broad Tech/Engineering Feed for inspiration
        try:
            url = "https://dev.to/feed"
            res = requests.get(url, timeout=10)
            if res.status_code != 200: return 0
            
            root = ET.fromstring(res.text)
            count = 0
            for item in root.findall(".//item")[:10]:
                title = item.find("title").text if item.find("title") is not None else ""
                url = item.find("link").text if item.find("link") is not None else ""
                
                category = self.categorize_topic(title)
                if category == "personal_story":
                    topic = {
                        "id": hashlib.md5(url.encode()).hexdigest(),
                        "title": title,
                        "url": url,
                        "timestamp": datetime.now().isoformat()
                    }
                    self.add_topic_to_cache("personal_story", topic)
                    count += 1
            return count
        except Exception as e:
            log.warning(f"Failed to fetch personal stories: {e}")
            return 0

    def _fetch_tips_lessons_topics(self) -> int:
        """Fetch tips/lessons topics from Engineering Blogs."""
        return self._fetch_personal_story_topics() # Dev.to covers both
    
    def get_category_post_for_frequency(self, frequencies: Dict[str, float]) -> str:
        """
        Get category based on frequency distribution.
        
        Args:
            frequencies: {'ai_tech': 0.6, 'news': 0.2, 'stories': 0.1, 'tips': 0.1}
        
        Returns:
            Selected category
        """
        categories = list(frequencies.keys())
        weights = list(frequencies.values())
        return random.choices(categories, weights=weights, k=1)[0]


# ═════════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Initialize detector with all categories
    detector = TrendingTopicDetectorEnhanced(
        enabled_categories=["ai_tech", "industry_news", "personal_story", "tips_lessons"]
    )
    
    # Test categorization
    test_topics = [
        ("Claude 3.5 Sonnet Released with 200K Context", "AI/Tech topic"),
        ("Microsoft Invests $80B in AI Infrastructure", "Industry news"),
        ("How I Went from Zero to AI Engineer in 6 Months", "Personal story"),
        ("5 Mistakes I Made Building RAG Systems", "Tips/Lessons"),
        ("Bitcoin Reaches All-Time High", "Should be excluded"),
    ]
    
    print("Testing topic categorization:")
    for title, expected in test_topics:
        category = detector.categorize_topic(title)
        status = "✓" if (category and expected) or (not category and "excluded" in expected) else "✗"
        print(f"{status} {title[:50]:<50} → {category or 'EXCLUDED'}")
