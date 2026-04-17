#!/usr/bin/env python3
"""
diagram_rotation.py — Intelligent Diagram Style Rotation

Ensures visual variety by rotating diagram styles across posts.
Without this, the same topic always gets the same diagram style (boring!).

This module tracks recent diagram styles and intelligently selects
the next style to maximize visual variety.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from collections import deque

try:
    from logger import get_logger
    log = get_logger("diagram_rotation")
except ImportError:
    class _Logger:
        def info(self, m): print(f"[ROTATION] {m}")
        def warning(self, m): print(f"[ROTATION] WARN {m}")
    log = _Logger()

# Rotation history file
ROTATION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".diagram_rotation.json")

# Available diagram styles — must stay in sync with diagram_generator.py STYLES list
AVAILABLE_STYLES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 20, 23]
# Styles 16, 19, 21, 22 are disabled/structured-only — excluded from rotation

STYLE_NAMES = {
    0:  "Vertical Flow",
    1:  "Mind Map",
    2:  "Pyramid/Funnel",
    3:  "Timeline",
    4:  "Hexagon Grid",
    5:  "Comparison Table",
    6:  "Circular Orbit",
    7:  "Card Grid",
    8:  "3-Tier Data Evolution",
    9:  "Horizontal Tree",
    10: "Layered Horizontal Flow",
    11: "Ecosystem Tree",
    12: "Honeycomb Map",
    13: "Parallel Pipelines",
    14: "Winding Roadmap",
    15: "Vertical Timeline",
    17: "Signal vs Noise",
    20: "Dark Column Flow",
    23: "Viral Poster",
}

# How many recent diagrams to track (prevent repetition)
RECENT_HISTORY = 30


class DiagramRotation:
    """Manage diagram style rotation for visual variety."""

    def __init__(self):
        self.history = self._load_history()

    def _load_history(self) -> List[Dict]:
        """Load rotation history from disk."""
        if not os.path.exists(ROTATION_FILE):
            return []
        try:
            with open(ROTATION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data[-RECENT_HISTORY:]
        except Exception as e:
            log.warning(f"Could not load rotation history: {e}")
        return []

    def _save_history(self) -> None:
        """Save rotation history to disk."""
        try:
            with open(ROTATION_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history[-RECENT_HISTORY:], f, indent=2)
        except Exception as e:
            log.warning(f"Could not save rotation history: {e}")

    def get_recent_styles(self, count: int = 10) -> List[int]:
        """Get the most recent N diagram styles used."""
        return [h.get("style_idx", 7) for h in self.history[-count:]]

    def get_style_frequency(self) -> Dict[int, int]:
        """Count how many times each style was used recently."""
        freq = {}
        for h in self.history[-RECENT_HISTORY:]:
            style_idx = h.get("style_idx", 7)
            freq[style_idx] = freq.get(style_idx, 0) + 1
        return freq

    def select_next_style(
        self,
        preferred_style: int = 7,
        available_styles: List[int] = None,
        avoid_repetition: bool = True,
    ) -> int:
        """
        Intelligently select the next diagram style.

        Args:
            preferred_style: Base style (usually from topic mapping)
            available_styles: List of styles to choose from (default: all)
            avoid_repetition: If True, avoid styles used in last 5 posts

        Returns:
            Selected style index
        """
        if available_styles is None:
            available_styles = AVAILABLE_STYLES

        available_styles = [s for s in available_styles if s is not None]
        if not available_styles:
            available_styles = AVAILABLE_STYLES

        # If no history, use preferred
        if not self.history:
            return preferred_style if preferred_style in available_styles else available_styles[0]

        recent = self.get_recent_styles(count=5)

        # If avoid repetition, remove recently used styles
        if avoid_repetition:
            candidates = [s for s in available_styles if s not in recent]
            if candidates:
                available_styles = candidates

        # Least recently used strategy
        freq = self.get_style_frequency()
        least_used = min(
            available_styles,
            key=lambda s: freq.get(s, 0),
        )

        return least_used

    def record_style_used(
        self,
        style_idx: int,
        topic_id: Optional[str] = None,
        topic_name: Optional[str] = None,
        diagram_type: Optional[str] = None,
    ) -> None:
        """Record that a style was used."""
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "style_idx": style_idx,
            "style_name": STYLE_NAMES.get(style_idx, f"Style {style_idx}"),
            "topic_id": topic_id,
            "topic_name": topic_name,
            "diagram_type": diagram_type,
        })
        self._save_history()

        freq = self.get_style_frequency()
        log.info(
            f"Used style {style_idx} ({STYLE_NAMES.get(style_idx, 'Unknown')}). "
            f"Recent distribution: {freq}"
        )

    def get_next_style_recommendation(
        self,
        preferred_style: int = 7,
        candidates: List[int] = None,
    ) -> Dict:
        """
        Get comprehensive recommendation for next style to use.

        Returns:
            {
                'recommended_style': int,
                'recent_frequency': dict,
                'reason': str,
                'alternatives': [int, ...],
            }
        """
        if candidates is None:
            candidates = AVAILABLE_STYLES

        recommended = self.select_next_style(
            preferred_style=preferred_style,
            available_styles=candidates,
            avoid_repetition=True,
        )

        freq = self.get_style_frequency()
        recent = self.get_recent_styles(count=5)

        alternatives = [
            s for s in sorted(
                candidates,
                key=lambda x: (freq.get(x, 0), recent.count(x)),
            )
            if s != recommended
        ][:3]

        reason = "Least recently used"
        if recommended not in recent:
            reason = "Not in recent 5 posts"
        if freq.get(recommended, 0) == min(freq.get(c, 0) for c in candidates):
            reason = "Minimal usage frequency"

        return {
            "recommended_style": recommended,
            "style_name": STYLE_NAMES.get(recommended, f"Style {recommended}"),
            "reason": reason,
            "recent_frequency": freq,
            "alternatives": alternatives,
            "recent_styles": recent,
        }

    def get_diversity_score(self) -> float:
        """
        Calculate diagram style diversity (0.0 = all same, 1.0 = perfect variety).
        """
        if len(self.history) < 10:
            return 0.0

        recent = self.get_recent_styles(count=20)
        unique_styles = len(set(recent))
        max_styles = min(len(AVAILABLE_STYLES), 20)

        return unique_styles / max_styles

    def get_stats_summary(self) -> Dict:
        """Get summary statistics on diagram style usage."""
        if not self.history:
            return {"history_length": 0, "message": "No history yet"}

        freq = self.get_style_frequency()
        recent = self.get_recent_styles(count=10)
        diversity = self.get_diversity_score()

        most_used = max(freq.items(), key=lambda x: x[1], default=(None, 0))
        least_used = min(freq.items(), key=lambda x: x[1], default=(None, 0))

        return {
            "history_length": len(self.history),
            "total_unique_styles": len(freq),
            "total_posts": sum(freq.values()),
            "most_used": {
                "style": most_used[0],
                "name": STYLE_NAMES.get(most_used[0], "Unknown"),
                "count": most_used[1],
            },
            "least_used": {
                "style": least_used[0],
                "name": STYLE_NAMES.get(least_used[0], "Unknown"),
                "count": least_used[1],
            },
            "recent_10": [STYLE_NAMES.get(s, f"Style {s}") for s in recent],
            "diversity_score": round(diversity, 2),
            "frequency_distribution": {
                STYLE_NAMES.get(k, f"Style {k}"): v for k, v in sorted(freq.items())
            },
        }


def main():
    """Demo: Show style rotation in action."""
    rotation = DiagramRotation()

    print("=" * 60)
    print("  Diagram Style Rotation Demo")
    print("=" * 60)

    # Show current stats
    stats = rotation.get_stats_summary()
    print(f"\nCurrent Statistics:")
    print(f"  Total posts: {stats.get('total_posts', 0)}")
    print(f"  Unique styles: {stats.get('total_unique_styles', 0)}")
    print(f"  Diversity score: {stats.get('diversity_score', 0)}")
    print(f"  Recent styles: {stats.get('recent_10', [])}")

    # Simulate adding a few posts
    print("\n" + "=" * 60)
    print("  Simulating 5 new posts...")
    print("=" * 60)

    for i in range(5):
        rec = rotation.get_next_style_recommendation(preferred_style=7)
        print(f"\nPost {i + 1}:")
        print(f"  Recommended: Style {rec['recommended_style']} ({rec['style_name']})")
        print(f"  Reason: {rec['reason']}")
        print(f"  Alternatives: {[STYLE_NAMES[s] for s in rec['alternatives']]}")

        # Record the choice
        rotation.record_style_used(
            rec["recommended_style"],
            topic_id=f"topic-{i+1}",
            topic_name=f"Topic {i+1}",
        )

    # Show updated stats
    print("\n" + "=" * 60)
    print("  Updated Statistics")
    print("=" * 60)
    stats = rotation.get_stats_summary()
    print(f"\n  Total posts: {stats.get('total_posts', 0)}")
    print(f"  Unique styles: {stats.get('total_unique_styles', 0)}")
    print(f"  Diversity score: {stats.get('diversity_score', 0)}")
    print(f"\n  Frequency distribution:")
    for style_name, count in stats.get("frequency_distribution", {}).items():
        print(f"    {style_name}: {count}")


if __name__ == "__main__":
    main()
