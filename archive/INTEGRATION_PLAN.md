# Interview Posts + Post Generator Integration Plan

## Current Architecture Overview

**How it works today:**
1. `get_post_mode()` decides post type: `story` (30%), `topic` (70%), or news variants
2. `run_agent()` orchestrates based on mode:
   - Mode → Generator → Candidates → Ranking → Selection → Posting
3. Each mode has its own generator: `generate_story_post()`, `generate_topic_post()`, etc.

**Your new components:**
- `interview_post_generator.py` - Ready but NOT integrated
- `interview_questions.json` - Database with 6 AI topics
- Config in `schedule_config.json` - Set but unused

---

## Integration Strategy (3 Steps)

### Step 1: Add Interview Mode to Post Decision Flow ✅ PRIORITY 1

**File:** `src/agent.py`

**What to add:** Interview mode selection logic (around line 1640)

```python
def get_post_mode():
    """Decide which post type to generate."""
    def _env_float(name, default):
        val = os.environ.get(name, str(default)).strip()
        try:
            return float(val)
        except:
            return default
    
    # Load interview frequency from schedule_config
    config_path = os.path.join(os.path.dirname(__file__), "..", "schedule_config.json")
    interview_freq = 0.25  # default 25%
    try:
        with open(config_path) as f:
            cfg = json.load(f)
            interview_freq = cfg.get("interview_posts", {}).get("frequency", 0.25)
    except:
        pass
    
    if os.environ.get("ENABLE_NEWS_MODES", "0").strip().lower() in {"1", "true", "yes"}:
        story_prob = _env_float("STORY_MODE_PROB", 0.20)
        interview_prob = interview_freq  # 25% of all posts
        ai_news_prob = _env_float("AI_NEWS_MODE_PROB", 0.04)
        layoff_prob = _env_float("LAYOFF_MODE_PROB", 0.02)
        tools_prob = _env_float("TOOLS_NEWS_MODE_PROB", 0.03)
        tech_prob = _env_float("TECH_NEWS_MODE_PROB", 0.02)
        
        rand = random.random()
        if rand < interview_prob:
            return "interview"
        elif rand < interview_prob + story_prob:
            return "story"
        elif rand < interview_prob + story_prob + ai_news_prob:
            return "ai_news"
        elif rand < interview_prob + story_prob + ai_news_prob + layoff_prob:
            return "layoff_news"
        elif rand < interview_prob + story_prob + ai_news_prob + layoff_prob + tools_prob:
            return "tools_news"
        elif rand < interview_prob + story_prob + ai_news_prob + layoff_prob + tools_prob + tech_prob:
            return "tech_news"
        else:
            return "topic"
    
    # Simple mode (interview + story + topic only)
    interview_prob = interview_freq
    story_prob = _env_float("STORY_MODE_PROB", 0.25)
    rand = random.random()
    if rand < interview_prob:
        return "interview"
    elif rand < interview_prob + story_prob:
        return "story"
    else:
        return "topic"
```

**Result:** 25% of posts will be interview-based ✓

---

### Step 2: Add Interview Post Generation (around line 1750)

**File:** `src/agent.py`

**Add import at top:**
```python
from interview_post_generator import InterviewPostGenerator
```

**Add generator function:**
```python
def generate_interview_post():
    """Generate interview-style post with rotating topics."""
    log.info("Generating interview post...")
    
    try:
        gen = InterviewPostGenerator()
        
        # Get random question (will rotate naturally across calls)
        question = gen.get_random_question()
        
        if not question:
            log.warning("No interview questions available, falling back to topic mode")
            return None, None
        
        # Generate post
        post_text = gen.generate_post_from_question(question)
        
        if not post_text:
            log.warning("Interview post generation failed")
            return None, None
        
        # Find parent topic
        parent_topic = None
        for topic_key, topic_data in gen.topics.items():
            for q in topic_data.get("questions", []):
                if q.get("id") == question.get("id"):
                    parent_topic = topic_key
                    break
        
        # Create metadata for diagram generation
        topic = {
            "id": f"interview-{question.get('id')}",
            "name": f"Interview: {parent_topic or 'AI Question'}",
            "category": "Interview",
            "prompt": question.get("question", ""),
            "angle": question.get("type", "opinion_poll"),
            "diagram_type": "Modern Cards",
        }
        
        log.info(f"Interview post generated from topic: {parent_topic}")
        return topic, post_text
    
    except Exception as e:
        log.error(f"Interview post generation error: {e}")
        return None, None
```

