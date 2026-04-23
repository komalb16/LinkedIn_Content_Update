#!/usr/bin/env python3
"""
check_token_expiry.py — LinkedIn Token Expiry Alert

LinkedIn OAuth tokens expire after ~60 days.
This script checks how many days are left and sends a notification
at 14, 7, and 3 days before expiry so you can renew before posts break.

Setup:
  Add a GitHub Secret named LINKEDIN_TOKEN_DATE (format: YYYY-MM-DD)
  Set it to the date you created/last refreshed your LinkedIn token.
  Update it each time you refresh the token.
"""

import os
import sys
from datetime import date, datetime, timezone

TOKEN_LIFETIME_DAYS = 60

WARN_CRITICAL = 3    # 🚨 CRITICAL — renew immediately
WARN_URGENT   = 7    # ⚠️  WARNING  — renew within a week
WARN_NOTICE   = 14   # ℹ️  NOTICE   — getting close

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

    token_date_str = os.environ.get("LINKEDIN_TOKEN_DATE", "").strip()

    if not token_date_str:
        log(
            f"{CYAN}ℹ️  LINKEDIN_TOKEN_DATE not set.{RESET}\n"
            f"   To enable expiry alerts, add a GitHub Secret:\n"
            f"     Name:  LINKEDIN_TOKEN_DATE\n"
            f"     Value: {date.today().isoformat()}  (the date you created your token)\n"
            f"   Update this secret each time you refresh your LinkedIn token."
        )
        return 0

    try:
        token_date = date.fromisoformat(token_date_str)
    except ValueError:
        log(
            f"{RED}❌ LINKEDIN_TOKEN_DATE has an invalid format: {token_date_str!r}{RESET}\n"
            f"   Use ISO date format: YYYY-MM-DD  (e.g. {date.today().isoformat()})"
        )
        return 1

    today          = date.today()
    days_old       = (today - token_date).days
    days_remaining = TOKEN_LIFETIME_DAYS - days_old
    pct_used       = min(100, round(days_old / TOKEN_LIFETIME_DAYS * 100))

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

    renew_url = (
        "https://www.linkedin.com/developers/apps  →  "
        "select your app  →  Auth  →  OAuth 2.0 Tools  →  Request Access Token"
    )

    if days_remaining <= 0:
        severity  = "EXPIRED"
        emoji     = "🚨"
        headline  = f"LinkedIn token EXPIRED {abs(days_remaining)} day(s) ago!"
        detail    = (
            "Posts are FAILING right now.\n"
            "Renew immediately:\n"
            f"  1. {renew_url}\n"
            "  2. Copy the new token\n"
            "  3. Update GitHub Secret: LINKEDIN_ACCESS_TOKEN\n"
            "  4. Update GitHub Secret: LINKEDIN_TOKEN_DATE → today's date"
        )
        log(f"{RED}{BOLD}🚨 CRITICAL: {headline}{RESET}")
        exit_code = 1

    elif days_remaining <= WARN_CRITICAL:
        severity  = "CRITICAL"
        emoji     = "🚨"
        headline  = f"LinkedIn token expires in {days_remaining} day(s)!"
        detail    = (
            f"Renew within {days_remaining} day(s) or posts will stop.\n"
            f"Renew at: {renew_url}\n"
            "After renewing, update LINKEDIN_ACCESS_TOKEN and LINKEDIN_TOKEN_DATE secrets."
        )
        log(f"{RED}{BOLD}🚨 CRITICAL ({days_remaining} days remaining): {headline}{RESET}")
        exit_code = 1

    elif days_remaining <= WARN_URGENT:
        severity  = "WARNING"
        emoji     = "⚠️"
        headline  = f"LinkedIn token expires in {days_remaining} days"
        detail    = (
            f"Renew within the next {days_remaining} days to avoid disruption.\n"
            f"Renew at: {renew_url}\n"
            "After renewing, update LINKEDIN_ACCESS_TOKEN and LINKEDIN_TOKEN_DATE secrets."
        )
        log(f"{YELLOW}{BOLD}⚠️  WARNING ({days_remaining} days remaining): {headline}{RESET}")
        exit_code = 0

    elif days_remaining <= WARN_NOTICE:
        severity  = "NOTICE"
        emoji     = "ℹ️"
        headline  = f"LinkedIn token expires in {days_remaining} days"
        detail    = (
            f"No immediate action needed, but schedule a renewal soon.\n"
            f"Renew at: {renew_url}"
        )
        log(f"{CYAN}ℹ️  NOTICE ({days_remaining} days remaining): {headline}{RESET}")
        exit_code = 0

    else:
        log(f"{GREEN}✅ Token is healthy — {days_remaining} days remaining. No action needed.{RESET}")
        return 0

    # ── Daily dedup: only notify ONCE per day ─────────────────────────────────
    #
    # BUG FIX: The old threshold was `utc_hour >= 6` which allowed BOTH the
    # 00:00 UTC and 03:00 UTC crons through (both are in the 0-5 range),
    # causing two alerts per day (one at ~8 PM EST, one at ~11 PM EST).
    #
    # FIX: Use `utc_hour >= 3` so only the 00:00 UTC cron (hour 0, 1, or 2)
    # sends the alert. The 03:00 UTC cron (hour 3) and all later crons are
    # deferred. This guarantees exactly ONE alert per day.
    #
    # Cron schedule: 0 */3 * * * → fires at 00, 03, 06, 09, 12, 15, 18, 21 UTC
    # Alert window:  hour 0-2    → only the 00:00 UTC cron qualifies
    #
    # Set FORCE_NOTIFY=1 to override (useful for manual testing).
    utc_hour = datetime.now(timezone.utc).hour
    if utc_hour >= 3 and not os.environ.get("FORCE_NOTIFY"):
        log(
            f"{CYAN}ℹ️  Notification deferred — only the 00:00 UTC cron sends daily alerts "
            f"(current UTC hour: {utc_hour}, cron window: 0-2). "
            f"Set FORCE_NOTIFY=1 to override.{RESET}"
        )
        return exit_code

    # ── Send notification ─────────────────────────────────────────────────────
    log("")
    log(f"📬 Sending {severity} notification...")

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from notifier import notify_all

        topic   = f"{emoji} LinkedIn Token Expiry {severity}"
        preview = (
            f"{headline}\n\n"
            f"{detail}\n\n"
            f"— LinkedIn Agent Token Monitor"
        )
        notify_all(topic=topic, post_preview=preview, is_dry_run=False)
        log("✅ Notification sent via notifier.py channels")

    except ImportError:
        log("ℹ️  notifier.py not importable — notification skipped (check NOTIFY_* secrets)")
    except Exception as e:
        log(f"⚠️  Notification failed: {e}")

    if severity in ("CRITICAL", "EXPIRED"):
        print(f"::error::🚨 LinkedIn token expires in {days_remaining} days! Renew LINKEDIN_ACCESS_TOKEN immediately and update LINKEDIN_TOKEN_DATE.")
    elif severity == "WARNING":
        print(f"::warning::⚠️ LinkedIn token expires in {days_remaining} days. Plan renewal soon.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
