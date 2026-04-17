# LinkedIn Agent - Enhancement Integration Guide

This guide explains how to integrate the three new modules into your existing LinkedIn automation system:

1. **Token Refresh Automation** (`token_manager.py`)
2. **A/B Testing Framework** (`ab_testing.py`)
3. **Analytics & Engagement Tracking** (`analytics.py`)

---

## 1. Token Refresh Automation

### Overview
Automatically refresh LinkedIn access tokens before expiry (60 days) to prevent posting failures.

### Setup

#### Step 1: Add GitHub Secrets
Go to **Repo Settings → Secrets and variables → Actions** and add:

```
LINKEDIN_CLIENT_ID           # From LinkedIn Developer Portal
LINKEDIN_CLIENT_SECRET       # From LinkedIn Developer Portal
LINKEDIN_REFRESH_TOKEN       # OAuth refresh token (if using refresh grant)
LINKEDIN_TOKEN_DATE          # Date token was created (YYYY-MM-DD)
```

> **Note**: LinkedIn access tokens last 60 days. Update `LINKEDIN_TOKEN_DATE` each time you manually refresh the token.

#### Step 2: Add GitHub Action Workflow

Create `.github/workflows/token-check.yml`:

```yaml
name: Check LinkedIn Token Expiry

on:
  schedule:
    - cron: "0 9 * * MON"  # Every Monday at 9 AM UTC
  workflow_dispatch:       # Manual trigger

jobs:
  check-token:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    env:
      LINKEDIN_TOKEN_DATE: ${{ secrets.LINKEDIN_TOKEN_DATE }}
      LINKEDIN_ACCESS_TOKEN: ${{ secrets.LINKEDIN_ACCESS_TOKEN }}
      LINKEDIN_CLIENT_ID: ${{ secrets.LINKEDIN_CLIENT_ID }}
      LINKEDIN_CLIENT_SECRET: ${{ secrets.LINKEDIN_CLIENT_SECRET }}
      LINKEDIN_REFRESH_TOKEN: ${{ secrets.LINKEDIN_REFRESH_TOKEN }}
      GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      GITHUB_REPOSITORY: ${{ github.repository }}

    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt pynacl

      - name: Run token check
        run: cd src && python token_manager.py
```

#### Step 3: Usage in Code

```python
from token_manager import TokenManager

# Check token status
manager = TokenManager()
status = manager.get_status()
print(status)  # {"status": "URGENT", "days_remaining": 5, ...}

# Verify token
if not manager.verify_token_valid():
    success, result = manager.attempt_token_refresh()
    if success:
        manager.update_github_secret("LINKEDIN_ACCESS_TOKEN", result)
        print("✅ Token refreshed and updated")
```

---

## 2. A/B Testing Framework

### Overview
Generate 3 variants (A, B, C) per post with different hooks, tones, formats, and CTAs. Track which combinations drive the best engagement.

### Setup

No additional setup needed. The module is self-contained and generates variants deterministically.

### Usage

#### Basic: Generate 3 Variants

```python
from ab_testing import ABTestHarness

harness = ABTestHarness()

topic = {
    "id": "llm-vs-agents",
    "name": "LLM vs AI Agents",
    "prompt": "The differences between LLMs and AI Agents in production",
    "angle": "Practical execution differences",
}

# Generate 3 variants with different combinations
variants = harness.generate_variants(topic, num_variants=3)

for variant in variants:
    print(f"Variant {variant.variant_id}: {variant.hook_style} + {variant.tone}")
    print(variant.text)
    print()

# Choose which variant to post (or rotate them for testing)
variant_to_post = variants[0]
```

#### Record Posted Variant

```python
# After posting to LinkedIn (when you get the post_id)
post_id = "urn:li:share:12345"  # LinkedIn post ID

harness.record_post(variant_to_post, linkedin_post_id=post_id)
```

#### Track Performance

```python
# Update engagement metrics (typically from LinkedIn API or dashboard)
harness.update_engagement(
    topic_id="llm-vs-agents",
    variant_id="A",
    likes=45,
    comments=12,
    shares=5,
    impressions=850,
)

# Get leaderboard for this topic
leaderboard = harness.get_topic_leaderboard("llm-vs-agents")
for entry in leaderboard:
    print(f"Variant {entry['variant_id']}: {entry['engagement_rate']:.2f}% engagement")
```

#### Integration into agent.py

Add this to your agent's main flow:

```python
from ab_testing import ABTestHarness

# In your main() function, replace single generation with variants:

ab_harness = ABTestHarness()

# Generate 3 variants
variants = ab_harness.generate_variants(
    topic,
    from_agent_generator=call_ai,  # or your post generation function
    num_variants=3,
)

# Choose variant strategy:
# Option 1: Post variant A (deterministic rotation)
chosen_variant = variants[0]

# Option 2: Check if topic has a winner, favor it
best_variant = ab_harness._get_topic_best_variant(topic["id"])
if best_variant:
    chosen_variant = next((v for v in variants if v.variant_id == best_variant), variants[0])
else:
    chosen_variant = variants[0]

# Post the chosen variant
post_text = chosen_variant.text

# After posting successfully
post_id = linkedin_poster.get_post_id()  # From LinkedIn API response
ab_harness.record_post(chosen_variant, linkedin_post_id=post_id)
```

