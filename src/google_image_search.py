"""
google_image_search.py
======================
Uses SerpApi (Google Images) to fetch professional technical diagrams.
Drop-in replacement for _fetch_internet_image() in diagram_generator.py.

SETUP:
  Set environment variable:
  SERPAPI_KEY=your_key_here

  Or in GitHub Secrets: SERPAPI_KEY

INTEGRATION into diagram_generator.py:
  1. Add at top:
       from google_image_search import fetch_diagram_image

  2. Replace _fetch_internet_image call with:
       img_bytes, img_source_url = fetch_diagram_image(
           _effective_search_name,
           post_text=post_text,
       )
"""

import io
import os
import re
import logging
import requests
from PIL import Image, ImageDraw, ImageFont, ImageStat
from branded_footer import add_branded_footer

log = logging.getLogger("google_image_search")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ── Config ────────────────────────────────────────────────────────────────────

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
SERPAPI_URL = "https://serpapi.com/search"

MIN_IMAGE_BYTES = 25_000
MAX_QUERIES     = 4

# ── Source quality scoring ────────────────────────────────────────────────────

SOURCE_PRIORITY = {
    "bytebytego.com":                   5,
    "blog.bytebytego.com":              5,
    "algomaster.io":                    5,
    "designgurus.io":                   5,
    "designgurus.substack.com":         5,
    "nikkisiapno.substack.com":         5,
    "eugeneyan.com":                    5,
    "huyenchip.com":                    5,
    "lilianweng.github.io":             5,
    "colah.github.io":                  5,
    "substackcdn.com":                  4,
    "learnbybuilding.ai":               4,
    "promptingguide.ai":                4,
    "cameronrwolfe.substack.com":       4,
    "newsletter.pragmaticengineer.com": 4,
    "towardsdatascience.com":           4,
    "levelup.gitconnected.com":         4,
    "martinfowler.com":                 4,
    "highscalability.com":              4,
    "newsletter.systemdesign.one":      4,
    "systemdesign.one":                 4,
    "architecturenotes.co":             4,
    "github.blog":                      4,
    "huggingface.co":                   4,
    "blog.langchain.dev":               4,
    "blog.llamaindex.ai":               4,
    "engineering.fb.com":               4,
    "engineering.linkedin.com":         4,
    "eng.uber.com":                     4,
    "techblog.netflix.com":             4,
    "dev.to":                           3,
    "medium.com":                       3,
    "substack.com":                     3,
    "dzone.com":                        3,
    "wandb.ai":                         3,
    "neptune.ai":                       3,
    "geeksforgeeks.org":                2,
    "educba.com":                       2,
    "docs.aws.amazon.com":              2,
    "cloud.google.com":                 2,
    "learn.microsoft.com":              2,
    "kubernetes.io":                    2,
    "docs.docker.com":                  2,
}

DOMAIN_BLACKLIST = {
    "shutterstock.com", "gettyimages.com", "dreamstime.com",
    "istockphoto.com", "unsplash.com", "pexels.com", "pixabay.com",
    "freepik.com", "flaticon.com", "vecteezy.com", "vectorstock.com",
    "stock.adobe.com", "alamy.com", "canva.com", "slideshare.net",
    "slideteam.net", "sketchbubble.com", "pinterest.com", "pinimg.com",
    "dribbble.com", "behance.net", "chegg.com", "coursehero.com",
    "quizlet.com", "brainly.com", "scribd.com", "simplilearn.com",
    "edureka.co", "wixstatic.com", "squarespace-cdn.com",
    "techcrunch.com", "wired.com", "theverge.com", "businessinsider.com",
}

URL_BLACKLIST_PATTERNS = [
    "lecture", "/slides/", ".pptx", "ppt/", "chapter", "lec-",
    "module-", "week-", "/photo/", "/photos/", "stock-photo",
    "-portrait", "-headshot", "clip-art", "clipart",
]

# ── Query builder ─────────────────────────────────────────────────────────────

