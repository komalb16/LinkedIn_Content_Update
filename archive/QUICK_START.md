# LinkedIn Agent Enhancements - Quick Start Checklist

Use this checklist to integrate the three improvements into your system.

---

## ✅ Phase 1: Setup & Install (10 minutes)

- [ ] Install additional dependency: `pip install pynacl` (for token encryption)
- [ ] OR update requirements: `cat requirements-enhanced.txt >> requirements.txt`
- [ ] Verify imports work: 
  ```bash
  cd src
  python -c "from token_manager import TokenManager; print('✅ token_manager OK')"
  python -c "from ab_testing import ABTestHarness; print('✅ ab_testing OK')"
  python -c "from analytics import AnalyticsTracker; print('✅ analytics OK')"
  ```

---

## ✅ Phase 2: Token Refresh Automation (5 minutes)

### GitHub Secrets Setup
Go to **Repo → Settings → Secrets and variables → Actions**

Add these secrets (get values from LinkedIn Developer Portal):
- [ ] `LINKEDIN_CLIENT_ID` → Your app's client ID
- [ ] `LINKEDIN_CLIENT_SECRET` → Your app's client secret  
- [ ] `LINKEDIN_TOKEN_DATE` → Today's date in YYYY-MM-DD format (e.g., 2026-04-06)
- [ ] `LINKEDIN_REFRESH_TOKEN` → (Optional) OAuth refresh token

### Create GitHub Action Workflow

Create file: `.github/workflows/token-check.yml`

```yaml
name: Check LinkedIn Token Expiry

on:
  schedule:
    - cron: "0 9 * * MON"  # Every Monday at 9 AM UTC
  workflow_dispatch:

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

- [ ] Commit and push this file
- [ ] Test manually: Navigate to **Actions** tab and click "Run workflow"
- [ ] Check output to verify token status

---

## ✅ Phase 3: A/B Testing Setup (15 minutes)

### Basic Integration

In your `src/agent.py` main function, replace single post generation:

**Before:**
```python
post_text = generate_topic_post(topic, structure, diagram_type)
```

**After:**
```python
from ab_testing import ABTestHarness

ab_harness = ABTestHarness()
variants = ab_harness.generate_variants(topic, num_variants=3)
chosen_variant = variants[0]  # Always post A for now (deterministic)
post_text = chosen_variant.text

# After successfully posting
post_id = linkedin_poster.post_id  # Get from LinkedIn API response
ab_harness.record_post(chosen_variant, linkedin_post_id=post_id)
```

- [ ] Test locally: `python src/ab_testing.py` (should show 3 variants)
- [ ] Verify `.ab_memory.json` is created with variant history
- [ ] Next 3 posts should have different variant combos

---

## ✅ Phase 4: Analytics Tracking (15 minutes)

### Integration

In your `src/agent.py`, after posting successfully:

```python
from analytics import AnalyticsTracker

tracker = AnalyticsTracker()
tracker.log_post_published(
    post_id=post_id,
    topic_id=topic["id"],
    topic_name=topic["name"],
    variant_id=chosen_variant.variant_id if hasattr(chosen_variant, 'variant_id') else None,
    post_text=post_text,
)
```

### Record Engagement

Create a separate workflow or script to update engagement metrics. For now, do this manually:

```python
# src/update_analytics.py (new file)

from analytics import AnalyticsTracker

tracker = AnalyticsTracker()
tracker.record_engagement(
    post_id="urn:li:share:XXXXX",  # Your post ID
    likes=45,
    comments=12,
    shares=5,
    impressions=850,
)

# Print insights
summary = tracker.get_performance_summary(days=7)
print(f"Last 7 days: {summary['avg_engagement_rate']:.2f}% engagement")

timing = tracker.get_posting_time_analysis(days=30)
print(f"Best hour: {timing['best_hour']}")
print(f"Best day: {timing['best_day_of_week']}")
```

- [ ] Test locally: `python src/update_analytics.py`
- [ ] Verify `.analytics.json` created
- [ ] Check summary output is sensible

---

## ✅ Testing Everything Together

### Local Test Run

```bash
cd src

# 1. Test token manager
echo "=== Testing Token Manager ==="
python << 'EOF'
from token_manager import TokenManager
manager = TokenManager()
status = manager.get_status()
print(f"Status: {status['status']}")
print(f"Days remaining: {status['days_remaining']}")
EOF

# 2. Test A/B testing
echo "=== Testing A/B Testing ==="
python << 'EOF'
from ab_testing import ABTestHarness
harness = ABTestHarness()
topic = {"id": "test", "name": "Test Topic", "prompt": "Test"}
variants = harness.generate_variants(topic, num_variants=3)
for v in variants:
    print(f"Variant {v.variant_id}: {v.hook_style} + {v.tone}")
EOF

