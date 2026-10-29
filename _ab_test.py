"""
A/B QUALITY + CONTAINER TEST — versi lama vs versi hasil renovasi.
Jalankan: python _ab_test.py
"""
import os
import re
import sys
import json
import time
import shutil
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from video_engine import VideoEngine
from audio_composer import AudioComposer
from ai_service import AIService

TMP = os.path.join(BASE, "_ab")
os.makedirs(TMP, exist_ok=True)

BG_DIR = os.path.join(BASE, "assets", "backgrounds")
EXT = (".jpg", ".jpeg", ".png", ".jfif", ".webp")
IMG = os.path.join(BG_DIR, sorted(f for f in os.listdir(BG_DIR) if f.lower().endswith(EXT))[0])
OVL = os.path.join(BASE, "assets", "overlays", "overlay_rain_window_glass.mp4")
AUD = os.path.join(TMP, "ab_audio.m4a")
CLIP = 20  # detik

FONT = "C:/Windows/Fonts/arial.ttf"
if not os.path.exists(FONT):
    FONT = "C:/Windows/Fonts/calibri.ttf"
SAFE_FONT = FONT.replace("\\", "/").replace(":", "\\:")
WM = (f"drawtext=text='© Cozy Mood Lounge':fontfile='{SAFE_FONT}':x=w-tw-40:y=h-th-30:"
      f"fontsize=22:fontcolor=white@0.30:shadowcolor=black@0.25:shadowx=1:shadowy=1")

FC = (
    "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=gbrp[bg];"
    "[1:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=gbrp[ov];"
    "[bg][ov]blend=all_mode='screen':all_opacity=0.65[blended];"
    f"[blended]format=yuv420p,{WM}[v]"
)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def boxes(path, limit=10):
    size = os.path.getsize(path)
    out, pos = [], 0
    with open(path, "rb") as f:
        while pos < size and len(out) < limit:
            f.seek(pos)
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            s = int.from_bytes(hdr[0:4], "big")
            t = hdr[4:8].decode("latin1")
            out.append((t, pos, s))
            if s < 8:
                break
            pos += s
    return out


def moov_offset(path):
    for t, p, s in boxes(path, 12):
        if t == "moov":
            return p
    return None


def build(out, crf=None, preset="veryfast", faststart=False):
    cmd = ["ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", IMG,
           "-stream_loop", "-1", "-i", OVL, "-i", AUD,
           "-filter_complex", FC, "-map", "[v]", "-map", "2:a",
           "-c:v", "libx264", "-preset", preset]
    if crf is not None:
        cmd += ["-crf", str(crf)]
    cmd += ["-c:a", "copy", "-pix_fmt", "yuv420p"]
    if faststart:
        cmd += ["-movflags", "+faststart"]
    cmd += ["-shortest", out]
    return cmd


def ssim(a, b):
    r = run(["ffmpeg", "-i", a, "-i", b, "-lavfi", "ssim", "-f", "null", "-"])
    m = re.search(r"All:([0-9.]+)", r.stderr)
    return float(m.group(1)) if m else None


def psnr(a, b):
    r = run(["ffmpeg", "-i", a, "-i", b, "-lavfi", "psnr", "-f", "null", "-"])
    m = re.search(r"average:([0-9.]+)", r.stderr)
    return float(m.group(1)) if m else None


print("=" * 78)
print("  A/B TEST — VERSI LAMA vs VERSI RENOVASI")
print("=" * 78)
print(f"  Sumber gambar : {os.path.basename(IMG)}")
print(f"  Overlay       : {os.path.basename(OVL)}")
print(f"  Durasi klip   : {CLIP}s @ 1920x1080 30fps")

# audio 20s dari musik asli
music = sorted(f for f in os.listdir(os.path.join(BASE, "assets", "music", "4_dark_academia"))
               if f.endswith(".mp3"))[0]
r = run(["ffmpeg", "-y", "-i", os.path.join(BASE, "assets", "music", "4_dark_academia", music),
         "-t", str(CLIP), "-c:a", "aac", "-b:a", "192k", AUD])
print(f"  Audio uji     : {music}")
print()

