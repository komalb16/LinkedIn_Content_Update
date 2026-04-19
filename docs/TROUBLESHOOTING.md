# 🐛 Troubleshooting Guide

Common issues and solutions.

---

## Installation Issues

### ❌ "ModuleNotFoundError: No module named 'groq'"

**Cause:** Dependencies not installed

**Solution:**
```bash
pip install -r requirements.txt

# Or install specific package
pip install groq
```

---

### ❌ "Python version not supported"

**Cause:** Using Python < 3.9

**Solution:**
```bash
python --version  # Check your version

# Install Python 3.9+
# On macOS:
brew install python@3.11

# On Ubuntu:
sudo apt-get install python3.11

# On Windows:
# Download from python.org
```

---

### ❌ "cairo not found" / "libcairo2-dev not installed"

**Cause:** Missing system dependencies for diagram generation

**Solution:**
```bash
# On macOS:
brew install cairo

# On Ubuntu/Debian:
sudo apt-get install libcairo2-dev pkg-config python3-dev

# On Windows:
# Use Docker instead of manual installation
```

---

## Configuration Issues

### ❌ "GROQ_API_KEY not found"

**Cause:** Environment variable not set

**Solutions:**

Option 1: Set in `.env` file
```bash
GROQ_API_KEY=gsk_your_key_here
```

Option 2: Set in shell
```bash
export GROQ_API_KEY=gsk_your_key_here
python src/agent.py
```

Option 3: Verify file exists
```bash
ls -la .env
# If missing:
cp .env.example .env
# Then edit with your key
```

---

### ❌ "LinkedIn token expired"

**Cause:** LinkedIn OAuth token has 60-day expiry

**Solution:**
```
1. Go to LinkedIn Developer Portal
2. Generate new access token
3. Update .env:
   LINKEDIN_ACCESS_TOKEN=new_token_here
4. Or set GitHub secret for CI/CD
   GitHub → Settings → Secrets → Actions → Update LINKEDIN_ACCESS_TOKEN
5. Restart agent
```

---

### ❌ "LINKEDIN_PERSON_URN not in correct format"

**Cause:** URN format invalid

**Solution:**
```
Correct format: urn:li:person:XXXXXXX

To get your URN:
1. Get LinkedIn OAuth token
2. Call:
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://api.linkedin.com/v2/userinfo
3. Extract the 'sub' field
4. Format will be: urn:li:person:XXXXXX
5. Add to .env:
   LINKEDIN_PERSON_URN=urn:li:person:XXXXXX
```

---

### ❌ "Invalid JSON in config file"

**Cause:** Malformed JSON syntax

**Solution:**
```bash
# Validate JSON syntax
python -m json.tool topics_config.json

# If error shown, check:
# 1. Remove trailing commas
# 2. Quote all keys and strings
# 3. Use double quotes, not single
# 4. Check for missing brackets/braces

# Example WRONG:
{
  "topics": ["AI", "Python",]  // Trailing comma!
}

# Example RIGHT:
{
  "topics": ["AI", "Python"]
}
```

---

## Runtime Issues

### ❌ "No posts generated / Empty output"

**Cause:** One of several issues

**Debug steps:**
```bash
# 1. Check if Groq API is accessible
python -c "import groq; print('✅ Groq library loaded')"

# 2. Verify API key is set
python -c "import os; print(f'Key set: {bool(os.getenv(\"GROQ_API_KEY\"))}')"

# 3. Test Groq connection
python src/check_groq_connection.py

# 4. Run with verbose logging
LOG_LEVEL=DEBUG python src/agent.py

# 5. Check log file
tail -f logs/agent.log
```

---

### ❌ "Posts not publishing to LinkedIn"

**Possible causes:**

1. Token expired
   ```bash
   # Regenerate token (see "LinkedIn token expired" above)
   ```

2. Auto-post disabled
   ```bash
   # Check .env:
   AUTO_POST=true
   
   # Or set:
   AUTO_POST=true python src/agent.py
   ```

3. Dry-run only mode
   ```bash
   # Check .env - should NOT have:
   DRY_RUN_ONLY=true
   
   # Should be:
   DRY_RUN_ONLY=false
   ```

4. LinkedIn API limits exceeded
   - Wait 24 hours
   - Check rate limit status in LinkedIn Developer Portal

---

### ❌ "Diagram generation failed"

**Cause:** SVG to PNG conversion failed

**Solution:**
```bash
# 1. Verify cairo installed
python -c "import cairosvg; print('✅ Cairo available')"

# If error, install dependencies (see "cairo not found" above)

# 2. Check if SVG file was created
ls -la diagrams/

# 3. Test diagram generation directly
python src/diagram_generator.py --style=0 --test

# 4. Use simpler test
python -c "from src.diagram_generator import generate_diagram; generate_diagram('Test', 0)"
```

