"""
branded_footer.py
=================
Adds a professional branded footer to diagram images.
Style: profile circle photo | Bold Name | tagline (2 lines) || Follow CTA
"""

import io
import os
from PIL import Image, ImageDraw, ImageFont

# ── Branding config ───────────────────────────────────────────────────────────

DEFAULT_AUTHOR   = "Komal Batra"
DEFAULT_TAGLINE  = "Microsoft Engineer · Turning AI Research into Production Reality"
DEFAULT_CTA      = "Follow for more AI & Engineering content"

# Split tagline into two balanced lines for better readability
TAGLINE_LINE1    = "Microsoft Engineer"
TAGLINE_LINE2    = "Turning AI Research into Production Reality"

# Colours
FOOTER_BG           = (235, 237, 255)
FOOTER_BORDER_TOP   = (99,  102, 241)
AVATAR_BG           = (99,  102, 241)
AVATAR_TEXT_COLOR   = (255, 255, 255)
NAME_COLOR          = (17,  24,  39)
TAGLINE_COLOR_1     = (99,  102, 241)   # indigo for line 1 (Microsoft Engineer)
TAGLINE_COLOR_2     = (75,  85,  99)    # grey for line 2
CTA_COLOR           = (99,  102, 241)
DIVIDER_COLOR       = (209, 213, 219)

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
            "C:\\Windows\\Fonts\\segoeuib.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",
        ]
        if bold else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
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


def _paste_circle(canvas, image_rgba, cx, cy, r):
    diameter = r * 2
    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, diameter, diameter], fill=255)
    rgb = Image.new("RGB", (diameter, diameter), (255, 255, 255))
    if image_rgba.mode == "RGBA":
        rgb.paste(image_rgba.convert("RGB"), mask=image_rgba.split()[3])
    else:
        rgb.paste(image_rgba.convert("RGB"))
    canvas.paste(rgb, (cx - r, cy - r), mask)


