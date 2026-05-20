"""
branded_footer.py
=================
Adds a professional branded footer to diagram images.
Style: profile circle photo | Bold Name | tagline || Follow CTA

SETUP:
  1. Save your LinkedIn photo as src/profile_photo.jpg  (or .png / .webp)
  2. Drop this file into src/
  3. Follow integration steps below

INTEGRATION into diagram_generator.py:
  At the top add:
      from branded_footer import add_branded_footer

  Replace the footer block (lines ~4763-4832) with:
      footer_img = add_branded_footer(img, author_name=_COPYRIGHT_NAME)
      footer_img.save(png_filename)

INTEGRATION into google_image_search.py:
  Replace add_attribution_footer() body with:
      from branded_footer import add_branded_footer_to_bytes
      return add_branded_footer_to_bytes(image_bytes, author_name=author_name)
"""

import io
import os
from PIL import Image, ImageDraw, ImageFont

# ── Branding config ───────────────────────────────────────────────────────────

DEFAULT_AUTHOR  = "Komal Batra"
DEFAULT_TAGLINE = "Microsoft Engineer · Turning AI Research into Production Reality"
DEFAULT_CTA     = "Follow for more AI & Engineering content"

# Colours — light lavender style matching sample image
FOOTER_BG           = (235, 237, 255)   # light lavender background
FOOTER_BORDER_TOP   = (99,  102, 241)   # indigo top accent line
AVATAR_BG           = (99,  102, 241)   # fallback avatar circle (if no photo)
AVATAR_TEXT_COLOR   = (255, 255, 255)   # initials colour
NAME_COLOR          = (17,  24,  39)    # near-black
TAGLINE_COLOR       = (75,  85,  99)    # grey
CTA_COLOR           = (99,  102, 241)   # indigo
DIVIDER_COLOR       = (209, 213, 219)   # light grey

# Profile photo — place your photo here as one of these filenames in src/
_HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE_PHOTO_CANDIDATES = [
    os.path.join(_HERE, "profile_photo.jpg"),
    os.path.join(_HERE, "profile_photo.png"),
    os.path.join(_HERE, "profile_photo.webp"),
]

# ── Font loader ───────────────────────────────────────────────────────────────

def _load_font(size, bold=False):
    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "C:\\Windows\\Fonts\\segoeuib.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",
        ]
        if bold else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "C:\\Windows\\Fonts\\segoeui.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
        ]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


# ── Profile photo loader ──────────────────────────────────────────────────────

def _load_profile_photo(diameter):
    """Load profile photo, centre-crop to square, resize to diameter."""
    for path in PROFILE_PHOTO_CANDIDATES:
        if os.path.exists(path):
            try:
                photo = Image.open(path).convert("RGBA")
                w, h  = photo.size
                side  = min(w, h)
                left  = (w - side) // 2
                top   = (h - side) // 2
                photo = photo.crop((left, top, left + side, top + side))
                photo = photo.resize((diameter, diameter), Image.LANCZOS)
                return photo
            except Exception:
                pass
    return None


# ── Circular mask paste ───────────────────────────────────────────────────────

def _paste_circle(canvas, image_rgba, cx, cy, r):
    """Paste image_rgba onto canvas clipped to a circle centred at (cx, cy)."""
    diameter = r * 2
    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, diameter, diameter], fill=255)
    rgb = Image.new("RGB", (diameter, diameter), (255, 255, 255))
    if image_rgba.mode == "RGBA":
        rgb.paste(image_rgba.convert("RGB"), mask=image_rgba.split()[3])
    else:
        rgb.paste(image_rgba.convert("RGB"))
    canvas.paste(rgb, (cx - r, cy - r), mask)


# ── Avatar drawing ────────────────────────────────────────────────────────────