---

### ❌ "Memory usage keeps growing"

**Cause:** Memory leak or large files not cleared

**Solution:**
```bash
# 1. Check engagement tracker size
wc -l .engagement_tracker.json

# 2. Limit rolling window size
# In src/agent.py, check:
# ENGAGEMENT_TRACKER_MAX_POSTS = 500

# 3. Clear old data
rm .engagement_tracker.json
rm .diagram_rotation.json

# 4. Monitor memory during run
top  # Linux/Mac
# or
wmic process list brief  # Windows
```

---

## Docker Issues

### ❌ "docker: command not found"

**Cause:** Docker not installed

**Solution:**
```
1. Install Docker Desktop from docker.com
2. Restart your computer
3. Verify:
   docker --version
```

---

### ❌ "docker-compose up fails with network error"

**Cause:** Networking misconfiguration

**Solution:**
```bash
# 1. Check if containers running
docker ps

# 2. Restart Docker
docker-compose down
docker-compose up -d

# 3. Check logs
docker-compose logs -f

# 4. Nuclear option - clean slate
docker-compose down -v
rm -rf data/
docker-compose up -d
```

---

### ❌ "Permission denied errors in Docker"

**Cause:** Volume mount permissions

**Solution:**
```bash
# On Linux:
sudo usermod -aG docker $USER
# Then log out and back in

# Or run with sudo:
sudo docker-compose up -d
```

---

### ❌ "Container exiting immediately"

**Cause:** Missing environment variables or startup error

**Solution:**
```bash
# 1. Check logs
docker-compose logs agent

# 2. Verify .env file exists and has API keys
ls -la .env
cat .env

# 3. Restart with output
docker-compose up agent  # (don't use -d)

# 4. Check if config files exist
ls -la schedule_config.json
ls -la topics_config.json
```

---

## Testing Issues

### ❌ "pytest: command not found"

**Cause:** Pytest not installed

**Solution:**
```bash
pip install pytest pytest-cov pytest-mock
```

---

### ❌ "Tests fail with import errors"

**Cause:** PYTHONPATH not set correctly

**Solution:**
```bash
# Run from project root:
cd linkedin-content-generator
python -m pytest tests/ -v

# Or set PYTHONPATH:
export PYTHONPATH=$PWD
pytest tests/ -v
```

---

### ❌ "Tests pass locally but fail in GitHub Actions"

**Cause:** Secrets not available in CI

**Solution:**
```
1. Check GitHub Secrets are set:
   Settings → Secrets and variables → Actions
2. Verify all required secrets present:
   ✓ GROQ_API_KEY
   ✓ LINKEDIN_ACCESS_TOKEN
   ✓ LINKEDIN_PERSON_URN
3. Re-run workflow
```

---

## API Issues (Phase 2)

### ❌ "Connection refused" on http://localhost:8000

**Cause:** Backend not running

**Solution:**
```bash
# 1. Check if backend running
ps aux | grep main.py

# 2. Start backend
python backend/main.py

# 3. Or via Docker
docker-compose up -d api
```

---

## Performance Issues

### ❌ "Posts generation very slow (>60 seconds)"

**Cause:** Either Groq API or diagram generation slow

**Solution:**
```bash
# 1. Test Groq API latency
time python -c "
from groq import Groq
client = Groq()
response = client.chat.completions.create(
    model='llama-3.3-70b-versatile',
    messages=[{'role': 'user', 'content': 'hello'}]
)
"

# 2. If slow, check Groq status page:
# https://status.groq.com

# 3. Test diagram generation speed
time python src/diagram_generator.py --style=0 --test

# 4. If diagram slow, try different style:
for style in {0..22}; do
  echo "Testing style $style"
  time python src/diagram_generator.py --style=$style --test
done
```

---

## Still Stuck?

1. **Search existing issues:** https://github.com/yourusername/linkedin-content-generator/issues
2. **Check logs:** `tail -f logs/agent.log`
3. **Enable debug mode:** `LOG_LEVEL=DEBUG python src/agent.py`
4. **Open new issue** with:
   - Error message (full output)
   - System info (`python --version`, `docker --version`, etc.)
   - What you already tried
   - Steps to reproduce

---

## Getting Help

- 📋 **Documentation:** [README.md](../README.md)
- 🔧 **Config Help:** [docs/CONFIGURATION.md](CONFIGURATION.md)
- 📥 **Installation:** [docs/INSTALLATION.md](INSTALLATION.md)
- 💬 **Discussions:** GitHub Discussions tab
- 🐛 **Report Bug:** GitHub Issues tab
