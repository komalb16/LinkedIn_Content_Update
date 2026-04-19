# 🏗️ Application Architecture & Separation

## Current Setup (After Fixes)

### Part 1: Original Application (Kept As-Is)
```
src/                          ← Your original post generation app
├── agent.py                 (Post generation)
├── topic_manager.py         (Topic selection)
├── diagram_generator.py      (Diagram creation)
├── linkedin_poster.py        (Publishing)
└── ...other modules
```

**Use Cases:**
- Scheduled automated posting via cron
- Command-line post generation
- Direct LinkedIn posting

**How to Run:**
```bash
python src/agent.py
```

---

### Part 2: NEW SaaS Monetized Application (Separate)
```
backend/                      ← NEW SaaS backend (Phase 2)
├── main.py                  (32 REST API endpoints)
├── models.py                (Database schema)
├── auth.py                  (JWT + OAuth)
└── billing.py               (Stripe integration)

frontend/                     ← NEW SaaS frontend (TO CREATE)
├── index.html               (Landing page)
├── dashboard.html           (Admin dashboard)
└── ...other pages
```

**Use Cases:**
- Hosted SaaS dashboard at saas.example.com
- User authentication & sign-up
- Subscription management with Stripe
- Multi-user support
- Professional hosting

**How to Run (Two Terminals):**

Terminal 1 - Backend:
```bash
python run_server.py
# Runs at http://localhost:8000
# API: http://localhost:8000/docs
```

Terminal 2 - Frontend:
```bash
cd frontend
python -m http.server 3000
# Runs at http://localhost:3000
```

---

## File Separation

### Original App Files (KEEP - Don't Modify)
```
✅ src/                      (Original modules)
✅ schedule_config.json      (Original scheduling)
✅ topics_config.json        (Original topics)
✅ requirements.txt          (Original dependencies)
✅ Dockerfile                (Original image)
```

### New SaaS Files (NEW - In backend/ folder)
```
✅ backend/                  (New backend code)
✅ .env                      (New configuration)
✅ backend/requirements.txt  (New dependencies)
✅ linkedin_generator.db     (New database)
```

### Shared Files (Both Use)
```
⚠️ index.html               (Landing page - for SaaS)
⚠️ templates/               (Templates - for SaaS)
⚠️  manifest.json           (PWA manifest - for SaaS)
```

---

## Architecture Diagram

```
USER

    ↓

  EITHER

    ↙             ↘

OLD APP          NEW SAAS
(CLI/Cron)       (Web Browser)

    ↓                ↓

src/agent.py     frontend/
(Generate)       (Dashboard)

    ↓                ↓

               backend/main.py
               (API Server)

    ↓

           Database

    ↓

    LinkedIn API
```

---

## Deployment Strategy

### Original App (Self-Hosted)
```
Your Server / Your Machine
- Run cron job: python src/agent.py
- Direct LinkedIn posting
- No dashboard needed
```

### New SaaS (Hosted)
```
Render.com or Railway.com
- Deploy: backend/ (FastAPI)
- Deploy: frontend/ (Static site)
- Domain: yoursaas.com
- Users pay subscription
```

---

## Database Separation

### Original App
```
No database (configuration via JSON files)
schedule_config.json
topics_config.json
```

### New SaaS
```
sqlite:///./linkedin_generator.db
- Users table (authentication)
- Subscriptions table (Stripe)
- Posts table (multi-user posts)
- Audit logs (compliance)
```

---

## Configuration Files Needed

### Original App (.env not used)
```bash
GROQ_API_KEY=gsk_...
LINKEDIN_ACCESS_TOKEN=...
```

### New SaaS (.env file required)
```bash
DATABASE_URL=sqlite:///./linkedin_generator.db
SECRET_KEY=dev-secret-...
STRIPE_SECRET_KEY=sk_test_...
```

---

## Quick Start: Both Apps

### Terminal 1: Run Original App (If Needed)
```bash
# Just set API keys, no database needed
export GROQ_API_KEY=gsk_your_key
export LINKEDIN_ACCESS_TOKEN=your_token

# Then run normally:
python src/agent.py
```

### Terminal 2: Run New SaaS Backend
```bash
# Automatic: loads .env file
python run_server.py

# Runs at http://localhost:8000/docs
```

### Terminal 3: Run New SaaS Frontend
```bash
cd frontend
python -m http.server 3000

# Runs at http://localhost:3000
```

---

## Result

| App | Type | URL | Purpose |
|-----|------|-----|---------|
| Original | CLI/Cron | None | Automated posting |
| New SaaS | Web Dashboard | localhost:3000 | User interface |
| New SaaS | API | localhost:8000/docs | Backend endpoints |

Both run independently - no conflicts!

---

## NEXT: Create the Frontend Dashboard

Once you confirm this separation, I'll create the SaaS frontend dashboard.
