"""
DAEMON — Full Auto YouTube Factory
Jalan 24/7, generate + upload otomatis tanpa input manusia.

Cara pakai:
    python daemon.py              # loop selamanya
    python daemon.py --once       # sekali jalan (buat test)
    python daemon.py --dry-run    # generate aja, nggak upload

Log: output/daemon.log
State: output/daemon_state.json (biar nggak upload dobel setelah restart)
"""
import os
import sys
import json
import time
import random
import traceback
import argparse
import logging
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from ai_service import AIService
from audio_composer import AudioComposer
from video_engine import VideoEngine
from youtube_uploader import YouTubeUploader
from thumbnail_gen import generate_thumbnail

CONFIG_PATH = os.path.join(BASE, "config.json")
STATE_PATH = os.path.join(BASE, "output", "daemon_state.json")
LOG_PATH = os.path.join(BASE, "output", "daemon.log")
REKAP_PATH = os.path.join(BASE, "output", "rekap_harian.json")

DAEMON_DEFAULTS = {
    "enabled": True,
    "videos_per_day": 3,
    "duration_minutes_min": 30,
    "duration_minutes_max": 60,
    "upload_privacy": "private",
    "publish_hours_wib": [8, 14, 21],
    "formula_pool": ["1", "2", "3", "4", "5"],
    "delete_after_upload": True,
    "max_disk_gb": 25,
    "retry_delay_minutes": 15
}


def setup_logging():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logger = logging.getLogger("daemon")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
        fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        logger.addHandler(sh)
    return logger


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def update_rekap_harian(entry_data):
    """
    Simpan rekap harian produksi video ke output/rekap_harian.json.
    Mencatat tanggal, jumlah video yang sudah dibuat hari ini,
    total durasi menit, serta list detail video yang berhasil diproduksi.
    """
    rekap = load_json(REKAP_PATH, {})
    now_wib = datetime.now(timezone.utc) + timedelta(hours=7)
    today = now_wib.date().isoformat()

    if today not in rekap:
        rekap[today] = {
            "tanggal": today,
            "total_video": 0,
            "total_menit": 0,
            "videos": []
        }

    item = {
        "waktu_selesai_wib": now_wib.strftime("%Y-%m-%d %H:%M:%S WIB"),
        "judul": entry_data.get("title", ""),
        "video_file": entry_data.get("video", ""),
        "formula": entry_data.get("formula", ""),
        "durasi_menit": entry_data.get("duration_min", 0),
        "video_id": entry_data.get("video_id"),
        "status_upload": "sukses" if entry_data.get("video_id") else "dry-run/local",
        "url": f"https://youtu.be/{entry_data.get('video_id')}" if entry_data.get("video_id") else None,
        "jadwal_tayang": entry_data.get("publish_at")
    }

    rekap[today]["videos"].append(item)
    rekap[today]["total_video"] = len(rekap[today]["videos"])
    rekap[today]["total_menit"] = sum(v.get("durasi_menit", 0) for v in rekap[today]["videos"])

    save_json(REKAP_PATH, rekap)
    return rekap[today]


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    daemon_cfg = dict(DAEMON_DEFAULTS)
    daemon_cfg.update(cfg.get("daemon", {}))
    cfg["daemon"] = daemon_cfg
    return cfg


def ensure_dirs():
    for sub in ("output", "assets/backgrounds", "assets/music", "assets/ambience"):
        os.makedirs(os.path.join(BASE, sub), exist_ok=True)


def disk_free_gb(path):
    import shutil
    try:
        return shutil.disk_usage(path).free / (1024 ** 3)
    except Exception:
        return 999.0


def pick_formula(cfg, state):
    """Pilih formula yang punya lagu, rotasi biar nggak monoton."""
    pool = cfg["daemon"].get("formula_pool") or list(cfg["formulas"].keys())
    composer = AudioComposer()
    usable = []
    for key in pool:
        files = composer.get_music_files(formula_key=key, shuffle=False)
        if len(files) >= 3:
            usable.append(key)
    if not usable:
        usable = pool

    last = state.get("last_formula")
    candidates = [k for k in usable if k != last] or usable
    return random.choice(candidates)


def pick_duration(cfg):
    d = cfg["daemon"]
    lo = int(d.get("duration_minutes_min", 30))
    hi = int(d.get("duration_minutes_max", 60))
    if hi < lo:
        lo, hi = hi, lo
    return random.randint(lo, hi)


