"""
Thumbnail Generator — High-CTR Cinematic Style v4
Semua fix berdasarkan review detail Argon:

  1. Tagline kuning: 26px Bold + drop shadow tegas
  2. Copyright branding: 19px Bold (naik dari 14px)
  3. Accent bar kuning: 12px lebar, tinggi dari tagline sampai copyright
  4. Dim highlights ~40% untuk background terang/overexposed
  5. Rain streaks overlay otomatis untuk tema rain/sleep/cozy
  6. Intent sync: sleep -> DEEP SLEEP, focus -> DEEP FOCUS (tidak campur)
  7. Gaussian blur radius 2.5 untuk background ramai (cafe/bossa/acoustic)
  8. Dark gradient overlay 65% opacity di area teks untuk kontras penuh

Fungsi utama:
    generate_thumbnail(background_path, title, output_path, accent="#F5C518", brand="")
"""
import os
import re
import time
import random
import urllib.request
from typing import List, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


WIDTH  = 1280
HEIGHT = 720

FONT_URLS = {
    "Montserrat-Black.ttf": "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Black.ttf",
    "Montserrat-Bold.ttf" : "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf",
}

FONT_FALLBACKS = [
    "C:/Windows/Fonts/seguibl.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
]

# Formula yang punya background "ramai" -> perlu blur tipis
BUSY_BG_FORMULAS = ["bossa", "cafe", "coffee", "acoustic", "guitar", "forest", "lofi"]


# ─── Font Loader ──────────────────────────────────────────────────────────────

def _get_font_dir() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(base, "assets", "fonts")
    os.makedirs(d, exist_ok=True)
    return d


def _load_font(size: int, bold: bool = False) -> Optional["ImageFont.FreeTypeFont"]:
    name = "Montserrat-Bold.ttf" if bold else "Montserrat-Black.ttf"
    path = os.path.join(_get_font_dir(), name)

    # Cek root project juga (kalau sudah didownload sebelumnya)
    root_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), name
    )
    if os.path.exists(root_path) and not os.path.exists(path):
        try:
            import shutil
            shutil.copy2(root_path, path)
        except Exception:
            path = root_path

    if not os.path.exists(path):
        try:
            req = urllib.request.Request(
                FONT_URLS[name], headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=12) as r:
                with open(path, "wb") as f:
                    f.write(r.read())
            print(f"    [+] Font {name} didownload.")
        except Exception as e:
            print(f"    [!] Gagal download {name}: {e}")

    if os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass

    for fb in FONT_FALLBACKS:
        if os.path.exists(fb):
            try:
                return ImageFont.truetype(fb, size)
            except Exception:
                continue
    return None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _strip_emoji(text: str) -> str:
    out = []
    for ch in text:
        cp = ord(ch)
        if (0x1F300 <= cp <= 0x1FAFF) or (0x2600 <= cp <= 0x27BF) or cp == 0xFE0F:
            continue
        out.append(ch)
    return "".join(out).strip()


def _detect_intent(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ["sleep", "asleep", "insomnia", "bedtime", "tidur"]):
        return "sleep"
    if any(k in t for k in ["focus", "deep work", "productivity", "coding", "work"]):
        return "focus"
    if any(k in t for k in ["study", "pomodoro", "belajar"]):
        return "study"
    if any(k in t for k in ["meditat", "calm", "peace", "relax", "zen"]):
        return "relax"
    return "chill"


