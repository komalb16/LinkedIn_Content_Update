"""
notifier.py — Multi-channel post notifications
Supports: Email (Gmail SMTP), WhatsApp (CallMeBot free), Telegram (bot)
"""

import os
import smtplib
import urllib.request
import urllib.parse
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from logger import get_logger
    log = get_logger("notifier")
except Exception:
    import logging
    log = logging.getLogger("notifier")
    logging.basicConfig(level=logging.INFO)


def notify_all(topic: str, post_preview: str, is_dry_run: bool = False) -> None:
    """Send notifications across all configured channels."""
    if is_dry_run:
        log.info("Dry run — skipping notifications")
        return

    preview = post_preview[:200].replace("\n", " ").strip()
    if len(post_preview) > 200:
        preview += "..."

    subject = f"✅ LinkedIn Post Published — {topic}"
    body    = f"Your LinkedIn post on '{topic}' was just published.\n\nPreview:\n{preview}\n\n— LinkedIn Agent 🤖"

    log.info("─" * 40)
    log.info("Sending notifications...")
    results = []
    results.append(("Email",    _send_email(subject, body)))
    results.append(("WhatsApp", _send_whatsapp(subject, preview, topic)))
    results.append(("Telegram", _send_telegram(subject, preview, topic)))
    log.info("─" * 40)

    active = [(ch, ok) for ch, ok in results if ok is not None]
    if not active:
        log.info("No notification channels configured. To enable Telegram:")
        log.info("  Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as GitHub Secrets")
    else:
        for ch, ok in active:
            log.info(f"  {ch}: {'✅ sent' if ok else '❌ failed — check secrets and logs above'}")


# ─── EMAIL ─────────────────────────────────────────────────────────────────
def _send_email(subject: str, body: str):
    sender   = os.environ.get("NOTIFY_EMAIL", "")
    password = os.environ.get("NOTIFY_EMAIL_PASSWORD", "")
    to_email = os.environ.get("NOTIFY_TO_EMAIL", "")

    if not all([sender, password, to_email]):
        return None  # not configured

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"LinkedIn Agent <{sender}>"
        msg["To"]      = to_email

        html = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
          <div style="background:linear-gradient(135deg,#0ea5e9,#8b5cf6);padding:20px;border-radius:12px 12px 0 0">
            <h2 style="color:white;margin:0">🤖 LinkedIn Post Published</h2>
          </div>
          <div style="background:#f8fafc;padding:24px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0">
            <p style="color:#475569;font-size:14px;margin-bottom:16px">
              Your post on <strong style="color:#0ea5e9">{topic}</strong> is now live on LinkedIn.
            </p>
            <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-bottom:20px">
              <p style="color:#0f172a;font-size:13px;line-height:1.6;margin:0">{body.split("Preview:")[1].split("—")[0].strip() if "Preview:" in body else ""}</p>
            </div>
            <p style="color:#94a3b8;font-size:12px;margin:0">Sent by LinkedIn Agent • Running on GitHub Actions</p>
          </div>
        </body></html>
        """
        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, to_email, msg.as_string())
        return True
    except Exception as e:
        log.error(f"Email notification failed: {e}")
        return False


# ─── WHATSAPP (CallMeBot) ──────────────────────────────────────────────────
def _send_whatsapp(subject: str, preview: str, topic: str):
    phone  = os.environ.get("CALLMEBOT_PHONE", "")
    apikey = os.environ.get("CALLMEBOT_APIKEY", "")

    if not all([phone, apikey]):
        return None

    try:
        text    = f"✅ LinkedIn Post Published!\n\nTopic: {topic}\n\n{preview}\n\n— LinkedIn Agent 🤖"
        encoded = urllib.parse.quote(text)
        url     = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded}&apikey={apikey}"
        req     = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            result = response.read().decode()
            if "Message sent" in result or "200" in result:
                return True
            log.error(f"WhatsApp response: {result[:200]}")
            return False
    except Exception as e:
        log.error(f"WhatsApp notification failed: {e}")
        return False


# ─── TELEGRAM ─────────────────────────────────────────────────────────────────
def _send_telegram(subject: str, preview: str, topic: str):
    """
    Send Telegram message via bot.

    Required GitHub Secrets:
      TELEGRAM_BOT_TOKEN  — from @BotFather  (looks like: 7123456789:AAExxxxxxxx)
      TELEGRAM_CHAT_ID    — from @userinfobot (looks like: 123456789)

    Setup (3 minutes):
      1. Telegram → @BotFather → /newbot → follow prompts → copy token
      2. Telegram → @userinfobot → /start → copy your chat ID (just the number)
      3. Open your new bot in Telegram and send it ANY message to start the chat
         (bot cannot message you first — this step is required)
      4. Add both as GitHub Secrets under repo → Settings → Secrets → Actions
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id   = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    # ── Validate secrets are present ─────────────────────────────────────────
    if not bot_token or not chat_id:
        missing = []
        if not bot_token: missing.append("TELEGRAM_BOT_TOKEN")
        if not chat_id:   missing.append("TELEGRAM_CHAT_ID")
        log.info(f"Telegram: not configured (missing secrets: {', '.join(missing)})")
        return None

    # ── Validate token format ──────────────────────────────────────────────
    if ":" not in bot_token:
        log.error(f"Telegram: TELEGRAM_BOT_TOKEN looks invalid (should contain ':') — got '{bot_token[:8]}...'")
        return False

    log.info(f"Telegram: sending to chat_id={chat_id} via bot token {bot_token[:8]}...")

    try:
        text = (
            f"✅ *LinkedIn Post Published*\n\n"
            f"📌 *Topic:* {topic}\n\n"
            f"📝 *Preview:*\n_{preview}_\n\n"
            f"🤖 _LinkedIn Agent via GitHub Actions_"
        )

        payload = {
            "chat_id":                  chat_id,
            "text":                     text,
            "parse_mode":               "Markdown",
            "disable_web_page_preview": True,
        }

        url  = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode())
            if result.get("ok"):
                log.info("Telegram: message delivered ✅")
                return True
            else:
                err = result.get("description", "unknown error")
                log.error(f"Telegram: API returned ok=false — {err}")
                log.error("  Common causes:")
                log.error("  • Bot token wrong/expired → regenerate at @BotFather")
                log.error("  • You haven't sent the bot a message yet → open bot in Telegram, send /start")
                log.error("  • Chat ID wrong → check with @userinfobot, use just the number")
                return False

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        log.error(f"Telegram HTTP {e.code}: {body}")
        if e.code == 401:
            log.error("  → 401 Unauthorized: TELEGRAM_BOT_TOKEN is invalid or revoked")
            log.error("    Fix: go to @BotFather → /mybots → your bot → API Token → Revoke & regenerate")
        elif e.code == 400:
            log.error("  → 400 Bad Request: check TELEGRAM_CHAT_ID value")
            log.error("    Fix: message @userinfobot to get your correct chat ID")
        return False
    except Exception as e:
        log.error(f"Telegram notification failed: {e}")
        return False
