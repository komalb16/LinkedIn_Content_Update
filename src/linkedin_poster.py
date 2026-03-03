import requests
from logger import get_logger

log = get_logger("linkedin")

LINKEDIN_API = "https://api.linkedin.com/v2"


class LinkedInPoster:
    def __init__(self, access_token, person_urn):
        if not access_token:
            raise ValueError("LINKEDIN_ACCESS_TOKEN is required")
        if not person_urn:
            raise ValueError("LINKEDIN_PERSON_URN is required")
        self.access_token = access_token
        self.person_urn = person_urn
        self.headers = {
            "Authorization": "Bearer " + access_token,
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        log.info("LinkedIn poster initialized for: " + person_urn)

    def create_post_with_image(self, text, image_path, title=""):
        return self.create_text_post(text)

    def create_text_post(self, text):
        try:
            url = LINKEDIN_API + "/ugcPosts"
            payload = {
                "author": self.person_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            resp = requests.post(url, headers=self.headers, json=payload)
            if resp.status_code != 201:
                log.error("LinkedIn API error: " + str(resp.status_code) + " " + resp.text)
                return {"success": False, "error": resp.text}
            post_id = resp.json().get("id", "unknown")
            log.info("Post created! ID: " + post_id)
            return {"success": True, "post_id": post_id}
        except Exception as e:
            log.error("Unexpected error: " + str(e))
            return {"success": False, "error": str(e)}
