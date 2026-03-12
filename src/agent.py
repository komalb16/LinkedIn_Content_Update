"""
LinkedIn Agent - Main Entry Point
Generates and posts AI-powered content with diagrams to LinkedIn.
© Author (see AUTHOR_NAME env var)
"""

import os
import sys
import json
import argparse
from openai import OpenAI
from datetime import datetime
from topic_manager import TopicManager
from linkedin_poster import LinkedInPoster
from diagram_generator import DiagramGenerator, save_newsletter_svg
from logger import get_logger

log = get_logger("agent")

# Author identity — reads from env var so any fork owner gets their name on posts.
# Set AUTHOR_NAME as a GitHub Actions variable (repo → Settings → Variables).
# Falls back to GITHUB_ACTOR (the repo owner's username) — zero setup needed.
_raw_author = (
    os.environ.get("AUTHOR_NAME") or
    os.environ.get("GITHUB_ACTOR") or
    "LinkedIn Agent"
)
AUTHOR    = _raw_author
COPYRIGHT = "© " + _raw_author

POST_SYSTEM_PROMPT = f"""You are a LinkedIn content strategist writing on behalf of {AUTHOR}, 
a tech thought leader and engineer. Your posts are insightful, engaging, and professional.

Rules:
- Open with a powerful hook (question, bold stat, or provocative statement)
- Use emojis strategically (not excessively)
- Write 150–300 words
- Include 3–5 relevant trending hashtags at the end
- End EVERY post with: {COPYRIGHT}
- Tone: Confident, knowledgeable, conversational
- Never use generic filler phrases like "In today's fast-paced world"
- Make it feel human-written and opinionated
"""

DIAGRAM_SYSTEM_PROMPT = f"""You are a technical diagram creator for {AUTHOR}.
Create SVG diagrams that are visually stunning and technically accurate.

Requirements:
- Return ONLY raw SVG code, starting with <svg and ending with </svg>
- viewBox="0 0 900 550" width="900" height="550"
- Dark background: #0A0F1E
- Color palette: #00D4AA (teal), #FF6B6B (coral), #FFE66D (yellow), #A29BFE (purple), #4ECDC4 (cyan), #FFFFFF, #94A3B8
- Font: use font-family="'Segoe UI', Arial, sans-serif"
- Include a title at the top in white, bold
- Add "{COPYRIGHT}" in bottom-right corner: font-size="11" fill="#475569"
- Make it professional, detailed, and informative — worth saving and sharing
- Use rounded rectangles, arrows, connecting lines, and clear labels
"""


NEWSLETTER_SYSTEM_PROMPT = """You are a technical writer for a developer newsletter called "The Automation Log".
Given a topic, produce a JSON object describing three sections of a newsletter edition.

Rules:
- Return ONLY valid JSON, no markdown fences, no extra text
- Each section has up to 3 steps, each step has: label (short title), detail (one sentence), and optionally code (one-line snippet)
- The last step of each section should have "result": true to highlight it
- Keep labels under 30 chars, details under 50 chars, code under 48 chars

JSON format:
{
  "title": "Short punchy edition title (max 70 chars)",
  "built": [
    {"label": "What was built", "detail": "One sentence description"},
    {"label": "Key feature", "detail": "How it works", "code": "example_code()"},
    {"label": "RESULT", "detail": "The outcome", "result": true}
  ],
  "broke": [
    {"label": "What broke", "detail": "The symptom"},
    {"label": "Root cause", "detail": "Why it happened", "code": "bad_code = 'example'"},
    {"label": "FIXED", "detail": "How it was resolved", "result": true}
  ],
  "learned": [
    {"label": "The insight", "detail": "First observation"},
    {"label": "The principle", "detail": "The general rule"},
    {"label": "TAKEAWAY", "detail": "What you should do differently", "result": true}
  ]
}
"""


