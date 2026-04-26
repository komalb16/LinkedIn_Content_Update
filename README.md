# 🚀 LinkedIn Content Architecture Agent

An institutional-grade content pipeline designed for high-authority, technical-leadership posting on LinkedIn.

## 🌟 Next-Gen Features (v2.5)

### 1. **Elite Technical Diagrams**
The agent has been upgraded to prioritize **production-grade engineering visuals** from elite sources:
*   Primary Sourcing: `ByteByteGo`, `AlgoMaster.io`, `DesignGurus`.
*   Fallback: Multi-candidate local SVG generation with scoring/ranking.
*   **Personal Branding**: Every diagram automatically features a "Software Engineer II ID Badge" (Customizable in `src/diagram_generator.py`).

### 2. **Synthesis News Engine**
Unlike basic RSS summaries, the agent now operates in **Synthesis Mode**:
*   Aggregates up to **5 different industry signals** (layoffs, launches, buyouts).
*   Analyzes the "Why" and "Future Impact" instead of just reporting numbers.
*   Specifically tuned to catch Microsoft and Big Tech workforce movements.

### 3. **Engagement Automation**
The agent now generates an independent **"First Comment"** for every post (saved to `output_comment.txt`).
*   **Goal**: Start technical debates and provide "Extra Pro-Tips" to boost LinkedIn's algorithm.

### 4. **Adaptive Analytics**
*   **Loopback**: Each post's quality and topic are logged to `src/analytics_data.json`.
*   **Optimization**: The agent learns from high-engagement posts to prioritize the most successful topics.

---

## 📅 Scheduling & Performance

### **Strict Scheduling Policy**
The agent uses a **Strict Lookback Policy**:
*   Posts will **never** trigger before their scheduled time.
*   Tolerance: 55-minute window to handle GitHub Actions cron delays.
*   **Note**: GitHub crons fire on a "best effort" basis and may be 0–45 minutes late. Our `schedule_checker.py` handles this drift safely.

## 🛠️ Key Commands

```powershell
# Run the agent in Dry-Run mode to preview content
python src/agent.py --dry-run

# Trigger a specific News synthesis (e.g. layoffs)
python src/agent.py --mode layoff_news

# Check scheduling status
python src/schedule_checker.py
```

## 👤 Branding Customization
To update your name or title on the diagram badge, modify the "PERSONAL BRANDING BADGE" section in `src/diagram_generator.py`.

---
*Curated by Komal Batra — Software Engineer @ Microsoft*
