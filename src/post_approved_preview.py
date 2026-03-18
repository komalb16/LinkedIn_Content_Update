import argparse
import json
import os
import tempfile
import zipfile
from datetime import datetime
from io import BytesIO

import requests

from linkedin_poster import LinkedInPoster
from logger import get_logger
from topic_manager import TopicManager

log = get_logger("approved_preview")


def write_github_output(key, value):
    gho = os.environ.get("GITHUB_OUTPUT")
    if not gho:
        return
    try:
        with open(gho, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
    except Exception as exc:
        log.warning(f"Could not write GITHUB_OUTPUT: {exc}")


def gh_get(url, token, accept="application/vnd.github+json"):
    return requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=60,
    )


def download_preview_bundle(repo, run_id, artifact_name, token):
    art_url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts"
    art_resp = gh_get(art_url, token)
    art_resp.raise_for_status()
    artifacts = art_resp.json().get("artifacts", [])
    artifact = next((a for a in artifacts if a.get("name") == artifact_name), None) if artifact_name else None
    if artifact is None and artifacts:
        artifact = artifacts[0]
    if artifact is None:
        raise RuntimeError("No artifact found for approved preview run")

    zip_resp = gh_get(artifact["archive_download_url"], token, accept="application/octet-stream")
    zip_resp.raise_for_status()
    return zip_resp.content


def extract_preview_bundle(zip_bytes):
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        payload_name = next((n for n in names if n.endswith(".json") and "preview_payload_" in n), None)
        post_name = next((n for n in names if n.endswith(".txt") and "output_post_" in n), None)
        if not payload_name or not post_name:
            raise RuntimeError("Preview bundle is missing metadata or post text")

        payload = json.loads(zf.read(payload_name).decode("utf-8"))
        post_text = zf.read(post_name).decode("utf-8")

        diagram_name = None
        if payload.get("diagram_file"):
            diagram_name = next((n for n in names if n.endswith(payload["diagram_file"])), None)
        if diagram_name is None:
            diagram_name = next((n for n in names if n.lower().endswith((".svg", ".png", ".gif"))), None)
        if diagram_name is None:
            raise RuntimeError("Preview bundle is missing the generated diagram")

        return payload, post_text, diagram_name, zf.read(diagram_name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-name", default="")
    args = parser.parse_args()

    gh_token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not gh_token or not repo:
        raise RuntimeError("GITHUB_TOKEN and GITHUB_REPOSITORY are required")

    preview_zip = download_preview_bundle(repo, args.run_id, args.artifact_name, gh_token)
    payload, post_text, diagram_name, diagram_bytes = extract_preview_bundle(preview_zip)

    suffix = os.path.splitext(diagram_name)[1] or ".svg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(diagram_bytes)
        temp_path = tmp.name

    try:
        poster = LinkedInPoster(
            access_token=os.environ.get("LINKEDIN_ACCESS_TOKEN"),
            person_urn=os.environ.get("LINKEDIN_PERSON_URN"),
        )
        result = poster.create_post_with_image(
            text=post_text,
            image_path=temp_path,
            title=payload.get("topic_name", ""),
        )
        if not result.get("success"):
            raise RuntimeError(result.get("error", "Unknown LinkedIn posting error"))

        try:
            TopicManager().save_run_history({
                "timestamp": datetime.now().isoformat(),
                "topic_id": payload.get("topic_id", ""),
                "topic_name": payload.get("topic_name", ""),
                "category": payload.get("category", ""),
                "mode": payload.get("mode", "topic"),
                "status": "success",
            })
        except Exception as exc:
            log.warning(f"Could not save approved-preview run history: {exc}")

        write_github_output("POSTED_TOPIC", payload.get("topic_name", ""))
        write_github_output("POSTED_TITLE", payload.get("topic_name", ""))
        write_github_output("POST_TOPIC_ID", payload.get("topic_id", ""))
        write_github_output("POSTED_DATE", datetime.now().strftime("%Y-%m-%d"))
        write_github_output("POSTED_URL", result.get("post_url", ""))
        log.info(f"Approved preview posted successfully for {payload.get('topic_name', 'unknown topic')}")
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