def generate_newsletter_content(client, topic: dict) -> dict:
    """Ask the LLM to produce Built/Broke/Learned content for the newsletter diagram."""
    log.info(f"Generating newsletter content for: {topic['name']}")
    prompt = (
        f"Topic: {topic['name']}\n"
        f"Context: {topic.get('prompt', topic['name'])}\n\n"
        "Produce the Built/Broke/Learned newsletter sections for this topic. "
        "The 'built' section shows what was built or how it works. "
        "The 'broke' section shows a common mistake or pitfall with this topic. "
        "The 'learned' section gives the key professional insight. "
        "Make it concrete, specific, and useful for a developer audience."
    )
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=800,
            messages=[
                {"role": "system", "content": NEWSLETTER_SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ]
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        import re
        raw = re.sub(r'^```[a-z]*\n?', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\n?```$', '', raw, flags=re.MULTILINE)
        data = json.loads(raw)
        log.info("Newsletter content generated successfully")
        return data
    except Exception as e:
        log.warning(f"Newsletter content generation failed: {e} — using fallback")
        # Fallback: minimal content so the diagram still renders
        return {
            "title": f"Building with {topic['name']}",
            "built":   [{"label": topic['name'], "detail": "Core concept implemented"},
                        {"label": "RESULT", "detail": "System running as expected", "result": True}],
            "broke":   [{"label": "Common pitfall", "detail": "Missed edge case"},
                        {"label": "FIXED", "detail": "Added validation + tests", "result": True}],
            "learned": [{"label": "Key insight", "detail": "Understanding the tradeoffs"},
                        {"label": "TAKEAWAY", "detail": "Test the unhappy path first", "result": True}],
        }


def generate_post(client, topic: dict) -> str:
    """Generate a LinkedIn post for the given topic."""
    log.info(f"Generating post for topic: {topic['name']}")
    
    prompt = f"""Write a LinkedIn post about: {topic['prompt']}

Include:
- A specific angle: {topic.get('angle', 'practical insights and real-world impact')}
- Make it timely and relevant to what's happening in {datetime.now().strftime('%B %Y')}
- Add a thought-provoking question at the end to drive comments
"""
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=800,
        messages=[
            {"role": "system", "content": POST_SYSTEM_PROMPT},
            {"role": "user",   "content": prompt}
        ]
    )
    
    post_text = response.choices[0].message.content
    log.info(f"Post generated ({len(post_text)} chars)")
    return post_text


def generate_diagram(client: OpenAI, topic: dict, diagram_type: str) -> str:
    """Generate an SVG diagram for the given topic."""
    log.info(f"Generating {diagram_type} diagram for: {topic['name']}")
    
    prompt = f"""Create a {diagram_type} SVG diagram about: {topic['diagram_subject']}

Make it a high-quality, shareable technical visual that {AUTHOR}'s LinkedIn followers will save and share.
Include real commands, steps, or concepts — not placeholders.
"""
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=3000,
        messages=[
            {"role": "system", "content": DIAGRAM_SYSTEM_PROMPT},
            {"role": "user",   "content": prompt}
        ]
    )
    
    raw = response.choices[0].message.content
    # Extract SVG from response
    import re
    match = re.search(r'<svg[\s\S]*?<\/svg>', raw, re.IGNORECASE)
    if match:
        svg = match.group(0)
        log.info("SVG diagram extracted successfully")
        return svg
    
    log.warning("Could not extract clean SVG from response")
    return raw


def run_agent(manual_topic_id: str = None, dry_run: bool = False, newsletter: bool = False):
    """Main agent execution."""
    log.info("=" * 60)
    log.info(f"LinkedIn Agent starting — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'} | Manual topic: {manual_topic_id or 'Auto'} | Newsletter diagram: {'ON' if newsletter else 'off'}")

    # ── Auto-detect newsletter day from schedule_config.json ─────────────────
    # If --newsletter was not explicitly passed, check whether today's schedule
    # config has newsletter: true. This is set from the dashboard toggle —
    # no manual intervention needed.
    if not newsletter:
        try:
            import schedule_checker as _sc
            _cfg    = _sc.load_config()
            _now    = _sc.utc_now()
            _daykey = _sc.DAYS[_now.weekday()]
            _day_cfg = _cfg.get("weekly", {}).get(_daykey, {})
            if _day_cfg.get("newsletter", False):
                newsletter = True
                log.info(f"📰 Auto-enabled newsletter: {_daykey} is marked as a newsletter day in schedule_config.json")
        except Exception as _e:
            log.warning(f"Could not auto-detect newsletter day: {_e}")
    log.info("=" * 60)

    # Initialize clients
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        log.error("GROQ_API_KEY not set")
        sys.exit(1)
    
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    topic_mgr = TopicManager()
    diagram_gen = DiagramGenerator()
    
    if not dry_run:
        poster = LinkedInPoster(
            access_token=os.environ.get("LINKEDIN_ACCESS_TOKEN"),
            person_urn=os.environ.get("LINKEDIN_PERSON_URN"),
        )

    # Select topic
    if manual_topic_id:
        topic = topic_mgr.get_topic(manual_topic_id)
        log.info(f"Manual topic selected: {topic['name']}")
    else:
        topic = topic_mgr.get_next_topic()
        log.info(f"Auto-selected topic: {topic['name']}")

    # Generate post
    post_text = generate_post(client, topic)
    log.info("\n--- GENERATED POST ---")
    log.info(post_text)
    log.info("---------------------\n")

    # Generate diagram
    diagram_type = topic_mgr.get_diagram_type_for_topic(topic)
    svg_content = generate_diagram(client, topic, diagram_type)
    
    # Save diagram as file
    diagram_path = diagram_gen.save_svg(svg_content, topic['id'])
    log.info(f"Diagram saved: {diagram_path}")

    # ── Newsletter diagram ────────────────────────────────────────────────────
    newsletter_diagram_path = None
    if newsletter:
        log.info("Newsletter mode ON — generating Built/Broke/Learned diagram...")
        edition_num = os.environ.get("NEWSLETTER_EDITION")  # optional: set as repo variable
        nl_data = generate_newsletter_content(client, topic)
        newsletter_diagram_path = save_newsletter_svg(
            topic_id   = topic['id'],
            topic_name = nl_data.get("title", topic['name']),
            built_steps  = nl_data.get("built",   []),
            broke_steps  = nl_data.get("broke",   []),
            learned_steps= nl_data.get("learned", []),
            edition      = edition_num,
        )
        log.info(f"Newsletter diagram saved: {newsletter_diagram_path}")


    if dry_run:
        log.info("DRY RUN complete — nothing posted to LinkedIn")
        # Save outputs for review
        with open(f"output_post_{topic['id']}.txt", "w") as f:
            f.write(post_text)
        log.info(f"Post saved to output_post_{topic['id']}.txt")
        if newsletter_diagram_path:
            log.info(f"Newsletter diagram (dry run): {newsletter_diagram_path}")
        return

    # Post to LinkedIn
    log.info("Posting to LinkedIn...")
    
    # First post the diagram as an image article/post
    result = poster.create_post_with_image(
        text=post_text,
        image_path=diagram_path,
        title=f"{topic['name']} | {diagram_type}",
    )
    
    if result.get("success"):
        log.info(f"✅ Successfully posted! Post ID: {result.get('post_id')}")

        # #18 Export post metadata to GITHUB_OUTPUT so the workflow can
        # pass it to update_profile_readme.py and check_token_expiry.py
        post_id   = result.get("post_id", "")
        post_date = datetime.now().strftime("%Y-%m-%d")
        # Build the LinkedIn post URL (profile-relative; exact URL needs post_id)
        post_url  = f"https://www.linkedin.com/feed/update/{post_id}/" if post_id else ""
        gh_output = os.environ.get("GITHUB_OUTPUT", "")
        if gh_output:
            with open(gh_output, "a") as gho:
                gho.write(f"POSTED_TOPIC={topic['name']}\n")
                gho.write(f"POSTED_DATE={post_date}\n")
                gho.write(f"POSTED_URL={post_url}\n")

        # Save run history
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "topic_id": topic['id'],
            "topic_name": topic['name'],
            "diagram_type": diagram_type,
            "post_id": post_id,
            "url": post_url,
            "status": "success",
            "newsletter_diagram": newsletter_diagram_path or "",
        }
        topic_mgr.save_run_history(history_entry)
    else:
        log.error(f"❌ Posting failed: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn Agent — " + COPYRIGHT)
    parser.add_argument("--topic", type=str, help="Manually specify topic ID", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Generate content but don't post")
    parser.add_argument("--newsletter", action="store_true", help="Also generate Built/Broke/Learned newsletter diagram")
    parser.add_argument("--list-topics", action="store_true", help="List all available topics")
    
    args = parser.parse_args()
    
    if args.list_topics:
        mgr = TopicManager()
        mgr.list_topics()
        sys.exit(0)
    
    run_agent(manual_topic_id=args.topic, dry_run=args.dry_run, newsletter=args.newsletter)