def pick_backgrounds(engine, allow_ai, ai, n=3):
    """
    Pilih N background untuk multi-scene. Bank stok + (opsional) AI.
    Return list of path, urut teracak.
    """
    bg_dir = os.path.join(engine.base_dir, "assets", "backgrounds")
    exts = (".jpg", ".jpeg", ".png", ".jfif", ".webp")
    try:
        bank = [
            os.path.join(bg_dir, f) for f in os.listdir(bg_dir)
            if f.lower().endswith(exts) and not f.startswith("test_")
            and not f.startswith("thumb_")
        ]
    except FileNotFoundError:
        bank = []

    random.shuffle(bank)
    chosen = list(bank[:n])

    if allow_ai and len(chosen) < n:
        prompts = [
            "cozy rainy window with warm lamp light, coffee cup on wooden table, cinematic, photorealistic 8k, no text",
            "victorian library with leather books and candlelight, dark academia aesthetic, cinematic 8k, no text",
            "peaceful forest stream at golden hour, soft bokeh, cinematic landscape, 8k, no text",
            "minimalist beige study desk with plant and notebook, soft morning light, aesthetic, 8k, no text",
        ]
        while len(chosen) < n:
            try:
                fname = f"ai_bg_{int(time.time())}_{random.randint(0, 9999)}.jpg"
                p = ai.generate_and_download_image(random.choice(prompts), fname)
                if p and os.path.exists(p):
                    chosen.append(p)
                else:
                    break
            except Exception:
                break

    if not chosen:
        raise RuntimeError("Tidak ada background yang tersedia")
    return chosen[:n]


def pick_overlay(formula_key):
    mapping = {
        "1": "rain_glass",
        "2": "sunlight",
        "3": "dust",
        "4": "embers",
        "5": "sunlight",
    }
    return mapping.get(str(formula_key), "dust")


def find_pending_video():
    """Cari video di folder output yang belum terupload (status: ready_for_upload)."""
    out_dir = os.path.join(BASE, "output")
    if not os.path.exists(out_dir):
        return None
    # Exclude domain livestream dari sweep upload daemon.
    live_dir_abs = os.path.abspath(os.path.join(out_dir, "live"))
    for f in sorted(os.listdir(out_dir)):
        if f.endswith(".mp4") and not f.startswith("bench_"):
            vid_path = os.path.join(out_dir, f)
            # Skip kalau masuk folder output/live/
            if os.path.commonpath([os.path.abspath(vid_path), live_dir_abs]) == live_dir_abs:
                continue
            meta_path = os.path.splitext(vid_path)[0] + ".json"
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as jf:
                        meta = json.load(jf)
                    if meta.get("status") == "ready_for_upload":
                        return vid_path, meta_path, meta
                except Exception:
                    pass
    return None


def wait_until_hour(target_hour, tz_offset_hours=7):
    """Sleep sampai jam target (WIB)."""
    now = datetime.now(timezone.utc) + timedelta(hours=tz_offset_hours)
    target = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    delta = (target - now).total_seconds()
    return max(0, delta)


