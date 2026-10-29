# -*- coding: utf-8 -*-
"""
Live Path Isolation — Konstanta folder khusus livestream.

Tujuan: pisahkan file live dari output/ daemon supaya daemon TIDAK
memangap video live sebagai kandidat upload dan tidak menghapusnya.

Layout:
  output/live/master_livestream_loop.mp4   <- video live (JANGAN di-daemon)
  output/live/live_playlist.json            <- state rotasi multi-source
  output/live/stream_state.json             <- persistent timer/telemetry
  output/live/live_telemetry.log            <- log khusus live
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OUTPUT_DIR = os.path.join(BASE_DIR, "output")
LIVE_DIR = os.path.join(OUTPUT_DIR, "live")

MASTER_LOOP = os.path.join(LIVE_DIR, "master_livestream_loop.mp4")
PLAYLIST_STATE = os.path.join(LIVE_DIR, "live_playlist.json")
STREAM_STATE = os.path.join(LIVE_DIR, "stream_state.json")
TELEMETRY_LOG = os.path.join(LIVE_DIR, "live_telemetry.log")

# Prefix file yang milik live. Daemon wajib skip semua ini.
LIVE_ONLY_NAMES = {"master_livestream_loop.mp4"}


def ensure_live_dir():
    os.makedirs(LIVE_DIR, exist_ok=True)
    return LIVE_DIR


def is_live_file(filename):
    """True kalau filename/absolute path ini milik domain livestream."""
    name = os.path.basename(filename)
    if name in LIVE_ONLY_NAMES:
        return True
    if os.path.commonpath([os.path.abspath(filename), os.path.abspath(LIVE_DIR)]) == os.path.abspath(LIVE_DIR):
        return True
    return False


def migrate_legacy():
    """Pindahkan master loop lama dari output/ ke output/live/ sekali saja."""
    ensure_live_dir()
    legacy = os.path.join(OUTPUT_DIR, "master_livestream_loop.mp4")
    if os.path.exists(legacy) and not os.path.exists(MASTER_LOOP):
        import shutil
        shutil.move(legacy, MASTER_LOOP)
        return True
    return False