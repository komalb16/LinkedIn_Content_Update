# 📥 Installation Guide

Complete step-by-step setup for LinkedIn Content Generator.

---

## Prerequisites

### Required
- **Python 3.9+** (for manual setup) OR **Docker**
- **Groq API Key** (free tier available)
- **LinkedIn OAuth Token**

### Optional
- **Git** (to clone repo)
- **GitHub account** (for automated scheduling)

---

## Option 1: Docker Setup (Recommended)

### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/linkedin-content-generator.git
cd linkedin-content-generator
```

### Step 2: Get API Credentials

#### A. Groq API Key (Free)
1. Visit https://console.groq.com
2. Sign up / Login
3. Go to API Keys → Create
4. Copy your key (starts with `gsk_`)
5. Add to `.env` (see Step 4)

#### B. LinkedIn Token
1. Visit [LinkedIn Developer Portal](https://www.linkedin.com/developers/)
2. Create an app (if first time)
3. Request `w_member_social` scope
4. Generate OAuth token
5. Get your LinkedIn URN
   - Call: `curl -H "Authorization: Bearer YOUR_TOKEN" https://api.linkedin.com/v2/userinfo`
   - Extract `sub` field (format: `urn:li:person:XXXXXXX`)

### Step 3: Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```bash
# Groq API
GROQ_API_KEY=gsk_your_key_here

# LinkedIn
LINKEDIN_ACCESS_TOKEN=your_oauth_token_here
LINKEDIN_PERSON_URN=urn:li:person:XXXXXXX

# Posting
AUTO_POST=true
SCHEDULE_CRON="0 9,21 * * *"  # 9 AM & 9 PM daily

# Features
ENABLE_TOPIC_DIVERSITY=true
ENABLE_ENGAGEMENT_TRACKING=true
ENABLE_DIAGRAM_ROTATION=true
```

### Step 4: Start with Docker Compose

```bash
# Start services
docker-compose up -d

# Verify running
docker-compose ps

# Check logs
docker-compose logs -f agent

# Run manual test
docker exec -it agent python src/agent.py --dry-run

# Preview output
cat output_post_*.txt
```

### Step 5: Verify Working

You should see:
```
✅ Post generated successfully
✅ Diagram created
✅ Topic diversity checked
✅ Engagement logged
```

**Done!** Your bot is running 24/7. 🚀

---

## Option 2: Manual Setup (Development)

### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/linkedin-content-generator.git
cd linkedin-content-generator
```

### Step 2: Create Virtual Environment

```bash
# Create venv
python -m venv venv

# Activate
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Get API Credentials

Same as Option 1 (Steps 2A & 2B above)

### Step 5: Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### Step 6: Initialize Configs

```bash
cp schedule_config.json.example schedule_config.json
cp topics_config.json.example topics_config.json
```

### Step 7: Test Installation

```bash
# Verify syntax
python -m py_compile src/agent.py

# Run tests
python -m pytest tests/ -v

# Dry-run (preview without posting)
python src/agent.py --dry-run

# Check output
cat output_post_*.txt
```

### Step 8: Generate First Post

```bash
# Generate & publish
python src/agent.py

# View logs
tail -f logs/agent.log
```

---

## Setup Troubleshooting

### ❌ "GROQ_API_KEY not found"
```bash
# Solution: Set in .env file
GROQ_API_KEY=gsk_your_actual_key

# Or via environment:
export GROQ_API_KEY=gsk_your_actual_key
python src/agent.py
```

### ❌ "LinkedIn token expired"
```
LinkedIn tokens expire after 60 days.
1. Go to LinkedIn Developer Portal
2. Generate new token
3. Update .env or GitHub secret
4. Restart agent
```

### ❌ "ModuleNotFoundError: No module named 'groq'"
```bash
# Solution: Requirements not installed
pip install -r requirements.txt

# Or specific module:
pip install groq
```

### ❌ "Connection refused" (Docker)
```bash
# Solution: Check if containers running
docker-compose ps

# If not running:
docker-compose up -d

