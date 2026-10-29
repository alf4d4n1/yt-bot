# -*- coding: utf-8 -*-
"""
Live Preflight — Cek koneksi sebelum push RTMP ke YouTube.

- Probe port 1935 di a.rtmp.youtube.com
- Query liveBroadcasts().list via YouTube Data API untuk dapat broadcast aktif
- Return dict status; kalau gagal, GUI harus refuse untuk start
"""
import os
import sys
import json
import subprocess

YT_RTMP_PORT = 1935
YT_RTMP_HOSTS = ["a.rtmp.youtube.com", "b.rtmp.youtube.com"]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


def probe_port_windows(host="a.rtmp.youtube.com", port=YT_RTMP_PORT, timeout=5):
    """Test-NetConnection wrapper. Returns True kalau reachable."""
    try:
        cmd = [
            "powershell.exe", "-NoProfile", "-Command",
            f"Test-NetConnection -ComputerName {host} -Port {port} -WarningAction SilentlyContinue | "
            "Select-Object -ExpandProperty TcpTestSucceeded"
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        return "True" in (out.stdout or "")
    except Exception:
        # Fallback ke raw TCP socket kalau PowerShell gagal
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            return True
        except Exception:
            return False
        finally:
            s.close()


def probe_endpoints(cfg=None, hosts=None):
    """Cek semua endpoint ingest. Return list[(host, reachable)]."""
    if cfg is None:
        cfg = {}
    hosts = hosts or cfg.get("livestream", {}).get("ingest_endpoints", YT_RTMP_HOSTS)
    result = []
    for h in hosts:
        full = h if "." in h else f"{h}.rtmp.youtube.com"
        result.append((full, probe_port_windows(full, YT_RTMP_PORT)))
    return result


def find_active_broadcast():
    """Query YouTube Data API untuk broadcast yang sedang 'live' atau 'ready'.

    Returns dict {video_id, url, lifecycle_status} atau None kalau tidak ada.
    None bukan error — bisa berarti broadcast memang belum dibuat di Studio.
    """
    try:
        import googleapiclient.discovery
        import google.oauth2.credentials

        token_path = os.path.join(BASE_DIR, "credentials", "token.json")
        if not os.path.exists(token_path):
            return None
        with open(token_path, "r", encoding="utf-8") as f:
            tdata = json.load(f)
        creds = google.oauth2.credentials.Credentials.from_authorized_user_info(tdata)
        yt = googleapiclient.discovery.build("youtube", "v3", credentials=creds)

        for st in ("active", "ready"):
            resp = yt.liveBroadcasts().list(
                part="snippet,status", broadcastStatus=st, maxResults=10
            ).execute()
            items = resp.get("items", [])
            if items:
                top = items[0]
                vid = top["id"]
                lifecycle = top.get("status", {}).get("lifeCycleStatus", "unknown")
                return {
                    "video_id": vid,
                    "url": f"https://youtu.be/{vid}",
                    "lifecycle_status": lifecycle,
                    "broadcastStatus": st,
                }
        return None
    except Exception as e:
        return {"error": str(e)}


def run_preflight(cfg=None):
    """Full preflight. Return dict {port_ok, endpoints, broadcast, ready}."""
    if cfg is None:
        cfg_path = os.path.join(BASE_DIR, "config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

    live_cfg = cfg.get("livestream", {})
    endpoints = probe_endpoints(live_cfg)

    broadcast = None
    if live_cfg.get("auto_get_active_broadcast", True):
        broadcast = find_active_broadcast()

    port_ok = any(reachable for _, reachable in endpoints)
    broadcast_ok = broadcast is not None and "error" not in broadcast

    return {
        "port_ok": port_ok,
        "endpoints": endpoints,
        "broadcast": broadcast,
        "broadcast_ok": broadcast_ok,
        "ready": port_ok and (broadcast_ok if live_cfg.get("auto_get_active_broadcast", True) else True),
    }
