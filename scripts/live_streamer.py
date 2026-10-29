"""
Headless 24/7 Live Streamer — Mengirim streaming non-stop langsung ke YouTube RTMP
menggunakan FFmpeg tanpa OBS dan tanpa makan resource CPU/RAM laptop.

Flow baru:
  1. Cek overlay_master_loop.mp4 di assets/overlays/ (video cinemagraph 10 detik)
  2. Ambil audio langsung dari assets/music/ sesuai formula aktif
  3. Gabungkan keduanya via FFmpeg stream — TANPA render dulu!
  4. Loop selamanya: visual loop + audio loop seamless
"""
import os
import sys
import json
import time
import subprocess
import glob
import random

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from live_paths import MASTER_LOOP, LIVE_DIR, ensure_live_dir, migrate_legacy
import live_playlist as playlist

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Path semua overlay video (urutan rotasi)
OVERLAY_MASTER = os.path.join(BASE_DIR, "assets", "overlays", "overlay_master_loop.mp4")

OVERLAY_PLAYLIST = [
    os.path.join(BASE_DIR, "assets", "overlays", "overlay_master_loop.mp4"),    # Amber Rain Room
    os.path.join(BASE_DIR, "assets", "overlays", "overlay_midnight_city.mp4"),  # Midnight Lofi City
    os.path.join(BASE_DIR, "assets", "overlays", "overlay_cafe_morning.mp4"),   # Morning Cafe
    os.path.join(BASE_DIR, "assets", "overlays", "overlay_dark_academia.mp4"),  # Dark Academia
    os.path.join(BASE_DIR, "assets", "overlays", "overlay_forest_cabin.mp4"),   # Forest Cabin
]

OVERLAY_LOOP_COUNT = 50   # Setiap video di-loop 50x sebelum ganti tema


def swap_minutes(live_cfg: dict) -> int:
    raw = live_cfg.get("playlist_swap_minutes", 60)
    try:
        val = int(raw)
    except (TypeError, ValueError):
        val = 60
    return max(30, min(val, 120))


