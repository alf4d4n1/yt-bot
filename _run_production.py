"""
RUN PRODUCTION NYATA — pakai pipeline asli main.py, non-interaktif.
Menghasilkan video sungguhan di output/ untuk dibandingkan.
Jalankan: python _run_production.py [menit] [formula]
"""
import os
import sys
import json
import time
import random

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from ai_service import AIService
from audio_composer import AudioComposer
from video_engine import VideoEngine

MINUTES = int(sys.argv[1]) if len(sys.argv) > 1 else 3
FORMULA = sys.argv[2] if len(sys.argv) > 2 else "4"
FX = sys.argv[3] if len(sys.argv) > 3 else "rain_glass"

CONFIG = json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8"))
FORMULA_NAME = CONFIG["formulas"][FORMULA]

print("=" * 74)
print("  PRODUKSI NYATA — PIPELINE ASLI main.py")
print("=" * 74)
print(f"  Formula  : {FORMULA} - {FORMULA_NAME}")
print(f"  Durasi   : {MINUTES} menit")
print(f"  Efek     : {FX}")
print("=" * 74)

ai = AIService()
composer = AudioComposer()
engine = VideoEngine()
ts = int(time.time())

# ---- STEP 1: SEO via Gemini ----
print("\n[1/4] Generate SEO metadata via 9router (Gemini)...")
t0 = time.time()
seo = ai.generate_seo_metadata(FORMULA_NAME, MINUTES, formula_key=FORMULA)
title_safe  = seo.get('title', '').encode('ascii', 'replace').decode('ascii')
tags_safe   = str(seo.get('tags', ''))[:90].encode('ascii', 'replace').decode('ascii')
prompt_safe = str(seo.get('image_prompt', ''))[:90].encode('ascii', 'replace').decode('ascii')
print(f"  [{time.time()-t0:.1f}s] Judul: {title_safe}")
print(f"  Tags  : {tags_safe}...")
print(f"  Prompt: {prompt_safe}...")

# ---- STEP 2: Background dari bank stok ----
print("\n[2/4] Pilih background dari bank stok...")
bg_dir = os.path.join(BASE, "assets", "backgrounds")
exts = (".jpg", ".jpeg", ".png", ".jfif", ".webp")
candidates = [f for f in os.listdir(bg_dir)
              if f.lower().endswith(exts)
              and not f.startswith("test_")
              and not f.startswith("thumb_")]
img_path = os.path.join(bg_dir, random.choice(candidates))
print(f"  Terpilih: {os.path.basename(img_path)}")

# ---- STEP 3: Compose audio ----
print(f"\n[3/4] Compose audio {MINUTES} menit (loop + ambience)...")
audio_name = f"master_audio_{ts}.m4a"
t0 = time.time()
audio_path = composer.compose_master_audio(MINUTES * 60, audio_name, formula_key=FORMULA, shuffle=True)
print(f"  [{time.time()-t0:.1f}s] Audio: {os.path.basename(audio_path)} "
      f"({os.path.getsize(audio_path)/1048576:.2f} MB)")

# ---- STEP 4: Render video ----
print(f"\n[4/4] Render video final (FFmpeg, motion={FX})...")
seo["duration_seconds"] = MINUTES * 60
seo["thumbnail_image"] = img_path
video_name = f"video_{FORMULA}_{ts}.mp4"
video_path = engine.render_video(
    img_path, audio_path, video_name,
    metadata=seo, motion_mode=True, overlay_type=FX,
)

if os.path.exists(audio_path):
    os.remove(audio_path)

meta_path = os.path.splitext(video_path)[0] + ".json"

print("\n" + "=" * 74)
print("  SELESAI")
print("=" * 74)
print(f"  Video    : {video_path}")
print(f"  Size     : {os.path.getsize(video_path)/1048576:.2f} MB")
print(f"  Metadata : {meta_path}")
print("=" * 74)
