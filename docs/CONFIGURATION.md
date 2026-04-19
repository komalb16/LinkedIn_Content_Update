# ⚙️ Configuration Guide

Complete reference for all configuration files and settings.

---

## Configuration Files

| File | Purpose | Required |
|------|---------|----------|
| `.env` | API keys & environment | ✅ Yes |
| `schedule_config.json` | Posting schedule | ✅ Yes |
| `topics_config.json` | Topic list | ✅ Yes |
| `topics_manifest.json` | Topic metadata | ❌ Auto-created |
| `interview_questions.json` | Interview Q&A | ❌ Optional |

---

## .env File

Environment variables for API keys and settings.

```bash
# 🔑 Required: API Keys
GROQ_API_KEY=gsk_your_groq_key_here
LINKEDIN_ACCESS_TOKEN=your_linkedin_token_here
LINKEDIN_PERSON_URN=urn:li:person:XXXXXXX

# ⏰ Posting Settings
AUTO_POST=true                    # Auto-publish or dry-run only
SCHEDULE_CRON="0 9,21 * * *"    # Cron expression (9 AM & 9 PM)
DRY_RUN_ONLY=false               # Preview mode (don't actually post)

# 🎯 Feature Flags
ENABLE_TOPIC_DIVERSITY=true      # Prevent topic repetition
ENABLE_ENGAGEMENT_TRACKING=true  # Log post metadata
ENABLE_DIAGRAM_ROTATION=true     # Smart diagram style selection
ENABLE_NEWS_MODES=true           # Include news posts

# 📝 Post Configuration
DEFAULT_POST_MODE=topic          # Default: topic|story|ai_news|interview
POST_INTERVAL_HOURS=12           # Hours between posts

# 📊 Logging
LOG_LEVEL=INFO                   # DEBUG|INFO|WARNING|ERROR
LOG_FILE=logs/agent.log          # Log file path

# 🌐 Environment
PYTHON_ENV=production            # development|production
DEBUG=false                       # Extra debug output
```

### Getting API Keys

**Groq API Key:**
```
1. Go to https://console.groq.com
2. Sign up / Login
3. Click "API Keys" in left menu
4. Click "Create New API Key"
5. Copy the key (starts with gsk_)
6. Add to .env: GROQ_API_KEY=gsk_xxx
```

**LinkedIn Token:**
```
1. Go to LinkedIn Developer Portal
2. Create an application
3. Go to Auth → OAuth 2.0 settings
4. Get access token (valid 60 days)
5. Optional: Get LinkedIn URN from /userinfo endpoint
```

---

## schedule_config.json

Controls posting schedule and frequency.

### Basic Example

```json
{
  "enabled": true,
  "timezone": "America/New_York",
  "schedule": [
    {
      "day": "Monday",
      "time": "09:00",
      "enabled": true
    },
    {
      "day": "Wednesday",
      "time": "21:00",
      "enabled": true
    },
    {
      "day": "Friday",
      "time": "09:00",
      "enabled": true
    }
  ],
  "post_settings": {
    "auto_publish": true,
    "emoji_frequency": "medium",
    "hashtag_count": 5,
    "include_poll": false
  }
}
```

### Advanced Configuration

```json
{
  "enabled": true,
  "timezone": "UTC",
  "batch_mode": {
    "enabled": false,
    "posts_per_batch": 3,
    "batch_interval_hours": 24
  },
  "schedule": [
    {
      "day": "Monday",
      "times": ["09:00", "17:00"],
      "post_types": ["interview", "topic"],
      "enabled": true
    },
    {
      "day": "Tuesday",
      "times": ["09:00"],
      "post_types": ["story", "ai_news"],
      "enabled": true,
      "override_topics": ["Python", "AI"]
    }
  ],
  "post_settings": {
    "auto_publish": true,
    "emoji_frequency": "high",
    "hashtag_count": 5,
    "include_poll": true,
    "include_cta": true,
    "min_engagement_score": 0.7,
    "include_vulnerability": true
  },
  "engagement_config": {
    "track_analytics": true,
    "notify_on_high_engagement": true,
    "engagement_threshold": 100
  }
}
```

### Fields Explained

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | bool | Enable/disable scheduling |
| `timezone` | string | Timezone for schedule (UTC, America/New_York, etc.) |
| `post_types` | array | Mix of post types (topic, story, ai_news, interview, etc.) |
| `auto_publish` | bool | Auto-post or dry-run only |
| `emoji_frequency` | string | low, medium, high |
| `hashtag_count` | number | 3-7 recommended |
| `include_poll` | bool | Add engagement poll |
| `include_cta` | bool | Include strong call-to-action |

---

## topics_config.json

Define topics for posts.

### Simple Format

```json
{
  "topics": [
    "AI & Machine Learning",
    "System Design",
    "Python Development",
    "Cloud Architecture",
    "DevOps & Kubernetes",
    "GraphQL APIs",
    "Database Design",
    "Microservices"
  ]
}
```

### Advanced Format (with Categories)

