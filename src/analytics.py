#!/usr/bin/env python3
"""
analytics.py — LinkedIn Post Analytics & Engagement Tracking

Tracks metrics for posted content:
- Post engagement (likes, comments, shares, impressions)
- Engagement rate trends over time
- Topic performance comparison
- Post timing optimization
- A/B test results
- Content type ROI

Data sources:
1. LinkedIn API (requires official API access with analytics scope)
2. Manual entry (for testing without API)
3. Dashboard reporting (if linked to third-party analytics)

Usage:
    from analytics import AnalyticsTracker
    
    tracker = AnalyticsTracker()
    tracker.log_post_published(post_id, topic_id, variant_id, timestamp, text)
    tracker.record_engagement(post_id, likes, comments, shares, impressions)
    tracker.get_performance_summary()
"""

import os
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from collections import defaultdict

try:
    from logger import get_logger
    log = get_logger("analytics")
except ImportError:
    class _Logger:
        def info(self, m): print(f"[ANALYTICS] {m}")
        def warning(self, m): print(f"[ANALYTICS] WARN {m}")
        def error(self, m): print(f"[ANALYTICS] ERROR {m}")
    log = _Logger()


# Analytics storage
ANALYTICS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".analytics.json")

# Engagement thresholds (for classification)
ENGAGEMENT_TIERS = {
    "viral": 25.0,           # > 25% engagement rate
    "high": 10.0,            # 10-25%
    "good": 5.0,             # 5-10%
    "average": 2.0,          # 2-5%
    "low": 0.0,              # < 2%
}


