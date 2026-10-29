"""
Health Monitor & Auto-Restart — Monitor FFmpeg process, auto-restart kalau crash,
kirim notif ke Telegram kalau stream mati/restart.
"""
import os
import sys
import time
import threading
import subprocess
from datetime import datetime

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPTS_DIR)


def send_telegram_notif(bot_token, chat_id, message):
    """Kirim notif ke Telegram via Bot API."""
    if not bot_token or not chat_id:
        return False, "Bot token atau chat_id kosong"
    try:
        import urllib.request
        import urllib.parse

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }).encode("utf-8")

        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, "OK"
    except Exception as e:
        return False, str(e)


class HealthMonitor:
    """
    Monitor FFmpeg stream process. Kalau mati:
    1. Kirim notif Telegram
    2. Auto-restart (kalau enabled)
    3. Log semua event
    """

    def __init__(self, log_fn=None, restart_callback=None, config=None):
        self.log_fn = log_fn or print
        self.restart_callback = restart_callback  # Fungsi yang dipanggil buat restart stream
        self.config = config or {}
        self.running = False
        self.thread = None
        self.stream_process = None  # Reference ke subprocess.Popen FFmpeg
        self.check_interval = 10  # Cek tiap 10 detik
        self.max_restarts = 5  # Max restart sebelum give up
        self.restart_count = 0
        self.restart_cooldown = 30  # Tunggu 30 detik sebelum restart
        self.last_restart_time = 0
        self.stream_start_time = None

        # Telegram config
        live_cfg = self.config.get("livestream", {})
        self.tg_bot_token = live_cfg.get("telegram_bot_token", "")
        self.tg_chat_id = live_cfg.get("telegram_chat_id", "")
        self.auto_restart = live_cfg.get("auto_restart", True)

    def set_process(self, proc):
        """Set FFmpeg process yang di-monitor."""
        self.stream_process = proc
        self.stream_start_time = datetime.now()
        self.restart_count = 0

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        self.log_fn("[Health] Monitor aktif — cek tiap 10 detik")

    def stop(self):
        self.running = False
        self.stream_process = None

    def _notify(self, message):
        """Log ke GUI panel. Semua error/restart masuk ke log stream."""
        self.log_fn(message)

    def _check_process_alive(self):
        """Cek apakah FFmpeg process masih jalan."""
        if not self.stream_process:
            return False
        return self.stream_process.poll() is None

    def _monitor_loop(self):
        # Tunggu 15 detik awal biar stream stabil
        for _ in range(15):
            if not self.running:
                return
            time.sleep(1)

        while self.running:
            if self.stream_process and not self._check_process_alive():
                # Stream mati!
                rc = self.stream_process.returncode
                uptime = ""
                if self.stream_start_time:
                    delta = datetime.now() - self.stream_start_time
                    hours, remainder = divmod(int(delta.total_seconds()), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    uptime = f" (uptime: {hours}j {minutes}m {seconds}d)"

                self._notify(
                    f"[Health] ⚠️ Stream MATI! Exit code: {rc}{uptime}"
                )

                # Auto restart?
                if self.auto_restart and self.restart_count < self.max_restarts:
                    now = time.time()
                    if now - self.last_restart_time < self.restart_cooldown:
                        wait = int(self.restart_cooldown - (now - self.last_restart_time))
                        self.log_fn(f"[Health] Cooldown {wait}s sebelum restart...")
                        for _ in range(wait):
                            if not self.running:
                                return
                            time.sleep(1)

                    self.restart_count += 1
                    self._notify(
                        f"[Health] 🔄 Auto-restart #{self.restart_count}/{self.max_restarts}..."
                    )
                    self.last_restart_time = time.time()

                    if self.restart_callback:
                        try:
                            self.restart_callback()
                        except Exception as e:
                            self._notify(f"[Health] ❌ Restart gagal: {e}")
                    else:
                        self.log_fn("[Health] ❌ Restart callback tidak tersedia")

                elif self.restart_count >= self.max_restarts:
                    self._notify(
                        f"[Health] ❌ Max restart ({self.max_restarts}x) tercapai. "
                        f"Stream TIDAK di-restart lagi. Cek manual!"
                    )
                    self.running = False
                    return

            # Sleep interval (responsive stop)
            for _ in range(self.check_interval):
                if not self.running:
                    return
                time.sleep(1)
