# -*- coding: utf-8 -*-
"""
Live Playlist Manager — Rotasi multi-source untuk livestream 24/7.

Masalah: 1 video di-loop 12 jam = Content ID flag + harga CPM anjlok.
Solusi: putar beberapa source, ganti tiap N menit, avoid recent replay.
"""
import os
import time
import json
import random

from live_paths import PLAYLIST_STATE, LIVE_DIR


def load_state():
    if os.path.exists(PLAYLIST_STATE):
        try:
            with open(PLAYLIST_STATE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"recent": [], "current": None, "swaps": 0, "history": []}


def save_state(state):
    os.makedirs(LIVE_DIR, exist_ok=True)
    with open(PLAYLIST_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def scan_sources(live_dir=LIVE_DIR):
    """List semua .mp4 yang eligible buat live (exclude bench/test/shorts)."""
    if not os.path.exists(live_dir):
        return []
    out = []
    for f in os.listdir(live_dir):
        if not f.lower().endswith(".mp4"):
            continue
        low = f.lower()
        if low.startswith("bench_") or low.startswith("shorts_") or low.startswith("test_"):
            continue
        p = os.path.join(live_dir, f)
        try:
            if os.path.getsize(p) > 1_000_000:  # < 1MB = stub/corrupt
                out.append(p)
        except OSError:
            pass
    return sorted(out)


def pick_next(sources, recent_limit=2, avoid_recent=True):
    """Pilih source berikutnya, hindari yang baru dipakai."""
    if not sources:
        return None
    if not avoid_recent or len(sources) <= recent_limit:
        return random.choice(sources)
    state = load_state()
    recent = set(state.get("recent", [])[-recent_limit:])
    fresh = [s for s in sources if s not in recent]
    return random.choice(fresh) if fresh else random.choice(sources)


def register_play(source):
    state = load_state()
    recent = state.get("recent", [])
    recent.append(source)
    state["recent"] = recent[-10:]
    state["current"] = source
    state["swaps"] = state.get("swaps", 0) + 1
    state.setdefault("history", []).append({
        "source": os.path.basename(source),
        "ts": int(time.time()),
    })
    state["history"] = state["history"][-50:]
    save_state(state)


def sources_remaining(live_dir=LIVE_DIR):
    """Berapa source yang bisa dipakai + apakah perlu render baru."""
    srcs = scan_sources(live_dir)
    return {
        "count": len(srcs),
        "names": [os.path.basename(s) for s in srcs],
        "need_render": len(srcs) == 0,
    }