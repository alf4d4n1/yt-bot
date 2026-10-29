"""
Auto Title Rotation — Ganti title live stream tiap X jam via YouTube Data API.
Ambil dari list title yang user siapin di config.json > livestream > titles[].
"""
import os
import sys
import json
import time
import random
import threading
from datetime import datetime

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPTS_DIR)
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_api_key(config):
    """Ambil YouTube API key dari config."""
    return config.get("youtube_api_key", "") or config.get("api_key", "")


def get_oauth_access_token(config=None):
    """Refresh OAuth access token dari credentials/token.json.

    Token rotasi tiap ~1 jam, jadi SELALU ambil yang fresh — jangan cache.
    Ini jalur yang sama dengan live_broadcast_manager.load_credentials().
    """
    import urllib.request
    import urllib.parse

    token_file = os.path.join(BASE_DIR, "credentials", "token.json")
    if not os.path.exists(token_file):
        return None
    try:
        with open(token_file, "r", encoding="utf-8") as f:
            t = json.load(f)
        payload = urllib.parse.urlencode({
            "client_id": t["client_id"],
            "client_secret": t["client_secret"],
            "refresh_token": t["refresh_token"],
            "grant_type": "refresh_token",
        }).encode()
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())["access_token"]
    except Exception:
        return None


def get_broadcast_id(config):
    """Cari broadcast ID yang aktif via YouTube Data API (OAuth)."""
    import urllib.request
    import urllib.parse

    token = get_oauth_access_token(config)
    if not token:
        return None, "OAuth token tidak bisa di-refresh"

    try:
        # broadcastStatus hanya valid: active|all|completed|id
        params = urllib.parse.urlencode({
            "part": "id,snippet,status",
            "broadcastStatus": "all",
            "broadcastType": "all",
            "maxResults": 25,
            "order": "date",
        })
        url = f"https://www.googleapis.com/youtube/v3/liveBroadcasts?{params}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        for it in data.get("items", []):
            st = it.get("status", {})
            if st.get("lifeCycleStatus") in ("live", "ready", "testing") \
                    and st.get("privacyStatus") == "public":
                return it["id"], None
        return None, "Tidak ada broadcast aktif"

    except Exception as e:
        return None, str(e)


def update_broadcast_title(config, broadcast_id, new_title, new_description=None):
    """Update title broadcast via YouTube Data API v3 (OAuth)."""
    oauth_token = get_oauth_access_token(config)
    if not oauth_token:
        return False, "OAuth token tidak bisa di-refresh"

    try:
        import urllib.request
        import urllib.parse

        # Get current broadcast snippet first
        get_url = (
            f"https://www.googleapis.com/youtube/v3/liveBroadcasts"
            f"?part=snippet,status&id={broadcast_id}"
        )
        req = urllib.request.Request(get_url)
        req.add_header("Authorization", f"Bearer {oauth_token}")

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        if not data.get("items"):
            return False, "Broadcast tidak ditemukan"

        snippet = data["items"][0]["snippet"]
        snippet["title"] = new_title
        if new_description:
            snippet["description"] = new_description

        # Update via PUT
        update_url = "https://www.googleapis.com/youtube/v3/liveBroadcasts?part=snippet"
        body = json.dumps({
            "id": broadcast_id,
            "snippet": snippet
        }).encode("utf-8")

        req = urllib.request.Request(update_url, data=body, method="PUT")
        req.add_header("Authorization", f"Bearer {oauth_token}")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            return True, result.get("snippet", {}).get("title", new_title)

    except Exception as e:
        return False, str(e)


class TitleRotator:
    """Background thread yang rotate title tiap X jam."""

    def __init__(self, config, interval_hours=2, log_fn=None):
        self.config = config
        self.interval_hours = interval_hours
        self.log_fn = log_fn or print
        self.running = False
        self.thread = None
        self.titles = config.get("livestream", {}).get("titles", [])
        self.current_idx = 0
        self.last_title = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def set_titles(self, titles):
        """Update title list on the fly."""
        self.titles = titles

    def _pick_next_title(self):
        """Pick next title, avoiding repeat."""
        if not self.titles:
            return None
        # Round-robin
        title = self.titles[self.current_idx % len(self.titles)]
        self.current_idx += 1
        return title

    def _loop(self):
        # Tunggu 5 detik sebelum mulai (biar stream stabil dulu)
        for _ in range(5):
            if not self.running:
                return
            time.sleep(1)

        while self.running:
            title = self._pick_next_title()
            if title:
                broadcast_id, err = get_broadcast_id(self.config)
                if broadcast_id:
                    ok, result = update_broadcast_title(self.config, broadcast_id, title)
                    if ok:
                        self.last_title = title
                        self.log_fn(f"[Title] ✅ Diganti: \"{title}\"")
                    else:
                        self.log_fn(f"[Title] ❌ Gagal update: {result}")
                else:
                    self.log_fn(f"[Title] ⚠ Broadcast tidak ditemukan: {err}")
            else:
                self.log_fn("[Title] ⚠ List title kosong — tambah di config")

            # Sleep interval (responsive stop)
            sleep_secs = self.interval_hours * 3600
            for _ in range(int(sleep_secs)):
                if not self.running:
                    return
                time.sleep(1)
