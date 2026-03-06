# 🤖 LinkedIn Content Agent

An AI-powered LinkedIn post automation system that generates and publishes technical content daily. Features architecture diagrams, real-time news integration, and a web dashboard to manage everything — no code required after setup.

---

## ✨ What It Does

- **Posts daily** at your scheduled time (default 9:30 AM IST) via GitHub Actions
- **Generates technical posts** on 16+ engineering topics (Kubernetes, LLM, AWS, CI/CD, etc.)
- **Fetches real news** — AI news, tech layoffs, new tools — and writes opinionated commentary
- **Creates architecture diagrams** as SVG images attached to every post
- **Rotates topics** intelligently — no repeats within 6 posts, no same category 3× in a row
- **Web dashboard** to preview posts, post manually, track history, and add custom topics
- **Dry Run preview** — generate and review a real post + diagram before it goes live
- **Notifications** — get alerted via WhatsApp, Email, or Telegram every time a post goes live
- **100% free** — GitHub Actions + Groq free tier (14,400 requests/day)

---

## 🏗️ Architecture

```
GitHub Actions (cron)
      │
      ▼
agent.py
  ├── fetch_rss_news()    ← VentureBeat, TechCrunch, HackerNews
  ├── get_next_topic()    ← rotation from topic_manager.py
  ├── generate_post()     ← Groq LLaMA 3.3 70B
  ├── generate_diagram()  ← diagram_generator.py (SVG)
  ├── post_to_linkedin()  ← linkedin_poster.py (OAuth API)
  └── notify_all()        ← notifier.py (email/WhatsApp/Telegram)
```

---

## 🚀 Complete Setup Guide (New User)

### Prerequisites
- GitHub account (free)
- LinkedIn account
- 30 minutes

---

### Step 1 — Fork the Repository

