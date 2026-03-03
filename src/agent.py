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

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"
POST_SYSTEM = "You are a LinkedIn content strategist for Komal Batra, a tech thought leader. Write engaging posts 150-300 words with emojis. Add 3-5 hashtags formatted as #AI #DevOps (just # symbol, no word hashtag). Do NOT add any copyright notice to the post."
DIAGRAM_SYSTEM = "You are a technical SVG diagram creator for Komal Batra. Return ONLY raw SVG code starting with <svg and ending with </svg>. Dark bg #0A0F1E. Colors: #00D4AA #FF6B6B #FFE66D #A29BFE #FFFFFF. Add © Komal Batra bottom-right font-size 11."

def call_ai(prompt, system):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY secret not set")
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2048,
        "temperature": 0.8
    }
    resp = requests.post(GROQ_URL, json=payload, headers=headers)
    if resp.status_code != 200:
        print("Groq error:", resp.text)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def generate_post(topic):
    log.info("Generating post: " + topic["name"])
    prompt = "Write a LinkedIn post about: " + topic["prompt"] + "\nAngle: " + topic.get("angle", "practical insights") + "\nMake it timely for " + datetime.now().strftime("%B %Y") + ". End with a question to drive comments."
    return call_ai(prompt, POST_SYSTEM)

def generate_diagram(topic, diagram_type):
    log.info("Generating diagram: " + diagram_type)
    prompt = "Create a " + diagram_type + " SVG about: " + topic["diagram_subject"] + "\nReturn ONLY raw SVG code, nothing else."
    result = call_ai(prompt, DIAGRAM_SYSTEM)
    match = re.search(r"<svg[\s\S]*?<\/svg>", result, re.IGNORECASE)
    return match.group(0) if match else result
    
def run_agent(manual_topic_id=None, dry_run=False):
    log.info("=" * 60)
    log.info("LinkedIn Agent — © Komal Batra — " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("Mode: " + ("DRY RUN" if dry_run else "LIVE"))
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
    log.info("Topic: " + topic["name"])

    post_text = generate_post(topic)
    log.info("POST:\n" + post_text)

    diagram_type = topic_mgr.get_diagram_type_for_topic(topic)
    svg_content = generate_diagram(topic, diagram_type)
    diagram_path = diagram_gen.save_svg(svg_content, topic["id"], topic["name"], diagram_type)
    log.info("Diagram saved: " + diagram_path)

    if dry_run:
        with open("output_post_" + topic["id"] + ".txt", "w") as f:
            f.write(post_text)
        log.info("DRY RUN complete. Post saved.")
        return

    result = poster.create_post_with_image(text=post_text, image_path=diagram_path, title=topic["name"])
    if result.get("success"):
        log.info("Posted! ID: " + str(result.get("post_id")))
        topic_mgr.save_run_history({"timestamp": datetime.now().isoformat(), "topic_id": topic["id"], "status": "success"})
    else:
        log.error("Failed: " + str(result.get("error")))
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-topics", action="store_true")
    args = parser.parse_args()
    if args.list_topics:
        TopicManager().list_topics()
        sys.exit(0)
    run_agent(manual_topic_id=args.topic, dry_run=args.dry_run)
