# -*- coding: utf-8 -*-
"""
Live Accounts Manager — Profil Chrome terisolasi untuk 5 akun Google pancingan.
Tiap profil punya folder user-data sendiri di data/chrome_profiles/acc_X.
"""
import os
import sys
import json
import time
import subprocess
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNTS_CONFIG = os.path.join(BASE_DIR, "data", "live_accounts.json")
CHROME_PROFILES_DIR = os.path.join(BASE_DIR, "data", "chrome_profiles")
CHROME_BIN = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not os.path.exists(CHROME_BIN):
    CHROME_BIN = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

DEFAULT_CHATS = [
    "Loving these cozy vibes ✨☕",
    "Perfect beats for late night studying 📖🎧",
    "Sending good energy to everyone working hard today 🙌",
    "So relaxing, this helps my focus a lot 🌿",
    "Such a peaceful stream, definitely staying here 🌧️",
    "Great music for coding and late night coffee ☕💻",
    "The aesthetic and sound selection are top tier 🔥",
    "Just what I needed after a long stressful day 🌙",
    "Adding this stream to my daily routine, pure chill vibes 🛋️",
    "Greeting from Oregon! Hope you all have a productive day ✨"
]


def load_accounts():
    os.makedirs(os.path.dirname(ACCOUNTS_CONFIG), exist_ok=True)
    if os.path.exists(ACCOUNTS_CONFIG):
        try:
            with open(ACCOUNTS_CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    default_data = {
        "accounts": [
            {"id": 1, "name": "Akun 1", "email": "", "status": "Belum Login"},
            {"id": 2, "name": "Akun 2", "email": "", "status": "Belum Login"},
            {"id": 3, "name": "Akun 3", "email": "", "status": "Belum Login"},
            {"id": 4, "name": "Akun 4", "email": "", "status": "Belum Login"},
            {"id": 5, "name": "Akun 5", "email": "", "status": "Belum Login"},
        ],
        "custom_chats": DEFAULT_CHATS,
        "chat_interval_minutes_min": 10,
        "chat_interval_minutes_max": 25,
        "auto_stay": True
    }
    save_accounts(default_data)
    return default_data


def save_accounts(data):
    os.makedirs(os.path.dirname(ACCOUNTS_CONFIG), exist_ok=True)
    with open(ACCOUNTS_CONFIG, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def open_login_profile(account_id):
    """Buka Chrome interaktif agar user bisa login akun Google sekali saja."""
    profile_path = os.path.join(CHROME_PROFILES_DIR, f"acc_{account_id}")
    os.makedirs(profile_path, exist_ok=True)

    cmd = [
        CHROME_BIN,
        f"--user-data-dir={profile_path}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://accounts.google.com"
    ]
    return subprocess.Popen(cmd)
