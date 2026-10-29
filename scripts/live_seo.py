"""
Live SEO Generator v2 — Seasonal Aware + Per-Formula + Thumbnail v4

Fungsi:
    gen_live_metadata(formula_name, duration_hours, formula_key) -> dict
    gen_live_thumbnail(image_prompt, output_path) -> path|None
"""

import os
import re
import json
import time
import random
import sys

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
THUMB_DIR  = os.path.join(BASE_DIR, "data", "thumbnails")

# Tambah scripts ke path agar bisa import ai_service & thumbnail_gen
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


def _config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ─── Seasonal Context (sama seperti di ai_service.py) ────────────────────────

def _seasonal():
    from datetime import datetime, timezone, timedelta
    m = (datetime.now(timezone.utc) + timedelta(hours=7)).month
    if m in (9, 10, 11):
        return {
            "season"  : "Autumn / Fall",
            "keywords": "autumn lofi, cozy fall night, october rain live, november chill stream",
            "mood"    : "cozy autumn night, falling leaves, warm amber candlelight, misty rain",
            "visual"  : "autumn leaves falling outside window, warm candlelight, misty evening"
        }
    elif m in (12, 1, 2):
        return {
            "season"  : "Winter",
            "keywords": "cozy winter live, snowy night stream, christmas cafe ambience live",
            "mood"    : "warm fireplace, snowy window, peaceful winter night",
            "visual"  : "snow falling outside window, fireplace glow, cozy winter cabin"
        }
    elif m in (3, 4, 5):
        return {
            "season"  : "Spring",
            "keywords": "spring morning live, fresh coffee piano stream, bloom season lofi live",
            "mood"    : "fresh spring morning, cherry blossoms, warm sunlight",
            "visual"  : "cherry blossoms, morning sunlight, open window spring breeze"
        }
    else:
        return {
            "season"  : "Summer",
            "keywords": "summer lofi live, sunset acoustic live stream, peaceful summer night",
            "mood"    : "warm summer evening, golden sunset, breezy retreat",
            "visual"  : "sunset veranda, warm golden light, summer afternoon breeze"
        }


# ─── Per-Formula Live Title Pool ─────────────────────────────────────────────

FORMULA_LIVE = {
    "1": {
        "hooks": [
            "Rainy Night Piano — Sleep & Relax LIVE",
            "Cozy Rain & Piano — 24/7 Deep Sleep Radio",
            "Soft Piano + Rain Sounds — Live Study & Sleep Session",
            "Peaceful Rain Night — Piano Ambience LIVE Stream",
            "Fall Asleep Tonight — Rain & Piano 24/7 LIVE",
        ],
        "badge": "432Hz DEEP SLEEP  •  RAIN AMBIENCE",
        "emoji": "🌧️🎹",
    },
    "2": {
        "hooks": [
            "Morning Bossa Nova Cafe — Work & Focus LIVE",
            "Sunny Coffee Shop Vibes — 24/7 Productivity Radio",
            "Cozy Cafe Morning — Bossa Nova Focus Stream LIVE",
            "Good Morning — Coffee & Bossa Nova LIVE 24/7",
            "Work From Home BGM — Cafe Bossa Nova LIVE",
        ],
        "badge": "BOSSA NOVA  •  COFFEE VIBES LIVE",
        "emoji": "☕🎸",
    },
    "3": {
        "hooks": [
            "Midnight Lofi Radio — Study & Chill LIVE 24/7",
            "Late Night Lofi — Code & Study Session LIVE",
            "Cozy Lofi Beats — Midnight Focus Radio LIVE",
            "Lofi Hip Hop — Study With Me LIVE Stream",
            "Night Owl Study Session — Lofi Radio LIVE 24/7",
        ],
        "badge": "LOFI RADIO  •  STUDY & CHILL LIVE",
        "emoji": "🌙🎧",
    },
    "4": {
        "hooks": [
            "Dark Academia Library — Deep Focus LIVE Radio",
            "Victorian Study Hall — Classical Focus Stream LIVE",
            "Dark Academia 24/7 — Read & Study LIVE",
            "Classical Focus Radio — Dark Academia LIVE Stream",
            "Late Night Scholar — Dark Academia Ambience LIVE",
        ],
        "badge": "DARK ACADEMIA  •  DEEP FOCUS LIVE",
        "emoji": "📚🕯️",
    },
    "5": {
        "hooks": [
            "Forest Stream & Guitar — Nature Healing LIVE 24/7",
            "Peaceful Acoustic Guitar — Nature Sounds LIVE Radio",
            "Calm Forest Ambience — Guitar & Stream LIVE",
            "Anxiety Relief — Acoustic Guitar Nature LIVE 24/7",
            "Forest Therapy — Guitar & Birds LIVE Stream",
        ],
        "badge": "NATURE SOUNDS  •  STRESS RELIEF LIVE",
        "emoji": "🌿🎸",
    },
    "6": {
        "hooks": [
            "Pomodoro Study Timer LIVE — 25/5 Focus Sessions",
            "Study With Me LIVE — Pomodoro Timer & Lofi 24/7",
            "Deep Work LIVE — Pomodoro 25/5 Focus Radio",
            "Productive Study Session LIVE — Pomodoro Timer",
            "Beat Procrastination — Pomodoro Study LIVE 24/7",
        ],
        "badge": "POMODORO 25/5  •  STUDY TIMER LIVE",
        "emoji": "⏱️📖",
    },
}


