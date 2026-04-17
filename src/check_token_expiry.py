#!/usr/bin/env python3
"""
check_token_expiry.py — LinkedIn Token Expiry Alert (#15)

LinkedIn OAuth tokens expire after ~60 days.
This script checks how many days are left and sends a notification
7 and 3 days before expiry so you can renew before it breaks.

Setup:
  Add a GitHub Secret named LINKEDIN_TOKEN_DATE (format: YYYY-MM-DD)
  Set it to the date you created/last refreshed your LinkedIn token.
  Update it each time you refresh the token.

The script reads LINKEDIN_TOKEN_DATE, calculates days remaining,
and calls notifier.py if a warning threshold is crossed.
"""

import os
import sys
from datetime import date, datetime, timezone

# ── How long LinkedIn tokens last (standard OAuth 2.0 token lifetime) ────────
TOKEN_LIFETIME_DAYS = 60

# ── Warning thresholds (days remaining) ──────────────────────────────────────
WARN_CRITICAL = 3   # 🚨 CRITICAL — renew immediately
WARN_URGENT   = 7   # ⚠️  WARNING  — renew within a week
WARN_NOTICE   = 14  # ℹ️  NOTICE   — getting close

# ── ANSI colours for log readability ─────────────────────────────────────────
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    print(f"[{ts}] {msg}")


