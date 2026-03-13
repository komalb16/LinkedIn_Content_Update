#!/usr/bin/env python3
"""
update_profile_readme.py — GitHub Profile README Auto-Update (#18)

After each successful LinkedIn post, this script updates the
"Latest LinkedIn Posts" section in your GitHub profile README
(the special  username/username  repository).

It finds the marker block:
  <!-- LINKEDIN_POSTS_START -->
  ...
  <!-- LINKEDIN_POSTS_END -->

…and replaces it with your 5 most recent posts (title + date + link).
If the markers don't exist yet, the script appends the entire block.

Setup:
  1. Create a repository at github.com/YOUR_USERNAME/YOUR_USERNAME
     (exactly the same name as your GitHub username).
  2. Add a README.md in it.
  3. Optionally add the placeholder markers where you want the section:
       <!-- LINKEDIN_POSTS_START -->
       <!-- LINKEDIN_POSTS_END -->
  4. Make sure the GITHUB_TOKEN secret has  contents:write  permission
     (it does by default in GitHub Actions for the same-owner repo).
  5. Add LINKEDIN_PERSON_URN to GitHub Secrets (already required for posting).

Environment variables (all available in the workflow automatically):
  GITHUB_TOKEN       — provided by Actions
  GITHUB_ACTOR       — the repo owner / your username
  LINKEDIN_POST_URL  — set by the workflow step (the live post URL)
  POST_TOPIC         — set by the workflow step (the topic that was posted)
  POST_DATE          — set by the workflow step (ISO date)
"""

import os
import sys
import json
import base64
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── Markers that delimit our section in the README ───────────────────────────
START_MARKER = "<!-- LINKEDIN_POSTS_START -->"
END_MARKER   = "<!-- LINKEDIN_POSTS_END -->"

# Maximum number of recent posts to show in the README
MAX_POSTS = 5


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    print(f"[{ts}] {msg}")


def gh_api(path: str, method: str = "GET", body: dict = None) -> dict:
    """Minimal GitHub API caller — no external dependencies."""
    token = os.environ.get("GITHUB_TOKEN", "")
    url   = f"https://api.github.com{path}"

    data    = json.dumps(body).encode() if body else None
    headers = {
        "Authorization":        f"Bearer {token}",
        "Accept":               "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent":           "linkedin-agent-readme-updater/1.0",
    }
    if data:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise RuntimeError(f"GitHub API {method} {path} → HTTP {e.code}: {err_body}") from e


def load_post_history(username: str, token: str) -> list[dict]:
    """
    Load the post history from .linkedin_post_history.json in the agent repo.
    Falls back to the single current post if the file doesn't exist.
    """
    agent_repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not agent_repo:
        log("GITHUB_REPOSITORY not set — using only current post")
        return []

    try:
        r = gh_api(f"/repos/{agent_repo}/contents/src/.linkedin_post_history.json")
        data = json.loads(base64.b64decode(r["content"]).decode())
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        log(f"Could not load post history: {e} — using only current post")
        return []


def build_posts_section(posts: list[dict]) -> str:
    """Build the markdown block that goes between the markers."""
    header = "### 📝 Latest LinkedIn Posts\n"
    if not posts:
        return f"{START_MARKER}\n{header}\n_No posts yet._\n\n{END_MARKER}"

    rows = []
    for p in posts[:MAX_POSTS]:
        topic = p.get("topic", "LinkedIn Post")
        date_str = p.get("date", "")[:10]  # YYYY-MM-DD
        url   = p.get("url", "")
        # Format: • [Topic Name](url) — YYYY-MM-DD
        if url:
            rows.append(f"- [{topic}]({url}) — {date_str}")
        else:
            rows.append(f"- {topic} — {date_str}")

    footer = (
        "\n> _Automated with [LinkedIn Agent](https://github.com/"
        + os.environ.get("GITHUB_ACTOR", "")
        + "/"
        + os.environ.get("GITHUB_REPOSITORY", "").split("/")[-1]
        + ")_"
    )

    section_md = header + "\n".join(rows) + "\n" + footer
    return f"{START_MARKER}\n{section_md}\n{END_MARKER}"