def gen_live_metadata(
    formula_name: str,
    duration_hours: int = 5,
    formula_key: str = "1"
) -> dict:
    """
    Generate SEO metadata live stream yang:
    - Judul English (target US/Global high CPM)
    - Seasonal aware (autumn/winter/spring/summer)
    - Per-formula unik
    - Selalu ada fallback offline
    """
    season = _seasonal()
    fdata  = FORMULA_LIVE.get(str(formula_key), FORMULA_LIVE["1"])
    hook   = random.choice(fdata["hooks"])
    badge  = fdata["badge"]
    emoji  = fdata["emoji"]

    # Coba Gemini dulu
    try:
        from ai_service import AIService
        ai  = AIService()
        dur_min = duration_hours * 60
        data = ai.generate_seo_metadata(formula_name, dur_min, formula_key=formula_key)
        if data and data.get("title"):
            # Pastikan judulnya tidak terpotong
            t = str(data["title"]).strip()
            data["title"] = t[:90] if len(t) > 90 else t
            # Tambah konteks LIVE kalau belum ada
            if "live" not in data["title"].lower() and "24/7" not in data["title"].lower():
                data["title"] = data["title"].rstrip(".]") + " [24/7 LIVE]"
            data["badge"]  = badge
            data["emoji"]  = emoji
            return data
    except Exception as e:
        print(f"[SEO] Gemini gagal ({e}), pakai fallback lokal.")

    # Fallback offline — tetap English, tetap seasonal
    title = f"{emoji} {hook} [{season['season']}]"
    if len(title) > 90:
        title = f"{hook} [{season['season']}]"

    description = (
        f"Welcome to Cozy Mood Lounge — your 24/7 {formula_name} live radio. "
        f"Perfect for the {season['season'].lower()} season: {season['mood']}.\n\n"
        f"We stream non-stop relaxing music to help you sleep, focus, study, or simply unwind.\n\n"
        f"🎧 Use headphones at 40-50% volume for the best spatial audio experience.\n\n"
        f"🎵 What you'll hear:\n"
        f"• {formula_name}\n"
        f"• 432Hz harmonic tuning for deep relaxation\n"
        f"• Soft ambient layering — rain, forest, or cafe sounds\n"
        f"• Seamless crossfades — no jarring transitions\n\n"
        f"📌 Save this stream to your playlist for daily use!\n"
        f"🔔 Subscribe to Cozy Mood Lounge for more daily sessions.\n\n"
        f"#CozyMoodLounge #RelaxingMusic #LiveStream #StudyMusic "
        f"#{season['season'].split('/')[0].strip().replace(' ', '')}Lofi #432Hz #DeepSleep #LofiRadio"
    )

    tags = (
        f"relaxing music live, {formula_name.lower()}, 24/7 live stream, "
        f"study music live, sleep music live, lofi live radio, {season['keywords']}, "
        f"cozy ambience live, deep focus music, 432hz live"
    )

    image_prompt = (
        f"cozy {formula_name.lower()} aesthetic scene, {season['visual']}, "
        f"warm golden desk lamp glowing, steaming coffee mug, soft bokeh, "
        f"Makoto Shinkai Studio Ghibli style, vibrant colors, no text, no people"
    )

    return {
        "title"       : title,
        "description" : description,
        "tags"        : tags,
        "image_prompt": image_prompt,
        "badge"       : badge,
        "emoji"       : emoji,
    }


def gen_live_thumbnail(image_prompt: str, output_path: str = None,
                       title: str = "", formula_key: str = "1") -> str:
    """
    Generate thumbnail live stream pakai thumbnail_gen.py v4.
    Hasilnya identik dengan thumbnail video biasa — cinematic, terbaca di mobile.
    """
    os.makedirs(THUMB_DIR, exist_ok=True)
    if output_path is None:
        ts = int(time.time())
        output_path = os.path.join(THUMB_DIR, f"live_thumb_{ts}.jpg")

    cfg   = _config()
    brand = cfg.get("branding", {}).get("channel_name", "Cozy Mood Lounge")

    # Coba pakai background dari bank stok dulu (lebih cepat & konsisten)
    bg_dir = os.path.join(BASE_DIR, "assets", "backgrounds")
    bg_path = None
    try:
        import glob as _glob
        candidates = [
            f for ext in ("*.jpg", "*.jpeg", "*.png", "*.jfif", "*.webp")
            for f in _glob.glob(os.path.join(bg_dir, ext))
            if not os.path.basename(f).startswith("thumb_")
        ]
        if candidates:
            bg_path = random.choice(candidates)
    except Exception:
        pass

    # Kalau tidak ada background stok, download dari Pollinations
    if not bg_path:
        try:
            from ai_service import AIService
            ai = AIService()
            ts = int(time.time())
            fname = f"live_bg_{ts}.jpg"
            bg_path = ai.generate_and_download_image(image_prompt, fname)
        except Exception as e:
            print(f"[THUMB] Download background gagal: {e}")

    if not bg_path or not os.path.exists(bg_path):
        print("[THUMB] Tidak ada background, thumbnail dilewati.")
        return None

    # Pakai thumbnail_gen v4
    try:
        from thumbnail_gen import generate_thumbnail
        fdata  = FORMULA_LIVE.get(str(formula_key), FORMULA_LIVE["1"])
        badge  = fdata["badge"]
        emoji  = fdata["emoji"]

        # Bangun judul untuk thumbnail — kalau title kosong, pakai hook
        if not title:
            title = random.choice(fdata["hooks"])

        # Inject badge ke dalam judul supaya thumbnail_gen bisa parse
        thumb_title = f"{title} [{badge}]"

        result = generate_thumbnail(
            background_path=bg_path,
            title=thumb_title,
            output_path=output_path,
            accent=cfg.get("daemon", {}).get("thumbnail_accent", "#F5C518"),
            brand=brand
        )
        return result
    except Exception as e:
        print(f"[THUMB] thumbnail_gen gagal: {e}")
        return None