def _build_queries(topic_name, post_text=""):
    # Map abstract topics to concrete searchable terms
    TOPIC_MAP = {
        "ai hype":           "AI adoption ROI diagram",
        "pitfall":           "AI integration architecture diagram",
        "python htmx":       "Python web framework comparison diagram",
        "secure data":       "data security architecture diagram",
        "implementation":    "system implementation architecture",
    }
    topic_lower = topic_name.lower()
    mapped = None
    for key, val in TOPIC_MAP.items():
        if key in topic_lower:
            mapped = val
            break

    subject = mapped or f"{topic_name} architecture diagram"

    return [
        f"{subject} site:medium.com OR site:dev.to OR site:towardsdatascience.com",
        f"{topic_name} system design diagram",
        f"{subject}",
        f"{topic_name} technical infographic engineering",
    ][:MAX_QUERIES]

# ── SerpApi call ──────────────────────────────────────────────────────────────

def _serpapi_image_search(query):
    if not SERPAPI_KEY:
        log.error("SERPAPI_KEY not set in environment.")
        return []

    params = {
        "engine":  "google_images",
        "q":       query,
        "api_key": SERPAPI_KEY,
        "num":     10,
        "safe":    "active",
    }

    try:
        resp = requests.get(SERPAPI_URL, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("images_results", [])
        elif resp.status_code == 401:
            log.error("SerpApi: Invalid API key.")
        elif resp.status_code == 429:
            log.warning("SerpApi: Rate limit hit.")
        else:
            log.warning(f"SerpApi returned {resp.status_code}: {resp.text[:120]}")
    except Exception as e:
        log.error(f"SerpApi request failed: {e}")

    return []

# ── Filtering and scoring ─────────────────────────────────────────────────────

def _source_priority(url):
    url_lower = url.lower()
    for domain, score in SOURCE_PRIORITY.items():
        if domain in url_lower:
            return score
    return 1

def _is_blacklisted(url):
    u = url.lower()
    if any(d in u for d in DOMAIN_BLACKLIST):
        return True
    return any(p in u for p in URL_BLACKLIST_PATTERNS)

def _relevance_score(url, topic_name):
    url_lower = url.lower()
    keywords = {w.lower() for w in re.split(r"\W+", topic_name) if len(w) >= 3}
    return min(sum(2 for kw in keywords if kw in url_lower), 6)

# ── Image quality checks ──────────────────────────────────────────────────────

def _is_person_photo(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((80, 80))
        pixels = list(img.getdata())
        skin = sum(
            1 for r, g, b in pixels
            if r > 80 and g > 50 and b > 30
            and r > g > b and r - b > 20
            and r < 240 and g < 200
        )
        return (skin / max(len(pixels), 1)) > 0.22
    except Exception:
        return False

def _is_low_complexity(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        stat = ImageStat.Stat(img)
        return (sum(stat.stddev) / 3) < 18
    except Exception:
        return False

def _is_illustration_or_photo(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((150, 150))
        q = img.quantize(colors=32)
        pixels = list(q.getdata())
        counts = {}
        for px in pixels:
            counts[px] = counts.get(px, 0) + 1
        dom_ratio = max(counts.values()) / max(len(pixels), 1)
        return dom_ratio < 0.08
    except Exception:
        return False

# ── Download and validate ─────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

def _is_svg(url, content_type, raw):
    """Detect SVG by URL extension, content-type, or file header."""
    if url.lower().endswith(".svg"):
        return True
    if "svg" in content_type.lower():
        return True
    if raw[:64].lstrip().startswith(b"<svg") or b"<svg" in raw[:256].lower():
        return True
    return False


def _svg_to_png(svg_bytes):
    """Convert SVG bytes to PNG bytes using cairosvg if available, else return None."""
    try:
        import cairosvg
        png = cairosvg.svg2png(bytestring=svg_bytes, output_width=1200)
        return png
    except ImportError:
        pass
    # Fallback: try Pillow's wand/inkscape via subprocess
    try:
        import subprocess, tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp_svg:
            tmp_svg.write(svg_bytes)
            tmp_svg_path = tmp_svg.name
        tmp_png_path = tmp_svg_path.replace(".svg", ".png")
        result = subprocess.run(
            ["inkscape", "--export-type=png", f"--export-filename={tmp_png_path}", tmp_svg_path],
            capture_output=True, timeout=15
        )
        if result.returncode == 0 and os.path.exists(tmp_png_path):
            with open(tmp_png_path, "rb") as f:
                png = f.read()
            os.unlink(tmp_svg_path)
            os.unlink(tmp_png_path)
            return png
    except Exception:
        pass
    return None


def _download_and_validate(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type and "svg" not in content_type:
            return None
        raw = resp.content
        if len(raw) < 1_000:
            return None

        # Handle SVG — convert to PNG first
        if _is_svg(url, content_type, raw):
            log.info(f"SVG detected, converting to PNG: {url[:60]}")
            png = _svg_to_png(raw)
            if png:
                raw = png
            else:
                # cairosvg/inkscape not available — skip quality checks, return as-is
                # The footer function will handle it gracefully
                log.info("SVG conversion unavailable, returning raw SVG bytes")
                return raw

        if len(raw) < MIN_IMAGE_BYTES:
            return None
        if _is_person_photo(raw):
            log.info(f"Rejected person photo: {url[:60]}")
            return None
        if _is_low_complexity(raw):
            log.info(f"Rejected low-complexity: {url[:60]}")
            return None
        # NOTE: _is_illustration_or_photo() removed — it incorrectly rejected
        # colorful technical diagrams (ByteByteGo, AlgoMaster, DesignGurus) because
        # those images have many distinct colors and no dominant palette entry,
        # causing dom_ratio < 0.08 and a false rejection. Person-photo detection
        # and low-complexity detection are sufficient guards.
        return raw
    except Exception as e:
        log.debug(f"Download failed {url[:60]}: {e}")
        return None

# ── Main public function ──────────────────────────────────────────────────────

def fetch_diagram_image(topic_name, post_text=""):
    """
    Search Google Images via SerpApi for a technical diagram.
    Returns (image_bytes, source_url).
    Drop-in replacement for _fetch_internet_image() in diagram_generator.py.
    """
    if not SERPAPI_KEY:
        log.error("SERPAPI_KEY not set.")
        return None, ""

    queries = _build_queries(topic_name, post_text)
    log.info(f"SerpApi search for '{topic_name}' — {len(queries)} queries")

    candidates = []
    seen_urls = set()

    for query in queries:
        log.info(f"  Query: {query}")
        results = _serpapi_image_search(query)
        log.info(f"  Got {len(results)} results")

        for item in results:
            url = item.get("original", "")
            if not url or url in seen_urls:
                continue
            if _is_blacklisted(url):
                continue
            seen_urls.add(url)
            priority  = _source_priority(url)
            relevance = _relevance_score(url, topic_name)
            score     = relevance * 100 + priority
            size_hint = item.get("original_width", 0) * item.get("original_height", 0)
            candidates.append((score, size_hint, url))

    if not candidates:
        log.warning(f"No valid candidates for '{topic_name}'")
        return None, ""

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    log.info(f"Evaluating top {min(len(candidates), 15)} candidates")

    for score, size_hint, url in candidates[:15]:
        log.info(f"  Trying score={score}: {url[:70]}")
        raw = _download_and_validate(url)
        if raw:
            log.info(f"  Selected: {url}")
            return raw, url

    log.warning(f"All candidates failed for '{topic_name}'")
    return None, ""

# ── Attribution footer ────────────────────────────────────────────────────────

def add_attribution_footer(image_bytes, author_name="Komal Batra", accent_color=None):
    from branded_footer import add_branded_footer_to_bytes
    return add_branded_footer_to_bytes(image_bytes, author_name=author_name)
# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    topic = " ".join(sys.argv[1:]) or "RAG architecture"
    print(f"\nSearching for: {topic!r}\n")

    if not SERPAPI_KEY:
        print("ERROR: SERPAPI_KEY not set.")
        print("Run: export SERPAPI_KEY=your_key_here")
        sys.exit(1)

    raw, url = fetch_diagram_image(topic)
    if raw:
        out_path = f"test_diagram_{topic.replace(' ', '_')[:30]}.png"
        with open(out_path, "wb") as f:
            f.write(add_attribution_footer(raw))
        print(f"\nSaved: {out_path}  ({len(raw):,} bytes)")
        print(f"Source: {url}")
    else:
        print("\nNo image found.")