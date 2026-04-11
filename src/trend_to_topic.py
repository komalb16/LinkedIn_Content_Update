"""
trend_to_topic.py — Convert raw trending titles into structured topic dicts
that are compatible with the existing topic/post generation pipeline.
"""

import re
import json
from logger import get_logger

log = get_logger("trend_to_topic")

CONVERT_SYSTEM = """\
You are a content strategist for a Staff Engineer LinkedIn account.
Your job is to turn trending tech news titles into structured post topics
written from the perspective of a senior engineer with practical opinions.

RULES:
- The angle must be practical and production-focused, NOT news reporting
- Avoid generic angles like "what this means for engineers"
- Pick a specific technical sub-angle that engineers will find useful
- diagram_type must be one of: Modern Cards, Flow Chart, Comparison Table, Architecture Diagram
- Respond ONLY with valid JSON — no preamble, no markdown fences, no explanation
"""


def convert_trend_to_topic(trend_item, call_ai_fn):
    """
    Convert a raw trending title into a structured topic dict.
    Returns a topic dict or None if conversion fails.
    """
    title = trend_item.get("title", "")
    source = trend_item.get("source", "internet")

    prompt = f"""Trending topic: "{title}"
Source: {source}

Convert this into a LinkedIn post topic for a Staff Engineer audience.
Respond ONLY with this exact JSON structure, no other text:
{{
  "id": "kebab-case-unique-id-max-5-words",
  "name": "Short Display Name (3-6 words)",
  "category": "topic",
  "prompt": "One sentence describing what the post should teach or argue",
  "angle": "The specific practical angle — what engineers get wrong or what actually works in production",
  "diagram_type": "Modern Cards",
  "diagram_subject": "What the diagram should visually show (3-5 items connected by arrows or columns)"
}}"""

    try:
        raw = call_ai_fn(prompt, CONVERT_SYSTEM)
        # Strip any accidental markdown fences
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        # Find JSON object in response
        match = re.search(r"\{[\s\S]+\}", clean)
        if not match:
            log.warning(f"No JSON found in trend conversion response for: {title}")
            return None
        topic = json.loads(match.group(0))
        # Validate required fields
        required = ("id", "name", "prompt", "angle", "diagram_type")
        if not all(topic.get(k) for k in required):
            log.warning(f"Incomplete topic from trend conversion: {topic}")
            return None
        # Prefix ID to mark as trending
        topic["id"] = f"trend-{topic['id']}"
        topic["category"] = "topic"
        log.info(f"Converted trend to topic: {topic['name']} (id: {topic['id']})")
        return topic
    except json.JSONDecodeError as e:
        log.warning(f"JSON parse failed for trend '{title}': {e}")
        return None
    except Exception as e:
        log.warning(f"Trend conversion failed for '{title}': {e}")
        return None


def pick_best_trend(trends, recent_topic_ids, call_ai_fn, max_attempts=5):
    """
    Try converting trends in order of score until one succeeds and
    hasn't been posted recently.
    Returns (topic_dict, trend_item) or (None, None).
    """
    for trend in trends[:max_attempts]:
        topic = convert_trend_to_topic(trend, call_ai_fn)
        if not topic:
            continue
        if topic["id"] in recent_topic_ids:
            log.info(f"Skipping recently posted trend: {topic['id']}")
            continue
        return topic, trend
    log.warning("No suitable trending topic found after max_attempts")
    return None, None