def _draw_avatar(canvas, draw, cx, cy, r, name):
    # Glow ring
    draw.ellipse([cx-r-3, cy-r-3, cx+r+3, cy+r+3], fill=(179, 184, 255))
    # White border
    draw.ellipse([cx-r-1, cy-r-1, cx+r+1, cy+r+1], fill=(255, 255, 255))

    photo = _load_profile_photo(r * 2)
    if photo:
        _paste_circle(canvas, photo, cx, cy, r)
    else:
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=AVATAR_BG)
        initials = "".join(w[0].upper() for w in name.split()[:2])
        font = _load_font(max(12, r // 2), bold=True)
        bb   = draw.textbbox((0, 0), initials, font=font)
        draw.text(
            (cx - (bb[2]-bb[0])//2, cy - (bb[3]-bb[1])//2),
            initials, font=font, fill=AVATAR_TEXT_COLOR,
        )


# ── Main public function ──────────────────────────────────────────────────────

def add_branded_footer(
    img,
    author_name=DEFAULT_AUTHOR,
    tagline=DEFAULT_TAGLINE,
    cta=DEFAULT_CTA,
):
    width, height = img.size

    # Taller footer to give text room to breathe — min 90px
    footer_h = max(90, min(130, int(height * 0.12)))
    avatar_r = footer_h // 2 - 10

    # Font sizes — generous so nothing gets compressed
    name_fs  = max(18, int(width * 0.024))
    tag1_fs  = max(13, int(width * 0.016))   # "Microsoft Engineer" — slightly larger
    tag2_fs  = max(12, int(width * 0.014))   # full tagline line 2
    cta_fs   = max(12, int(width * 0.015))

    out  = Image.new("RGB", (width, height + footer_h), FOOTER_BG)
    out.paste(img, (0, 0))
    draw = ImageDraw.Draw(out)

    # Top accent border
    draw.rectangle([(0, height), (width, height + 4)], fill=FOOTER_BORDER_TOP)

    # ── Avatar ────────────────────────────────────────────────────────────────
    pad_left  = int(width * 0.025)
    avatar_cx = pad_left + avatar_r
    avatar_cy = height + footer_h // 2
    _draw_avatar(out, draw, avatar_cx, avatar_cy, avatar_r, author_name)

    # ── Name + 2-line tagline ─────────────────────────────────────────────────
    text_x = avatar_cx + avatar_r + 16

    font_name  = _load_font(name_fs,  bold=True)
    font_tag1  = _load_font(tag1_fs,  bold=True)    # bold for "Microsoft Engineer"
    font_tag2  = _load_font(tag2_fs,  bold=False)   # regular for tagline

    name_bb  = draw.textbbox((0, 0), author_name,  font=font_name)
    tag1_bb  = draw.textbbox((0, 0), TAGLINE_LINE1, font=font_tag1)
    tag2_bb  = draw.textbbox((0, 0), TAGLINE_LINE2, font=font_tag2)

    name_h   = name_bb[3]  - name_bb[1]
    tag1_h   = tag1_bb[3]  - tag1_bb[1]
    tag2_h   = tag2_bb[3]  - tag2_bb[1]

    # Stack: Name / Line1 / Line2 with small gaps
    line_gap = 4
    total_h  = name_h + line_gap + tag1_h + line_gap + tag2_h
    start_y  = height + (footer_h - total_h) // 2

    draw.text((text_x, start_y),                                    author_name,   font=font_name,  fill=NAME_COLOR)
    draw.text((text_x, start_y + name_h + line_gap),                TAGLINE_LINE1, font=font_tag1,  fill=TAGLINE_COLOR_1)
    draw.text((text_x, start_y + name_h + line_gap + tag1_h + line_gap), TAGLINE_LINE2, font=font_tag2, fill=TAGLINE_COLOR_2)

    # ── Vertical divider ──────────────────────────────────────────────────────
    divider_x = width // 2
    draw.line(
        [(divider_x, height + 16), (divider_x, height + footer_h - 16)],
        fill=DIVIDER_COLOR, width=1,
    )

    # ── CTA right side — 2 lines ──────────────────────────────────────────────
    font_cta  = _load_font(cta_fs, bold=False)
    words     = cta.split()
    mid       = len(words) // 2
    line1     = " ".join(words[:mid])
    line2     = " ".join(words[mid:])

    right_cx  = (divider_x + width) // 2

    bb1  = draw.textbbox((0, 0), line1, font=font_cta)
    bb2  = draw.textbbox((0, 0), line2, font=font_cta)
    h1   = bb1[3] - bb1[1]
    h2   = bb2[3] - bb2[1]
    cta_y = height + (footer_h - h1 - 6 - h2) // 2

    draw.text((right_cx - (bb1[2]-bb1[0])//2, cta_y),       line1, font=font_cta, fill=CTA_COLOR)
    draw.text((right_cx - (bb2[2]-bb2[0])//2, cta_y+h1+6),  line2, font=font_cta, fill=CTA_COLOR)

    return out


# ── Bytes wrapper ─────────────────────────────────────────────────────────────

def add_branded_footer_to_bytes(
    image_bytes,
    author_name=DEFAULT_AUTHOR,
    tagline=DEFAULT_TAGLINE,
    cta=DEFAULT_CTA,
):
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
    draw.text((250, 270), "Sample Diagram", fill=(50, 50, 80), font=font)

    out = add_branded_footer(test_img)
    out.save("test_branded_footer.png")
    print(f"Saved: test_branded_footer.png ({out.size[0]}x{out.size[1]}px)")
    print(f"Footer height: {out.size[1] - 600}px")
    photo_found = any(os.path.exists(p) for p in PROFILE_PHOTO_CANDIDATES)
    print(f"Profile photo: {'found ✅' if photo_found else 'using initials fallback'}")
