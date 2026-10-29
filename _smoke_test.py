"""Smoke test renovasi bot YT. Jalankan dari root project: python _smoke_test.py"""
import os
import sys
import json
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

from audio_composer import AudioComposer
from video_engine import VideoEngine
from ai_service import AIService

FAIL = []


def check(label, ok, detail=""):
    print(("  [OK]   " if ok else "  [FAIL] ") + label + (f"  -> {detail}" if detail else ""))
    if not ok:
        FAIL.append(label)


print("=" * 70)
print("  SMOKE TEST - YT CONTENT FACTORY (post-renovation)")
print("=" * 70)

# 1. Ambience mapping per formula
print("\n[1] Ambience mapping per formula")
ac = AudioComposer()
for k in ["1", "2", "3", "4", "5"]:
    f = ac.get_ambience_file(k)
    check(f"formula {k} ambience", f is not None, os.path.basename(f) if f else "NONE")

# 2. Music files per formula
print("\n[2] Music library per formula")
for k in ["1", "2", "3", "4", "5"]:
    files = ac.get_music_files(k, shuffle=False)
    check(f"formula {k} music", len(files) > 0, f"{len(files)} tracks")

# 3. Overlay map completeness
print("\n[3] Overlay map files exist")
engine = VideoEngine()
overlay_map = {
    "rain": "overlay_rain_window_glass.mp4",
    "rain_glass": "overlay_rain_window_glass.mp4",
    "rain_downpour": "overlay_rain_downpour.mp4",
    "dust": "overlay_golden_dust.mp4",
    "sunlight": "overlay_sunlight_beam.mp4",
    "embers": "overlay_embers_sparks.mp4",
    "snow": "overlay_snow_falling.mp4",
    "steam": "overlay_steam.mp4",
}
for k, v in overlay_map.items():
    p = os.path.join(engine.base_dir, "assets", "overlays", v)
    check(f"overlay {k}", os.path.exists(p), v)

# 4. Backgrounds
print("\n[4] Background bank")
bg_dir = os.path.join(engine.base_dir, "assets", "backgrounds")
exts = (".jpg", ".jpeg", ".png", ".jfif", ".webp")
bgs = [f for f in os.listdir(bg_dir) if f.lower().endswith(exts)]
check("background count", len(bgs) >= 5, f"{len(bgs)} images")

# 5. Render 8-second test clip with motion
print("\n[5] Render test clip 8s + motion overlay")
test_img = os.path.join(bg_dir, sorted(bgs)[0])
test_audio = os.path.join(engine.output_dir, "_smoke_audio.m4a")
subprocess.run(
    ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=8",
     "-c:a", "aac", "-b:a", "128k", test_audio],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
)
test_out = engine.render_video(
    test_img, test_audio, "_smoke_video.mp4",
    metadata={"title": "Smoke Test", "description": "d", "tags": "t",
              "duration_seconds": 8, "thumbnail_image": test_img},
    motion_mode=True, overlay_type="rain_glass",
)
check("render produced file", os.path.exists(test_out), os.path.basename(test_out))

# 6. Verify faststart (moov before mdat)
print("\n[6] Faststart verification (moov before mdat)")
with open(test_out, "rb") as f:
    pos = 0
    boxes = []
    size_total = os.path.getsize(test_out)
    while pos < size_total and len(boxes) < 6:
        f.seek(pos)
        hdr = f.read(8)
        if len(hdr) < 8:
            break
        sz = int.from_bytes(hdr[0:4], "big")
        typ = hdr[4:8].decode("latin1")
        boxes.append((typ, pos))
        if sz < 8:
            break
        pos += sz
order = [b[0] for b in boxes]
check("moov present", "moov" in order, str(order))
if "moov" in order and "mdat" in order:
    check("moov before mdat (faststart)", order.index("moov") < order.index("mdat"), str(order))

# 7. Metadata JSON includes thumbnail_image
print("\n[7] Metadata JSON completeness")
meta_path = os.path.splitext(test_out)[0] + ".json"
if os.path.exists(meta_path):
    with open(meta_path, encoding="utf-8") as f:
        m = json.load(f)
    for key in ["title", "description", "tags", "thumbnail_image", "duration_seconds", "status"]:
        check(f"meta key '{key}'", key in m, str(m.get(key))[:40])
else:
    check("metadata json exists", False, meta_path)

# 8. FFmpeg probe of output
print("\n[8] Output stream probe")
r = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries",
     "stream=codec_name,width,height,r_frame_rate", "-show_entries", "format=duration",
     "-of", "json", test_out],
    capture_output=True, text=True,
)
if r.returncode == 0:
    d = json.loads(r.stdout)
    v = [s for s in d.get("streams", []) if s.get("width")]
    a = [s for s in d.get("streams", []) if s.get("codec_name") in ("aac", "mp3")]
    check("video stream 1920x1080", bool(v) and v[0]["width"] == 1920 and v[0]["height"] == 1080, str(v[0]) if v else "")
    check("audio stream", bool(a), a[0]["codec_name"] if a else "NONE")
    check("duration ~8s", abs(float(d["format"]["duration"]) - 8) < 1.0, d["format"]["duration"])
else:
    check("ffprobe", False, r.stderr[:100])

# 9. AI service reachable
print("\n[9] AI router (9router) reachable")
try:
    ai = AIService()
    out = ai.query_llm("Reply with exactly: OK", "")
    check("9router responds", "OK" in out.upper(), out[:40].replace("\n", " "))
except Exception as e:
    check("9router responds", False, str(e)[:80])

# 10. Cleanup
for p in [test_audio, test_out, os.path.splitext(test_out)[0] + ".json"]:
    if os.path.exists(p):
        os.remove(p)
print("\n  [cleanup] test artifacts removed")

print("\n" + "=" * 70)
if FAIL:
    print(f"  RESULT: {len(FAIL)} CHECK(S) FAILED")
    for f in FAIL:
        print(f"    - {f}")
    sys.exit(1)
else:
    print("  RESULT: ALL CHECKS PASSED - BOT READY FOR PRODUCTION")
print("=" * 70)
