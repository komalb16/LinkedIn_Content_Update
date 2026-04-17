# 🤖 LinkedIn Agent

> **Auto-post technical content to LinkedIn on a schedule — powered by Groq LLM and GitHub Actions. Fork, add 4 secrets, done.**

No server. No cloud bill. No code changes required.

---

## ✨ What it does

- Generates a professional LinkedIn post + a custom technical diagram every time it runs.
- Runs on a schedule you control (default: twice daily).
- Posts directly to your LinkedIn via their API
- Dashboard to monitor posts, trigger manually, and change topics — works on mobile as a PWA

---

## 🚀 Setup in 5 minutes

### 1 · Fork this repo

Click **Fork** at the top-right of this page. Give it any name you like.

### 2 · Get a LinkedIn access token

You need two values from LinkedIn:

| Value | Where to get it |
|---|---|
| `LINKEDIN_ACCESS_TOKEN` | [LinkedIn Developer Portal](https://www.linkedin.com/developers/) → create an app → OAuth 2.0 → request `w_member_social` scope |
| `LINKEDIN_PERSON_URN` | Call `https://api.linkedin.com/v2/userinfo` with your token — the `sub` field is your URN (format: `urn:li:person:XXXXXXX`) |

> **Tip:** The [LinkedIn Token Generator](https://www.linkedin.com/developers/tools/oauth/token-generator) makes this easier.

### 3 · Get a Groq API key

Sign up at [console.groq.com](https://console.groq.com) → API Keys → Create. Free tier is plenty.  
Your secret will be named `GROQ_API_KEY` (legacy naming — it holds the Groq key).

### 4 · Add secrets to GitHub

Go to your forked repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `GROQ_API_KEY` | Your Groq key — starts with `gsk_` · get it free at [console.groq.com](https://console.groq.com) |
| `LINKEDIN_ACCESS_TOKEN` | Your LinkedIn OAuth token · 60-day expiry |
| `LINKEDIN_PERSON_URN` | Your LinkedIn member URN · format: `urn:li:person:XXXXXXX` |

That's it. The agent will now run on its default schedule.

### 5 · (Optional) Personalise

**Your name on posts** — Go to your repo → **Settings → Variables → New repository variable**

| Variable | Value |
|---|---|
| `AUTHOR_NAME` | Your full name (e.g. `Jane Smith`) |

If you skip this, your GitHub username is used automatically — no posts will break.

---

## 📱 Dashboard

Open `https://YOUR_USERNAME.github.io/YOUR_REPO_NAME/dashboard.html`

> Enable GitHub Pages first: repo **Settings → Pages → Source → Deploy from branch → `main` → `/root`**

On first open:
1. Enter a GitHub personal access token (needs `repo` + `workflow` scopes)
2. The dashboard auto-detects your repo and connects
3. Enter your name and role when prompted (10 seconds)
4. Done — monitor posts, trigger manually, change schedule

### Install as app (PWA)

- **Android:** tap the banner that appears, or browser menu → "Add to Home Screen"
- **iOS:** tap Share (□↑) → "Add to Home Screen"

### Use on multiple devices

Once connected, tap **📱 Share** in the header. Scan the QR code on your other device — it connects automatically, no token re-entry.

---

## ⚙️ Configuration

### Posting schedule

Edit the cron in `.github/workflows/linkedin-agent.yml`:

```yaml
schedule:
  - cron: "30 3 * * *"    # 9 AM IST
  - cron: "30 12 * * *"   # 6 PM IST
```

Or control it visually from the dashboard → Schedule tab.

### Topics

The agent cycles through these automatically. You can add your own in the dashboard → Topics tab, or edit `src/topics_config.json`.

Built-in topics: LLM Architecture · AI Agents · MLOps · RAG Systems · Kubernetes · Docker · AWS · CI/CD · System Design · API Design · Git Workflow · SOLID Principles · Zero Trust · DevSecOps · Data Lakehouse · Kafka Streaming

### Post frequency

Edit `src/schedule_checker.py` — the `POSTING_DAYS` and `POSTING_HOURS` lists control which days and hours posts go out.

---

## 🗂 Project structure

```
├── .github/
│   └── workflows/
│       └── linkedin-agent.yml     ← GitHub Actions workflow
├── src/
│   ├── agent.py                   ← Main orchestrator
│   ├── schedule_checker.py        ← Decides whether to post now
│   ├── linkedin_poster.py         ← LinkedIn API integration
│   ├── diagram_generator.py       ← SVG diagram builder
│   ├── topic_manager.py           ← Topic rotation logic
│   └── topics_config.json         ← Topic list (edit freely)
├── dashboard.html                 ← Web dashboard (GitHub Pages)
├── manifest.json                  ← PWA manifest
├── sw.js                          ← Service worker (offline)
└── requirements.txt
```

---

## 🔐 Required secrets summary

| Secret | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | ✅ | Groq API key (`gsk_...`) |
| `LINKEDIN_ACCESS_TOKEN` | ✅ | LinkedIn OAuth token |
| `LINKEDIN_PERSON_URN` | ✅ | Your LinkedIn member URN |

| Variable | Required | Description |
|---|---|---|
| `AUTHOR_NAME` | ❌ Optional | Your name on posts/diagrams. Defaults to GitHub username |

---

## 🛠 Troubleshooting

**Posts aren't going out on schedule**  
→ Check Actions tab — cron runs fire every 30 min as a heartbeat and self-cancel when it's not posting time. Only `workflow_dispatch` runs appear in the dashboard's Post History.

**LinkedIn token expired**  
→ LinkedIn tokens expire after 60 days. Re-generate at the developer portal and update the `LINKEDIN_ACCESS_TOKEN` secret.

**Dashboard shows "no repo found"**  
→ Open the dashboard → ⚙️ Settings → enter your repo as `username/repo-name`.

**`AUTHOR_NAME` not showing on posts**  
→ Set it as a repository **variable** (not a secret) — repo Settings → Variables → Actions.

---

## 🔒 Your secrets stay yours

When someone forks this project they get an **independent copy** of the code only — completely separate from your repo. They cannot see, access, or affect:

- Your GitHub secrets (`GROQ_API_KEY`, `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_PERSON_URN`)
- Your post history, schedule config, or topic list
- Your LinkedIn account or API credentials
- Any of your workflow run logs

Each person who forks adds **their own** secrets to **their own** forked repo under their own GitHub account. Your original repo is completely untouched. Think of it like sharing a recipe — giving someone the recipe doesn't give them access to your kitchen.

## 📄 License

MIT — fork freely, use commercially, no attribution required.

---

*Built with [Groq](https://groq.com) · Hosted on [GitHub Actions](https://github.com/features/actions) · Dashboard on [GitHub Pages](https://pages.github.com)*