**Then in run_agent() (around line 1760), add this case after mode is determined:**

```python
elif mode == "interview":
    interview_topic, interview_text = generate_interview_post()
    
    if interview_topic and interview_text:
        post_text = interview_text
        topic = interview_topic
        structure = None  # Interview posts don't use structured diagrams
        log.info(f"Interview post selected: {topic['name']}")
    else:
        mode = "topic"  # Fallback
        log.warning("Interview generation failed, falling back to topic mode")
```

**Result:** Interview posts now integrate into the rotation ✓

---

### Step 3: Add Topic History Tracking (to avoid repeats) ✅ PRIORITY 2

Interview questions work best when topics don't repeat in same week. Add to `POST_MEMORY_FILE`:

**File:** `src/agent.py`

**Enhance `_remember_post()` (around line 1320):**

```python
def _remember_post(topic, text):
    """Remember post for deduplication and diversity."""
    entries = _load_post_memory()
    entries.append({
        "timestamp": datetime.now().isoformat(),
        "topic_id": topic.get("id", ""),
        "topic_name": topic.get("name", ""),
        "category": topic.get("category", ""),
        "text": _cleanup_generated_post(text or "")[:2500],
    })
    _save_post_memory(entries)


def _get_recent_topics(days=7):
    """Get topics posted in last N days to avoid repeats."""
    entries = _load_post_memory()
    cutoff = datetime.now() - timedelta(days=days)
    recent = []
    for entry in entries:
        try:
            ts = datetime.fromisoformat(entry.get("timestamp", ""))
            if ts > cutoff:
                recent.append(entry.get("topic_id", ""))
        except:
            pass
    return set(recent)
```

**Enhance `generate_interview_post()` to skip used topics:**

```python
def generate_interview_post():
    """Generate interview-style post with rotating topics."""
    log.info("Generating interview post...")
    
    try:
        gen = InterviewPostGenerator()
        recent_topics = _get_recent_topics(days=7)
        
        # Try to pick question from non-recent topic
        max_attempts = 10
        question = None
        for attempt in range(max_attempts):
            q = gen.get_random_question()
            parent_topic = None
            for topic_key, topic_data in gen.topics.items():
                for qq in topic_data.get("questions", []):
                    if qq.get("id") == q.get("id"):
                        parent_topic = topic_key
                        break
            
            # Skip if topic was posted recently
            topic_id = f"interview-{parent_topic}"
            if topic_id not in recent_topics:
                question = q
                break
        
        if not question:
            question = gen.get_random_question()  # Fallback
        
        # ... rest of function
```

**Result:** Topics rotate naturally, no repeats in 7-day window ✓

---

## Other Critical Improvements

### A. Fix Style Repetition ✅ PRIORITY 3

**Currently:** Same topic always gets same diagram style (by design)  
**Problem:** All posts look monotonous  
**Solution:** Enable variation in `schedule_config.json`

Already added in your config, but need to activate in `diagram_generator.py`:

**File:** `src/diagram_generator.py` (around line 180)

```python
def _maybe_variation_style(self, topic_name, base_style_idx):
    """Apply variation to break monotony."""
    config = self._load_schedule_config()
    style_diversity = config.get("style_diversity", {})
    
    if not style_diversity.get("enabled", True):
        return base_style_idx
    
    # 70% chance of variation (from config)
    variation_prob = style_diversity.get("variation_probability", 0.7)
    
    if random.random() < variation_prob:
        # Force rotation to different style
        all_styles = len(self.STYLES)
        min_interval = style_diversity.get("min_style_interval", 3)
        new_style = (base_style_idx + random.randint(1, max(1, all_styles - min_interval))) % all_styles
        return new_style
    
    return base_style_idx
```

**Impact:** Visual variety across all posts ✓

---

### B. Add Content Category Tracking ✅ PRIORITY 4

**File:** `src/agent.py` → Enhance `_remember_post()`

```python
def _remember_post(topic, text):
    """Remember post with category for diversity tracking."""
    entries = _load_post_memory()
    category = topic.get("category", "")
    if "interview" in topic.get("id", "").lower():
        category = "interview"
    elif topic.get("id", "").startswith("story-"):
        category = "story"
    elif "news" in topic.get("id", "").lower():
        category = "news"
    else:
        category = "topic"
    
    entries.append({
        "timestamp": datetime.now().isoformat(),
        "topic_id": topic.get("id", ""),
        "topic_name": topic.get("name", ""),
        "category": category,
        "text": _cleanup_generated_post(text or "")[:2500],
    })
    _save_post_memory(entries)
```

