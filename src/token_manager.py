#!/usr/bin/env python3
"""
token_manager.py — LinkedIn Token Management & Auto-Refresh

This module handles:
1. Token expiry tracking and alerts
2. Automatic token refresh via OAuth flow
3. GitHub Actions secret update automation
4. Fallback notifications if refresh fails

Setup:
  Add GitHub Secrets:
    - LINKEDIN_ACCESS_TOKEN (your current token)
    - LINKEDIN_TOKEN_DATE (YYYY-MM-DD when token was created/refreshed)
    - LINKEDIN_CLIENT_ID (from LinkedIn Developer Portal)
    - LINKEDIN_CLIENT_SECRET (from LinkedIn Developer Portal)
    - LINKEDIN_REFRESH_TOKEN (optional, for OAuth refresh grants)

  Add GitHub Action environment variable:
    - GITHUB_TOKEN (auto-provided by GHA)
"""

import os
import json
import requests
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Tuple

try:
    from logger import get_logger
    log = get_logger("token_manager")
except ImportError:
    class _Logger:
        def info(self, m): print(f"[TOKEN_MANAGER] {m}")
        def warning(self, m): print(f"[TOKEN_MANAGER] WARN {m}")
        def error(self, m): print(f"[TOKEN_MANAGER] ERROR {m}")
    log = _Logger()


# Token management constants
TOKEN_LIFETIME_DAYS = 60
WARN_CRITICAL = 3     # Renew immediately
WARN_URGENT = 7       # Renew within a week
WARN_NOTICE = 14      # Getting close
TOKEN_DATE_ENV = "LINKEDIN_TOKEN_DATE"
TOKEN_ENV = "LINKEDIN_ACCESS_TOKEN"
TOKEN_REFRESH_ENV = "LINKEDIN_REFRESH_TOKEN"
CLIENT_ID_ENV = "LINKEDIN_CLIENT_ID"
CLIENT_SECRET_ENV = "LINKEDIN_CLIENT_SECRET"
GITHUB_TOKEN_ENV = "GITHUB_TOKEN"

# LinkedIn OAuth endpoints
LINKEDIN_OAUTH_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"