variants = [
    ("A_LAMA",   dict(crf=None, preset="veryfast", faststart=False), "kode lama (crf23 veryfast, tanpa faststart)"),
    ("B_RENOV",  dict(crf=None, preset="veryfast", faststart=True),  "kode baru (crf23 veryfast, +faststart)"),
    ("C_KUALITAS", dict(crf=20, preset="medium", faststart=True),    "usulan (crf20 medium, +faststart)"),
]

print("-" * 78)
print("  ENCODE")
print("-" * 78)
results = {}
for name, kw, desc in variants:
    out = os.path.join(TMP, f"{name}.mp4")
    t0 = time.time()
    p = run(build(out, **kw))
    dt = time.time() - t0
    if not os.path.exists(out):
        print(f"  [FAIL] {name}: {p.stderr[-300:]}")
        continue
    results[name] = {
        "path": out, "desc": desc, "encode_s": dt,
        "size_mb": os.path.getsize(out) / 1048576,
        "moov": moov_offset(out),
        "boxes": [b[0] for b in boxes(out, 6)],
    }
    print(f"  [OK] {name:11s} {dt:6.1f}s  {results[name]['size_mb']:7.2f} MB  boxes={results[name]['boxes']}")

# referensi lossless untuk ukur kualitas
print("\n" + "-" * 78)
print("  REFERENSI LOSSLESS (crf 0) untuk pengukuran kualitas")
print("-" * 78)
REF = os.path.join(TMP, "REF.mp4")
t0 = time.time()
run(build(REF, crf=0, preset="ultrafast", faststart=False))
print(f"  [OK] REF {time.time()-t0:6.1f}s  {os.path.getsize(REF)/1048576:7.2f} MB")

print("\n" + "-" * 78)
print("  KUALITAS (SSIM & PSNR vs referensi lossless — makin tinggi makin baik)")
print("-" * 78)
for name, d in results.items():
    s = ssim(REF, d["path"])
    p = psnr(REF, d["path"])
    d["ssim"] = s
    d["psnr"] = p
    print(f"  {name:11s} SSIM={s:.6f}  PSNR={p:.2f} dB")

print("\n" + "-" * 78)
print("  CONTAINER / FASTSTART")
print("-" * 78)
for name, d in results.items():
    mo = d["moov"]
    total = os.path.getsize(d["path"])
    pct = (mo / total * 100) if mo is not None else -1
    verdict = "moov di DEPAN (siap streaming)" if pct < 5 else "moov di BELAKANG (harus unduh penuh)"
    print(f"  {name:11s} moov@{mo:>10,} / {total:>10,} = {pct:6.2f}%  -> {verdict}")

# ---- perbandingan stream identik? ----
print("\n" + "-" * 78)
print("  APAKAH STREAM VIDEO BERUBAH? (A vs B, hanya beda container)")
print("-" * 78)
a, b = results.get("A_LAMA"), results.get("B_RENOV")
if a and b:
    s = ssim(a["path"], b["path"])
    print(f"  SSIM A vs B = {s:.6f}  -> {'IDENTIK secara visual' if s and s > 0.999 else 'ADA PERBEDAAN'}")
    same_bytes = os.path.getsize(a["path"]) == os.path.getsize(b["path"])
    print(f"  Ukuran file sama persis: {same_bytes}  (A={a['size_mb']:.2f}MB B={b['size_mb']:.2f}MB)")

# ---- ringkasan ----
print("\n" + "=" * 78)
print("  RINGKASAN")
print("=" * 78)
print(f"  {'VARIAN':<12} {'SIZE':>9} {'SSIM':>10} {'PSNR':>9} {'MOOV%':>8} {'ENCODE':>8}")
for name, d in results.items():
    total = os.path.getsize(d["path"])
    pct = (d["moov"] / total * 100) if d["moov"] is not None else -1
    print(f"  {name:<12} {d['size_mb']:>8.2f}M {d['ssim']:>10.6f} {d['psnr']:>8.2f} {pct:>7.2f}% {d['encode_s']:>7.1f}s")

print()
shutil.rmtree(TMP, ignore_errors=True)
print("  [cleanup] file uji dihapus")
print("=" * 78)
