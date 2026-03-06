"""
notifier.py — Multi-channel post notifications
Supports: Email (Gmail SMTP), WhatsApp (CallMeBot free), Telegram (bot)

Setup guide is in README.md under "Notifications".
All channels are optional — only active if env vars are set.
"""

import os
import smtplib
import urllib.request
import urllib.parse
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from logger import get_logger

log = get_logger("notifier")


def notify_all(topic: str, post_preview: str, is_dry_run: bool = False) -> None:
    """Send notifications across all configured channels."""
    if is_dry_run:
        log.info("Dry run — skipping notifications")
        return

    # Build a short preview (first 200 chars)
    preview = post_preview[:200].replace("\n", " ").strip()
    if len(post_preview) > 200:
        preview += "..."

    subject = f"✅ LinkedIn Post Published — {topic}"
    body = f"Your LinkedIn post on '{topic}' was just published.\n\nPreview:\n{preview}\n\n— LinkedIn Agent 🤖"

    results = []
    results.append(("Email",     _send_email(subject, body)))
    results.append(("WhatsApp",  _send_whatsapp(subject, preview, topic)))
    results.append(("Telegram",  _send_telegram(subject, preview, topic)))

    active = [(ch, ok) for ch, ok in results if ok is not None]
    if not active:
        log.info("No notification channels configured — skipping")
    else:
        for ch, ok in active:
            log.info(f"  {ch}: {'✅ sent' if ok else '❌ failed'}")


# ─── EMAIL (Gmail SMTP) ───────────────────────────────────────────────────────
def _send_email(subject: str, body: str):
    """
    Send email via Gmail SMTP.
    Required env vars:
      NOTIFY_EMAIL          — your Gmail address (e.g. yourname@gmail.com)
      NOTIFY_EMAIL_PASSWORD — Gmail App Password (not your real password)
      NOTIFY_TO_EMAIL       — recipient email (can be same as sender)

    How to get a Gmail App Password:
      1. Enable 2FA on your Google account
      2. Go to myaccount.google.com → Security → App Passwords
      3. Create one for "Mail" → copy the 16-char password
    """
    sender   = os.environ.get("NOTIFY_EMAIL", "")
    password = os.environ.get("NOTIFY_EMAIL_PASSWORD", "")
    to_email = os.environ.get("NOTIFY_TO_EMAIL", "")

    if not all([sender, password, to_email]):
        return None  # Not configured

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
              Your post on <strong style="color:#0ea5e9">{subject.split('—')[-1].strip()}</strong> is now live on LinkedIn.
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


# ─── WHATSAPP (CallMeBot — free, no credit card) ─────────────────────────────
def _send_whatsapp(subject: str, preview: str, topic: str):
    """
    Send WhatsApp message via CallMeBot (100% free).
    Required env vars:
      CALLMEBOT_PHONE  — your WhatsApp number with country code (e.g. +919876543210)
      CALLMEBOT_APIKEY — your CallMeBot API key

    How to get your CallMeBot API key (takes 2 minutes):
      1. Save the number +34 644 59 71 29 in your WhatsApp contacts as "CallMeBot"
      2. Send this message to that number:
         I allow callmebot to send me messages
      3. You'll receive your API key via WhatsApp
      4. Add CALLMEBOT_PHONE and CALLMEBOT_APIKEY as GitHub secrets
    """
    phone  = os.environ.get("CALLMEBOT_PHONE", "")
    apikey = os.environ.get("CALLMEBOT_APIKEY", "")

    if not all([phone, apikey]):
        return None  # Not configured

    try:
        text = f"✅ LinkedIn Post Published!\n\nTopic: {topic}\n\n{preview}\n\n— LinkedIn Agent 🤖"
        encoded = urllib.parse.quote(text)
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded}&apikey={apikey}"

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            result = response.read().decode()
            if "Message sent" in result or "200" in result:
                return True
            else:
                log.error(f"WhatsApp response: {result[:200]}")
                return False
    except Exception as e:
        log.error(f"WhatsApp notification failed: {e}")
        return False


# ─── TELEGRAM (free bot) ──────────────────────────────────────────────────────
def _send_telegram(subject: str, preview: str, topic: str):
    """
    Send Telegram message via bot (free, instant).
    Required env vars:
      TELEGRAM_BOT_TOKEN — your bot token from @BotFather
      TELEGRAM_CHAT_ID   — your chat ID from @userinfobot

    How to set up Telegram notifications (takes 3 minutes):
      1. Open Telegram → search @BotFather → send /newbot
      2. Follow prompts → you'll get a token like 7123456789:AAE...
      3. Search @userinfobot in Telegram → send /start → copy your chat ID
      4. Search your new bot → send it any message to activate the chat
      5. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as GitHub secrets
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id   = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not all([bot_token, chat_id]):
        return None  # Not configured

    try:
        text = (
            f"✅ *LinkedIn Post Published*\n\n"
            f"📌 *Topic:* {topic}\n\n"
            f"📝 *Preview:*\n_{preview}_\n\n"
            f"🤖 _LinkedIn Agent via GitHub Actions_"
        )

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            return result.get("ok", False)

    except Exception as e:
        log.error(f"Telegram notification failed: {e}")
        return False