def update_readme(username: str) -> bool:
    """
    Fetch the profile README, splice in the posts section, and push the update.
    Returns True if an update was committed, False if no changes were needed.
    """
    profile_repo = f"{username}/{username}"
    log(f"Fetching profile README from {profile_repo}...")

    try:
        r = gh_api(f"/repos/{profile_repo}/contents/README.md")
    except RuntimeError as e:
        if "404" in str(e):
            log(
                f"Profile repository {profile_repo} not found.\n"
                "  Create it at: https://github.com/new\n"
                f"  Repository name must be exactly: {username}"
            )
        else:
            log(f"Failed to fetch README: {e}")
        return False

    sha          = r["sha"]
    current_text = base64.b64decode(r["content"]).decode("utf-8")

    # ── Build updated posts section ───────────────────────────────────────────
    posts = load_post_history(username, os.environ.get("GITHUB_TOKEN", ""))

    # Inject current post at the front if provided
    current_post_url   = os.environ.get("LINKEDIN_POST_URL",  "").strip()
    current_post_topic = os.environ.get("POST_TOPIC",         "LinkedIn Post").strip()
    current_post_date  = os.environ.get("POST_DATE",          datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    if current_post_topic:
        current_entry = {
            "topic": current_post_topic,
            "date":  current_post_date,
            "url":   current_post_url,
        }
        # Avoid duplicates (same topic + date)
        posts = [p for p in posts if not (p.get("topic") == current_post_topic and p.get("date","")[:10] == current_post_date[:10])]
        posts.insert(0, current_entry)

    new_section  = build_posts_section(posts)

    # ── Splice into README ────────────────────────────────────────────────────
    if START_MARKER in current_text and END_MARKER in current_text:
        # Replace existing block
        updated_text = re.sub(
            re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
            new_section,
            current_text,
            flags=re.DOTALL,
        )
    else:
        # No markers found — append the entire section at the end
        updated_text = current_text.rstrip() + "\n\n" + new_section + "\n"
        log("Markers not found in README — appending section at the end.")
        log(f"  Tip: add these markers where you want the section:\n  {START_MARKER}\n  {END_MARKER}")

    if updated_text == current_text:
        log("README is already up-to-date — no commit needed.")
        return False

    # ── Commit the update ─────────────────────────────────────────────────────
    commit_message = f"chore: update LinkedIn posts section [skip ci]"
    encoded        = base64.b64encode(updated_text.encode("utf-8")).decode("ascii")

    log(f"Committing README update to {profile_repo}...")
    gh_api(
        f"/repos/{profile_repo}/contents/README.md",
        method="PUT",
        body={
            "message": commit_message,
            "content": encoded,
            "sha":     sha,
            "committer": {
                "name":  "linkedin-agent[bot]",
                "email": "github-actions[bot]@users.noreply.github.com",
            },
        },
    )
    log(f"✅ Profile README updated at github.com/{profile_repo}")
    return True


def main() -> int:
    log("=" * 56)
    log("  GitHub Profile README Updater")
    log("=" * 56)

    username = os.environ.get("GITHUB_ACTOR", "").strip()
    if not username:
        log("❌ GITHUB_ACTOR not set — cannot determine profile repo name.")
        return 1

    log(f"  GitHub user:   {username}")
    log(f"  Profile repo:  {username}/{username}")
    log(f"  Post topic:    {os.environ.get('POST_TOPIC', '(not set)')}")
    log(f"  Post URL:      {os.environ.get('LINKEDIN_POST_URL', '(not set)')}")
    log("")

    try:
        updated = update_readme(username)
        if updated:
            log("✅ Done — your GitHub profile now shows your latest LinkedIn posts.")
        else:
            log("ℹ️  No update committed.")
        return 0
    except Exception as e:
        log(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
