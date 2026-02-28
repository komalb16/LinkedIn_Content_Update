# 🤖 LinkedIn Agent — © Komal Batra

> An autonomous LinkedIn content agent that generates trending tech posts + visual diagrams using Claude AI, scheduled twice daily via GitHub Actions. Runs completely offline — no computer needed.

---

## ✨ What It Does

- **Posts twice daily** automatically (9 AM + 6 PM IST) to your LinkedIn
- **Generates AI-powered posts** on AI, Engineering, Cloud, Security, Data topics
- **Creates SVG diagrams** — architecture diagrams, cheat sheets, command references, flow charts
- **Rotates topics** intelligently — no repeats within 6 posts
- **Watermarks everything** with `© Komal Batra`
- **Manual trigger** — run any topic on demand from GitHub UI
- **Saves all artifacts** — every diagram and post is archived

---

## 🚀 Setup in 4 Steps

### Step 1 — Fork & Clone This Repo

```bash
# Fork on GitHub, then:
git clone https://github.com/YOUR_USERNAME/linkedin-agent.git
cd linkedin-agent
```

---

### Step 2 — Get Your LinkedIn Credentials

LinkedIn requires OAuth 2.0. Here's how:

#### 2a. Create a LinkedIn App
1. Go to [linkedin.com/developers/apps/new](https://www.linkedin.com/developers/apps/new)
2. Create an app (use your personal page as the company)
3. Go to **Products** tab → Request access to **"Share on LinkedIn"** and **"Sign In with LinkedIn"**
4. Go to **Auth** tab → copy your **Client ID** and **Client Secret**

#### 2b. Get Your Access Token (one-time setup)

```bash
pip install requests

python3 - <<'EOF'
# Step 1: Get auth URL
CLIENT_ID = "YOUR_CLIENT_ID"
REDIRECT_URI = "https://localhost"  # must match your app settings
scope = "openid profile email w_member_social"

url = f"https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope={scope}"
print("Open this URL in your browser:")
print(url)
EOF
```

Then open the URL → authorize → copy the `code` from the redirect URL.

```bash
python3 - <<'EOF'
import requests

CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"  
REDIRECT_URI = "https://localhost"
CODE = "PASTE_CODE_FROM_URL_HERE"

resp = requests.post("https://www.linkedin.com/oauth/v2/accessToken", data={
    "grant_type": "authorization_code",
    "code": CODE,
    "redirect_uri": REDIRECT_URI,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
})
data = resp.json()
print("ACCESS TOKEN:", data["access_token"])
print("Expires in:", data["expires_in"], "seconds (~60 days)")
EOF
```

#### 2c. Get Your Person URN

```bash
python3 - <<'EOF'
import requests
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"
resp = requests.get("https://api.linkedin.com/v2/me", 
    headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
data = resp.json()
print("PERSON URN: urn:li:person:" + data["id"])
EOF
```

---

### Step 3 — Add GitHub Secrets

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value |
|-------------|-------|
| `ANTHROPIC_API_KEY` | Your Claude API key from [console.anthropic.com](https://console.anthropic.com) |
| `LINKEDIN_ACCESS_TOKEN` | Token from Step 2b |
| `LINKEDIN_PERSON_URN` | URN from Step 2c (e.g. `urn:li:person:ABC123xyz`) |

---

### Step 4 — Enable GitHub Actions

1. Go to your repo → **Actions** tab
2. Click **"I understand my workflows, go ahead and enable them"**
3. The schedule starts automatically!

---

## 🎮 Manual Trigger (Post Right Now)

1. Go to **Actions** tab in your GitHub repo
2. Click **"LinkedIn Agent — Komal Batra"** in the left sidebar
3. Click **"Run workflow"** button (top right)
4. Choose your topic from the dropdown (or leave blank for auto)
5. Choose dry run = true to preview without posting
6. Click **"Run workflow"** ✅

---

## ⏰ Schedule

| Time | Post |
|------|------|
| 9:00 AM IST | Morning post (AI/Engineering topic) |
| 6:00 PM IST | Evening post (different category) |

> **To change times:** Edit `.github/workflows/linkedin-agent.yml` and modify the cron values.  
> Cron is in UTC. IST = UTC+5:30. Use [crontab.guru](https://crontab.guru) to convert.

---

## 📂 Project Structure

```
linkedin-agent/
├── .github/
│   └── workflows/
│       └── linkedin-agent.yml    ← GitHub Actions (schedule + manual trigger)
├── src/
│   ├── agent.py                  ← Main entry point
│   ├── topic_manager.py          ← 16 topics with rotation logic
│   ├── linkedin_poster.py        ← LinkedIn API v2 integration
│   ├── diagram_generator.py      ← SVG file management
│   └── logger.py                 ← Logging
├── requirements.txt
└── README.md
```

---

## 📋 Available Topics

Run locally to see all topics:
```bash
cd src && python agent.py --list-topics
```

| Category | Topics |
|----------|--------|
| 🤖 AI | LLM Architecture, AI Agents, MLOps, RAG Systems |
| ☁️ Cloud | Kubernetes, Docker, AWS Architecture, CI/CD |
| ⚙️ Engineering | System Design, API Design, Git, SOLID Principles |
| 🔐 Security | Zero Trust, DevSecOps |
| 📊 Data | Data Lakehouse, Apache Kafka |

---

## 🔧 Run Locally

```bash
cd src

# Install deps
pip install -r ../requirements.txt

# Set env vars
export ANTHROPIC_API_KEY="sk-ant-..."
export LINKEDIN_ACCESS_TOKEN="AQ..."
export LINKEDIN_PERSON_URN="urn:li:person:..."

# Auto topic, dry run (safe preview)
python agent.py --dry-run

# Specific topic, dry run
python agent.py --topic docker-cheatsheet --dry-run

# Live post
python agent.py --topic rag-systems
```

---

## 🔄 Token Renewal (~60 days)

LinkedIn access tokens expire after ~60 days. When that happens:

1. Re-run Step 2b to get a new token
2. Update the `LINKEDIN_ACCESS_TOKEN` secret in GitHub
3. Done — the agent resumes automatically

> **Tip:** Set a calendar reminder 55 days after setup to renew your token.

---

## 📊 Viewing Results

After each run:
1. Go to **Actions** → click the run → expand **"Upload Diagrams"**
2. Download the artifact zip — contains all SVGs, PNGs, and the post text
3. View logs directly in the Action run

---

## ⚠️ Troubleshooting

| Error | Fix |
|-------|-----|
| `401 Unauthorized` | LinkedIn token expired → renew it (Step 2b) |
| `403 Forbidden` | App doesn't have `w_member_social` scope → re-authorize |
| `SVG parse error` | Claude returned extra text → check agent.log in artifacts |
| `ANTHROPIC_API_KEY not set` | Add the secret in GitHub Settings |
| Workflow not running | Check Actions tab is enabled in repo settings |

---

## 📜 License

All generated content is attributed to **© Komal Batra**.  
This agent is personal automation tooling — not for redistribution.