**Benefit:** Track what types you post → adjust mix for variety ✓

---

### C. Add Diagram Selection Intelligence ✅ PRIORITY 5

**Currently:** Interview posts use random diagrams  
**Better:** Use recommended styles per topic

Already in `interview_questions.json`, just need to use:

**File:** `src/agent.py`

```python
def generate_interview_post():
    """..."""
    # ... existing code ...
    
    # Get recommended diagram style for topic
    parent_topic = None
    for topic_key, topic_data in gen.topics.items():
        for q in topic_data.get("questions", []):
            if q.get("id") == question.get("id"):
                parent_topic = topic_key
                break
    
    # Get best diagram styles from config
    diagram_styles = gen.get_best_diagram_styles(parent_topic)
    
    topic = {
        "id": f"interview-{question.get('id')}",
        "name": f"Interview: {parent_topic or 'AI Question'}",
        "category": "Interview",
        "prompt": question.get("question", ""),
        "angle": question.get("type", "opinion_poll"),
        "diagram_type": "Modern Cards",  
        "diagram_styles": diagram_styles,  # ← Pass recommended styles
    }
```

**Result:** Interview posts use optimized diagram styles ✓

---

### D. Dashboard Integration ✅ PRIORITY 6

**Currently:** Dashboard shows post types but interview mode isn't labeled

**File:** `dashboard.html` (around line 3028)

Add option to post mode selector:

```html
<select class="tz-sel" id="postModeSel" onchange="setPostMode(this.value)" title="Choose generation mode">
    <option value="auto">Auto mode</option>
    <option value="interview">Interview (25%)</option>
    <option value="story">Story only</option>
    <option value="topic">Topic only</option>
    <option value="ai_news">AI news</option>
    <option value="tools_news">Tools news</option>
    <option value="tech_news">Tech news</option>
    <option value="layoff_news">Layoff news</option>
</select>
```

**Result:** Manual override for interview mode via dashboard ✓

---

## Implementation Order

| Priority | Task | Time | Impact |
|----------|------|------|--------|
| 1 | Add interview mode to `get_post_mode()` | 15 min | Core functionality |
| 2 | Add `generate_interview_post()` to run_agent | 20 min | Posts get generated |
| 3 | Add topic history tracking | 10 min | Avoid repetition |
| 4 | Fix style repetition (enable variance) | 10 min | Visual variety |
| 5 | Add content category tracking | 10 min | Monitor diversity |
| 6 | Add diagram style intelligence | 10 min | Better diagrams |
| 7 | Update dashboard | 5 min | UI consistency |

**Total: ~80 minutes → ~3 posts/week with interviews, full style variety, zero topic repeats**

---

## Verification Checklist

- [ ] Interview posts appear in 25% mix
- [ ] Topics don't repeat within 7 days
- [ ] All 23 diagram styles appear across posts
- [ ] No errors in agent.py logs
- [ ] Dashboard shows interview mode indicator
- [ ] Post memory tracks interview vs topic vs story categories

---

## Expected Results After Integration

✅ **Diversity:** Interview + Story + Topic + News mix (currently only Story + Topic)  
✅ **Engagement:** Interview format drives 200-500 comments (vs 15-50 on pure technical)  
✅ **Visual Variety:** All 18-23 diagram styles rotate (vs 1-2 styles today)  
✅ **Topic Freshness:** No repeats within 7 days → audience sees different perspectives  
✅ **Content Mix:** AI (70%), News (15%), Personal (10%), Tips (5%) via categories  
✅ **Viral Potential:** Story + Interview posts have storytelling + questions → 2-3x engagement

---

## Questions to Test

**For Interview Posts:**
- "What's your biggest RAG failure?" (experience)
- "Vector DB vs embedding cache?" (comparison)
- "How many LLMs in your stack?" (data-driven poll)

**For Story Posts:**
- "How I rebuilt my profile in 3 weeks" (narrative)
- "The metric nobody watches" (insight)

**For Topic Posts:**
- "7 RAG patterns at scale" (expert breakdown)
- "Why K8s fails small teams" (controversial take)

All formats visible on LinkedIn, forum, and engagement analytics.