```json
{
  "topics": [
    {
      "name": "AI & Machine Learning",
      "category": "emerging_tech",
      "difficulty": "intermediate",
      "keywords": ["LLM", "RAG", "embeddings", "transformers"],
      "post_frequency": 3,
      "emoji": "🤖",
      "color": "#FF6B6B",
      "enabled": true
    },
    {
      "name": "System Design",
      "category": "backend",
      "difficulty": "advanced",
      "keywords": ["scalability", "database", "cache", "load balancing"],
      "post_frequency": 2,
      "emoji": "🏗️",
      "color": "#4ECDC4",
      "enabled": true
    },
    {
      "name": "DevOps & Kubernetes",
      "category": "infrastructure",
      "difficulty": "intermediate",
      "keywords": ["Docker", "K8s", "CI/CD", "deployment"],
      "post_frequency": 2,
      "emoji": "⚙️",
      "color": "#95E1D3",
      "enabled": true
    }
  ],
  "category_mix": {
    "emerging_tech": 0.35,
    "backend": 0.25,
    "infrastructure": 0.20,
    "tools": 0.15,
    "career": 0.05
  }
}
```

### Creating Good Topics

✅ **DO:**
- Use specific, searchable topics ("React Hooks Patterns" not "Programming")
- Include 3-5 keywords per topic
- Mix difficulty levels
- Vary categories

❌ **DON'T:**
- Use generic terms ("Technology", "Development")
- Have too many topics (12-15 optimal)
- Repeat similar topics too close together (diversity check prevents this)
- Use overly niche topics (limited audience)

---

## interview_questions.json

Interview Q&A pairs for interview posts.

### Format

```json
{
  "questions": [
    {
      "question": "What does SOLID stand for?",
      "answer": "SOLID is an acronym for five design principles: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion. These principles help create more maintainable and scalable code.",
      "category": "design_patterns",
      "difficulty": "intermediate",
      "tags": ["SOLID", "OOP", "design", "architecture"],
      "topic": "System Design"
    },
    {
      "question": "How do you optimize a slow database query?",
      "answer": "Start with EXPLAIN/ANALYZE to understand the query plan. Look for: 1) Full table scans (add indexes), 2) N+1 queries (use joins), 3) Missing query filters, 4) Slow joins on large tables. Then profile again to verify improvement.",
      "category": "database",
      "difficulty": "advanced",
      "tags": ["SQL", "performance", "optimization", "database"],
      "topic": "Database Design"
    }
  ]
}
```

---

## Environment-Specific Configs

### Development (.env.development)

```bash
AUTO_POST=false              # Preview only
LOG_LEVEL=DEBUG              # Verbose logging
DRY_RUN_ONLY=true           # Never post
ENABLE_ENGAGEMENT_TRACKING=false
```

### Production (.env.production)

```bash
AUTO_POST=true               # Actually post
LOG_LEVEL=WARNING            # Only errors
DRY_RUN_ONLY=false          # Post for real
ENABLE_ENGAGEMENT_TRACKING=true
```

---

## Data Files (Auto-Generated)

### .engagement_tracker.json

Automatically created, tracks post metadata:

```json
{
  "posts": [
    {
      "post_id": "post_20240115_001",
      "timestamp": "2024-01-15T09:00:00Z",
      "topic": "AI & Machine Learning",
      "post_type": "topic",
      "category": "emerging_tech",
      "diagram_style": 8,
      "text_length": 1248,
      "emoji_count": 4,
      "hashtag_count": 5,
      "has_poll": false,
      "has_vulnerability": true,
      "has_strong_cta": true,
      "engagement_score": 0.85
    }
  ],
  "stats": {
    "total_posts": 42,
    "avg_engagement": 187,
    "max_engagement": 523
  }
}
```

### .diagram_rotation.json

Tracks diagram style rotation:

```json
{
  "rotation_index": 8,
  "style_history": [0, 8, 1, 9, 2, 10, 3, 11],
  "last_updated": "2024-01-15T09:00:00Z"
}
```

---

## Configuration Checklist

Before first run:

- [ ] `.env` file created with all required keys
- [ ] `GROQ_API_KEY` set correctly
- [ ] `LINKEDIN_ACCESS_TOKEN` set correctly
- [ ] `LINKEDIN_PERSON_URN` set correctly
- [ ] `schedule_config.json` customized
- [ ] `topics_config.json` populated with 8-15 topics
- [ ] `interview_questions.json` updated (optional)
- [ ] `.env` file is `.gitignored` (don't commit secrets!)

---

## Common Configuration Mistakes

### ❌ "Posts not publishing"
```
Check:
1. AUTO_POST=true in .env
2. LinkedIn token not expired (60-day limit)
3. LINKEDIN_PERSON_URN correct format: urn:li:person:XXXXXXX
```

### ❌ "Schedule not running"
```
Check:
1. Cron expression valid (use https://crontab.guru)
2. Timezone correct in schedule_config.json
3. enabled: true at top level
```

### ❌ "No topics showing up"
```
Check:
1. topics_config.json has valid JSON
2. topics array not empty
3. File in correct location
```

### ❌ "Credentials showing in logs"
```
✅ Solution:
1. Never commit .env to Git
2. Add .env to .gitignore
3. Use GitHub Secrets for CI/CD
```

---

## Next Steps

1. Set up `.env` with your API keys
2. Customize `schedule_config.json`
3. Add your topics to `topics_config.json`
4. Run dry-run: `python src/agent.py --dry-run`
5. Check output
6. Publish: `python src/agent.py`

---

## Support

- **Config issues?** Check [Troubleshooting Guide](TROUBLESHOOTING.md)
- **More examples?** See [examples/](../examples/)
- **Still stuck?** Open a [GitHub Issue](https://github.com/yourusername/linkedin-content-generator/issues)
