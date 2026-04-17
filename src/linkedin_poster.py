import os
import re
import time
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

    def _normalize_post_text(self, text):
        cleaned = (text or "").replace("hashtag#", "#").strip()
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned

    def _svg_to_png_bytes(self, svg_path):
        """Convert SVG to PNG bytes using cairosvg, preserving the SVG's native aspect ratio."""
        try:
            import cairosvg
            import re as _re
            # Read SVG to detect its declared width/height so we preserve aspect ratio.
            # LinkedIn recommends max 1200px wide; square posters stay at native 1080px.
            with open(svg_path, "rb") as _f:
                svg_raw = _f.read(512).decode("utf-8", errors="ignore")
            w_m = _re.search(r'width=["\'](\d+)["\']', svg_raw)
            h_m = _re.search(r'height=["\'](\d+)["\']', svg_raw)
            native_w = int(w_m.group(1)) if w_m else 900
            native_h = int(h_m.group(1)) if h_m else 620
            # Scale up to 2× for retina/crisp quality, capped at 2160px
            scale = min(2.0, 2160 / max(native_w, native_h))
            out_w = int(native_w * scale)
            out_h = int(native_h * scale)
            png_bytes = cairosvg.svg2png(
                url=svg_path,
                output_width=out_w,
                output_height=out_h,
            )
            log.info(f"SVG→PNG: {native_w}×{native_h} → {out_w}×{out_h} (scale={scale:.1f}×)")
            return png_bytes
        except Exception as e:
            log.warning("SVG to PNG failed: " + str(e))
            return None

    def _register_image_upload(self):
        """Register image upload with LinkedIn API."""
        url = LINKEDIN_API + "/assets?action=registerUpload"
        payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": self.person_urn,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent"
                }]
            }
        }
        resp = requests.post(url, headers=self.headers, json=payload, timeout=20)
        if resp.status_code != 200:
            log.error("Register upload failed: " + resp.text)
            return None, None
        data = resp.json()
        upload_url = data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
        asset = data["value"]["asset"]
        log.info("Upload registered. Asset: " + asset)
        return upload_url, asset

    def _upload_image_bytes(self, upload_url, image_bytes):
        """Upload image bytes to LinkedIn."""
        upload_headers = {
            "Authorization": "Bearer " + self.access_token,
            "Content-Type": "application/octet-stream",
        }
        resp = requests.put(upload_url, headers=upload_headers, data=image_bytes, timeout=30)
        if resp.status_code not in [200, 201]:
            log.error("Image upload failed: " + str(resp.status_code))
            return False
        log.info("Image uploaded successfully")
        return True

    # LinkedIn ShareCommentary hard limit
    MAX_POST_CHARS = 2950

    def _truncate_text(self, text):
        """Ensure post text never exceeds LinkedIn's 3000-char limit."""
        if len(text) <= self.MAX_POST_CHARS:
            return text
        # Find a good break point — end of a line near the limit
        truncated = text[:self.MAX_POST_CHARS]
        last_nl = truncated.rfind('\n')
        if last_nl > self.MAX_POST_CHARS - 300:  # within last 300 chars
            truncated = truncated[:last_nl]
        else:
            # Fall back to last space
            last_sp = truncated.rfind(' ')
            if last_sp > 0:
                truncated = truncated[:last_sp]
        log.warning(f"Post truncated: {len(text)} -> {len(truncated)} chars")
        return truncated + "\n\n[continued in comments...]"

    def _create_ugc_post(self, text, asset=None):
        """Create LinkedIn UGC post with optional image. Retries on 429/5xx."""
        text = self._truncate_text(text)
        url = LINKEDIN_API + "/ugcPosts"
        media = []
        if asset:
            media = [{
                "status": "READY",
                "description": {"text": "© Komal Batra"},
                "media": asset,
                "title": {"text": "Technical Diagram by Komal Batra"}
            }]
        payload = {
            "author": self.person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "IMAGE" if asset else "NONE",
                    "media": media,
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        for attempt in range(3):
            resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
            if resp.status_code == 201:
                post_id = resp.json().get("id", "unknown")
                log.info("Post created! ID: " + post_id)
                return {"success": True, "post_id": post_id}
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 30))
                log.warning(f"LinkedIn rate-limited — waiting {wait}s (attempt {attempt+1}/3)")
                time.sleep(wait)
                continue
            if resp.status_code >= 500:
                log.warning(f"LinkedIn server error {resp.status_code} (attempt {attempt+1}/3) — retrying in 10s")
                time.sleep(10)
                continue
            log.error("Post creation failed: " + str(resp.status_code) + " " + resp.text)
            return {"success": False, "error": resp.text}
        return {"success": False, "error": "LinkedIn API unavailable after 3 attempts"}

    def create_post_with_image(self, text, image_path, title=""):
        """Post text + diagram image to LinkedIn."""
        try:
            text = self._normalize_post_text(text)
            # Step 1: Get image bytes
            if image_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                log.info(f"Uploading native image: {image_path}")
                with open(image_path, "rb") as f:
                    png_bytes = f.read()
            else:
                # Fallback/Default: Convert SVG to PNG
                png_bytes = self._svg_to_png_bytes(image_path)

            if not png_bytes:
                log.warning("Image processing failed — posting text only")
                return self.create_text_post(text)

            # Step 2: Register upload
            upload_url, asset = self._register_image_upload()
            if not upload_url:
                log.warning("Upload registration failed — posting text only")
                return self.create_text_post(text)

            time.sleep(1)

            # Step 3: Upload image
            uploaded = self._upload_image_bytes(upload_url, png_bytes)
            if not uploaded:
                log.warning("Image upload failed — posting text only")
                return self.create_text_post(text)

            time.sleep(3)  # LinkedIn needs time to process

            # Step 4: Create post with image
            result = self._create_ugc_post(text, asset)
            if result.get("success"):
                return result

            # Fallback to text if image post fails
            log.warning("Image post failed — falling back to text only")
            return self.create_text_post(text)

        except Exception as e:
            log.error("Unexpected error: " + str(e))
            return self.create_text_post(text)

    def create_text_post(self, text):
        """Post text only to LinkedIn."""
        try:
            text = self._normalize_post_text(text)
            result = self._create_ugc_post(text, asset=None)
            return result
        except Exception as e:
            log.error("Text post failed: " + str(e))
            return {"success": False, "error": str(e)}
