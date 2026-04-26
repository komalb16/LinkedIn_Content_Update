"""
analytics_engine.py - Tracks post performance and optimizes topic weights.
"""
import json
import os
from pathlib import Path
from datetime import datetime

DATA_FILE = Path(__file__).resolve().parent / "analytics_data.json"

def record_post_metadata(topic_id, score, mode):
    """Initializes tracking for a new post."""
    data = _load_data()
    post_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    data["posts"][post_id] = {
        "topic_id": topic_id,
        "mode": mode,
        "ai_score": score,
        "engagement": 0, # To be updated by external sync or simulated
        "timestamp": datetime.now().isoformat()
    }
    _save_data(data)

def get_optimized_weights():
    """Returns a multiplier dict for topic selection based on performance."""
    data = _load_data()
    weights = {}
    for p_id, p_info in data["posts"].items():
        t_id = p_info["topic_id"]
        # Basic logic: topics with high AI scores or high engagement get a boost
        engagement = p_info.get("engagement", 0)
        boost = 1.0 + (engagement * 0.1)
        weights[t_id] = max(weights.get(t_id, 1.0), boost)
    return weights

def _load_data():
    if not DATA_FILE.exists():
        return {"posts": {}, "topic_scores": {}}
    try:
        return json.loads(DATA_FILE.read_text())
    except:
        return {"posts": {}, "topic_scores": {}}

def _save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2))