def produce_one(cfg, state, logger, dry_run=False):
    # Cek apakah ada video pending dari sesi sebelumnya yang belum terupload
    pending = find_pending_video()
    if pending:
        video_path, meta_path, seo = pending
        vid_filename = os.path.basename(video_path)
        logger.info("=" * 60)
        logger.info(f"DITEMUKAN VIDEO PENDING DARI SESI SEBELUMNYA: {vid_filename}")
        logger.info(f"Judul    : {seo.get('title')}")
        logger.info("Melewati tahap render, langsung memproses upload...")

        import re
        m = re.search(r"video_([0-9a-zA-Z]+)_", vid_filename)
        formula_key = m.group(1) if m else "1"
        duration_sec = seo.get("duration_seconds", 1800)
        duration_min = int(duration_sec // 60)

        bg_candidate = seo.get("thumbnail_image")
        thumb_path = None
        if cfg["daemon"].get("thumbnail_enabled", True):
            brand = cfg.get("branding", {}).get("channel_name", "")
            if bg_candidate and os.path.exists(bg_candidate):
                try:
                    thumb_path = generate_thumbnail(
                        bg_candidate, seo.get("title", ""),
                        accent=cfg["daemon"].get("thumbnail_accent", "#F5C518"),
                        brand=brand
                    )
                except Exception as e:
                    logger.warning(f"      Thumbnail gagal ({e})")
                    thumb_path = bg_candidate
        bg_paths = [bg_candidate] if bg_candidate else [None]
    else:
        logger.info("=" * 60)
        logger.info("MULAI PRODUKSI VIDEO BARU")

        ai = AIService()
        composer = AudioComposer()
        engine = VideoEngine()

        formula_key = pick_formula(cfg, state)
        formula_name = cfg["formulas"].get(formula_key, "Relaxing Music")
        duration_min = pick_duration(cfg)
        duration_sec = duration_min * 60
        ts = int(time.time())

        logger.info(f"Formula  : {formula_key} - {formula_name}")
        logger.info(f"Durasi   : {duration_min} menit")

        # 1. SEO
        logger.info("[1/4] Generate SEO metadata...")
        seo = ai.generate_seo_metadata(formula_name, duration_min)
        logger.info(f"      Judul: {seo.get('title')}")

        # 2. Visual (multi-scene)
        scene_change_min = int(cfg["daemon"].get("scene_change_minutes", 3))
        n_scenes = max(2, duration_min // scene_change_min)
        n_scenes = min(n_scenes, 6)  # batas atas supaya tetap ringan
        logger.info(f"[2/4] Pilih {n_scenes} background untuk multi-scene...")
        try:
            bg_paths = pick_backgrounds(engine, allow_ai=True, ai=ai, n=n_scenes)
        except Exception as e:
            logger.warning(f"      pick_backgrounds gagal ({e}), fallback ke 1 background")
            try:
                bgs = pick_backgrounds(engine, allow_ai=False, ai=ai, n=1)
            except Exception:
                # Hard fallback: ambil file apa pun
                bg_dir = os.path.join(engine.base_dir, "assets", "backgrounds")
                any_bg = [
                    os.path.join(bg_dir, f) for f in os.listdir(bg_dir)
                    if f.lower().endswith((".jpg", ".jpeg", ".png", ".jfif", ".webp"))
                ]
                bg_paths = [any_bg[0]] if any_bg else [None]
            if not bg_paths or not bg_paths[0]:
                raise RuntimeError("Tidak ada background sama sekali")
        for p in bg_paths:
            logger.info(f"      {os.path.basename(p)}")

        # 3. Audio
        logger.info(f"[3/4] Compose audio {duration_min} menit...")
        audio_name = f"master_audio_{ts}.m4a"
        audio_path = composer.compose_master_audio(
            duration_sec, audio_name, formula_key=formula_key, shuffle=True
        )
        logger.info(f"      {os.path.basename(audio_path)} "
                    f"({os.path.getsize(audio_path) / 1048576:.1f} MB)")

        # 4. Render (multi-scene dengan Ken Burns + xfade)
        logger.info(f"[4/4] Render multi-scene ({len(bg_paths)} scene)...")
        seo["duration_seconds"] = duration_sec
        seo["thumbnail_image"] = bg_paths[0]
        video_name = f"video_{formula_key}_{ts}.mp4"

        free_ram = VideoEngine.free_ram_gb()
        min_ram = float(cfg["daemon"].get("min_free_ram_gb", 2.0))
        if free_ram < min_ram:
            logger.warning(f"      RAM cuma {free_ram:.1f} GB (min {min_ram}). Pause 5 menit.")
            time.sleep(300)
            free_ram = VideoEngine.free_ram_gb()
            if free_ram < min_ram:
                logger.error(f"      RAM masih {free_ram:.1f} GB. Skip video ini.")
                raise RuntimeError("RAM tidak cukup")

        # Tentukan scene_seconds: n_scenes dengan total_dur, kurangi xfade
        # xfade = 1.0s antar scene; scene_seconds approx target_total / n_scenes
        target_scene = max(60, int(duration_sec / n_scenes))

        try:
            video_path = engine.render_multiscene(
                bg_paths, audio_path, video_name,
                metadata=seo,
                scene_seconds=target_scene,
                transition_seconds=1.0,
                formula_key=formula_key
            )
        except Exception as e:
            logger.warning(f"      Multi-scene gagal ({e}), fallback single-scene")
            video_path = engine.render_video(
                bg_paths[0], audio_path, video_name,
                metadata=seo, motion_mode=True, overlay_type=pick_overlay(formula_key)
            )
        logger.info(f"      {os.path.basename(video_path)} "
                    f"({os.path.getsize(video_path) / 1048576:.1f} MB)")

        if os.path.exists(audio_path):
            os.remove(audio_path)

        meta_path = os.path.splitext(video_path)[0] + ".json"

        # 4b. Thumbnail (kalau enable)
        thumb_path = None
        if cfg["daemon"].get("thumbnail_enabled", True):
            brand = cfg.get("branding", {}).get("channel_name", "")
            try:
                thumb_path = generate_thumbnail(
                    bg_paths[0], seo.get("title", ""),
                    accent=cfg["daemon"].get("thumbnail_accent", "#F5C518"),
                    brand=brand
                )
            except Exception as e:
                logger.warning(f"      Thumbnail gagal: {e}")
                thumb_path = None

    # 5. Upload
    if dry_run:
        logger.info("DRY-RUN: skip upload. File siap di output/")
        state["last_formula"] = formula_key
        dry_entry = {
            "video": os.path.basename(video_path),
            "title": seo.get("title", ""),
            "formula": formula_key,
            "duration_min": duration_min,
            "created": datetime.now().isoformat()
        }
        state.setdefault("produced", []).append(dry_entry)
        save_json(STATE_PATH, state)
        r_today = update_rekap_harian(dry_entry)
        logger.info(f"[REKAP] Hari ini ({r_today['tanggal']}): {r_today['total_video']} video, total {r_today['total_menit']} menit.")
        return {"uploaded": False, "video": video_path}

    logger.info("Upload ke YouTube...")
    uploader = YouTubeUploader()
    privacy = cfg["daemon"].get("upload_privacy", "private")

    # Jadwalkan tayang di jam prime berikutnya
    hours = cfg["daemon"].get("publish_hours_wib", [8, 14, 21])
    now_wib = datetime.now(timezone.utc) + timedelta(hours=7)
    target_hour = None
    for h in sorted(hours):
        if now_wib.hour < h:
            target_hour = h
            break
    if target_hour is None:
        target_hour = sorted(hours)[0]
        next_day = True
    else:
        next_day = False

    pub_wib = now_wib.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    if next_day:
        pub_wib += timedelta(days=1)
    pub_utc = pub_wib - timedelta(hours=7)
    publish_at = pub_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    logger.info(f"Jadwal tayang: {pub_wib.strftime('%Y-%m-%d %H:%M WIB')}")

    result = uploader.upload_video(
        video_path=video_path,
        meta_path=meta_path,
        thumbnail_path=thumb_path or bg_paths[0],
        privacy_status=privacy,
        publish_at_iso=publish_at
    )

    state["last_formula"] = formula_key
    entry = {
        "video": os.path.basename(video_path),
        "title": seo.get("title", ""),
        "formula": formula_key,
        "duration_min": duration_min,
        "video_id": (result or {}).get("video_id") or (result or {}).get("id"),
        "publish_at": publish_at,
        "created": datetime.now().isoformat()
    }
    state.setdefault("produced", []).append(entry)
    state["produced"] = state["produced"][-200:]
    save_json(STATE_PATH, state)

    r_today = update_rekap_harian(entry)
    logger.info(f"UPLOAD OK: https://youtu.be/{entry.get('video_id')}")
    logger.info(f"[REKAP] Hari ini ({r_today['tanggal']}): {r_today['total_video']} video berhasil, total {r_today['total_menit']} menit.")

    # 6. Auto-generate Teaser Shorts (Traffic Siphon) jika diaktifkan
    if cfg.get("video_settings", {}).get("generate_shorts", True) and entry.get("video_id"):
        try:
            logger.info("[Shorts] Merender Teaser Shorts vertikal 9:16 (Traffic Siphon)...")
            from shorts_gen import ShortsGenerator
            s_gen = ShortsGenerator()
            # Ambil lagu tema pertama dan background pertama untuk Shorts teaser
            composer = AudioComposer()
            first_songs = composer.get_music_files(formula_key=formula_key, shuffle=False)
            shorts_audio = first_songs[0] if first_songs else None
            if shorts_audio and bg_paths:
                shorts_vid, shorts_meta = s_gen.generate_teaser_shorts(
                    background_path=bg_paths[0],
                    audio_path=shorts_audio,
                    main_title=seo.get("title", "Relaxing Music"),
                    main_video_id=entry.get("video_id"),
                    duration_seconds=35
                )
                logger.info("[Shorts] Mengupload teaser shorts ke YouTube...")
                s_res = uploader.upload_video(
                    video_path=shorts_vid,
                    meta_path=shorts_meta,
                    thumbnail_path=None,
                    privacy_status=privacy,
                    publish_at_iso=publish_at
                )
                shorts_id = (s_res or {}).get("video_id") or (s_res or {}).get("id")
                logger.info(f"[Shorts] UPLOAD OK: https://youtu.be/{shorts_id}")
                if cfg["daemon"].get("delete_after_upload", True):
                    if os.path.exists(shorts_vid): os.remove(shorts_vid)
                    if os.path.exists(shorts_meta): os.remove(shorts_meta)
        except Exception as e:
            logger.warning(f"[Shorts] Gagal generate/upload teaser shorts: {e}")

    # Bersihkan file besar video utama
    if cfg["daemon"].get("delete_after_upload", True):
        try:
            os.remove(video_path)
            if os.path.exists(meta_path):
                os.remove(meta_path)
            logger.info("File lokal dihapus (hemat disk).")
        except Exception as e:
            logger.warning(f"Gagal hapus file: {e}")

    return {"uploaded": True, "video_id": entry.get("video_id")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Jalan sekali lalu keluar")
    parser.add_argument("--dry-run", action="store_true", help="Generate tanpa upload")
    parser.add_argument("--videos", type=int, default=0, help="Override jumlah video per hari")
    args = parser.parse_args()

    logger = setup_logging()
    ensure_dirs()

    cfg = load_config()
    if not cfg["daemon"].get("enabled", True):
        logger.info("Daemon disabled di config. Keluar.")
        return

    videos_per_day = args.videos or cfg["daemon"].get("videos_per_day", 3)
    logger.info(f"DAEMON START — target {videos_per_day} video/hari")

    state = load_json(STATE_PATH, {"last_formula": None, "produced": []})

    if args.once:
        try:
            produce_one(cfg, state, logger, dry_run=args.dry_run)
            logger.info("SELESAI (--once)")
        except Exception as e:
            logger.error(f"GAGAL: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
        return

    while True:
        try:
            free_gb = disk_free_gb(BASE)
            if free_gb < 5:
                logger.error(f"Disk hampir penuh ({free_gb:.1f} GB). Tidur 1 jam.")
                time.sleep(3600)
                continue

            now_wib = datetime.now(timezone.utc) + timedelta(hours=7)
            today_str = now_wib.date().isoformat()

            rekap = load_json(REKAP_PATH, {})
            rekap_today = rekap.get(today_str, {})
            produced_today = rekap_today.get("total_video", 0)
            total_menit_today = rekap_today.get("total_menit", 0)

            logger.info(f"STATUS HARIAN [{today_str}]: {produced_today}/{videos_per_day} video selesai ({total_menit_today} menit)")

            if produced_today >= videos_per_day:
                sleep_s = wait_until_hour(0)  # Cek lagi tepat saat ganti hari (00:00 WIB)
                jam_tidur = sleep_s / 3600
                logger.info(f"Target hari ini {today_str} tercapai ({produced_today}/{videos_per_day} video).")
                logger.info(f"Menunggu pergantian hari (00:00 WIB) sekitar {jam_tidur:.1f} jam untuk mulai siklus hari berikutnya.")
                time.sleep(min(sleep_s, 1800))  # Cek ulang maksimal tiap 30 menit
                continue

            produce_one(cfg, state, logger, dry_run=args.dry_run)

            # Jeda antar video: 45-90 menit biar nggak kena spam detection
            pause = random.randint(45 * 60, 90 * 60)
            logger.info(f"Jeda {pause // 60} menit sebelum video berikutnya.")
            time.sleep(pause)

        except KeyboardInterrupt:
            logger.info("Daemon dihentikan user.")
            break
        except Exception as e:
            logger.error(f"ERROR: {e}")
            logger.error(traceback.format_exc())
            delay = cfg["daemon"].get("retry_delay_minutes", 15) * 60
            logger.info(f"Retry dalam {delay // 60} menit.")
            time.sleep(delay)


if __name__ == "__main__":
    main()