1. Go to [github.com/komalb16/LinkedIn_Content_Update](https://github.com/komalb16/LinkedIn_Content_Update)
2. Click **Fork** (top right)
3. Keep the name as-is or rename it
4. Click **Create fork**

You now have your own copy at `github.com/YOUR_USERNAME/LinkedIn_Content_Update`

---

### Step 2 — Get a Groq API Key (Free)

Groq provides a free LLM API with 14,400 requests/day — more than enough.

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up / log in
3. Click **API Keys** → **Create API Key**
4. Copy the key (starts with `gsk_...`)

---

### Step 3 — Set Up LinkedIn Developer App

1. Go to [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)
2. Click **Create app**
3. Fill in:
   - **App name**: Content Agent (or anything)
   - **LinkedIn Page**: Pick any company page (doesn't affect personal posting)
4. Click **Create app**
5. Go to the **Products** tab → find **Share on LinkedIn** → click **Request access**
6. Wait for approval (usually instant or a few hours)

---

### Step 4 — Generate LinkedIn OAuth Token

You need to run the OAuth flow once to get an access token.

#### 4a. Get your Client ID and Secret

1. In your LinkedIn app → **Auth** tab
2. Note your **Client ID**
3. Click **Generate** next to Client Secret → copy it

#### 4b. Get Authorization Code

Open this URL in your browser (replace `YOUR_CLIENT_ID`):

```
https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=https://localhost&scope=openid%20profile%20w_member_social
```

- Log in to LinkedIn if prompted
- Click **Allow**
- You'll be redirected to `https://localhost/?code=LONG_CODE_HERE`
- Copy everything after `code=` (before any `&` if present)

#### 4c. Exchange Code for Access Token

Run this in your terminal (replace all placeholders):

```bash
curl -X POST https://www.linkedin.com/oauth/v2/accessToken \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "code=YOUR_AUTHORIZATION_CODE" \
  -d "redirect_uri=https://localhost" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET"
```

Response:
```json
{
  "access_token": "AQX...long_token...",
  "expires_in": 5183944
}
```

Copy the `access_token` value. **It expires in ~60 days** — set a reminder to refresh it.

#### 4d. Get Your Person URN

```bash
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  https://api.linkedin.com/v2/userinfo
```

Response includes:
```json
{
  "sub": "tS9T_Jc38A"
}
```

Your Person URN is: `urn:li:person:tS9T_Jc38A` (replace with your `sub` value)

---

### Step 5 — Add GitHub Secrets

In your forked repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these 3 secrets:

| Secret Name | Value |
|-------------|-------|
| `LINKEDIN_ACCESS_TOKEN` | The `access_token` from Step 4c |
| `LINKEDIN_PERSON_URN` | `urn:li:person:YOUR_SUB` from Step 4d |
| `ANTHROPIC_API_KEY` | Your Groq key from Step 2 (starts with `gsk_`) |

> ⚠️ The secret is named `ANTHROPIC_API_KEY` for historical reasons but stores your Groq key.

---

### Step 6 — Enable GitHub Actions

1. In your repo → **Actions** tab
2. If you see "Workflows aren't running", click **Enable workflows**
3. Find **LinkedIn Content Agent** → click **Enable workflow**
4. Find **Keepalive** workflow → click **Enable workflow**

---

### Step 7 — Personalise the Code

Make these small changes before your first post:

**`src/agent.py`** — Find and replace `Komal Batra` with your name in the system prompts:
```python
# Line ~30 (POST_SYSTEM)
"You are Komal Batra, a senior software engineer..."
# Change to your name

# Line ~55 (NEWS_SYSTEM)  
"You are Komal Batra, commenting on tech news..."
# Change to your name
```

**`src/diagram_generator.py`** — Find and replace the signature:
```python
# Find:
"&#10022; AI &#169; Komal Batra"
# Replace:
"&#10022; AI &#169; Your Name"
```

**`dashboard.html`** — Find and replace the repo reference:
```javascript
// Line ~5
const REPO = 'komalb16/LinkedIn_Content_Update';
// Change to:
const REPO = 'YOUR_USERNAME/LinkedIn_Content_Update';
```

---

### Step 8 — Test It

1. Go to **Actions** → **LinkedIn Content Agent** → **Run workflow**
2. Leave all inputs as default → click **Run workflow**
3. Watch it run (takes 2-3 minutes)
4. Check your LinkedIn profile — a post should appear!

If it fails, check the logs in Actions for error messages.

---

### Step 9 — Set Up Your Dashboard

1. Make your repo **public** (Settings → General → scroll down → Change visibility)  
   *Or download `dashboard.html` and open it locally — both work*

2. Enable GitHub Pages: **Settings** → **Pages** → Source: **main** → **/ (root)** → Save

3. Your dashboard will be live at:
   ```
   YOUR_USERNAME.github.io/LinkedIn_Content_Update/dashboard.html
   ```

4. Generate a GitHub Personal Access Token:
   - Go to **github.com → Settings → Developer Settings → Personal Access Tokens → Tokens (classic)**
   - Click **Generate new token (classic)**
   - Check: `repo`, `workflow`
   - Expiration: **No expiration**
   - Copy the `ghp_xxx...` token

5. Open your dashboard → paste the GitHub token → click **Connect**

6. Add your Groq key in **⚙️ Settings** (for Dry Run preview feature)

---

## 📊 Dashboard Features

| Feature | Description |
|---------|-------------|
| **Post Now** | Trigger a post immediately with selected topic |
| **Dry Run Preview** | Generate post + diagram in browser without posting |
| **Topic Picker** | Choose a specific topic or let it auto-select |
| **Add Custom Topic** | Type any topic → saved permanently to your list |
| **Run History** | See all runs with topic, mode, duration, and status |
| **Schedule Display** | See next scheduled post and countdown |
| **Theme Switcher** | Light / Medium / Dark themes |
| **Stats** | Total runs, successful posts, this week, last post time |

### Dry Run Preview Setup

The Dry Run feature calls the Groq API directly from your browser to generate a real post preview.

1. Open dashboard → click ⚙️ Settings
2. Enter your Groq API key (from console.groq.com)
3. Enter your name and role (shown in preview)
4. Save Settings
5. Toggle **Dry Run** → click **Preview Post**

You'll see the generated post + architecture diagram before deciding to publish.

---

## ⏰ Schedule Configuration

The default schedule is **9:30 AM IST** (4:00 AM UTC).

To change it:
1. Open `.github/workflows/linkedin-agent.yml`
2. Find the `cron:` line:
   ```yaml
   - cron: '30 4 * * *'  # 9:30 AM IST = 4:00 AM UTC
   ```
3. Use the dashboard's Schedule section to calculate the new cron expression
4. Update the file and commit

**IST to UTC conversion**: Subtract 5 hours 30 minutes from IST time.

| IST Time | UTC Cron |
|----------|----------|
| 8:00 AM | `30 2 * * *` |
| 9:30 AM | `0 4 * * *` |
| 10:00 AM | `30 4 * * *` |
| 12:00 PM | `30 6 * * *` |

---

## 🎯 Adding Custom Topics

### Temporarily (for one post)
Use the topic picker in the dashboard — click any chip and hit Post Now.

### Permanently via Dashboard
1. Open dashboard → Topic section
2. Type your topic in the "Add your own topic" field
3. Click **＋ Add**
4. The topic is saved in your browser and shown every time

### Permanently in the codebase
Add to `src/topic_manager.py` in the `TOPICS` list:
```python
{
    "id": "your-topic-id",
    "name": "Your Topic Name",
    "category": "engineering",
    "diagram_type": "architecture",
    "keywords": ["keyword1", "keyword2"]
},
```
Commit and push. This adds it to the automated rotation.

---

## 🔄 Post Types

| Type | Frequency | Description |
|------|-----------|-------------|
| AI News | 15% | Commentary on latest AI developments from VentureBeat, TechCrunch |
| Layoff News | 10% | Industry commentary on tech layoffs (HackerNews, TechCrunch) |
| Tools News | 10% | Reviews of new developer tools and product launches |
| Tech Topic | 60% | Deep technical posts on rotating engineering topics with diagrams |
| General Tech | 5% | Broader tech industry commentary |

---

---

## 🔔 Notifications Setup

Get alerted the moment your post goes live. Three channels supported — set up one, two, or all three. Each is independent and optional.

### Files to upload first
- `src/notifier.py` — the notification module
- `src/agent.py` — updated to call notifier after posting
- `.github/workflows/Linkedin_Content_Update.yml` — updated to pass notification secrets

### Recommended channel

| Channel | Reliability | Setup time | Cost |
|---------|-------------|------------|------|
| ⭐ **Telegram** | Excellent — permanent bot, same chat always | 3 min | Free forever |
| **Email** | Excellent — stable Gmail SMTP | 3 min | Free |
| **WhatsApp** | Limited — see caveats below | 5 min | Free |

**Telegram is the recommended primary channel.** Messages always arrive in the same chat from your own named bot. Email is a solid secondary. WhatsApp works but has limitations explained in its section.

---

### Option A — Telegram ⭐ Recommended

Telegram bots are free, instant, and permanent. Your bot has a fixed username that never changes — notifications always land in the same chat.

**Step 1 — Create a bot via BotFather:**
1. Open Telegram → search **@BotFather** → tap Start
2. Send `/newbot`
3. Follow the prompts — choose a name (e.g. "My LinkedIn Agent") and a username ending in `bot` (e.g. `komal_linkedin_bot`)
4. BotFather will reply with a token like:
   ```
   7123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
   Copy this — it's your `TELEGRAM_BOT_TOKEN`

**Step 2 — Get your Chat ID:**
1. Open Telegram → search **@userinfobot** → tap Start
2. It will immediately reply with your info including:
   ```
   Id: 123456789
   ```
   That number is your `TELEGRAM_CHAT_ID`

**Step 3 — Activate your bot:**
1. Search for your new bot by its username in Telegram
2. Tap **Start** (or send it any message)
   > This is required once — bots can only message users who have started a conversation with them first

**Step 4 — Add GitHub Secrets:**

Go to your repo → **Settings → Secrets and variables → Actions** → add:

| Secret Name | Value |
|-------------|-------|
| `TELEGRAM_BOT_TOKEN` | Token from BotFather |
| `TELEGRAM_CHAT_ID` | Your numeric ID from @userinfobot |

You'll receive a notification like this every time a post goes live:

```
✅ LinkedIn Post Published

📌 Topic: CI/CD Pipelines

📝 Preview:
Most CI/CD pipelines fail silently. Here's what I've learned...

🤖 LinkedIn Agent via GitHub Actions
```

---

### Option B — Email (Gmail)

Uses Gmail's SMTP with an App Password — your real Gmail password is never used or stored.

**Step 1 — Create a Gmail App Password:**
1. Make sure **2-Step Verification** is enabled on your Google account
   → [myaccount.google.com → Security → 2-Step Verification](https://myaccount.google.com/security)
2. Go to [myaccount.google.com → Security → App Passwords](https://myaccount.google.com/apppasswords)
3. Select app: **Mail** → Select device: **Other** → type "LinkedIn Agent" → click **Generate**
4. Copy the 16-character password shown (e.g. `abcd efgh ijkl mnop`)

**Step 2 — Add GitHub Secrets:**

| Secret Name | Value | Example |
|-------------|-------|---------|
| `NOTIFY_EMAIL` | Your Gmail address | `yourname@gmail.com` |
| `NOTIFY_EMAIL_PASSWORD` | The 16-char App Password (no spaces) | `abcdefghijklmnop` |
| `NOTIFY_TO_EMAIL` | Where to receive alerts | `yourname@gmail.com` |

> `NOTIFY_TO_EMAIL` can be the same as `NOTIFY_EMAIL`, or a different address entirely (e.g. your work email or phone's SMS-to-email gateway).

You'll receive a nicely formatted HTML email with the post preview every time a post goes live.

---

### Option C — WhatsApp (via CallMeBot)

> ⚠️ **Know the limitations before setting this up:**
> - CallMeBot is a **hobby project** run by one developer — not a commercial service
> - The sender number **rotates periodically** — new notifications may arrive from an unknown number in your WhatsApp, not the contact you saved. This is a known, unfixed quirk of CallMeBot
> - Occasionally goes down for hours at a time with no warning
> - No SLA, no support
>
> **Use this only as a secondary/bonus channel alongside Telegram or Email, not as your sole notification method.**

Uses [CallMeBot](https://www.callmebot.com/) — completely free, no credit card needed.

**Step 1 — Activate CallMeBot:**
1. Go to the official page: **[callmebot.com/blog/free-api-whatsapp-messages](https://www.callmebot.com/blog/free-api-whatsapp-messages/)**
2. Note the phone number shown at the top of that page (do not use numbers from tutorials — CallMeBot's number changes and third-party docs are often outdated)
3. Save that number in your WhatsApp contacts (name it anything, e.g. "CallMeBot")
4. Send it this exact message via WhatsApp:
   ```
   I allow callmebot to send me messages
   ```
5. You'll receive your API key via WhatsApp within a few seconds (a 7-digit number)
   > If nothing arrives after 2 minutes, wait 24 hours and try again — a known reliability issue

**Step 2 — Add GitHub Secrets:**

| Secret Name | Value | Example |
|-------------|-------|---------|
| `CALLMEBOT_PHONE` | Your WhatsApp number with country code | `+919876543210` |
| `CALLMEBOT_APIKEY` | The API key you received | `1234567` |

Notifications will look like:

```
✅ LinkedIn Post Published!

Topic: Kubernetes
"I wasted 3 hours debugging a CrashLoopBackOff last week..."

— LinkedIn Agent 🤖
```

> **Reminder:** Due to CallMeBot's rotating sender numbers, these messages may appear under different unknown contacts over time. If you find this annoying, disable WhatsApp and rely on Telegram or Email instead.

---

### Notification Secrets Summary

Add whichever secrets match the channel(s) you want. Any channel with missing secrets is silently skipped — no errors, no failed runs.

| Secret Name | Channel | Notes |
|-------------|---------|-------|
| `TELEGRAM_BOT_TOKEN` | ⭐ Telegram | Pair with CHAT_ID |
| `TELEGRAM_CHAT_ID` | ⭐ Telegram | Pair with BOT_TOKEN |
| `NOTIFY_EMAIL` | Email | Pair with PASSWORD + TO |
| `NOTIFY_EMAIL_PASSWORD` | Email | Pair with EMAIL + TO |
| `NOTIFY_TO_EMAIL` | Email | Pair with EMAIL + PASSWORD |
| `CALLMEBOT_PHONE` | WhatsApp ⚠️ | Pair with APIKEY |
| `CALLMEBOT_APIKEY` | WhatsApp ⚠️ | Pair with PHONE |

---

---

## 🔑 Token Management

### LinkedIn Access Token
- **Expires**: ~60 days from generation
- **Action**: Re-run OAuth flow (Steps 4b–4c) and update `LINKEDIN_ACCESS_TOKEN` secret
- **Reminder**: Set a calendar reminder 1 week before expiry

### Groq API Key
- **Expires**: Never (unless you revoke it)
- **Action**: None needed

### GitHub Personal Access Token (Dashboard)
- **Expires**: Based on what you set (recommend: No expiration)
- **Action**: If expired, generate new token and paste in dashboard

---

## 🛠️ Troubleshooting

### Post not appearing on LinkedIn
1. Check Actions → run logs for errors
2. Verify `LINKEDIN_ACCESS_TOKEN` is not expired (60-day limit)
3. Verify `LINKEDIN_PERSON_URN` format: `urn:li:person:XXXX`
4. Check that **Share on LinkedIn** product is approved in your LinkedIn app

### Post ran twice (double posting)

This happens when the `keepalive.yml` workflow accidentally dispatches the main workflow in addition to its own job. The fix:

1. Replace `.github/workflows/keepalive.yml` with the latest version from this repo
2. Replace `.github/workflows/Linkedin_Content_Update.yml` with the latest version

**What changed in the fix:**
- `keepalive.yml` now runs **weekly** (every Sunday) instead of daily — it only commits a `keepalive.txt` file and never triggers the main agent
- `linkedin-agent.yml` now has exactly **one** `cron:` entry — two cron entries = two posts per day
- The two schedules are now 1 hour apart (keepalive at 3:00 AM UTC, main agent at 4:00 AM UTC) to avoid any overlap

### Workflow not running automatically
1. GitHub disables scheduled workflows after 60 days of inactivity
2. The **Keepalive** workflow prevents this, but if it stopped:
   - Go to Actions → Keepalive → Enable workflow
   - Push any small commit to reactivate

### Dashboard "Connection failed"
1. Token must start with `ghp_`
2. Token needs `repo` and `workflow` scopes
3. Repo must be public (for GitHub Pages) or use the file locally

### Groq API errors in Dry Run preview
1. Verify key starts with `gsk_`
2. Check free tier limits at console.groq.com
3. Try a different model — update `GROQ_MODEL` in dashboard.html if needed

### Diagram looks wrong
- Diagrams are generated as SVG from Python
- If topic isn't recognized, it falls back to a generic system design diagram
- Custom topics added via dashboard use the generic template

---

## 🔁 Reusing This for Someone Else

To set up this system for another person:

1. They **fork** your repo
2. Complete Steps 2–8 above with their own credentials
3. In `src/agent.py` — replace your name with theirs in system prompts
4. In `src/diagram_generator.py` — replace signature with their name  
5. In `dashboard.html` — replace the `REPO` constant with their repo path
6. That's it — everything else works out of the box

**Only 4 lines of code need changing** for a complete new setup.

---

## 📁 Project Structure

```
LinkedIn_Content_Update/
├── .github/
│   └── workflows/
│       ├── linkedin-agent.yml      # Main daily posting workflow
│       └── keepalive.yml           # Prevents workflow from being disabled
├── src/
│   ├── agent.py                    # Main agent — orchestrates everything
│   ├── topic_manager.py            # Topic rotation and selection logic
│   ├── diagram_generator.py        # SVG architecture diagram generator
│   ├── linkedin_poster.py          # LinkedIn API integration
│   ├── notifier.py                 # Email / WhatsApp / Telegram alerts
│   └── logger.py                   # Logging utilities
├── dashboard.html                  # Web dashboard (GitHub Pages)
├── diagrams/                       # Generated diagram files (gitignored)
├── README.md                       # This file
└── requirements.txt                # Python dependencies
```

---

## 📦 Dependencies

```
groq
requests
python-dotenv
```

Install locally for testing:
```bash
pip install -r requirements.txt
```

Run locally (dry run):
```bash
python src/agent.py --dry-run
```

Run locally with specific topic:
```bash
python src/agent.py --topic llm-architecture
```

---

## 📝 License

MIT — use it, fork it, build on it.

---

## 🙏 Credits

Built by [Komal Batra](https://linkedin.com/in/komal-batra) · Powered by [Groq](https://groq.com) · Hosted on [GitHub Actions](https://github.com/features/actions)