# 3. Test analytics
echo "=== Testing Analytics ==="
python << 'EOF'
from analytics import AnalyticsTracker
tracker = AnalyticsTracker()
tracker.log_post_published("test-post-1", topic_id="test", topic_name="Test", variant_id="A", post_text="Test")
tracker.record_engagement("test-post-1", likes=50, comments=10, shares=5, impressions=1000)
summary = tracker.get_performance_summary(days=1)
print(f"Avg engagement rate: {summary['avg_engagement_rate']:.2f}%")
EOF
```

- [ ] All three tests run without errors
- [ ] Files `.ab_memory.json` and `.analytics.json` created
- [ ] Output shows expected values

---

## ✅ Deploy to Production

### Commit & Push

```bash
# Add new files
git add src/token_manager.py src/ab_testing.py src/analytics.py
git add .github/workflows/token-check.yml
git add INTEGRATION_GUIDE.md IMPLEMENTATION_SUMMARY.md requirements-enhanced.txt
git commit -m "feat: add token refresh, A/B testing, and analytics"
git push
```

- [ ] All files committed and pushed to main branch
- [ ] GitHub Actions tab shows workflow available

### Enable GitHub Pages (if not already enabled)

For dashboard analytics display:
- [ ] Go to **Settings → Pages**
- [ ] Set source to **Deploy from a branch → main (root)**
- [ ] Confirm Pages is active

### Monitor First Post

- [ ] Next post should include A/B variant tracking
- [ ] Check GitHub Actions: **token-check** runs on Monday
- [ ] Verify `.ab_memory.json` and `.analytics.json` updated after posts

---

## ✅ Ongoing Operations

### Weekly
- [ ] Monday: Check GitHub Actions for token check results
  - Navigate to **Actions → Check LinkedIn Token Expiry**
  - Verify status (should be GREEN ✅)
  - If YELLOW or RED, take action immediately
- [ ] Update engagement metrics (manual copy from LinkedIn for now)

### Monthly
- [ ] Review `IMPLEMENTATION_SUMMARY.md` → Recommended Next Steps
- [ ] Run analytics query: `python src/analytics.py` 
- [ ] Identify best-performing topics and posting times
- [ ] Update `schedule_config.json` based on insights

### As Data Accumulates (Week 3+)
- [ ] Check A/B leaderboard: `python src/ab_testing.py`
- [ ] Identify winning variant for each topic
- [ ] Update variant selection logic to favor winners

---

## ✅ Debugging

### If token check fails
```bash
cd src
python token_manager.py
# Check output for specific error
# Common: LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET missing or wrong
```

### If A/B variants not generating
```bash
cd src
python ab_testing.py
# Should show 3 variants with different combos
# If error: check call_ai is working (same as existing agent.py)
```

### If analytics not saving
```bash
# Check file permissions
ls -l src/.analytics.json src/.ab_memory.json

# Check disk space
df -h

# Try manual write
cd src && python -c "from analytics import AnalyticsTracker; t = AnalyticsTracker(); print('OK')"
```

### Review logs in GitHub Actions
- [ ] Go to **repo → Actions → [workflow name]**
- [ ] Click latest run
- [ ] Check "Run token check" step for output
- [ ] Look for error messages or warnings

---

## ✅ Quick Reference

| Command | Purpose |
|---------|---------|
| `python src/token_manager.py` | Check token status |
| `python src/ab_testing.py` | Generate sample variants |
| `python src/analytics.py` | Test analytics tracking |
| `git add src/*.py .github/` | Stage new files |
| Queue: GitHub **Actions** tab | Monitor workflows |

---

## Expected Results After Implementation

### Day 1
- ✅ All modules imported successfully
- ✅ No errors in local test runs
- ✅ Files committed and pushed

### Week 1
- ✅ 5-10 posts published with A/B variants
- ✅ `.ab_memory.json` shows variant tracking
- ✅ Manual engagement data entered
- ✅ `.analytics.json` shows first posts

### Week 2-3
- ✅ 15-20 posts with engagement data
- ✅ First patterns visible (best day/hour emerging)
- ✅ Variant performance visible (A vs B vs C)

### Month 2+
- ✅ Data-driven optimization underway
- ✅ Posting times adjusted based on analytics
- ✅ Topic mix optimized based on engagement
- ✅ Winning variants favored going forward

---

## Support

- 📖 **INTEGRATION_GUIDE.md** — Detailed setup & examples
- 📖 **IMPLEMENTATION_SUMMARY.md** — High-level overview
- 📝 **Module docstrings** — API reference (`src/*.py`)
- 🧪 **Module demos** — Example usage (end of each `.py` file)

---

## Final Checklist

- [ ] All GitHub Secrets added
- [ ] GitHub Action workflow created
- [ ] Dependencies installed
- [ ] Local tests pass
- [ ] Files committed and pushed
- [ ] First post generated with A/B variant
- [ ] First engagement metrics recorded
- [ ] Analytics queries work
- [ ] Dashboard displays correctly
- [ ] You're ready to optimize! 🚀

---

**Total time to complete**: ~45 minutes  
**Difficulty level**: Low (copy-paste from this checklist)  
**Breaking changes**: None (fully backward compatible)

Good luck! 🎉