---

## 3. Analytics & Engagement Tracking

### Overview
Track post performance metrics (likes, comments, shares, impressions) and identify patterns for optimization.

### Setup

No additional dependencies needed beyond standard library.

### Usage

#### Log a Published Post

```python
from analytics import AnalyticsTracker

tracker = AnalyticsTracker()

# When you post to LinkedIn
tracker.log_post_published(
    post_id="urn:li:share:12345",
    topic_id="llm-vs-agents",
    topic_name="LLM vs AI Agents",
    variant_id="A",
    post_text=post_text,
    linkedin_url="https://linkedin.com/feed/update/urn:li:share:12345",
)
```

#### Record Engagement (Manual or API)

```python
# Option 1: Manual entry (for testing)
tracker.record_engagement(
    post_id="urn:li:share:12345",
    likes=45,
    comments=12,
    shares=5,
    impressions=850,
)

# Option 2: From LinkedIn API
# (See "Fetch Engagement from LinkedIn API" section below)
```

#### Get Performance Summary

```python
# Last 30 days
summary = tracker.get_performance_summary(days=30)
print(summary)
# Output:
# {
#   "posts_published": 15,
#   "total_impressions": 12500,
#   "avg_engagement_rate": 6.8,
#   "engagement_breakdown": {"high": 5, "good": 7, "average": 3},
#   "best_posts": [...],
#   ...
# }
```

#### Analyze Posting Times

```python
timing = tracker.get_posting_time_analysis(days=60)
print(f"Best hour: {timing['best_hour']}")
print(f"Best day: {timing['best_day_of_week']}")

# Use this to optimize your schedule_config.json
```

#### Get Topic Performance

```python
topic_stats = tracker.get_topic_performance("llm-vs-agents")
print(f"Average engagement: {topic_stats['avg_engagement_rate']:.2f}%")
print(f"Best post: {topic_stats['best_post']['post_id']}")
```

#### Export Analytics

```python
# Export to CSV for external analysis (Excel, Google Sheets, etc.)
tracker.export_csv("analytics_export.csv", days=90)
```

#### Integration into agent.py

```python
from analytics import AnalyticsTracker

tracker = AnalyticsTracker()

# After posting successfully
response = linkedin_poster.post(post_text, diagram_path)
post_id = response.get("id")

tracker.log_post_published(
    post_id=post_id,
    topic_id=topic["id"],
    topic_name=topic["name"],
    variant_id=ab_variant.variant_id if ab_variant else None,
    post_text=post_text,
)

# Periodically (from dashboard or another workflow)
# Fetch engagement and update
tracker.record_engagement(
    post_id=post_id,
    likes=45,
    comments=12,
    shares=5,
    impressions=850,
)
```

---

## 4. Complete Integration Example

Here's how to integrate all three modules into agent.py:

```python
#!/usr/bin/env python3
# src/agent.py (enhanced)

import os
from token_manager import TokenManager
from ab_testing import ABTestHarness
from analytics import AnalyticsTracker
from linkedin_poster import LinkedInPoster

def main():
    # 1. Check token health
    token_mgr = TokenManager()
    status = token_mgr.get_status()
    if status["status"] in ["CRITICAL", "URGENT"]:
        log.warning(f"Token expiring: {status['message']}")
        # Auto-refresh attempt (optional)
        # success, result = token_mgr.attempt_token_refresh()
    
    # 2. Initialize analytics
    tracker = AnalyticsTracker()
    
    # 3. Initialize A/B testing
    ab_harness = ABTestHarness()
    
    # 4. Select topic and generate content
    topic = topic_manager.get_topic()
    
    # 5. Generate 3 variants
    variants = ab_harness.generate_variants(
        topic,
        from_agent_generator=call_ai,
        num_variants=3,
    )
    
    # 6. Choose best performing variant or rotate
    best_variant_id = ab_harness._get_topic_best_variant(topic["id"])
    if best_variant_id:
        chosen = next((v for v in variants if v.variant_id == best_variant_id), variants[0])
    else:
        chosen = variants[0]
    
    # 7. Generate diagram
    diagram_path = diagram_gen.generate(topic, diagram_type)
    
    # 8. Render and post
    final_text = _render_linkedin_text(chosen.text)
    response = linkedin_poster.post(final_text, diagram_path)
    post_id = response.get("id")
    
    # 9. Record in analytics and A/B tracking
    tracker.log_post_published(
        post_id=post_id,
        topic_id=topic["id"],
        topic_name=topic["name"],
        variant_id=chosen.variant_id,
        post_text=chosen.text,
    )
    ab_harness.record_post(chosen, linkedin_post_id=post_id)
    
    log.info(f"✅ Posted variant {chosen.variant_id} for {topic['name']}")

if __name__ == "__main__":
    main()
```