def main() -> int:
    log("=" * 56)
    log("  LinkedIn Token Expiry Check")
    log("=" * 56)

    # ── Read the token creation date ──────────────────────────────────────────
    token_date_str = os.environ.get("LINKEDIN_TOKEN_DATE", "").strip()

    if not token_date_str:
        log(
            f"{CYAN}ℹ️  LINKEDIN_TOKEN_DATE not set.{RESET}\n"
            f"   To enable expiry alerts, add a GitHub Secret:\n"
            f"     Name:  LINKEDIN_TOKEN_DATE\n"
            f"     Value: {date.today().isoformat()}  (the date you created your token)\n"
            f"   Update this secret each time you refresh your LinkedIn token."
        )
        return 0  # Not an error — just not configured yet

    # ── Parse the date ────────────────────────────────────────────────────────
    try:
        token_date = date.fromisoformat(token_date_str)
    except ValueError:
        log(
            f"{RED}❌ LINKEDIN_TOKEN_DATE has an invalid format: {token_date_str!r}{RESET}\n"
            f"   Use ISO date format: YYYY-MM-DD  (e.g. {date.today().isoformat()})"
        )
        return 1

    # ── Calculate days remaining ──────────────────────────────────────────────
    today          = date.today()
    days_old       = (today - token_date).days
    days_remaining = TOKEN_LIFETIME_DAYS - days_old
    pct_used       = min(100, round(days_old / TOKEN_LIFETIME_DAYS * 100))

    # Progress bar
    bar_len   = 30
    filled    = round(pct_used / 100 * bar_len)
    bar_color = RED if pct_used >= 90 else (YELLOW if pct_used >= 75 else GREEN)
    bar       = bar_color + "█" * filled + RESET + "░" * (bar_len - filled)

    log(f"  Created:       {token_date.isoformat()}")
    log(f"  Today:         {today.isoformat()}")
    log(f"  Age:           {days_old} days old  ({pct_used}% of lifetime used)")
    log(f"  Remaining:     {BOLD}{days_remaining} days{RESET}")
    log(f"  Progress:      [{bar}] {pct_used}%")
    log("")

    # ── Build notification message ────────────────────────────────────────────
    renew_url = (
        "https://www.linkedin.com/developers/apps  →  "
        "select your app  →  Auth  →  OAuth 2.0 Tools  →  Request Access Token"
    )

    if days_remaining <= 0:
        severity = "EXPIRED"
        emoji    = "🚨"
        headline = f"LinkedIn token EXPIRED {abs(days_remaining)} day(s) ago!"
        detail   = (
            "Posts are FAILING right now.\n"
            "Renew immediately:\n"
            f"  1. {renew_url}\n"
            "  2. Copy the new token\n"
            "  3. Update GitHub Secret: LINKEDIN_ACCESS_TOKEN\n"
            "  4. Update GitHub Secret: LINKEDIN_TOKEN_DATE → today's date"
        )
        log(f"{RED}{BOLD}🚨 CRITICAL: {headline}{RESET}")
        exit_code = 1  # Fail the workflow step to alert via GitHub UI

    elif days_remaining <= WARN_CRITICAL:
        severity = "CRITICAL"
        emoji    = "🚨"
        headline = f"LinkedIn token expires in {days_remaining} day(s)!"
        detail   = (
            f"Renew within {days_remaining} day(s) or posts will stop.\n"
            f"Renew at: {renew_url}\n"
            "After renewing, update LINKEDIN_ACCESS_TOKEN and LINKEDIN_TOKEN_DATE secrets."
        )
        log(f"{RED}{BOLD}🚨 CRITICAL ({days_remaining} days remaining): {headline}{RESET}")
        exit_code = 1

    elif days_remaining <= WARN_URGENT:
        severity = "WARNING"
        emoji    = "⚠️"
        headline = f"LinkedIn token expires in {days_remaining} days"
        detail   = (
            f"Renew within the next {days_remaining} days to avoid disruption.\n"
            f"Renew at: {renew_url}\n"
            "After renewing, update LINKEDIN_ACCESS_TOKEN and LINKEDIN_TOKEN_DATE secrets."
        )
        log(f"{YELLOW}{BOLD}⚠️  WARNING ({days_remaining} days remaining): {headline}{RESET}")
        exit_code = 0  # Warning only — don't fail the workflow

    elif days_remaining <= WARN_NOTICE:
        severity = "NOTICE"
        emoji    = "ℹ️"
        headline = f"LinkedIn token expires in {days_remaining} days"
        detail   = (
            f"No immediate action needed, but schedule a renewal soon.\n"
            f"Renew at: {renew_url}"
        )
        log(f"{CYAN}ℹ️  NOTICE ({days_remaining} days remaining): {headline}{RESET}")
        exit_code = 0

    else:
        # Token is healthy
        log(f"{GREEN}✅ Token is healthy — {days_remaining} days remaining. No action needed.{RESET}")
        return 0

    # ── Daily dedup: only notify once per day ─────────────────────────────────
    # Crons fire at UTC 0, 6, 12, 18.  Only the midnight window (hour 0-5)
    # sends the notification so the user gets exactly one alert per day.
    # Set FORCE_NOTIFY=1 to override (useful for manual/dry-run testing).
    utc_hour = datetime.now(timezone.utc).hour
    if utc_hour >= 6 and not os.environ.get("FORCE_NOTIFY"):
        log(
            f"{CYAN}ℹ️  Notification deferred — already covered by first daily run "
            f"(UTC hour {utc_hour}, threshold {days_remaining}d). "
            f"Set FORCE_NOTIFY=1 to override.{RESET}"
        )
        return exit_code

    # ── Send notification if threshold crossed ────────────────────────────────
    log("")
    log(f"📬 Sending {severity} notification...")

    try:
        # Use notifier.py infrastructure (Email / Telegram / WhatsApp)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from notifier import notify_all

        topic   = f"{emoji} LinkedIn Token Expiry {severity}"
        preview = (
            f"{headline}\n\n"
            f"{detail}\n\n"
            f"— LinkedIn Agent Token Monitor"
        )
        notify_all(topic=topic, post_preview=preview, is_dry_run=False)
        log(f"✅ Notification sent via notifier.py channels")

    except ImportError:
        log("ℹ️  notifier.py not importable — notification skipped (check NOTIFY_* secrets)")
    except Exception as e:
        log(f"⚠️  Notification failed: {e}")

    # Print GitHub Actions warning/error annotation
    if severity in ("CRITICAL", "EXPIRED"):
        print(f"::error::🚨 LinkedIn token expires in {days_remaining} days! Renew LINKEDIN_ACCESS_TOKEN immediately and update LINKEDIN_TOKEN_DATE.")
    elif severity == "WARNING":
        print(f"::warning::⚠️ LinkedIn token expires in {days_remaining} days. Plan renewal soon.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())