"""
LinkedIn Poster — Handles posting text + images to LinkedIn via API v2.
© Komal Batra
"""

import os
import json
import time
import base64
import requests
import cairosvg
from pathlib import Path
from logger import get_logger

log = get_logger("linkedin")

LINKEDIN_API = "https://api.linkedin.com/v2"
LINKEDIN_MEDIA_API = "https://uploads.linkedin.com/mediaUpload"


class LinkedInPoster:
    def __init__(self, access_token: str, person_urn: str):
        if not access_token:
            raise ValueError("LINKEDIN_ACCESS_TOKEN is required")
        if not person_urn:
            raise ValueError("LINKEDIN_PERSON_URN is required (e.g. urn:li:person:ABC123)")
        
        self.access_token = access_token
        self.person_urn = person_urn
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        log.info(f"LinkedIn poster initialized for: {person_urn}")

    def _svg_to_png(self, svg_path: str) -> str:
        """Convert SVG to PNG for LinkedIn upload."""
        png_path = svg_path.replace(".svg", ".png")
        cairosvg.svg2png(
            url=svg_path,
            write_to=png_path,
            output_width=1200,
            output_height=630,
        )
        log.info(f"SVG converted to PNG: {png_path}")
        return png_path

    def _register_image_upload(self) -> tuple[str, str]:
        """Step 1: Register image upload with LinkedIn."""
        url = f"{LINKEDIN_API}/assets?action=registerUpload"
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
        
        resp = requests.post(url, headers=self.headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        
        upload_url = data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
        asset = data["value"]["asset"]
        
        log.info(f"Image upload registered. Asset: {asset}")
        return upload_url, asset

    def _upload_image(self, upload_url: str, image_path: str):
        """Step 2: Upload the image binary."""
        with open(image_path, "rb") as f:
            img_data = f.read()
        
        upload_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/octet-stream",
        }
        resp = requests.put(upload_url, headers=upload_headers, data=img_data)
        resp.raise_for_status()
        log.info("Image uploaded successfully")

    def _create_post(self, text: str, asset: str = None) -> dict:
        """Step 3: Create the LinkedIn post."""
        url = f"{LINKEDIN_API}/ugcPosts"
        
        media_content = []
        if asset:
            media_content = [{
                "status": "READY",
                "description": {"text": "© Komal Batra"},
                "media": asset,
                "title": {"text": "Technical Diagram"}
            }]
        
        payload = {
            "author": self.person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "IMAGE" if asset else "NONE",
                    "media": media_content,
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        resp = requests.post(url, headers=self.headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    def create_post_with_image(self, text: str, image_path: str, title: str = "") -> dict:
        """Full flow: upload image + create post."""
        try:
            # Convert SVG to PNG if needed
            if image_path.endswith(".svg"):
                image_path = self._svg_to_png(image_path)
            
            # Register upload
            upload_url, asset = self._register_image_upload()
            time.sleep(1)
            
            # Upload image
            self._upload_image(upload_url, image_path)
            time.sleep(2)  # LinkedIn needs processing time
            
            # Create post
            result = self._create_post(text, asset)
            post_id = result.get("id", "unknown")
            
            log.info(f"Post created successfully! ID: {post_id}")
            return {"success": True, "post_id": post_id}
            
        except requests.HTTPError as e:
            log.error(f"LinkedIn API error: {e.response.status_code} — {e.response.text}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            log.error(f"Unexpected error: {e}")
            return {"success": False, "error": str(e)}

    def create_text_post(self, text: str) -> dict:
        """Create text-only post (fallback if image fails)."""
        try:
            result = self._create_post(text)
            post_id = result.get("id", "unknown")
            log.info(f"Text post created! ID: {post_id}")
            return {"success": True, "post_id": post_id}
        except Exception as e:
            log.error(f"Text post failed: {e}")
            return {"success": False, "error": str(e)}