# Check logs:
docker-compose logs agent
```

### ❌ "No diagram generated"
```
Check if svg2png library installed:
python -c "import cairosvg"

If missing:
- On macOS: brew install cairo
- On Ubuntu: sudo apt-get install libcairo2-dev
- On Windows: Use Docker instead
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | ✅ | - | Groq API key (get free at console.groq.com) |
| `LINKEDIN_ACCESS_TOKEN` | ✅ | - | LinkedIn OAuth token |
| `LINKEDIN_PERSON_URN` | ✅ | - | Your LinkedIn URN (urn:li:person:XXXXX) |
| `AUTO_POST` | ❌ | true | Whether to auto-publish posts |
| `SCHEDULE_CRON` | ❌ | "0 9,21 * * *" | Cron schedule (9 AM & 9 PM daily) |
| `ENABLE_TOPIC_DIVERSITY` | ❌ | true | Check for topic repetition (7-day window) |
| `ENABLE_ENGAGEMENT_TRACKING` | ❌ | true | Log engagement data |
| `ENABLE_DIAGRAM_ROTATION` | ❌ | true | Rotate through 23 diagram styles |
| `LOG_LEVEL` | ❌ | INFO | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `PYTHON_ENV` | ❌ | production | Environment (development/production) |

---

## Quick Verification

After setup, verify everything works:

```bash
# Test 1: Environment
python -c "import os; print('✅ Env loaded')"

# Test 2: Dependencies
python -m pytest tests/unit/test_imports.py -v

# Test 3: Groq API
python src/check_groq_connection.py

# Test 4: LinkedIn Auth
python src/check_linkedin_token.py

# Test 5: Dry-run
python src/agent.py --dry-run

# Test 6: Generate full pipeline
python src/agent.py --test
```

---

## Linux/Ubuntu Installation (Full)

```bash
#!/bin/bash

# 1. Install system dependencies
sudo apt-get update
sudo apt-get install -y python3.9 python3.9-venv git

# 2. Clone repo
git clone https://github.com/yourusername/linkedin-content-generator.git
cd linkedin-content-generator

# 3. Create venv
python3.9 -m venv venv
source venv/bin/activate

# 4. Install Python deps
pip install -r requirements.txt

# 5. Get credentials (manual step - edit .env)
cp .env.example .env
nano .env  # Edit with credentials

# 6. Test
python -m pytest tests/ -v

# 7. Run
python src/agent.py
```

---

## macOS Installation (Full)

```bash
#!/bin/bash

# 1. Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install Python & cairo
brew install python@3.9 cairo

# 3. Clone repo
git clone https://github.com/yourusername/linkedin-content-generator.git
cd linkedin-content-generator

# 4. Create venv
python3.9 -m venv venv
source venv/bin/activate

# 5. Install deps
pip install -r requirements.txt

# 6. Configure
cp .env.example .env
# Edit .env with your credentials

# 7. Test
python -m pytest tests/ -v

# 8. Run
python src/agent.py
```

---

## Windows Installation (Full)

```powershell
# 1. Install Python 3.9+ from python.org

# 2. Clone repo
git clone https://github.com/yourusername/linkedin-content-generator.git
cd linkedin-content-generator

# 3. Create venv
python -m venv venv
venv\Scripts\activate

# 4. Install deps
pip install -r requirements.txt

# 5. Configure
copy .env.example .env
# Edit .env with your credentials using Notepad

# 6. Test
python -m pytest tests\ -v

# 7. Run
python src\agent.py
```

---

## Next Steps

1. **Configure Topics** → See [Configuration Guide](CONFIGURATION.md)
2. **Run First Post** → `python src/agent.py --dry-run`
3. **Schedule Posting** → GitHub Actions or cron
4. **Monitor Analytics** → Check `.engagement_tracker.json`
5. **Customize Posts** → Edit `topics_config.json`

---

## Getting Help

- **Errors?** Check [Troubleshooting Guide](TROUBLESHOOTING.md)
- **Questions?** See [FAQ](FAQ.md)
- **Issues?** Report on [GitHub Issues](https://github.com/yourusername/linkedin-content-generator/issues)
