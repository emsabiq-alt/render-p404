"""Thumbnail, title, description, chapter pack for Project 404 render.

Thumbnail generation is deterministic fallback PNG. It also writes MCP-ready
prompts so the same variants can be sent to an image MCP/9router server.
"""
import json
import math
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 720
INK = (28, 20, 14)
PAPER = (235, 216, 177)
PAPER2 = (232, 223, 208)
COPPER = (164, 98, 43)
DARK = (18, 13, 9)
OUT_DIR = Path(__file__).resolve().parents[1] / "export" / "thumbnail_ab"
FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"


def viral_titles():
    return [
        "GUNUNG INI MENGUBAH IKLIM DUNIA",
        "MISTERI LETUSAN RAKSASA 1257",
        "MONSTER LOMBOK YANG DILUPAKAN",
    ]


def format_ts(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def chapters():
    # Dari assembly v3; offsets bridge chapter. Dibulatkan untuk YouTube.
    return [
        ("PROLOG — JEJAK ABU DI LANGIT DUNIA", 0),
        ("BAB 1 — LOMBOK SEBELUM 1257", 4),
        ("BAB 2 — KALDERA YANG MELEDAK", 174),
        ("BAB 3 — MUSIM DINGIN TANPA MATAHARI", 348),
        ("BAB 4 — BUKTI ILMIAH DI ES DAN TANAH", 522),
        ("BAB 5 — WARISAN SAMALAS", 696),
        ("PENUTUP", 858),
    ]


def youtube_description(chs=None):
    chs = chs or chapters()
    ch_text = "\n".join(f"{format_ts(t)} {name}" for name, t in chs)
    return f"""SAMALAS 1257 adalah salah satu letusan vulkanik terbesar dalam sejarah manusia. Dari Lombok, abu dan sulfur letusan ini menyebar ke atmosfer, meninggalkan jejak di inti es kutub, catatan sejarah, dan perubahan iklim abad pertengahan.

Dokumenter ini merangkai bukti geologi, sejarah, dan sains iklim untuk menjelaskan bagaimana satu gunung di Nusantara ikut mengubah langit dunia.

CHAPTERS
{ch_text}

CREDIT MUSIK
- Ossuary 5 - Rest by Kevin MacLeod (incompetech.com), Licensed under Creative Commons: By Attribution 4.0 License.
- Prelude and Action by Kevin MacLeod (incompetech.com), Licensed under Creative Commons: By Attribution 4.0 License.

CREDIT PRODUKSI
Documentary by: BANYAK TAU
Voice: Supertonic v3 M2
Visual tone: copper sepia nineteenth-century scientific engraving / Project 404 inspired documentary.

#Samalas #GunungApi #SejarahNusantara #Geologi #DokumenterIndonesia"""


def font(size, bold=True):
    candidates = [
        FONT_DIR / "Poppins-Bold.ttf",
        FONT_DIR / "CourierPrime-Bold.ttf",
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def mcp_prompts():
    base = """Create a YouTube thumbnail, 16:9, copper sepia 19th century scientific engraving documentary tone, Project 404 style, full bleed, dramatic volcanic caldera silhouette, ash plume, ice core rings, old map texture, high contrast, no logos, no small unreadable text, Indonesian documentary mood."""
    return [
        base + " Main composition: giant ash cloud shaped like a world map behind Lombok volcano, ominous but scholarly.",
        base + " Main composition: cracked antique globe with volcanic ash spreading from Indonesia, archival etching texture.",
        base + " Main composition: lone scientist silhouette holding ice core, Samalas caldera erupting in background, cinematic copper ink.",
    ]


def _paper_texture(img):
    px = img.load()
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            n = int(10 * math.sin(x * 0.04) + 8 * math.sin(y * 0.07))
            r, g, b = px[x, y]
            col = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
            px[x, y] = col
    return img.filter(ImageFilter.GaussianBlur(0.25))


def _etch_lines(draw, y0=0):
    for y in range(y0, H, 9):
        draw.line([(0, y), (W, y + int(16 * math.sin(y * 0.04)))], fill=(55, 38, 24, 70), width=1)
    for x in range(-80, W, 18):
        draw.line([(x, H), (x + 240, 0)], fill=(55, 38, 24, 42), width=1)


def _mountain(draw, variant):
    base_y = 585
    peaks = [(120, base_y), (345, 215 + variant*18), (520, base_y), (700, 255), (930, base_y), (1160, 310), (1280, base_y)]
    draw.polygon(peaks, fill=(34, 23, 16), outline=(8, 6, 4))
    for i in range(30):
        x = 280 + i * 25
        draw.line([(x, 270 + i % 5 * 9), (x - 90, base_y)], fill=(101, 63, 35), width=2)
    cx = 610 if variant != 2 else 760
    for r, a in [(230, 72), (170, 95), (105, 120)]:
        draw.ellipse([cx-r, 35-r//2, cx+r, 35+r], outline=(74, 49, 30, a), width=8)
    draw.polygon([(cx-70, 250), (cx+35, 75), (cx+150, 250)], fill=(78, 47, 27))
    draw.ellipse([cx-140, 65, cx+165, 250], outline=(42, 28, 18), width=4)


def _title(draw, text, variant):
    words = text.split()
    lines = [" ".join(words[:3]), " ".join(words[3:])]
    f1 = font(70 if variant != 1 else 64)
    f2 = font(78 if variant == 2 else 68)
    y = 448
    for i, line in enumerate(lines):
        f = f1 if i == 0 else f2
        box = draw.textbbox((0, 0), line, font=f, stroke_width=4)
        tw = box[2] - box[0]
        x = 52 if variant != 1 else (W - tw) // 2
        draw.text((x+4, y+4), line, font=f, fill=(0,0,0), stroke_width=7, stroke_fill=(0,0,0))
        draw.text((x, y), line, font=f, fill=(248, 232, 185), stroke_width=4, stroke_fill=(33, 20, 10))
        y += 78


def create_thumbnail(path, title, variant):
    img = Image.new("RGB", (W, H), PAPER if variant != 1 else PAPER2)
    img = _paper_texture(img).convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(overlay, "RGBA")
    _etch_lines(d)
    # vignette
    d.rectangle([0,0,W,H], outline=(22,14,8,255), width=18)
    for i in range(80):
        alpha = int(i * 1.7)
        d.rectangle([i, i, W-i, H-i], outline=(25,17,10,alpha), width=1)
    if variant == 1:
        d.ellipse([250, 60, 1030, 620], outline=(73,45,28,160), width=10)
        d.text((485, 168), "1257", font=font(138), fill=(40,25,15), stroke_width=3, stroke_fill=(225,202,154))
    elif variant == 2:
        d.rectangle([42, 50, 1238, 388], outline=(64,42,28,150), width=5)
        d.text((72, 72), "SAMALAS", font=font(122), fill=(44,27,16), stroke_width=2, stroke_fill=(228,207,164))
    else:
        d.text((64, 68), "1257", font=font(148), fill=(43,27,16), stroke_width=3, stroke_fill=(232,212,170))
    _mountain(d, variant)
    _title(d, title, variant)
    img = Image.alpha_composite(img, overlay).convert("RGB")
    img.save(path, quality=95)


def build_thumbnail_pack(out_dir=OUT_DIR):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    titles = viral_titles()
    prompts = mcp_prompts()
    thumbs = []
    for i, title in enumerate(titles, 1):
        p = out / f"thumbnail_AB_{i}.png"
        create_thumbnail(p, title, i-1)
        thumbs.append({"variant": f"A/B {i}", "title": title, "path": str(p).replace('\\', '/'), "mcp_prompt": prompts[i-1]})
    data = {
        "titles": titles,
        "thumbnails": thumbs,
        "description": youtube_description(),
        "chapters": [{"time": format_ts(t), "title": name} for name, t in chapters()],
        "music_credit": [
            "Ossuary 5 - Rest by Kevin MacLeod (incompetech.com), CC BY 4.0",
            "Prelude and Action by Kevin MacLeod (incompetech.com), CC BY 4.0",
        ],
        "method": "MCP-ready prompts + deterministic local fallback PNG",
    }
    meta = out / "thumbnail_pack.json"
    meta.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    data["metadata_path"] = str(meta).replace('\\', '/')
    return data


if __name__ == "__main__":
    pack = build_thumbnail_pack()
    print(json.dumps(pack, ensure_ascii=False, indent=2))
