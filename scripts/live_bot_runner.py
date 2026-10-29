# -*- coding: utf-8 -*-
"""
Live Bot Runner v2 - Headless HTTP viewer tanpa buka Chrome.

Cookies diambil dari Chrome profile yang sudah login (via tombol Login Chrome di GUI).
Setiap akun jalan sebagai requests.Session - RAM ~3-5 MB per akun, bukan ~300 MB Chrome.
"""
import os
import time
import random
import threading
import sqlite3
import shutil
import tempfile
import re

import json
import base64

import requests

from live_accounts import load_accounts, save_accounts, CHROME_PROFILES_DIR


def _get_chrome_key(profile_path):
    """Get Chrome AES key dari Local State, decrypt via Windows DPAPI."""
    local_state_path = os.path.join(profile_path, "Local State")
    if not os.path.exists(local_state_path):
        return None
    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)
        encrypted_key = base64.b64decode(
            local_state["os_crypt"]["encrypted_key"]
        )
        encrypted_key = encrypted_key[5:]  # strip 'DPAPI' prefix
        import ctypes
        import ctypes.wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", ctypes.wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char)),
            ]

        p = ctypes.create_string_buffer(encrypted_key, len(encrypted_key))
        blob_in = DATA_BLOB(ctypes.sizeof(p), p)
        blob_out = DATA_BLOB()
        if ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0,
            ctypes.byref(blob_out),
        ):
            key = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return key
    except Exception:
        pass
    return None


def _decrypt_cookie_value(encrypted_value, key):
    """Decrypt Chrome cookie encrypted_value (AES-256-GCM)."""
    try:
        from Crypto.Cipher import AES
        if encrypted_value[:3] in (b"v10", b"v20"):
            nonce = encrypted_value[3:15]
            ciphertext = encrypted_value[15:-16]
            tag = encrypted_value[-16:]
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            decrypted = cipher.decrypt_and_verify(ciphertext, tag)
            try:
                return decrypted.decode("utf-8")
            except UnicodeDecodeError:
                return decrypted.decode("latin-1")
    except Exception:
        pass
    return ""

YT_WATCH = "https://www.youtube.com/watch"
YT_LIVE_CHAT_SEND = "https://www.youtube.com/youtubei/v1/live_chat/send_message"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

HEARTBEAT_INTERVAL = 30  # YouTube watchtime ping tiap 30 detik

YT_PLAYER_API = "https://www.youtube.com/youtubei/v1/player"
YT_WATCHTIME = "https://www.youtube.com/api/stats/watchtime"
YT_PLAYBACK = "https://www.youtube.com/api/stats/playback"


def extract_cookies_from_profile(profile_path):
    """Extract cookies via Selenium headless Chrome (bypasses App-Bound Encryption).
    Caches ke JSON supaya gak perlu buka Chrome tiap kali."""
    cache_file = os.path.join(profile_path, "cached_cookies.json")

    # Pakai cache kalau ada dan belum expired (max 1 jam)
    if os.path.exists(cache_file):
        try:
            age = time.time() - os.path.getmtime(cache_file)
            if age < 3600:  # 1 jam
                with open(cache_file, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                if cookies and any(k in cookies for k in ("SID", "__Secure-1PSID")):
                    return cookies
        except Exception:
            pass

    # Extract fresh via Selenium headless
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        opts = Options()
        opts.add_argument(f"--user-data-dir={profile_path}")
        opts.add_argument("--headless=new")
        opts.add_argument("--no-first-run")
        opts.add_argument("--no-default-browser-check")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--mute-audio")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--disable-background-networking")

        driver = webdriver.Chrome(options=opts)
        driver.set_page_load_timeout(15)
        driver.get("https://www.youtube.com/")
        time.sleep(2)

        raw_cookies = driver.get_cookies()
        driver.quit()

        cookies = {}
        for c in raw_cookies:
            if "youtube" in c.get("domain", "") or "google" in c.get("domain", ""):
                cookies[c["name"]] = c["value"]

        # Cache ke JSON
        if cookies:
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(cookies, f)
            except Exception:
                pass

        return cookies if cookies else None
    except Exception:
        return None


def check_login_status(cookies):
    if not cookies:
        return False
    indicators = ["SID", "__Secure-1PSID", "__Secure-3PSID", "LOGIN_INFO"]
    return any(k in cookies for k in indicators)