class TokenManager:
    """Manage LinkedIn OAuth tokens: track expiry, alert, and auto-refresh."""

    def __init__(self):
        self.token = os.environ.get(TOKEN_ENV, "")
        self.token_date_str = os.environ.get(TOKEN_DATE_ENV, "")
        self.refresh_token = os.environ.get(TOKEN_REFRESH_ENV, "")
        self.client_id = os.environ.get(CLIENT_ID_ENV, "")
        self.client_secret = os.environ.get(CLIENT_SECRET_ENV, "")
        self.github_token = os.environ.get(GITHUB_TOKEN_ENV, "")
        self.github_repo = os.environ.get("GITHUB_REPOSITORY", "")

    def get_days_remaining(self) -> Optional[int]:
        """
        Calculate days until token expiry.
        Returns None if token_date not set or invalid.
        """
        if not self.token_date_str:
            log.warning(f"No {TOKEN_DATE_ENV} set; cannot calculate token expiry")
            return None

        try:
            token_date = datetime.strptime(self.token_date_str, "%Y-%m-%d").date()
            expiry_date = token_date + timedelta(days=TOKEN_LIFETIME_DAYS)
            today = date.today()
            days_remaining = (expiry_date - today).days
            return max(-1, days_remaining)  # -1 if already expired
        except ValueError as e:
            log.error(f"Invalid token date format: {self.token_date_str} (use YYYY-MM-DD): {e}")
            return None

    def get_status(self) -> Dict[str, any]:
        """Return detailed token status for reporting."""
        days_remaining = self.get_days_remaining()
        
        if days_remaining is None:
            return {"status": "UNKNOWN", "days_remaining": None, "message": "Token date not configured"}
        
        if days_remaining < 0:
            return {"status": "EXPIRED", "days_remaining": 0, "message": "Token expired!"}
        elif days_remaining <= WARN_CRITICAL:
            return {"status": "CRITICAL", "days_remaining": days_remaining, "message": f"🚨 Token expires in {days_remaining} days — renew NOW"}
        elif days_remaining <= WARN_URGENT:
            return {"status": "URGENT", "days_remaining": days_remaining, "message": f"⚠️ Token expires in {days_remaining} days"}
        elif days_remaining <= WARN_NOTICE:
            return {"status": "NOTICE", "days_remaining": days_remaining, "message": f"ℹ️ Token expires in {days_remaining} days"}
        else:
            return {"status": "HEALTHY", "days_remaining": days_remaining, "message": f"✅ Token healthy ({days_remaining} days remaining)"}

    def verify_token_valid(self) -> bool:
        """Test if token is still valid by calling LinkedIn API."""
        if not self.token:
            log.warning("No access token set")
            return False

        try:
            url = "https://api.linkedin.com/v2/userinfo"
            headers = {"Authorization": f"Bearer {self.token}"}
            resp = requests.get(url, headers=headers, timeout=10)
            
            if resp.status_code == 200:
                log.info("✅ Token verified successfully")
                return True
            elif resp.status_code == 401:
                log.error("❌ Token invalid or expired (401)")
                return False
            else:
                log.warning(f"Unexpected status {resp.status_code} when verifying token")
                return False
        except Exception as e:
            log.error(f"Failed to verify token: {e}")
            return False

    def attempt_token_refresh(self) -> Tuple[bool, str]:
        """
        Attempt to refresh token using refresh_token grant.
        Returns (success: bool, message: str)
        """
        if not self.refresh_token:
            return False, "No refresh_token set — manual token regeneration required"

        if not self.client_id or not self.client_secret:
            return False, "Missing LINKEDIN_CLIENT_ID or LINKEDIN_CLIENT_SECRET"

        try:
            log.info("Attempting OAuth token refresh...")
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            resp = requests.post(LINKEDIN_OAUTH_TOKEN_URL, data=payload, timeout=30)

            if resp.status_code != 200:
                error_msg = resp.json().get("error_description", resp.text)
                return False, f"OAuth refresh failed: {error_msg}"

            data = resp.json()
            new_token = data.get("access_token")
            if not new_token:
                return False, "No access_token in OAuth response"

            log.info("✅ Token refreshed successfully")
            # Note: Caller must update GitHub secret with new token
            return True, new_token

        except Exception as e:
            return False, f"Token refresh exception: {e}"

    def update_github_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        Update a GitHub repository secret via REST API.
        Requires GITHUB_TOKEN with 'repo' scope.
        Returns True if successful.
        """
        if not self.github_token or not self.github_repo:
            log.warning("Cannot update GitHub secret: missing GITHUB_TOKEN or GITHUB_REPOSITORY")
            return False

        try:
            owner, repo = self.github_repo.split("/", 1)
            url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{secret_name}"
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }

            # Get public key for encryption (GitHub requires encrypted secrets)
            pub_key_url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key"
            pk_resp = requests.get(pub_key_url, headers=headers, timeout=10)
            if pk_resp.status_code != 200:
                log.error(f"Failed to get GitHub public key: {pk_resp.text}")
                return False

            pk_data = pk_resp.json()
            public_key = pk_data.get("key")
            key_id = pk_data.get("key_id")

            # Encrypt secret with libsodium
            try:
                import nacl.public
                import nacl.encoding
                public_key_obj = nacl.public.PublicKey(public_key, encoder=nacl.encoding.Base64Encoder)
                encrypted = nacl.public.Box(nacl.public.PrivateKey.generate(), public_key_obj).encrypt(
                    secret_value.encode(), encoder=nacl.encoding.Base64Encoder
                )
                encoded_secret = encrypted.ciphertext.decode()
            except ImportError:
                log.warning("PyNaCl not installed; skipping secret encryption. Install with: pip install pynacl")
                return False
            except Exception as e:
                log.error(f"Failed to encrypt secret: {e}")
                return False

            # Update secret
            payload = {
                "encrypted_value": encoded_secret,
                "key_id": key_id,
            }
            resp = requests.put(url, headers=headers, json=payload, timeout=30)

            if resp.status_code in [201, 204]:
                log.info(f"✅ GitHub secret '{secret_name}' updated successfully")
                return True
            else:
                log.error(f"Failed to update GitHub secret: {resp.status_code} {resp.text}")
                return False

        except Exception as e:
            log.error(f"GitHub secret update exception: {e}")
            return False

    def send_alert_notification(self, status: Dict) -> None:
        """Send alert via notifier module if token is expiring soon."""
        try:
            import notifier
            
            if status["status"] == "CRITICAL":
                notifier.alert(
                    "🚨 LinkedIn Token Critical",
                    f"Token expires in {status['days_remaining']} days. Renew immediately to prevent posting failures.",
                    severity="critical"
                )
            elif status["status"] == "URGENT":
                notifier.alert(
                    "⚠️ LinkedIn Token Expiring Soon",
                    f"Token expires in {status['days_remaining']} days. Plan token refresh this week.",
                    severity="warning"
                )
            elif status["status"] == "NOTICE":
                notifier.alert(
                    "ℹ️ LinkedIn Token Refresh Coming",
                    f"Token expires in {status['days_remaining']} days. No action needed yet.",
                    severity="info"
                )
        except ImportError:
            log.warning("notifier module not available; skipping alerts")
        except Exception as e:
            log.warning(f"Failed to send alert: {e}")


def main():
    """
    Entry point for token management checks.
    Typically called from a scheduled GitHub Action.
    """
    manager = TokenManager()
    status = manager.get_status()

    print("=" * 60)
    print("  LinkedIn Token Status Check")
    print("=" * 60)
    print(f"Status: {status['status']}")
    print(f"Message: {status['message']}")
    print(f"Days Remaining: {status['days_remaining']}")

    # Alert if expiring soon
    if status["status"] in ["CRITICAL", "URGENT", "NOTICE"]:
        manager.send_alert_notification(status)

        # Attempt auto-refresh if token is not verified
        if not manager.verify_token_valid():
            log.info("Token verification failed; attempting refresh...")
            success, result = manager.attempt_token_refresh()
            if success:
                if manager.update_github_secret(TOKEN_ENV, result):
                    # Update date as well
                    today = date.today().isoformat()
                    manager.update_github_secret(TOKEN_DATE_ENV, today)
                    print("✅ Token refreshed and GitHub secrets updated")
                    return 0
                else:
                    print("❌ Token refreshed but GitHub secret update failed")
                    return 1
            else:
                print(f"❌ Token refresh failed: {result}")
                return 1

    print("=" * 60)
    return 0


if __name__ == "__main__":
    exit(main())