class PostAnalytics:
    """Single post analytics record."""

    def __init__(
        self,
        post_id: str,
        linkedin_url: Optional[str] = None,
        topic_id: Optional[str] = None,
        topic_name: Optional[str] = None,
        variant_id: Optional[str] = None,
        published_at: Optional[str] = None,
        post_text: Optional[str] = None,
    ):
        self.post_id = post_id
        self.linkedin_url = linkedin_url
        self.topic_id = topic_id
        self.topic_name = topic_name
        self.variant_id = variant_id
        self.published_at = published_at or datetime.now(timezone.utc).isoformat()
        self.post_text = post_text
        
        # Engagement metrics
        self.likes = 0
        self.comments = 0
        self.shares = 0
        self.impressions = 0
        self.last_updated = datetime.now(timezone.utc).isoformat()

    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate (%)."""
        if self.impressions == 0:
            return 0.0
        total_engagement = self.likes + (self.comments * 1.5) + (self.shares * 2.0)
        return (total_engagement / self.impressions) * 100

    @property
    def engagement_tier(self) -> str:
        """Classify engagement into tier."""
        rate = self.engagement_rate
        for tier, threshold in sorted(ENGAGEMENT_TIERS.items(), key=lambda x: x[1], reverse=True):
            if rate >= threshold:
                return tier
        return "low"

    @property
    def total_engagement(self) -> int:
        """Sum of all engagement actions."""
        return self.likes + self.comments + self.shares

    def to_dict(self) -> Dict:
        """Serialize to JSON-friendly dict."""
        return {
            "post_id": self.post_id,
            "linkedin_url": self.linkedin_url,
            "topic_id": self.topic_id,
            "topic_name": self.topic_name,
            "variant_id": self.variant_id,
            "published_at": self.published_at,
            "post_text": self.post_text[:500] if self.post_text else None,  # First 500 chars
            "engagement": {
                "likes": self.likes,
                "comments": self.comments,
                "shares": self.shares,
                "impressions": self.impressions,
                "total_engagement": self.total_engagement,
                "engagement_rate": round(self.engagement_rate, 2),
                "tier": self.engagement_tier,
            },
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PostAnalytics":
        """Deserialize from JSON dict."""
        analytics = cls(
            post_id=data.get("post_id", ""),
            linkedin_url=data.get("linkedin_url"),
            topic_id=data.get("topic_id"),
            topic_name=data.get("topic_name"),
            variant_id=data.get("variant_id"),
            published_at=data.get("published_at"),
            post_text=data.get("post_text"),
        )
        eng = data.get("engagement", {})
        analytics.likes = eng.get("likes", 0)
        analytics.comments = eng.get("comments", 0)
        analytics.shares = eng.get("shares", 0)
        analytics.impressions = eng.get("impressions", 0)
        analytics.last_updated = data.get("last_updated", "")
        return analytics


class AnalyticsTracker:
    """Track and analyze post performance metrics."""

    def __init__(self):
        self.posts: Dict[str, PostAnalytics] = {}
        self._load_analytics()

    def _load_analytics(self) -> None:
        """Load analytics history from disk."""
        if not os.path.exists(ANALYTICS_FILE):
            return

        try:
            with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                for post_data in data[-1000:]:  # Keep last 1000 posts
                    post_analytics = PostAnalytics.from_dict(post_data)
                    self.posts[post_analytics.post_id] = post_analytics
                log.info(f"Loaded {len(self.posts)} posts from analytics history")
        except Exception as e:
            log.error(f"Failed to load analytics: {e}")

    def _save_analytics(self) -> None:
        """Save analytics to disk."""
        try:
            data = [p.to_dict() for p in self.posts.values()]
            with open(ANALYTICS_FILE, "w", encoding="utf-8") as f:
                json.dump(data[-1000:], f, indent=2)
        except Exception as e:
            log.error(f"Failed to save analytics: {e}")

    def log_post_published(
        self,
        post_id: str,
        topic_id: Optional[str] = None,
        topic_name: Optional[str] = None,
        variant_id: Optional[str] = None,
        post_text: Optional[str] = None,
        linkedin_url: Optional[str] = None,
    ) -> PostAnalytics:
        """Record a newly published post."""
        analytics = PostAnalytics(
            post_id=post_id,
            linkedin_url=linkedin_url,
            topic_id=topic_id,
            topic_name=topic_name,
            variant_id=variant_id,
            published_at=datetime.now(timezone.utc).isoformat(),
            post_text=post_text,
        )
        self.posts[post_id] = analytics
        self._save_analytics()
        log.info(f"Logged post: {post_id} (topic: {topic_name})")
        return analytics

    def record_engagement(
        self,
        post_id: str,
        likes: int = 0,
        comments: int = 0,
        shares: int = 0,
        impressions: int = 0,
    ) -> Optional[PostAnalytics]:
        """Update engagement metrics for a post."""
        if post_id not in self.posts:
            log.warning(f"Post {post_id} not found in analytics")
            return None

        analytics = self.posts[post_id]
        analytics.likes = likes
        analytics.comments = comments
        analytics.shares = shares
        analytics.impressions = impressions
        analytics.last_updated = datetime.now(timezone.utc).isoformat()

        self._save_analytics()
        log.info(
            f"Updated {post_id}: {likes}L {comments}C {shares}S | "
            f"Rate: {analytics.engagement_rate:.2f}% ({analytics.engagement_tier})"
        )
        return analytics

    def get_post(self, post_id: str) -> Optional[PostAnalytics]:
        """Retrieve analytics for specific post."""
        return self.posts.get(post_id)

    def get_recent_posts(self, days: int = 30, limit: int = 50) -> List[PostAnalytics]:
        """Get recent posts within time range, sorted by publish date (newest first)."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        recent = [
            p for p in self.posts.values()
            if p.published_at
            and datetime.fromisoformat(p.published_at) > cutoff
        ]

        return sorted(recent, key=lambda p: p.published_at, reverse=True)[:limit]

    def get_topic_performance(self, topic_id: str) -> Dict:
        """Get aggregated performance for all posts in a topic."""
        topic_posts = [p for p in self.posts.values() if p.topic_id == topic_id]

        if not topic_posts:
            return {}

        total_posts = len(topic_posts)
        total_likes = sum(p.likes for p in topic_posts)
        total_comments = sum(p.comments for p in topic_posts)
        total_shares = sum(p.shares for p in topic_posts)
        total_impressions = sum(p.impressions for p in topic_posts)
        avg_engagement_rate = sum(p.engagement_rate for p in topic_posts) / total_posts

        best_post = max(topic_posts, key=lambda p: p.engagement_rate, default=None)
        worst_post = min(topic_posts, key=lambda p: p.engagement_rate, default=None)

        return {
            "topic_id": topic_id,
            "total_posts": total_posts,
            "total_impressions": total_impressions,
            "total_engagement": {
                "likes": total_likes,
                "comments": total_comments,
                "shares": total_shares,
                "combined": total_likes + total_comments + total_shares,
            },
            "avg_engagement_rate": round(avg_engagement_rate, 2),
            "best_post": {
                "post_id": best_post.post_id,
                "engagement_rate": round(best_post.engagement_rate, 2),
                "total_engagement": best_post.total_engagement,
            } if best_post else None,
            "worst_post": {
                "post_id": worst_post.post_id,
                "engagement_rate": round(worst_post.engagement_rate, 2),
                "total_engagement": worst_post.total_engagement,
            } if worst_post else None,
        }

    def get_performance_summary(self, days: int = 30) -> Dict:
        """Get overall performance summary for recent posts."""
        recent = self.get_recent_posts(days=days)

        if not recent:
            return {"status": "no_data", "days": days}

        total_posts = len(recent)
        total_likes = sum(p.likes for p in recent)
        total_comments = sum(p.comments for p in recent)
        total_shares = sum(p.shares for p in recent)
        total_impressions = sum(p.impressions for p in recent)

        engagement_tiers_count = defaultdict(int)
        for post in recent:
            engagement_tiers_count[post.engagement_tier] += 1

        topics = defaultdict(int)
        for post in recent:
            if post.topic_id:
                topics[post.topic_id] += 1

        variants = defaultdict(int)
        for post in recent:
            if post.variant_id:
                variants[post.variant_id] += 1

        avg_engagement_rate = sum(p.engagement_rate for p in recent) / total_posts if recent else 0

        return {
            "period_days": days,
            "posts_published": total_posts,
            "total_impressions": total_impressions,
            "avg_impressions_per_post": round(total_impressions / total_posts, 0) if total_posts else 0,
            "total_engagement": {
                "likes": total_likes,
                "comments": total_comments,
                "shares": total_shares,
                "combined": total_likes + total_comments + total_shares,
            },
            "avg_engagement_rate": round(avg_engagement_rate, 2),
            "engagement_breakdown": dict(engagement_tiers_count),
            "top_topics": dict(sorted(topics.items(), key=lambda x: x[1], reverse=True)[:5]),
            "variant_distribution": dict(variants),
            "best_posts": [
                {
                    "post_id": p.post_id,
                    "topic": p.topic_name,
                    "engagement_rate": round(p.engagement_rate, 2),
                    "engagement": p.total_engagement,
                    "impressions": p.impressions,
                    "published_at": p.published_at,
                }
                for p in sorted(recent, key=lambda p: p.engagement_rate, reverse=True)[:5]
            ],
        }

    def get_posting_time_analysis(self, days: int = 60) -> Dict:
        """Analyze engagement by day of week and hour posted."""
        recent = self.get_recent_posts(days=days)

        if not recent:
            return {}

        by_hour = defaultdict(lambda: {"likes": 0, "comments": 0, "shares": 0, "posts": 0, "impressions": 0})
        by_dow = defaultdict(lambda: {"likes": 0, "comments": 0, "shares": 0, "posts": 0, "impressions": 0})

        for post in recent:
            if not post.published_at:
                continue

            try:
                pub_dt = datetime.fromisoformat(post.published_at)
                hour = pub_dt.hour
                dow = pub_dt.strftime("%A")

                by_hour[hour]["likes"] += post.likes
                by_hour[hour]["comments"] += post.comments
                by_hour[hour]["shares"] += post.shares
                by_hour[hour]["posts"] += 1
                by_hour[hour]["impressions"] += post.impressions

                by_dow[dow]["likes"] += post.likes
                by_dow[dow]["comments"] += post.comments
                by_dow[dow]["shares"] += post.shares
                by_dow[dow]["posts"] += 1
                by_dow[dow]["impressions"] += post.impressions
            except Exception as e:
                log.warning(f"Failed to parse timestamp {post.published_at}: {e}")
                continue

        # Calculate engagement rates
        hour_analysis = {}
        for hour, data in by_hour.items():
            if data["posts"] > 0 and data["impressions"] > 0:
                engagement = (data.get("likes", 0) + (data.get("comments", 0) * 1.5) + (data.get("shares", 0) * 2.0)) / data["impressions"] * 100
                hour_analysis[hour] = {
                    "posts": data["posts"],
                    "avg_engagement_rate": round(engagement, 2),
                    "avg_impressions": round(data["impressions"] / data["posts"], 0),
                }

        dow_analysis = {}
        for dow, data in by_dow.items():
            if data["posts"] > 0 and data["impressions"] > 0:
                engagement = (data.get("likes", 0) + (data.get("comments", 0) * 1.5) + (data.get("shares", 0) * 2.0)) / data["impressions"] * 100
                dow_analysis[dow] = {
                    "posts": data["posts"],
                    "avg_engagement_rate": round(engagement, 2),
                    "avg_impressions": round(data["impressions"] / data["posts"], 0),
                }

        best_hour = max(hour_analysis.items(), key=lambda x: x[1]["avg_engagement_rate"], default=(None, {}))[0]
        best_dow = max(dow_analysis.items(), key=lambda x: x[1]["avg_engagement_rate"], default=(None, {}))[0]

        return {
            "by_hour": hour_analysis,
            "by_day_of_week": dow_analysis,
            "best_hour": best_hour,
            "best_day_of_week": best_dow,
        }

    def export_csv(self, filepath: str, days: int = 90) -> None:
        """Export recent analytics to CSV for external analysis."""
        import csv

        recent = self.get_recent_posts(days=days)

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "post_id",
                        "published_at",
                        "topic_name",
                        "variant_id",
                        "likes",
                        "comments",
                        "shares",
                        "impressions",
                        "engagement_rate",
                        "tier",
                    ],
                )
                writer.writeheader()
                for post in sorted(recent, key=lambda p: p.published_at, reverse=True):
                    writer.writerow({
                        "post_id": post.post_id,
                        "published_at": post.published_at,
                        "topic_name": post.topic_name or "N/A",
                        "variant_id": post.variant_id or "N/A",
                        "likes": post.likes,
                        "comments": post.comments,
                        "shares": post.shares,
                        "impressions": post.impressions,
                        "engagement_rate": f"{post.engagement_rate:.2f}%",
                        "tier": post.engagement_tier,
                    })
            log.info(f"Exported {len(recent)} posts to {filepath}")
        except Exception as e:
            log.error(f"Failed to export CSV: {e}")


def main():
    """Demo: Generate sample analytics."""
    tracker = AnalyticsTracker()

    # Log sample posts
    for i in range(5):
        post_id = f"urn:li:share:{datetime.now().timestamp() + i}"
        tracker.log_post_published(
            post_id=post_id,
            topic_id="sample-topic",
            topic_name="Sample Topic",
            variant_id=["A", "B", "C"][i % 3],
            post_text=f"Sample post {i+1}",
        )

    # Record sample engagement
    if tracker.posts:
        first_post_id = list(tracker.posts.keys())[0]
        tracker.record_engagement(
            post_id=first_post_id,
            likes=45,
            comments=12,
            shares=5,
            impressions=850,
        )

    # Print summary
    summary = tracker.get_performance_summary()
    print(json.dumps(summary, indent=2))

    # Print timing analysis
    timing = tracker.get_posting_time_analysis()
    if timing:
        print("\nBest posting time:")
        print(f"  Hour: {timing.get('best_hour')}")
        print(f"  Day: {timing.get('best_day_of_week')}")


if __name__ == "__main__":
    main()
