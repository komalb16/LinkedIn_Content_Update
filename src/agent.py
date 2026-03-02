import os
import sys
import re
import argparse
import requests
from datetime import datetime
from topic_manager import TopicManager
from diagram_generator import DiagramGenerator
from logger import get_logger

log = get_logger("agent")

COPYRIGHT = "© Komal Batra"
AUTHOR = "Komal Batra"

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

POST_SYSTEM = "You are a LinkedIn content strategist writing for " + AUTHOR + ", a tech thought leader. Rules: Open with a powerful hook. Use emojis strategically. Write 150-300 words. Include 3-5 trending hashtags at the end. End EVERY post with: " + COPYRIGHT + ". Tone: Confident, knowledgeable, conversational."

DIAGRAM_SYSTEM = "You are a technical SVG diagram creator for " + AUTHOR + ". Requirements: Return ONLY raw SVG code, starting with <svg and ending with </svg>. viewBox 0 0 900 550, width 900, height 550. Dark background #0A0F1E. Colors: #00D4AA, #FF6B6B, #FFE66D, #A29BFE, #4ECDC4, #FFFFFF. Include " + COPYRIGHT + " in bottom-right font-size 11 fill #475569. Professional and detailed."


def call_gemini(prompt, system):
    print("DEBUG: Checking for GEMINI_API_KEY in environment...")
    print("DEBUG: Available env keys:", [k for k in os.environ.keys() if not k.startswith("npm") and not k.startswith("RUNNER")])

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        print("DEBUG: GEMINI_API_KEY not found! Trying alternate names...")
        for key in os.environ.keys():
            if "GEMINI" in key.upper() or "API" in key.upper():
                print("DEBUG: Found possible key:", key)
        raise ValueError("GEMINI_API_KEY not set in environment")

    print("DEBUG: GEMINI_API_KEY found, length=" + str(len(api_key)))

    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 2048, "temperature": 0.8}
    }

    resp = requests.post(
        GEMINI_API_URL + "?key=" + api_key,
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    print("DEBUG: Gemini API response status:", resp.status_code)

    if resp.status_code != 200:
        print("DEBUG: Gemini error response:", resp.text)

    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def generate_post(topic):
    log.info("Generating post for topic: " + topic["name"])
    prompt = "Write a LinkedIn post about: " + topic["prompt"] + "\nAngle: " + topic.get("angle", "practical insights") + "\nMake it timely for " + datetime.now().strftime("%B %Y") + ".\nEnd with a question to drive comments."
    result = call_gemini(prompt, POST_SYSTEM)
    log.info("Post generated (" + str(len(result)) + " chars)")
    return result


def generate_diagram(topic, diagram_type):
    log.info("Generating " + diagram_type + " for: " + topic["name"])
    prompt = "Create a " + diagram_type + " SVG about: " + topic["diagram_subject"] + "\nMake it detailed and informative. Return ONLY the SVG code, nothing else."
    result = call_gemini(prompt, DIAGRAM_SYSTEM)
    match = re.search(r"<svg[\s\S]*?<\/svg>", result, re.IGNORECASE)
    if match:
        return match.group(0)
    return result


def run_agent(manual_topic_id=None, dry_run=False):
    log.info("=" * 60)
    log.info("LinkedIn Agent starting — " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("Mode: " + ("DRY RUN" if dry_run else "LIVE") + " | Topic: " + (manual_topic_id or "Auto"))
    log.info("=" * 60)

    topic_mgr = TopicManager()
    diagram_gen = DiagramGenerator()

    if not dry_run:
        from linkedin_poster import LinkedInPoster
        poster = LinkedInPoster(
            access_token=os.environ.get("LINKEDIN_ACCESS_TOKEN"),
            person_urn=os.environ.get("LINKEDIN_PERSON_URN"),
        )

    topic = topic_mgr.get_topic(manual_topic_id) if manual_topic_id else topic_mgr.get_next_topic()
    log.info("Selected topic: " + topic["name"])

    post_text = generate_post(topic)
    log.info("\n--- GENERATED POST ---")
    log.info(post_text)
    log.info("---------------------\n")

    diagram_type = topic_mgr.get_diagram_type_for_topic(topic)
    svg_content = generate_diagram(topic, diagram_type)
    diagram_path = diagram_gen.save_svg(svg_content, topic["id"])
    log.info("Diagram saved: " + diagram_path)

    if dry_run:
        log.info("DRY RUN complete — nothing posted to LinkedIn")
        with open("output_post_" + topic["id"] + ".txt", "w") as f:
            f.write(post_text)
        log.info("Post saved to output_post_" + topic["id"] + ".txt")
        return

    log.info("Posting to LinkedIn...")
    result = poster.create_post_with_image(
        text=post_text,
        image_path=diagram_path,
        title=topic["name"] + " | " + diagram_type,
    )

    if result.get("success"):
        log.info("Successfully posted! ID: " + str(result.get("post_id")))
        topic_mgr.save_run_history({
            "timestamp": datetime.now().isoformat(),
            "topic_id": topic["id"],
            "topic_name": topic["name"],
            "post_id": result.get("post_id"),
            "status": "success",
        })
    else:
        log.error("Posting failed: " + str(result.get("error")))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn Agent — © Komal Batra")
    parser.add_argument("--topic", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-topics", action="store_true")
    args = parser.parse_args()

    if args.list_topics:
        TopicManager().list_topics()
        sys.exit(0)

    run_agent(manual_topic_id=args.topic, dry_run=args.dry_run)
