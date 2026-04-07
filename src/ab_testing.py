#!/usr/bin/env python3
"""
ab_testing.py — A/B Testing Framework for LinkedIn Posts

Generates multiple post variants per topic and tracks which performs best.
Variants differ in:
  - Hook style (problem-first, stat-first, story-first, etc.)
  - Tone (senior-engineer, tech-lead, principal-engineer, etc.)
  - Format (numbered sections, short paragraphs, before/after, myth/reality)
  - Length (tight 150-200w, medium 220-280w, full 280-340w)
  - CTA style (direct question, poll, discussion prompt)

This creates natural content variation without duplicating ideas while
tracking which combinations drive the best engagement.

Usage:
    from ab_testing import ABTestHarness
    
    harness = ABTestHarness()
    variants = harness.generate_variants(topic, num_variants=3)
    # variants[0]["text"], variants[1]["text"], variants[2]["text"]
    # Each has variant["metadata"] with generation parameters
"""

import os
import json
import hashlib
import random
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path

try:
    from logger import get_logger
    log = get_logger("ab_testing")
except ImportError:
    class _Logger:
        def info(self, m): print(f"[AB_TESTING] {m}")
        def warning(self, m): print(f"[AB_TESTING] WARN {m}")
    log = _Logger()

# A/B Testing Constants
VARIANTS_PER_TOPIC = 3  # Generate 3 variants: A, B, C

# Metadata file for tracking variant performance
AB_MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ab_memory.json")

# Hook styles (from agent.py)
HOOK_VARIANTS = [
    "incident",      # Open mid-incident discovery
    "stat",          # Lead with surprising statistic
    "myth",          # Name wrong belief, then correct
    "quote",         # Start with code review / Slack quote
    "admission",     # Honest admission of past mistake
    "claim",         # Confident, slightly controversial claim
    "gap",           # 'Nobody talks about X' 
    "evolution",     # Time delta: 3-5 years ago vs now
]

# Tone variations (from agent.py)
TONE_VARIANTS = [
    "engineer_11pm",      # Senior engineer at 11pm fixing prod (direct, dark humor)
    "tech_lead",          # Tech lead writing post-mortem (precise, owns mistakes)
    "principal",          # Principal engineer in design review (thoughtful, questions)
    "staff_mentoring",    # Staff engineer mentoring (patient, analogies)
    "tried_four_times",   # Tried 4 approaches, found one that works (specific, quiet confidence)
    "hallway_talk",       # Best hallway talk at conference (opinionated, concrete)
]

# Format variations (from agent.py)
FORMAT_VARIANTS = [
    "numbered",       # Numbered sections with emoji
    "prose",          # Short paragraphs, story flow
    "before_after",   # Contrast: how vs what actually works
    "myth_reality",   # Myth vs Reality structure
]

# Length variations (from agent.py)
LENGTH_VARIANTS = [
    "tight",          # 150-200 words, every sentence earns
    "medium",         # 220-280 words, teach without boring
    "full",           # 280-340 words, go deep on interesting section
]

# CTA styles
CTA_VARIANTS = [
    "direct_poll",        # "What do you use?" - 1️⃣ Option A 2️⃣ Option B
    "open_question",      # "What's your biggest challenge?" - Open discussion
    "metric_poll",        # "Which matters most?" - 1️⃣ Speed 2️⃣ Reliability
    "experience_share",   # "Have you run into this?" - Yes / No / Different
    "advice_seek",        # "What would you do?" - Open reflection prompt
]


