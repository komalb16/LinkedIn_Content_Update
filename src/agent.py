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
from diagram_generator import DiagramGenerator
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


def run_agent(manual_topic_id: str = None, dry_run: bool = False):
    """Main agent execution."""
    log.info("=" * 60)
    log.info(f"LinkedIn Agent starting — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'} | Manual topic: {manual_topic_id or 'Auto'}")
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

    if dry_run:
        log.info("DRY RUN complete — nothing posted to LinkedIn")
        with open(f"output_post_{topic['id']}.txt", "w") as f:
            f.write(post_text)
        log.info(f"Post saved to output_post_{topic['id']}.txt")
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
        }
        topic_mgr.save_run_history(history_entry)
    else:
        log.error(f"❌ Posting failed: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn Agent — " + COPYRIGHT)
    parser.add_argument("--topic", type=str, help="Manually specify topic ID", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Generate content but don't post")
    parser.add_argument("--list-topics", action="store_true", help="List all available topics")

    args = parser.parse_args()

    if args.list_topics:
        mgr = TopicManager()
        mgr.list_topics()
        sys.exit(0)

    run_agent(manual_topic_id=args.topic, dry_run=args.dry_run)