def get_stream_key():
    cfg_path = os.path.join(BASE_DIR, "config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    current_key = cfg.get("livestream", {}).get("stream_key", "").strip()

    print("\n" + "="*60)
    print("  YOUTUBE LIVE STREAMING 24/7 (HEADLESS - TANPA OBS)")
    print("="*60)

    if current_key:
        masked_key = current_key[:4] + "****" + current_key[-4:] if len(current_key) > 8 else current_key
        print(f"  Stream Key tersimpan : {masked_key}")
        print("  - Tekan [ENTER] langsung untuk pakai key ini")
        print("  - Atau paste Stream Key BARU lalu tekan [ENTER]")
    else:
        print("  Belum ada Stream Key yang tersimpan.")
        print("  Buka YouTube Studio -> 'Go Live' -> Salin Stream Key.")

    print("="*60)
    user_input = input("Masukkan / Ganti Stream Key (Enter = Pakai yang lama): ").strip()

    if user_input:
        stream_key = user_input
        cfg.setdefault("livestream", {})["stream_key"] = stream_key
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print("[OK] Stream Key berhasil diperbarui!")
    else:
        if not current_key:
            print("[!] Stream Key kosong! Siaran dibatalkan.")
            sys.exit(1)
        stream_key = current_key
        print("[OK] Menggunakan Stream Key yang sudah tersimpan.")

    return stream_key


def pick_audio_files(formula_key: str = "1") -> list:
    """Ambil semua file MP3 dari folder formula aktif untuk di-concat."""
    formula_folders = {
        "1": "1_piano_rain",
        "2": "2_bossa_nova",
        "3": "3_lofi_chill",
        "4": "4_dark_academia",
        "5": "5_acoustic_guitar",
        "6": "3_lofi_chill",
    }
    subfolder = formula_folders.get(str(formula_key), "1_piano_rain")
    music_dir = os.path.join(BASE_DIR, "assets", "music", subfolder)

    files = glob.glob(os.path.join(music_dir, "*.mp3"))
    if not files:
        # Fallback ke semua folder musik
        files = glob.glob(os.path.join(BASE_DIR, "assets", "music", "**", "*.mp3"), recursive=True)

    random.shuffle(files)
    return files


def build_concat_file(audio_files: list, repeat: int = 10) -> str:
    """Buat file concat list FFmpeg — loop audio files sekian kali."""
    concat_path = os.path.join(BASE_DIR, "output", f"live_concat_{os.getpid()}.txt")
    os.makedirs(os.path.dirname(concat_path), exist_ok=True)
    with open(concat_path, "w", encoding="utf-8") as f:
        for _ in range(repeat):
            for af in audio_files:
                safe = af.replace("\\", "/")
                f.write(f"file '{safe}'\n")
    return concat_path


def get_available_overlays() -> list:
    """Return daftar overlay yang filenya benar-benar ada."""
    available = [p for p in OVERLAY_PLAYLIST if os.path.exists(p)]
    if not available and os.path.exists(OVERLAY_MASTER):
        available = [OVERLAY_MASTER]
    return available


def build_live_cmd(rtmp_url: str, formula_key: str = "1",
                   overlay_path: str = None) -> tuple:
    """
    Bangun FFmpeg command untuk live stream:
    - Visual: overlay video (loop OVERLAY_LOOP_COUNT kali)
    - Audio: musik formula aktif (432Hz + reverb)
    - Tanpa render dulu — langsung stream!
    """
    if overlay_path is None:
        overlay_path = OVERLAY_MASTER

    audio_files = pick_audio_files(formula_key)
    if not audio_files:
        raise FileNotFoundError(f"Tidak ada file MP3 di folder formula {formula_key}")

    # Loop audio lebih banyak dari loop video supaya tidak habis duluan
    concat_file = build_concat_file(audio_files, repeat=30)

    # Cek ambience
    ambience_folders = {
        "1": "1_piano_rain", "2": "2_bossa_nova",
        "3": "3_lofi_chill",  "4": "4_dark_academia",
        "5": "5_acoustic_guitar",
    }
    amb_sub   = ambience_folders.get(str(formula_key), "1_piano_rain")
    amb_dir   = os.path.join(BASE_DIR, "assets", "ambience", amb_sub)
    amb_files = (glob.glob(os.path.join(amb_dir, "*.mp3")) +
                 glob.glob(os.path.join(amb_dir, "*.wav")) +
                 glob.glob(os.path.join(amb_dir, "*.m4a")))
    ambience  = amb_files[0] if amb_files else None

    # Hitung total durasi overlay (durasi video x loop count)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", overlay_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        vid_dur  = float(probe.stdout.strip())
        total_dur = vid_dur * OVERLAY_LOOP_COUNT
    except Exception:
        total_dur = 0

    overlay_name = os.path.basename(overlay_path)
    print(f"[*] Visual  : {overlay_name} x{OVERLAY_LOOP_COUNT} loop (~{total_dur/60:.0f} menit)")
    print(f"[*] Audio   : {len(audio_files)} lagu formula {formula_key}")
    print(f"[*] Ambience: {os.path.basename(ambience) if ambience else 'tidak ada'}")

    if ambience:
        filter_complex = (
            "[1:a]asetrate=47127,aresample=48000,"
            "aecho=0.85:0.7:35|55:0.18|0.12,"
            "volume=1.0[music];"
            "[2:a]volume=0.18,aloop=loop=-1:size=2e+09[amb];"
            "[music][amb]amix=inputs=2:duration=first:dropout_transition=3[aout]"
        )
        cmd = [
            "ffmpeg", "-y",
            # Visual: loop overlay N kali
            "-stream_loop", str(OVERLAY_LOOP_COUNT), "-re", "-i", overlay_path,
            # Audio 1: musik concat
            "-f", "concat", "-safe", "0", "-i", concat_file,
            # Audio 2: ambience loop
            "-stream_loop", "-1", "-i", ambience,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-r", "30", "-g", "60",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-f", "flv", "-flvflags", "no_duration_filesize",
            rtmp_url
        ]
    else:
        filter_audio = (
            "[1:a]asetrate=47127,aresample=48000,"
            "aecho=0.85:0.7:35|55:0.18|0.12,"
            "volume=1.0[aout]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", str(OVERLAY_LOOP_COUNT), "-re", "-i", overlay_path,
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-filter_complex", filter_audio,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-r", "30", "-g", "60",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-f", "flv", "-flvflags", "no_duration_filesize",
            rtmp_url
        ]

    return cmd, concat_file


def start_live():
    stream_key = get_stream_key()
    cfg_path   = os.path.join(BASE_DIR, "config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    live_cfg   = cfg.get("livestream", {})
    formula    = live_cfg.get("active_formula", "1")
    rtmp_url   = f"rtmp://a.rtmp.youtube.com/live2/{stream_key}"

    ensure_live_dir()
    migrate_legacy()

    # Pastikan ada overlay yang tersedia
    overlays = get_available_overlays()
    if not overlays:
        print(f"[!] Tidak ada overlay video di assets/overlays/")
        print(f"    Taruh file video dari Google Flow di sana dulu!")
        sys.exit(1)

    print("\n" + "="*60)
    print("  LIVE STREAMING 24/7 — TANPA RENDER, LANGSUNG STREAM")
    print(f"  Overlay  : {len(overlays)} video tersedia (rotasi tiap {OVERLAY_LOOP_COUNT}x loop)")
    for i, ov in enumerate(overlays, 1):
        print(f"    [{i}] {os.path.basename(ov)}")
    print(f"  Formula  : {formula} - {cfg.get('formulas', {}).get(formula, '')}")
    print(f"  RTMP     : rtmp://a.rtmp.youtube.com/live2/****")
    print(f"  Stop     : Ctrl+C")
    print("="*60 + "\n")

    # Setup broadcast YouTube
    broadcast = None
    try:
        from live_broadcast_manager import start_broadcast_now
        broadcast = start_broadcast_now(stream_key)
        bc_id = broadcast.get("id")
        print(f"[OK] Broadcast ID : {bc_id}")
        print(f"[OK] Public URL   : https://www.youtube.com/watch?v={bc_id}\n")
    except Exception as e:
        print(f"[!] Broadcast setup gagal: {e}")
        print(f"[!] Stream tetap jalan tapi tanpa URL publik.\n")

    concat_file    = None
    proc           = None
    overlay_index  = 0   # Mulai dari video pertama

    while True:
        try:
            current_overlay = overlays[overlay_index % len(overlays)]
            overlay_name    = os.path.basename(current_overlay)

            print(f"[*] Tema [{overlay_index % len(overlays) + 1}/{len(overlays)}]: {overlay_name}")
            cmd, concat_file = build_live_cmd(rtmp_url, formula_key=formula,
                                              overlay_path=current_overlay)
            print(f"[*] Streaming ke YouTube...")
            proc = subprocess.Popen(cmd, stderr=subprocess.DEVNULL)
            proc.wait()

            # Video selesai N loop → ganti ke tema berikutnya
            overlay_index += 1
            next_overlay = overlays[overlay_index % len(overlays)]
            print(f"[*] Ganti tema -> {os.path.basename(next_overlay)}")
            time.sleep(2)

        except KeyboardInterrupt:
            print("\n[OK] Live stream dihentikan.")
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
            break

        except Exception as e:
            print(f"[!] Error: {e}. Reconnect dalam 10 detik...")
            if proc and proc.poll() is None:
                proc.terminate()
            time.sleep(10)

        finally:
            if concat_file and os.path.exists(concat_file):
                try:
                    os.remove(concat_file)
                except Exception:
                    pass


if __name__ == "__main__":
    start_live()


def swap_minutes(live_cfg: dict) -> int:
    """Durasi per source sebelum rotasi, dalam menit.

    Floor 30 menit: YouTube menghitung concurrent-viewer-rate dari durasi
    rewrite, dan source yang terlalu pendek bikin viewer sering dapat
    "stream ended, reconnecting". Ceiling 120 menit: setelah itu file
    streaming mulai berat dan `-c:v copy` kehilangan advantages.
    """
    raw = live_cfg.get("playlist_swap_minutes", 60)
    try:
        val = int(raw)
    except (TypeError, ValueError):
        val = 60
    return max(30, min(val, 120))


def get_stream_key():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg_path = os.path.join(base_dir, "config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    current_key = cfg.get("livestream", {}).get("stream_key", "").strip()

    print("\n" + "="*60)
    print("  YOUTUBE LIVE STREAMING 24/7 (HEADLESS - TANPA OBS)")
    print("="*60)

    if current_key:
        masked_key = current_key[:4] + "****" + current_key[-4:] if len(current_key) > 8 else current_key
        print(f"  Stream Key tersimpan : {masked_key}")
        print("  - Tekan [ENTER] langsung untuk pakai key ini")
        print("  - Atau paste Stream Key BARU lalu tekan [ENTER]")
    else:
        print("  Belum ada Stream Key yang tersimpan.")
        print("  Buka YouTube Studio -> 'Go Live' / 'Mulai Live' -> Salin Stream Key.")

    print("="*60)
    user_input = input("Masukkan / Ganti Stream Key (Enter = Pakai yang lama): ").strip()

    if user_input:
        stream_key = user_input
        cfg.setdefault("livestream", {})["stream_key"] = stream_key
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print(f"[✓] Stream Key berhasil diperbarui dan disimpan ke config.json!")
    else:
        if not current_key:
            print("[!] Stream Key kosong! Siaran dibatalkan.")
            sys.exit(1)
        stream_key = current_key
        print("[✓] Menggunakan Stream Key yang sudah tersimpan.")

    return stream_key


def start_live():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    stream_key = get_stream_key()
    cfg_path = os.path.join(base_dir, "config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    live_cfg = cfg.get("livestream", {})

    rtmp_url = f"rtmp://a.rtmp.youtube.com/live2/{stream_key}"

    # Cari file video mp4 yang siap distreaming
    ensure_live_dir()
    migrate_legacy()

    sources = playlist.scan_sources()
    source_video = playlist.pick_next(sources) if sources else None
    vids = glob.glob(os.path.join(base_dir, "output", "*.mp4"))

    if not source_video and os.path.exists(MASTER_LOOP):
        source_video = MASTER_LOOP
    if not source_video and vids:
        source_video = vids[0]
    if not source_video:
        print("[!] Tidak ada video MP4 di folder output. Merender video master loop...")
        from video_engine import VideoEngine
        from audio_composer import AudioComposer

        engine = VideoEngine()
        composer = AudioComposer()
        bg_dir = os.path.join(base_dir, "assets", "backgrounds")
        bgs = [f for f in glob.glob(os.path.join(bg_dir, "*.jp*"))]
        if not bgs:
            raise FileNotFoundError("Tidak ada background di assets/backgrounds")

        # Render multi-scene, bukan 1 gambar diam. YouTube menandai live
        # stream dengan 1 still image sebagai "reused content" dan lowers
        # monetisasi; rotating 4 background + Ken Burns jauh lebih aman.
        audio_path = composer.compose_master_audio(
            target_duration_seconds=swap_minutes(live_cfg) * 60,
            formula_key=live_cfg.get("active_formula", "3"),
        )
        source_video = engine.render_multiscene(
            image_paths=bgs[:4],
            audio_path=audio_path,
            output_filename="master_livestream_loop.mp4",
            metadata={"title": "24/7 Lofi Live Stream", "is_432hz": True},
            scene_seconds=180,
            formula_key=live_cfg.get("active_formula", "3"),
        )

    print("\n" + "="*60)
    print("  LIVE STREAMING DIMULAI (HEADLESS - TANPA OBS)")
    print(f"  • Source Video : {os.path.basename(source_video)}")
    print(f"  • RTMP Target  : rtmp://a.rtmp.youtube.com/live2/****")
    print(f"  • Mode         : Ultra-light -c:v copy (CPU 1-3%, RAM ~50MB)")
    print(f"  • Catatan      : Tekan Ctrl+C untuk menghentikan siaran.")
    print("="*60 + "\n")

    def build_cmd(src):
        return [
            "ffmpeg", "-re",
            "-stream_loop", "-1",
            "-i", src,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-f", "flv",
            "-flvflags", "no_duration_filesize",
            rtmp_url
        ]

    proc = None
    playlist.register_play(source_video)

    # --- Broadcast lifecycle: WAJIB sebelum push RTMP -------------------
    # Tanpa broadcast object, stream tetap keluar tapi tidak punya URL
    # publik, tidak di-index search, dan tidak masuk recommendation.
    # Itu penyebab 8 jam live cuma 6 viewer.
    broadcast = None
    try:
        from live_broadcast_manager import start_broadcast_now
        titles = live_cfg.get("titles") or ["Live Stream"]
        descs = live_cfg.get("descriptions") or {}
        formula = live_cfg.get("active_formula", "3")
        title = titles[0]
        desc = descs.get(formula) or descs.get(str(formula)) or ""
        broadcast = start_broadcast_now(stream_key, title, desc)
        bc_id = broadcast.get("id")
        print(f"  • Broadcast ID : {bc_id}")
        print(f"  • Public URL   : https://www.youtube.com/watch?v={bc_id}")
    except Exception as e:
        print(f"  [!] Broadcast setup gagal: {e}")
        print(f"  [!] Stream tetap jalan, TAPI tanpa URL publik / tanpa SEO.")
        broadcast = None

    while True:
        try:
            print(f"[*] Menghubungkan siaran langsung ke YouTube... ({os.path.basename(source_video)})")
            proc = subprocess.Popen(build_cmd(source_video))
            proc.wait()
            print("[!] Koneksi terputus. Mencoba reconnect dalam 5 detik...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n[✓] Live stream dihentikan oleh user.")
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
            break
        except Exception as e:
            print(f"[!] Error: {e}. Reconnect dalam 10 detik...")
            if proc and proc.poll() is None:
                proc.terminate()
            time.sleep(10)
        finally:
            # Rotasi source di reconnect berikutnya. Versi lama looping
            # file yang sama selamanya -> 1 still frame seharian, yang
            #正是 penyebab "reused content" flag + drop retention.
            if live_cfg.get("playlist_enabled", True):
                pool = playlist.scan_sources()
                if len(pool) > 1:
                    nxt = playlist.pick_next(pool)
                    if nxt and nxt != source_video:
                        print(f"[*] Rotasi source -> {os.path.basename(nxt)}")
                        source_video = nxt
                        playlist.register_play(source_video)


if __name__ == "__main__":
    start_live()
