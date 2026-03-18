import base64
import glob
import json
import mimetypes
import os
from pathlib import Path

import requests

from logger import get_logger

log = get_logger("preview_cache")

BRANCH = "preview-cache"
TARGET_PATH = "preview_cache/latest_preview.json"


def gh_request(method, url, token, **kwargs):
    headers = kwargs.pop("headers", {})
    headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    return requests.request(method, url, headers=headers, timeout=60, **kwargs)


def ensure_branch(repo, token):
    branch_url = f"https://api.github.com/repos/{repo}/branches/{BRANCH}"
    resp = gh_request("GET", branch_url, token)
    if resp.status_code == 200:
        return
    if resp.status_code != 404:
        resp.raise_for_status()

    repo_resp = gh_request("GET", f"https://api.github.com/repos/{repo}", token)
    repo_resp.raise_for_status()
    default_branch = repo_resp.json()["default_branch"]

    ref_resp = gh_request("GET", f"https://api.github.com/repos/{repo}/git/ref/heads/{default_branch}", token)
    ref_resp.raise_for_status()
    sha = ref_resp.json()["object"]["sha"]

    create_resp = gh_request(
        "POST",
        f"https://api.github.com/repos/{repo}/git/refs",
        token,
        json={"ref": f"refs/heads/{BRANCH}", "sha": sha},
    )
    if create_resp.status_code not in (201, 422):
        create_resp.raise_for_status()


def load_preview_bundle(base_dir):
    payload_files = sorted(glob.glob(str(base_dir / "preview_payload_*.json")))
    if not payload_files:
        raise RuntimeError("No preview payload file found")

    payload_path = Path(payload_files[-1])
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    post_text = (base_dir / payload["post_file"]).read_text(encoding="utf-8")

    diagram_path = base_dir / "diagrams" / payload["diagram_file"]
    if not diagram_path.exists():
        alt_path = base_dir / payload["diagram_file"]
        diagram_path = alt_path if alt_path.exists() else diagram_path
    if not diagram_path.exists():
        raise RuntimeError(f"Diagram file not found: {payload['diagram_file']}")

    suffix = diagram_path.suffix.lower()
    if suffix == ".svg":
        diagram = {
            "kind": "svg",
            "filename": diagram_path.name,
            "content": diagram_path.read_text(encoding="utf-8"),
        }
    else:
        mime = mimetypes.guess_type(diagram_path.name)[0] or "application/octet-stream"
        diagram = {
            "kind": "binary",
            "filename": diagram_path.name,
            "mime": mime,
            "base64": base64.b64encode(diagram_path.read_bytes()).decode("ascii"),
        }

    return {
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_number": os.environ.get("GITHUB_RUN_NUMBER", ""),
        "updated_at": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "payload": payload,
        "post_text": post_text,
        "diagram": diagram,
    }


def put_preview_cache(repo, token, preview_doc):
    ensure_branch(repo, token)
    url = f"https://api.github.com/repos/{repo}/contents/{TARGET_PATH}"

    existing = gh_request("GET", f"{url}?ref={BRANCH}", token)
    sha = None
    if existing.status_code == 200:
        sha = existing.json().get("sha")
    elif existing.status_code != 404:
        existing.raise_for_status()

    body = {
        "message": "chore: update preview cache [skip ci]",
        "content": base64.b64encode(json.dumps(preview_doc, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii"),
        "branch": BRANCH,
    }
    if sha:
        body["sha"] = sha

    put_resp = gh_request("PUT", url, token, json=body)
    put_resp.raise_for_status()


def main():
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        raise RuntimeError("GITHUB_TOKEN and GITHUB_REPOSITORY are required")

    base_dir = Path(__file__).resolve().parent
    preview_doc = load_preview_bundle(base_dir)
    put_preview_cache(repo, token, preview_doc)
    log.info("Preview cache published successfully")


if __name__ == "__main__":
    main()