def _extract_badge(title: str, intent: str) -> str:
    """
    Badge tagline dinamis — sinkron dengan intent.
    Sleep video TIDAK boleh dapat badge 'DEEP FOCUS'.
    """
    m = re.search(r"\[([^\]]+)\]", title)
    if m:
        raw = _strip_emoji(m.group(1)).upper().strip()
        # Fix kontradiksi: kalau intent sleep tapi bracket bilang FOCUS
        if intent == "sleep" and "FOCUS" in raw and "SLEEP" not in raw:
            raw = raw.replace("DEEP FOCUS", "DEEP SLEEP").replace("FOCUS", "SLEEP")
        return raw

    t = title.lower()
    if intent == "sleep":
        return "432HZ  •  DEEP SLEEP"
    if intent == "focus":
        return "432HZ  •  DEEP FOCUS"
    if intent == "study":
        return "POMODORO 25/5  •  STUDY SESSION"
    if intent == "relax":
        return "432HZ  •  STRESS RELIEF"
    if "piano" in t or "rain" in t:
        return "SOFT PIANO  •  RAIN AMBIENCE"
    if "bossa" in t or "coffee" in t or "cafe" in t:
        return "BOSSA NOVA  •  COFFEE VIBES"
    if "dark academia" in t or "library" in t:
        return "DARK ACADEMIA  •  AMBIENT FOCUS"
    if "guitar" in t or "forest" in t or "acoustic" in t:
        return "ACOUSTIC GUITAR  •  NATURE SOUNDS"
    if "lofi" in t or "chill" in t:
        return "LOFI CHILL  •  COZY VIBES"
    return "432HZ  •  COZY AMBIENCE"


def _clean_title(title: str, max_words: int = 6) -> str:
    t = _strip_emoji(title)
    t = re.sub(r"[\(\[][^\)\]]*[\)\]]", " ", t)
    t = re.split(r"[|•]", t)[0]
    t = re.sub(r"[\u2013\u2014\-_/]+", " ", t)
    words = [w.strip(",;:") for w in t.split() if w.strip(",;:")]
    if not words:
        return "COZY MUSIC SESSION"
    picked = words[:max_words]
    stop = {"and", "for", "with", "the", "of", "to", "in", "or", "&", "a", "an"}
    while picked and picked[-1].lower() in stop:
        picked.pop()
    return " ".join(picked).upper()


def _word_wrap(draw, text: str, font, max_width: int, max_lines: int) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current = ""
    for w in words:
        trial = f"{current} {w}".strip()
        w_px = draw.textbbox((0, 0), trial, font=font)[2]
        if w_px <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = w
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines[:max_lines]


def _dim_highlights(img: "Image.Image", strength: float = 0.40) -> "Image.Image":
    """
    Redupkan area overexposed/terlalu terang ~40%.
    Pixel > 200 brightness di-blend ke warm dark amber.
    Tidak menyentuh area gelap sama sekali.
    """
    img_rgb  = img.convert("RGB")
    warm_dark = Image.new("RGB", img_rgb.size, (35, 24, 12))
    gray = img_rgb.convert("L")
    mask_data = []
    for px in gray.getdata():
        if px > 200:
            alpha = min(int(255 * strength), int((px - 200) * 2.2 * strength))
            mask_data.append(min(180, alpha))
        else:
            mask_data.append(0)
    mask = Image.new("L", img_rgb.size)
    mask.putdata(mask_data)
    result = img_rgb.copy()
    result.paste(warm_dark, (0, 0), mask)
    return result


def _apply_busy_bg_blur(img: "Image.Image", radius: float = 2.5) -> "Image.Image":
    """
    Gaussian blur tipis untuk background ramai (cafe, forest, acoustic).
    Hanya di area atas — area bawah yang sudah kena scrim tidak perlu blur.
    Membuat teks tetap jadi titik fokus.
    """
    blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
    # Blend: 70% blurred + 30% original = tipis, tidak kehilangan detail
    return Image.blend(img, blurred, alpha=0.70)


def _draw_rain_streaks(draw: "ImageDraw.Draw", seed: int = 0):
    """
    Rain streaks overlay tipis berbasis Pillow murni.
    Garis diagonal putih kebiruan, opacity rendah (18-52).
    """
    rng = random.Random(seed)
    for _ in range(380):
        x     = rng.randint(-40, WIDTH)
        y     = rng.randint(0, HEIGHT)
        length = rng.randint(10, 26)
        alpha  = rng.randint(18, 52)
        x2 = x + int(length * 0.22)
        y2 = y + length
        draw.line([(x, y), (x2, y2)], fill=(190, 215, 245, alpha), width=1)