---

## 5. Dashboard Integration

Update your `dashboard.html` to display analytics:

```html
<!-- Add to dashboard.html -->
<section id="analytics-tab">
  <h2>📊 Analytics</h2>
  
  <div id="performance-summary"></div>
  
  <div id="timing-analysis">
    <h3>Best Posting Time</h3>
    <p>Hour: <span id="best-hour">Loading...</span></p>
    <p>Day: <span id="best-day">Loading...</span></p>
  </div>
  
  <div id="topic-leaderboard">
    <h3>Top Topics</h3>
    <table id="topic-table"></table>
  </div>
  
  <div id="ab-leaderboard">
    <h3>Variant Performance</h3>
    <table id="variant-table"></table>
  </div>
</section>

<script>
async function loadAnalytics() {
  const response = await fetch('./.analytics.json');
  const analytics = await response.json();
  
  // Calculate summary
  // Populate DOM
  document.getElementById('performance-summary').innerHTML = summary;
}
</script>
```

---

## 6. GitHub Actions: Scheduled Analytics & A/B Sync

Create `.github/workflows/analytics-sync.yml`:

```yaml
name: Sync Analytics & A/B Results

on:
  schedule:
    - cron: "0 */6 * * *"  # Every 6 hours
  workflow_dispatch:

jobs:
  sync-metrics:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Fetch LinkedIn engagement (placeholder)
        run: |
          cd src
          python << 'EOF'
          from analytics import AnalyticsTracker
          
          tracker = AnalyticsTracker()
          # TODO: Fetch LinkedIn API for updates
          # For now, this just validates the module
          summary = tracker.get_performance_summary(days=7)
          print(summary)
          EOF
      
      - name: Commit updated analytics
        run: |
          git config user.name "LinkedIn Agent"
          git config user.email "bot@example.com"
          git add src/.analytics.json src/.ab_memory.json
          git commit -m "chore: update analytics" || true
          git push
```

---

## 7. LinkedIn API Setup (Optional for Auto Engagement Fetch)

To automatically fetch engagement metrics from LinkedIn:

```python
# In src/linkedin_analytics_sync.py (new file)

import requests

class LinkedInAnalyticsSyncer:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.linkedin.com/v2"
    
    def fetch_post_engagement(self, post_urn: str) -> dict:
        """Fetch likes, comments, shares for a post."""
        # LinkedIn's official engagement API is limited
        # Consider: selenium scraping, third-party tools, or manual entry
        pass

# Note: LinkedIn's official Analytics API is restricted
# Alternatives:
# 1. Manual entry via dashboard
# 2. Selenium web scraping (unofficial)
# 3. Third-party LinkedIn analytics tools
# 4. Export CSV from LinkedIn Creator Mode
```

---

## 8. Recommended Workflow

### Daily
- Agent posts automatically on schedule
- A/B variants rotate deterministically

### Weekly
- Token expiry check runs (Monday morning)
- Analytics summary generated

### Monthly
- Review best-performing topics and variants
- Update `topics_config.json` to prioritize winners
- Adjust posting schedule based on timing analysis
- Export analytics for external reporting

---

## 9. Quick Reference: Module File Sizes

| Module | Lines | Purpose |
|--------|-------|---------|
| `token_manager.py` | ~400 | Token expiry alerts + auto-refresh |
| `ab_testing.py` | ~550 | Generate variants, track performance |
| `analytics.py` | ~600 | Engagement tracking, timing analysis |
| **Total** | **~1550** | Complete analytics + optimization system |

---

## 10. Troubleshooting

### Token Refresh Fails
- Check `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET` are correct
- Verify `LINKEDIN_REFRESH_TOKEN` is valid
- Check GitHub secret update permissions

### A/B Variants Look Too Similar
- Increase variant count or check seed logic in `_select_variant_combo()`
- Each letter (A, B, C) gets a unique deterministic combo per topic

### Analytics Not Updating
- Ensure `record_engagement()` is called with correct post_id
- Check `.analytics.json` file exists and is writable
- Verify JSON format for manual engagement entries

### Engagement Data Not Appearing
- LinkedIn's official API has limited analytics access
- Consider manual entry or web scraping (unofficial)
- Export from LinkedIn Creator Mode analytics dashboard

---

## 11. Next Steps

1. **Add token refresh to GitHub Actions** (prevent 60-day failures)
2. **Switch to A/B variants** in your next 5 posts
3. **Collect engagement data** for 2-3 weeks
4. **Analyze** which hooks, tones, formats drive highest engagement
5. **Optimize** your posting strategy based on data

---

## Questions?

- Review individual module docstrings for detailed API docs
- Check `.py` files for example usage in `if __name__ == "__main__"` blocks
- Test locally: `python src/token_manager.py`, `python src/ab_testing.py`, `python src/analytics.py`