class ABTestVariant:
    """Single post variant with metadata for tracking performance."""

    def __init__(
        self,
        topic: Dict,
        text: str,
        variant_id: str,  # "A", "B", "C"
        hook_style: str,
        tone: str,
        format_style: str,
        length: str,
        cta_style: str,
    ):
        self.topic = topic
        self.text = text
        self.variant_id = variant_id
        self.hook_style = hook_style
        self.tone = tone
        self.format_style = format_style
        self.length = length
        self.cta_style = cta_style
        self.created_at = datetime.now().isoformat()
        self.posted_at: Optional[str] = None
        self.linkedin_post_id: Optional[str] = None
        self.engagement_data: Dict = {}

    def to_dict(self) -> Dict:
        """Serialize variant to JSON-friendly dict."""
        return {
            "topic_id": self.topic.get("id", ""),
            "topic_name": self.topic.get("name", ""),
            "variant_id": self.variant_id,
            "text": self.text,
            "metadata": {
                "hook_style": self.hook_style,
                "tone": self.tone,
                "format": self.format_style,
                "length": self.length,
                "cta_style": self.cta_style,
                "created_at": self.created_at,
                "posted_at": self.posted_at,
            },
            "performance": {
                "linkedin_post_id": self.linkedin_post_id,
                "engagement": self.engagement_data,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ABTestVariant":
        """Deserialize variant from JSON dict."""
        topic = {
            "id": data.get("topic_id"),
            "name": data.get("topic_name"),
        }
        variant = cls(
            topic=topic,
            text=data.get("text", ""),
            variant_id=data.get("variant_id", ""),
            hook_style=data.get("metadata", {}).get("hook_style", ""),
            tone=data.get("metadata", {}).get("tone", ""),
            format_style=data.get("metadata", {}).get("format", ""),
            length=data.get("metadata", {}).get("length", ""),
            cta_style=data.get("metadata", {}).get("cta_style", ""),
        )
        variant.posted_at = data.get("metadata", {}).get("posted_at")
        variant.linkedin_post_id = data.get("performance", {}).get("linkedin_post_id")
        variant.engagement_data = data.get("performance", {}).get("engagement", {})
        return variant


class ABTestHarness:
    """Generate and track A/B test variants."""

    def __init__(self):
        self.memory = self._load_memory()

    def _load_memory(self) -> List[Dict]:
        """Load variant history from disk."""
        if not os.path.exists(AB_MEMORY_FILE):
            return []
        try:
            with open(AB_MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data[-500:]  # Keep last 500 variants
        except Exception as e:
            log.warning(f"Could not load AB memory: {e}")
        return []

    def _save_memory(self) -> None:
        """Save variant history to disk."""
        try:
            with open(AB_MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.memory[-500:], f, indent=2)
        except Exception as e:
            log.warning(f"Could not save AB memory: {e}")

    def _select_variant_combo(self, topic_id: str, variant_letter: str) -> Tuple[str, str, str, str, str]:
        """
        Select a deterministic combination of hook, tone, format, length, CTA for this topic.
        Ensures same topic + letter always gets same combo (for consistency in testing),
        but different topics/letters get different combos (for variety).
        """
        seed_str = f"{topic_id}_{variant_letter}"
        seed_hash = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)

        rng = random.Random(seed_hash)

        hook = rng.choice(HOOK_VARIANTS)
        tone = rng.choice(TONE_VARIANTS)
        fmt = rng.choice(FORMAT_VARIANTS)
        length = rng.choice(LENGTH_VARIANTS)
        cta = rng.choice(CTA_VARIANTS)

        return hook, tone, fmt, length, cta

    def _get_topic_best_variant(self, topic_id: str) -> Optional[str]:
        """
        Find which variant (A, B, C) performed best for this topic in history.
        Returns variant letter of highest engagement, or None.
        """
        topic_variants = [
            v for v in self.memory
            if v.get("topic_id") == topic_id 
            and v.get("performance", {}).get("engagement", {}).get("engagement_rate")
        ]

        if not topic_variants:
            return None

        best = max(
            topic_variants,
            key=lambda v: v.get("performance", {}).get("engagement", {}).get("engagement_rate", 0),
        )
        return best.get("variant_id")

    def _should_favor_winner(self, topic_id: str) -> bool:
        """
        If a variant is clearly winning (engagement_rate > 8%), favor it in future
        posts from this topic. Otherwise, keep rotating through A/B/C.
        """
        best_variant = self._get_topic_best_variant(topic_id)
        if not best_variant:
            return False

        topic_variants = [
            v for v in self.memory[-20:]  # Recent posts only
            if v.get("topic_id") == topic_id
        ]
        if len(topic_variants) < 3:
            return False  # Need at least 3 posts to declare a winner

        best_engagement = max(
            [
                v.get("performance", {}).get("engagement", {}).get("engagement_rate", 0)
                for v in topic_variants
                if v.get("variant_id") == best_variant
            ],
            default=0,
        )

        return best_engagement > 8.0  # Arbitrarily threshold for "winning"

    def generate_variants(
        self,
        topic: Dict,
        from_agent_generator=None,  # Optional callable: (prompt, system) -> str
        num_variants: int = 3,
    ) -> List[ABTestVariant]:
        """
        Generate N variants of a post for A/B testing.
        
        Args:
            topic: Topic dict with id, name, prompt, etc.
            from_agent_generator: Function that generates post text given (prompt, system) tuple
            num_variants: How many variants to create (typically 3 for A/B/C)
        
        Returns:
            List of ABTestVariant objects, one for each letter (A, B, C, ...)
        """
        variants = []
        topic_id = topic.get("id", "unknown")

        log.info(f"Generating {num_variants} post variants for topic: {topic_id}")

        for i, variant_letter in enumerate(["A", "B", "C"][:num_variants]):
            hook_style, tone, fmt, length, cta = self._select_variant_combo(topic_id, variant_letter)

            # Build generation prompt
            prompt = self._build_variant_prompt(topic, hook_style, tone, fmt, length, cta)

            # Generate post text (use agent generator if provided, else use stub)
            if from_agent_generator:
                try:
                    post_text = from_agent_generator(prompt, "")
                except Exception as e:
                    log.warning(f"Generator failed for variant {variant_letter}: {e}")
                    post_text = self._fallback_post_text(topic, variant_letter)
            else:
                post_text = self._fallback_post_text(topic, variant_letter)

            variant = ABTestVariant(
                topic=topic,
                text=post_text,
                variant_id=variant_letter,
                hook_style=hook_style,
                tone=tone,
                format_style=fmt,
                length=length,
                cta_style=cta,
            )
            variants.append(variant)
            log.info(f"  Variant {variant_letter}: {hook_style} + {tone} + {fmt}")

        return variants

    def _build_variant_prompt(
        self,
        topic: Dict,
        hook_style: str,
        tone: str,
        fmt: str,
        length: str,
        cta: str,
    ) -> str:
        """Build Groq prompt for specific variant combo."""
        hook_guidance = self._hook_guidance(hook_style)
        tone_guidance = self._tone_guidance(tone)
        fmt_guidance = self._format_guidance(fmt)
        length_guidance = self._length_guidance(length)
        cta_guidance = self._cta_guidance(cta)

        return f"""\
Topic: {topic.get("prompt", topic.get("name", ""))}

Generate a LinkedIn post with these specific characteristics:

HOOK: {hook_guidance}
TONE: {tone_guidance}
FORMAT: {fmt_guidance}
LENGTH: {length_guidance}
CTA: {cta_guidance}

Post must:
- Be between 140 and 340 words
- Include exactly one fenced visual block (3-6 lines)
- End with the CTA style above
- Use 4-7 hashtags
- NOT use forced claims, metrics, or tool names not in the topic
- Sound like a real engineer wrote it (no corporate speak)
"""

    def _fallback_post_text(self, topic: Dict, variant: str) -> str:
        """Fallback post text if generation fails."""
        return f"""\
{topic.get("name", "Topic")} requires a different mindset in production. 🧠

Variant {variant}: Most teams approach this reactively, then optimize based on what breaks. 
Instead, the high-performing teams build with trade-offs visible from day one. 📊

Each choice has a cost: speed vs reliability, flexibility vs maintainability. 
Pick based on what matters most right now. 🎯

```text
Choice → Trade-off → Cost → Benefit
```

💬 What's your biggest constraint when making this call?

#Engineering #SystemDesign #Architecture #TechLeadership #SoftwareArchitecture
"""

    @staticmethod
    def _hook_guidance(style: str) -> str:
        guidance_map = {
            "incident": "Open with a specific incident or failure moment",
            "stat": "Lead with one surprising, counterintuitive statistic",
            "myth": "Name a wrong belief, then immediately correct it",
            "quote": "Start with a quote from a code review or Slack conversation",
            "admission": "Begin with an honest admission of past mistake",
            "claim": "Lead with a confident, slightly controversial claim",
            "gap": "Start with 'Nobody talks about X'",
            "evolution": "Show the delta: how it was 3-5 years ago vs today",
        }
        return guidance_map.get(style, "Make a strong, specific claim")

    @staticmethod
    def _tone_guidance(style: str) -> str:
        guidance_map = {
            "engineer_11pm": "Senior engineer at 11pm fixing production — direct, economical, dark humor",
            "tech_lead": "Tech lead writing post-mortem — precise, owns mistakes, owns next",
            "principal": "Principal engineer in design review — thoughtful, asks hard questions",
            "staff_mentoring": "Staff engineer mentoring — patient, uses analogies, skips nothing",
            "tried_four_times": "Engineer who tried 4 approaches and found one that works",
            "hallway_talk": "Best hallway talk at conference — opinionated, concrete examples",
        }
        return guidance_map.get(style, "Sound like a real engineer")

    @staticmethod
    def _format_guidance(style: str) -> str:
        guidance_map = {
            "numbered": "Use numbered sections (1️⃣ 2️⃣ etc), 2-3 sentences per section",
            "prose": "No numbers. Short paragraphs (2-3 sentences), story flow",
            "before_after": "Structure around contrast: how vs what actually works",
            "myth_reality": "Each section: Myth → Reality. Keep tight.",
        }
        return guidance_map.get(style, "Organize for readability")

    @staticmethod
    def _length_guidance(style: str) -> str:
        guidance_map = {
            "tight": "Keep it tight: 150-200 words. Every sentence earns its place.",
            "medium": "Medium length: 220-280 words. Enough to teach, not boring.",
            "full": "Full breakdown: 280-340 words. Go deep on most interesting section.",
        }
        return guidance_map.get(style, "200-280 words")

    @staticmethod
    def _cta_guidance(style: str) -> str:
        guidance_map = {
            "direct_poll": "End with: 💬 + direct question + numbered options (1️⃣ 2️⃣ 3️⃣)",
            "open_question": "End with: 💬 + open-ended question inviting personal experience",
            "metric_poll": "End with: 💬 + 'Which matters most?' + ranked options",
            "experience_share": "End with: 💬 + 'Have you seen this?' + yes/no/other options",
            "advice_seek": "End with: 💬 + 'What would you do?' + open reflection prompt",
        }
        return guidance_map.get(style, "End with 💬 + genuine question")

    def record_post(
        self,
        variant: ABTestVariant,
        linkedin_post_id: Optional[str] = None,
    ) -> None:
        """Record that a variant was posted and track its LinkedIn ID."""
        variant.posted_at = datetime.now().isoformat()
        if linkedin_post_id:
            variant.linkedin_post_id = linkedin_post_id

        self.memory.append(variant.to_dict())
        self._save_memory()

    def update_engagement(
        self,
        topic_id: str,
        variant_id: str,
        likes: int = 0,
        comments: int = 0,
        shares: int = 0,
        impressions: int = 0,
    ) -> None:
        """Update engagement metrics for a posted variant."""
        for entry in reversed(self.memory):
            if entry.get("topic_id") == topic_id and entry.get("variant_id") == variant_id:
                total_engagement = likes + comments + (shares * 2)  # Weight shares higher
                engagement_rate = (total_engagement / max(impressions, 1)) * 100 if impressions else 0

                entry["performance"]["engagement"] = {
                    "likes": likes,
                    "comments": comments,
                    "shares": shares,
                    "impressions": impressions,
                    "total_engagement": total_engagement,
                    "engagement_rate": round(engagement_rate, 2),
                }
                entry["performance"]["updated_at"] = datetime.now().isoformat()
                self._save_memory()
                log.info(
                    f"Updated engagement for {topic_id}/{variant_id}: "
                    f"{total_engagement} engagements, {engagement_rate:.2f}% rate"
                )
                return

    def get_topic_leaderboard(self, topic_id: str, limit: int = 10) -> List[Dict]:
        """
        Get top-performing variants for a topic, ranked by engagement rate.
        Useful for understanding which combinations work best.
        """
        topic_variants = [
            v for v in self.memory
            if v.get("topic_id") == topic_id
            and v.get("performance", {}).get("engagement", {}).get("engagement_rate")
        ]

        sorted_variants = sorted(
            topic_variants,
            key=lambda v: v.get("performance", {}).get("engagement", {}).get("engagement_rate", 0),
            reverse=True,
        )

        leaderboard = []
        for variant in sorted_variants[:limit]:
            engagement = variant.get("performance", {}).get("engagement", {})
            leaderboard.append({
                "variant_id": variant.get("variant_id"),
                "posted_at": variant.get("metadata", {}).get("posted_at"),
                "hook_style": variant.get("metadata", {}).get("hook_style"),
                "tone": variant.get("metadata", {}).get("tone"),
                "format": variant.get("metadata", {}).get("format"),
                "engagement_rate": engagement.get("engagement_rate", 0),
                "total_engagement": engagement.get("total_engagement", 0),
                "impressions": engagement.get("impressions", 0),
            })

        return leaderboard


def main():
    """Demo: Generate variants for a sample topic."""
    harness = ABTestHarness()

    sample_topic = {
        "id": "llm-vs-agents",
        "name": "LLM vs AI Agents",
        "prompt": "The differences between LLMs, Generative AI, AI Agents, and Agentic AI systems",
        "angle": "Practical execution differences in production",
    }

    log.info("Generating 3 A/B test variants...")
    variants = harness.generate_variants(sample_topic, num_variants=3)

    for variant in variants:
        print(f"\n{'='*60}")
        print(f"VARIANT {variant.variant_id}")
        print(f"  Hook:   {variant.hook_style}")
        print(f"  Tone:   {variant.tone}")
        print(f"  Format: {variant.format_style}")
        print(f"  Length: {variant.length}")
        print(f"  CTA:    {variant.cta_style}")
        print(f"{'='*60}")
        print(variant.text)
        print()


if __name__ == "__main__":
    main()