def _draw_strong_gradient(draw_ov: "ImageDraw.Draw", opacity_top: float = 0.0,
                           opacity_bottom: float = 0.65, start_pct: float = 0.45):
    """
    Dark gradient overlay dari start_pct ke bawah.
    opacity_bottom=0.65 = gradient 65% hitam di area teks (rekomendasi Argon).
    """
    start_y = int(HEIGHT * start_pct)
    for y in range(start_y, HEIGHT):
        progress = (y - start_y) / (HEIGHT - start_y)
        alpha    = int(255 * opacity_bottom * (progress ** 1.2))
        draw_ov.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, alpha))


# ─── Main Function ─────────────────────────────────────────────────────────────

def generate_thumbnail(
    background_path: str,
    title: str,
    output_path: Optional[str] = None,
    accent: str = "#F5C518",
    brand: str = ""
) -> Optional[str]:
    """
    Generate thumbnail YouTube 1280x720 High-CTR — Cinematic Lofi Style v4.

    Semua fix Argon v4:
    - Tagline 26px Bold + drop shadow tegas
    - Copyright 19px Bold
    - Accent bar 12px lebar
    - Dim highlights ~40% untuk background overexposed
    - Rain streaks otomatis untuk tema rain/sleep/cozy
    - Gaussian blur 2.5 untuk background ramai (cafe/acoustic)
    - Dark gradient 65% di area teks
    - Intent sync: tidak campur sleep + focus
    """
    if not PIL_AVAILABLE:
        print("    [!] Pillow tidak terinstall, thumbnail dilewati.")
        return None

    if not background_path or not os.path.exists(background_path):
        print(f"    [!] Background tidak ditemukan: {background_path}")
        return None

    if output_path is None:
        base = os.path.splitext(os.path.basename(background_path))[0][:28]
        output_path = os.path.join(
            os.path.dirname(background_path),
            f"thumb_{base}_{int(time.time()*1000) % 100000}.jpg"
        )

    t_lower = title.lower()

    # ── 1. Load & crop ke 1280x720 ──
    img = Image.open(background_path).convert("RGB")
    src_ratio = img.width / img.height
    dst_ratio = WIDTH / HEIGHT
    if abs(src_ratio - dst_ratio) > 0.01:
        if src_ratio > dst_ratio:
            new_w = int(img.height * dst_ratio)
            left  = (img.width - new_w) // 2
            img   = img.crop((left, 0, left + new_w, img.height))
        else:
            new_h = int(img.width / dst_ratio)
            top   = (img.height - new_h) // 2
            img   = img.crop((0, top, img.width, top + new_h))
    img = img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)

    # ── 2. Dim highlights terang ~40% (fix: tidak menyilaukan) ──
    img = _dim_highlights(img, strength=0.40)

    # ── 3. Blur background ramai (cafe/forest/acoustic) ──
    needs_blur = any(k in t_lower for k in BUSY_BG_FORMULAS)
    if needs_blur:
        img = _apply_busy_bg_blur(img, radius=2.5)

    # ── 4. Color grading ──
    img = ImageEnhance.Brightness(img).enhance(1.05)
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = ImageEnhance.Color(img).enhance(1.20)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))
    img_rgba = img.convert("RGBA")

    # ── 5. Dark gradient overlay 65% di area teks (fix kontras penuh) ──
    grad_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw_grad  = ImageDraw.Draw(grad_layer)
    _draw_strong_gradient(draw_grad, opacity_bottom=0.65, start_pct=0.42)
    img_rgba = Image.alpha_composite(img_rgba, grad_layer)

    # ── 6. Rain streaks (hanya tema rain/sleep/cozy) ──
    needs_rain = any(k in t_lower for k in [
        "rain", "rainy", "drizzle", "shower", "sleep", "asleep",
        "cozy", "night rain", "hujan", "rintik"
    ])
    if needs_rain:
        rain_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        rain_draw  = ImageDraw.Draw(rain_layer)
        _draw_rain_streaks(rain_draw, seed=int(time.time()) % 9999)
        img_rgba = Image.alpha_composite(img_rgba, rain_layer)

    draw = ImageDraw.Draw(img_rgba)
    rgb  = _hex_to_rgb(accent)

    # ── 7. Siapkan teks & intent ──
    intent     = _detect_intent(title)
    main_text  = _clean_title(title, max_words=6)
    badge_text = _extract_badge(title, intent)

    margin_x   = 76
    max_text_w = WIDTH - margin_x - 90

    # ── 8. Font sizes (semua naik sesuai rekomendasi Argon) ──
    TAGLINE_SIZE   = 26   # naik dari ~14 -> 26px Bold
    BRAND_SIZE     = 19   # naik dari ~14 -> 19px Bold
    BAR_WIDTH      = 12   # naik dari 8px -> 12px

    # Auto-size judul utama
    title_font  = None
    chosen_size = 72
    for size in (80, 72, 64, 56, 48, 42):
        f = _load_font(size, bold=False)
        if f is None:
            continue
        lines = _word_wrap(draw, main_text, f, max_text_w, 2)
        if lines:
            title_font  = f
            chosen_size = size
            break

    if title_font is None:
        print("    [!] Font tidak tersedia, thumbnail dilewati.")
        return None

    lines      = _word_wrap(draw, main_text, title_font, max_text_w, 2)
    badge_font = _load_font(TAGLINE_SIZE, bold=True)
    brand_font = _load_font(BRAND_SIZE,   bold=True)

    line_h      = int(chosen_size * 1.15)
    badge_h     = TAGLINE_SIZE + 18 if badge_font else 0
    brand_h     = BRAND_SIZE   + 14 if (brand and brand_font) else 0
    total_block = badge_h + line_h * len(lines) + brand_h + 12

    y_block = HEIGHT - total_block - 48

    # ── 9. Accent bar kuning 12px lebar (dari atas tagline sampai bawah copyright) ──
    bar_x0 = margin_x - BAR_WIDTH - 10
    bar_x1 = bar_x0 + BAR_WIDTH
    draw.rounded_rectangle(
        [bar_x0, y_block + 2, bar_x1, y_block + total_block - 4],
        radius=6,
        fill=(*rgb, 255)
    )

    cur_y = y_block

    # ── 10. Tagline badge 26px Bold + drop shadow tegas ──
    if badge_font:
        # Drop shadow tegas (offset 2px, alpha tinggi)
        for sx, sy in [(2, 2), (1, 2), (2, 1)]:
            draw.text(
                (margin_x + sx, cur_y + sy),
                badge_text, font=badge_font,
                fill=(0, 0, 0, 210)
            )
        draw.text((margin_x, cur_y), badge_text, font=badge_font, fill=(*rgb, 255))
        cur_y += badge_h

    # ── 11. Judul utama putih + double drop shadow ──
    for ln in lines:
        for off, a in [(6, 80), (3, 160)]:
            draw.text(
                (margin_x + off, cur_y + off),
                ln, font=title_font,
                fill=(0, 0, 0, a)
            )
        draw.text((margin_x, cur_y), ln, font=title_font, fill=(255, 255, 255, 255))
        cur_y += line_h

    # ── 12. Copyright branding 19px ──
    if brand and brand_font:
        cur_y += 8
        brand_str = f"© {brand.upper()}"
        # Shadow
        draw.text((margin_x + 1, cur_y + 1), brand_str, font=brand_font, fill=(0, 0, 0, 180))
        draw.text((margin_x,     cur_y),     brand_str, font=brand_font, fill=(255, 255, 255, 230))

    # ── 13. Simpan ──
    img_rgba.convert("RGB").save(output_path, "JPEG", quality=95, optimize=True)
    print(f"    [OK] Thumbnail v4: {os.path.basename(output_path)}")
    return output_path


# ─── Test Runner ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import glob as _glob

    bg_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "backgrounds"
    )
    bgs = [
        f for ext in ("*.jpg", "*.jpeg", "*.png", "*.jfif", "*.webp")
        for f in _glob.glob(os.path.join(bg_dir, ext))
        if not os.path.basename(f).startswith("thumb_")
    ]

    if bgs:
        out = generate_thumbnail(
            bgs[-1],
            "Fall Asleep in Peace Cozy Rain & Piano [432Hz / Deep Sleep]",
            accent="#F5C518",
            brand="Cozy Mood Lounge"
        )
        print("Output:", out)
        try:
            os.startfile(out)
        except Exception:
            pass
    else:
        print("Tidak ada background di assets/backgrounds/")
