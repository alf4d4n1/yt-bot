"""
Video Processor untuk overlay Google Flow
- Slow down video 3x (10 detik -> 30 detik)
- Hapus audio original
- Resize ke 1920x1080
- Output siap dipakai bot live stream & konten

Cara pakai:
    python process_overlay.py input.mp4 output.mp4
    python process_overlay.py input.mp4 output.mp4 --speed 0.4
"""
import os
import sys
import subprocess
import argparse


def process_overlay(
    input_path: str,
    output_path: str,
    speed: float = 0.33,   # 0.33 = 3x lebih lambat (default)
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
):
    """
    Proses video overlay dari Google Flow:
    1. Slow down (speed 0.33 = 3x lebih lambat)
    2. Hapus audio
    3. Resize ke 1920x1080
    4. 30fps smooth
    """
    if not os.path.exists(input_path):
        print(f"[!] File tidak ditemukan: {input_path}")
        return None

    # Cek durasi original
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", input_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        original_dur = float(probe.stdout.strip())
        new_dur = original_dur / speed
        print(f"[*] Durasi original : {original_dur:.1f} detik")
        print(f"[*] Durasi baru     : {new_dur:.1f} detik (speed {speed}x)")
    except Exception:
        print("[!] Gagal baca durasi, lanjut proses...")

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    # FFmpeg command:
    # - setpts: slow down video frames
    # - scale: resize ke target resolusi
    # - fps: normalize ke 30fps
    # - an: hapus audio (no audio)
    vf = (
        f"setpts={1/speed:.4f}*PTS,"
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"fps={fps}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf,
        "-an",                          # hapus audio original
        "-c:v", "libx264",
        "-preset", "slow",              # slow preset = kualitas lebih baik
        "-crf", "18",                   # kualitas tinggi (18 = hampir lossless)
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path
    ]

    print(f"[*] Memproses: {os.path.basename(input_path)}")
    print(f"[*] Output   : {os.path.basename(output_path)}")
    print(f"[*] Proses FFmpeg...")

    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        print(f"[!] FFmpeg error:\n{result.stderr[-500:]}")
        return None

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"[OK] Selesai! Ukuran: {size_mb:.1f} MB -> {output_path}")
    return output_path


def batch_process(input_dir: str, output_dir: str, speed: float = 0.33):
    """Proses semua MP4 dalam folder sekaligus."""
    import glob as _glob

    os.makedirs(output_dir, exist_ok=True)
    files = _glob.glob(os.path.join(input_dir, "*.mp4"))

    if not files:
        print(f"[!] Tidak ada MP4 di {input_dir}")
        return

    print(f"[*] Ditemukan {len(files)} file, mulai proses batch...\n")

    for i, f in enumerate(files, 1):
        name = os.path.basename(f)
        out  = os.path.join(output_dir, name)
        print(f"--- [{i}/{len(files)}] {name} ---")
        process_overlay(f, out, speed=speed)
        print()

    print(f"[DONE] Semua selesai! Cek folder: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Google Flow video untuk overlay bot")
    parser.add_argument("input",  help="File input MP4 atau folder (untuk batch)")
    parser.add_argument("output", help="File output MP4 atau folder output (untuk batch)")
    parser.add_argument("--speed", type=float, default=0.33,
                        help="Speed multiplier (0.33 = 3x lambat, 0.5 = 2x lambat). Default: 0.33")
    parser.add_argument("--batch", action="store_true",
                        help="Mode batch: proses semua MP4 dalam folder input")
    args = parser.parse_args()

    if args.batch or os.path.isdir(args.input):
        batch_process(args.input, args.output, speed=args.speed)
    else:
        process_overlay(args.input, args.output, speed=args.speed)