def extract_chat_params(html):
    try:
        m = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
        api_key = m.group(1) if m else "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
        m = re.search(r'"clientVersion":"([^"]+)"', html)
        client_ver = m.group(1) if m else "2.20241201.00.00"
        m = re.search(r'"continuation":"([^"]+)"', html)
        continuation = m.group(1) if m else None
        m = re.search(r'"sendLiveChatMessageEndpoint":\{"params":"([^"]+)"', html)
        send_params = m.group(1) if m else None
        return {"api_key": api_key, "client_version": client_ver,
                "continuation": continuation, "send_params": send_params}
    except Exception:
        return None


class HeadlessViewer:
    def __init__(self, acc_id, acc_name, cookies, log_fn=print):
        self.acc_id = acc_id
        self.acc_name = acc_name
        self.log = log_fn
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain=".youtube.com")
        self.chat_params = None
        self.alive = True

    def heartbeat(self, video_id):
        try:
            resp = self.session.get(YT_WATCH, params={"v": video_id}, timeout=15)
            if resp.status_code == 200:
                self.chat_params = extract_chat_params(resp.text)
                # Extract player params untuk watchtime
                self._extract_player_params(resp.text, video_id)
                return True
            self.log(f"[{self.acc_name}] Heartbeat HTTP {resp.status_code}")
            return False
        except Exception as e:
            self.log(f"[{self.acc_name}] Heartbeat error: {e}")
            return False

    def _extract_player_params(self, html, video_id):
        """Extract cpn, ei, dan lact dari watch page buat watchtime API."""
        try:
            # Generate CPN (client playback nonce) - 16 char alphanumeric
            import string
            self.cpn = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            self.video_id = video_id

            # Extract ei parameter
            m = re.search(r'"ei":"([^"]+)"', html)
            self.ei = m.group(1) if m else ""

            # Extract sts (signature timestamp)
            m = re.search(r'"sts":(\d+)', html)
            self.sts = m.group(1) if m else "0"

            # Track watch time
            self.watch_start = time.time()
            self.last_pos = 0.0

        except Exception:
            self.cpn = None

    def player_init(self, video_id):
        """Call /youtubei/v1/player - registrasi viewer ke YouTube."""
        try:
            payload = {
                "context": {
                    "client": {
                        "clientName": "WEB",
                        "clientVersion": self.chat_params["client_version"] if self.chat_params else "2.20241201.00.00",
                        "hl": "en",
                        "gl": "US",
                    }
                },
                "videoId": video_id,
                "playbackContext": {
                    "contentPlaybackContext": {
                        "autoCaptionsDefaultOn": False,
                        "html5Preference": "HTML5_PREF_WANTS",
                        "lactMilliseconds": "0",
                        "signatureTimestamp": self.sts if hasattr(self, 'sts') else "0",
                    }
                },
            }
            api_key = self.chat_params["api_key"] if self.chat_params else "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
            resp = self.session.post(
                f"{YT_PLAYER_API}?key={api_key}",
                json=payload, timeout=15,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def playback_ping(self, video_id):
        """Send /api/stats/playback - bilang YouTube kita mulai nonton."""
        try:
            params = {
                "ns": "yt",
                "el": "detailpage",
                "cpn": self.cpn or "x" * 16,
                "docid": video_id,
                "ver": "2",
                "referrer": "https://www.youtube.com/",
                "cmt": "0",
                "ei": getattr(self, 'ei', ''),
                "fmt": "243",
                "fs": "0",
                "rt": str(random.uniform(1, 5)),
                "lact": str(random.randint(100, 3000)),
                "cl": str(random.randint(500000000, 600000000)),
                "mos": "0",
                "volume": "100",
                "cbr": "Chrome",
                "cbrver": "131.0.0.0",
                "c": "WEB",
                "cver": "2.20241201.00.00",
                "cplayer": "UNIPLAYER",
                "cos": "Windows",
                "cosver": "10.0",
                "cplatform": "DESKTOP",
                "live": "dvr",
            }
            resp = self.session.get(YT_PLAYBACK, params=params, timeout=10)
            return resp.status_code == 204 or resp.status_code == 200
        except Exception:
            return False

    def watchtime_ping(self, video_id):
        """Send /api/stats/watchtime - heartbeat tiap 30 detik biar dihitung viewer."""
        if not hasattr(self, 'cpn') or not self.cpn:
            return False
        try:
            elapsed = time.time() - self.watch_start
            self.last_pos = elapsed
            cmt = str(round(elapsed, 1))

            params = {
                "ns": "yt",
                "el": "detailpage",
                "cpn": self.cpn,
                "docid": video_id,
                "ver": "2",
                "cmt": cmt,
                "ei": getattr(self, 'ei', ''),
                "fmt": "243",
                "fs": "0",
                "rt": str(round(elapsed + random.uniform(0.5, 2), 1)),
                "lact": str(random.randint(500, 5000)),
                "cl": str(random.randint(500000000, 600000000)),
                "mos": "0",
                "volume": "100",
                "st": str(round(max(0, elapsed - 30), 1)),
                "et": cmt,
                "cbr": "Chrome",
                "cbrver": "131.0.0.0",
                "c": "WEB",
                "cver": "2.20241201.00.00",
                "cplayer": "UNIPLAYER",
                "cos": "Windows",
                "cosver": "10.0",
                "cplatform": "DESKTOP",
                "live": "dvr",
                "muted": "0",
            }
            resp = self.session.get(YT_WATCHTIME, params=params, timeout=10)
            return resp.status_code == 204 or resp.status_code == 200
        except Exception:
            return False

    def send_chat(self, message):
        if not self.chat_params or not self.chat_params.get("send_params"):
            self.log(f"[{self.acc_name}] Chat skip - params belum ready")
            return False
        try:
            payload = {
                "context": {"client": {"clientName": "WEB",
                            "clientVersion": self.chat_params["client_version"]}},
                "params": self.chat_params["send_params"],
                "richMessage": {"textSegments": [{"text": message}]},
            }
            resp = self.session.post(
                f"{YT_LIVE_CHAT_SEND}?key={self.chat_params['api_key']}",
                json=payload, timeout=15)
            if resp.status_code == 200:
                self.log(f'[{self.acc_name}] Chat: "{message}"')
                return True
            self.log(f"[{self.acc_name}] Chat gagal HTTP {resp.status_code}")
            return False
        except Exception as e:
            self.log(f"[{self.acc_name}] Chat error: {e}")
            return False


class LiveAudienceBot:
    def __init__(self, log_callback=None, status_callback=None):
        self.log_cb = log_callback or print
        self.status_cb = status_callback
        self.running = False
        self.viewers = {}
        self.thread = None
        self.live_url = ""
        self.video_id = ""

    def log(self, msg):
        if self.log_cb:
            self.log_cb(msg)

    def _extract_video_id(self, url):
        for pat in [r'youtu\.be/([a-zA-Z0-9_-]{11})',
                    r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
                    r'youtube\.com/live/([a-zA-Z0-9_-]{11})']:
            m = re.search(pat, url)
            if m:
                return m.group(1)
        return None

    def start_stay(self, live_url):
        if self.running:
            return
        self.running = True
        self.live_url = live_url
        self.video_id = self._extract_video_id(live_url) or ""
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop_stay(self):
        self.running = False
        for v in self.viewers.values():
            v.alive = False
        self.viewers.clear()
        # Quit Chrome drivers
        for d in getattr(self, '_drivers', []):
            try:
                d.quit()
            except Exception:
                pass
        self._drivers = []
        self.log("[Pancingan] Semua akun dihentikan.")
        if self.status_cb:
            self.status_cb(0, 0, "Idle")

    def _launch_chrome_stay(self, profile_path, video_id, acc_name):
        """Buka Chrome headless, masuk live page = nongkrong sebagai participant."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            opts = Options()
            opts.add_argument(f"--user-data-dir={profile_path}")
            opts.add_argument("--headless=new")
            opts.add_argument("--no-first-run")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--mute-audio")
            opts.add_argument("--disable-extensions")
            opts.add_argument("--window-size=320,240")
            opts.add_argument("--disable-dev-shm-usage")
            # Block heavy resources to save RAM
            opts.add_argument("--blink-settings=imagesEnabled=false")
            opts.add_experimental_option("prefs", {
                "profile.managed_default_content_settings.images": 2,
                "profile.managed_default_content_settings.media_stream": 2,
            })

            driver = webdriver.Chrome(options=opts)
            driver.set_page_load_timeout(30)
            driver.get(f"https://www.youtube.com/watch?v={video_id}")
            time.sleep(5)

            # Mute video, let it play (YouTube needs video element active)
            driver.execute_script(
                'var v=document.querySelector("video");'
                'if(v){v.muted=true;v.play().catch(function(){});}'
            )

            # Verify logged in
            logged = driver.execute_script(
                'return !document.querySelector("a[aria-label*=\\"Sign in\\"]")'
            )
            if not logged:
                self.log(f"[Pancingan] [{acc_name}] Chrome: BELUM LOGIN — skip")
                driver.quit()
                return None

            self.log(f"[Pancingan] [{acc_name}] Chrome nongkrong AKTIF ✓")
            return driver
        except Exception as e:
            self.log(f"[Pancingan] [{acc_name}] Chrome error: {str(e)[:60]}")
            return None

    def _run_loop(self):
        data = load_accounts()
        accounts = data.get("accounts", [])
        ok_count = 0
        failed_count = 0
        self._drivers = []

        if not self.video_id:
            self.log(f"[Pancingan] Video ID tidak ditemukan dari: {self.live_url}")
            return

        self.log("[Pancingan] Mode CHROME STAY — akun nongkrong di live via Chrome headless")
        self.log(f"[Pancingan] Target: https://youtu.be/{self.video_id}")

        # Cap configurable via env YT_BOT_MAX_VIEWERS. Default 3 supaya
        # tidak tiba-tiba makan 3.5 GB RAM kalau lo lupa. Set ke 5+
        # hanya kalau host punya RAM cadangan.
        try:
            max_viewers = int(os.environ.get("YT_BOT_MAX_VIEWERS", "3") or "3")
        except (TypeError, ValueError):
            max_viewers = 3
        max_viewers = max(1, min(max_viewers, 10))
        self.log(f"[Pancingan] Max {max_viewers} akun (RAM ~700 MB/akun)")

        MAX_CHROME = max_viewers
        for acc in accounts:
            if not self.running:
                break
            if ok_count >= MAX_CHROME:
                self.log(f"[Pancingan] [{acc['name']}] Skip — max {MAX_CHROME} akun tercapai")
                continue

            acc_id = acc["id"]
            profile_path = os.path.join(CHROME_PROFILES_DIR, f"acc_{acc_id}")

            # Quick cookie check dulu sebelum launch Chrome (hemat waktu)
            cookies = extract_cookies_from_profile(profile_path)
            if not cookies or not check_login_status(cookies):
                failed_count += 1
                acc["status"] = "Belum login / expired"
                self.log(f"[Pancingan] [{acc['name']}] Skip — belum login")
                continue

            self.log(f"[Pancingan] [{acc['name']}] Launching Chrome headless...")
            driver = self._launch_chrome_stay(profile_path, self.video_id, acc["name"])
            if driver:
                self._drivers.append(driver)
                ok_count += 1
                acc["status"] = "Nongkrong (Chrome)"
            else:
                failed_count += 1
                acc["status"] = "Chrome gagal"
            time.sleep(3)

        ram_est = ok_count * 700
        self.log(f"[Pancingan] {ok_count} akun nongkrong, {failed_count} gagal | RAM: ~{ram_est} MB")
        if self.status_cb:
            self.status_cb(ok_count, failed_count,
                           f"{ok_count} nongkrong (Chrome)")
        save_accounts(data)

        # --- Stay loop: keep Chrome alive, refresh tiap 15 menit ---
        refresh_interval = 900  # 15 menit
        last_refresh = time.time()

        while self.running:
            now = time.time()

            # Refresh page tiap 15 menit biar session gak mati
            if now - last_refresh >= refresh_interval:
                for i, driver in enumerate(self._drivers):
                    if not self.running:
                        break
                    try:
                        driver.refresh()
                        time.sleep(3)
                        driver.execute_script(
                            'var v=document.querySelector("video");'
                            'if(v){v.muted=true;v.play().catch(function(){});}'
                        )
                    except Exception:
                        self.log(f"[Pancingan] Chrome #{i+1} refresh error — mungkin crash")
                last_refresh = time.time()
                self.log(f"[Pancingan] Refresh OK — {len(self._drivers)} akun masih nongkrong")

            # Sleep 5 detik per loop (responsive stop)
            for _ in range(5):
                if not self.running:
                    break
                time.sleep(1)