def _draw_avatar(canvas, draw, cx, cy, r, name):
    """Draw circular avatar: real photo if available, else initials fallback."""
    # Glow ring
    draw.ellipse(
        [cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3],
        fill=(179, 184, 255),
    )
    # White border ring
    draw.ellipse(
        [cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1],
        fill=(255, 255, 255),
    )

    photo = _load_profile_photo(r * 2)
    if photo:
        _paste_circle(canvas, photo, cx, cy, r)
    else:
        # Fallback — solid colour + initials
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=AVATAR_BG)
        initials = "".join(w[0].upper() for w in name.split()[:2])
        font = _load_font(max(12, r // 2), bold=True)
        bb   = draw.textbbox((0, 0), initials, font=font)
        draw.text(
            (cx - (bb[2] - bb[0]) // 2, cy - (bb[3] - bb[1]) // 2),
            initials, font=font, fill=AVATAR_TEXT_COLOR,
        )


# ── Main public function ──────────────────────────────────────────────────────

def add_branded_footer(
    img,
    author_name=DEFAULT_AUTHOR,
    tagline=DEFAULT_TAGLINE,
    cta=DEFAULT_CTA,
):
    """
    Add a professional branded footer to a PIL Image (RGB mode).
    Returns a new PIL Image with the footer appended at the bottom.
    """
    width, height = img.size

    # Footer height — proportional, min 72px
    footer_h = max(72, min(110, int(height * 0.10)))
    avatar_r = footer_h // 2 - 8

    # Font sizes — scale with image width
    name_fs = max(16, int(width * 0.022))
    tag_fs  = max(11, int(width * 0.014))   # slightly smaller for longer tagline
    cta_fs  = max(11, int(width * 0.014))

    # Create output canvas
    out  = Image.new("RGB", (width, height + footer_h), FOOTER_BG)
    out.paste(img, (0, 0))
    draw = ImageDraw.Draw(out)

    # Top accent border
    draw.rectangle([(0, height), (width, height + 3)], fill=FOOTER_BORDER_TOP)

    # ── Avatar ────────────────────────────────────────────────────────────────
    pad_left  = int(width * 0.025)
    avatar_cx = pad_left + avatar_r
    avatar_cy = height + footer_h // 2
    _draw_avatar(out, draw, avatar_cx, avatar_cy, avatar_r, author_name)

    # ── Name + tagline (left of divider) ─────────────────────────────────────
    text_x = avatar_cx + avatar_r + 14

    font_name = _load_font(name_fs, bold=True)
    font_tag  = _load_font(tag_fs,  bold=False)

    name_bb = draw.textbbox((0, 0), author_name, font=font_name)
    name_h  = name_bb[3] - name_bb[1]
    tag_bb  = draw.textbbox((0, 0), tagline,     font=font_tag)
    tag_h   = tag_bb[3]  - tag_bb[1]

    block_h = name_h + 5 + tag_h
    text_y  = height + (footer_h - block_h) // 2

    draw.text((text_x, text_y),              author_name, font=font_name, fill=NAME_COLOR)
    draw.text((text_x, text_y + name_h + 5), tagline,     font=font_tag,  fill=TAGLINE_COLOR)

    # ── Vertical divider ──────────────────────────────────────────────────────
    divider_x = width // 2
    draw.line(
        [(divider_x, height + 14), (divider_x, height + footer_h - 14)],
        fill=DIVIDER_COLOR, width=1,
    )

    # ── CTA (right of divider) ────────────────────────────────────────────────
    font_cta = _load_font(cta_fs, bold=False)
    words    = cta.split()
    mid      = len(words) // 2
    line1    = " ".join(words[:mid])
    line2    = " ".join(words[mid:])

    right_cx = (divider_x + width) // 2

    bb1  = draw.textbbox((0, 0), line1, font=font_cta)
    bb2  = draw.textbbox((0, 0), line2, font=font_cta)
    h1   = bb1[3] - bb1[1]
    h2   = bb2[3] - bb2[1]
    cta_y = height + (footer_h - h1 - 4 - h2) // 2

    draw.text((right_cx - (bb1[2] - bb1[0]) // 2, cta_y),          line1, font=font_cta, fill=CTA_COLOR)
    draw.text((right_cx - (bb2[2] - bb2[0]) // 2, cta_y + h1 + 4), line2, font=font_cta, fill=CTA_COLOR)

    return out


# ── Bytes convenience wrapper ─────────────────────────────────────────────────

def add_branded_footer_to_bytes(
    image_bytes,
    author_name=DEFAULT_AUTHOR,
    tagline=DEFAULT_TAGLINE,
    cta=DEFAULT_CTA,
):
    """
    Accept raw image bytes, add branded footer, return PNG bytes.
    Drop-in replacement for add_attribution_footer() in google_image_search.py.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        bg  = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img).convert("RGB")
        out = add_branded_footer(img, author_name=author_name, tagline=tagline, cta=cta)
        buf = io.BytesIO()
        out.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        print(f"[branded_footer] Footer failed ({e}), returning original")
        return image_bytes


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_img = Image.new("RGB", (900, 600), (240, 242, 255))
    draw = ImageDraw.Draw(test_img)
    draw.rectangle([40, 40, 860, 560], outline=(99, 102, 241), width=3)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
    draw.text((180, 270), "Sample Diagram — Komal Batra", fill=(50, 50, 80), font=font)

    out = add_branded_footer(test_img)
    out_path = "test_branded_footer.png"
    out.save(out_path)
    print(f"Saved: {out_path}  ({out.size[0]}x{out.size[1]}px)")
    print(f"Tagline: {DEFAULT_TAGLINE}")
    photo_found = any(os.path.exists(p) for p in PROFILE_PHOTO_CANDIDATES)
    print(f"Profile photo: {'found ✅' if photo_found else 'not found — using initials fallback'}")
