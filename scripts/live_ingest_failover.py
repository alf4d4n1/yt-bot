# -*- coding: utf-8 -*-
"""
Ingest Failover — Rotation a.rtmp.youtube.com <-> b.rtmp.youtube.com
dengan exponential backoff. Dipakai oleh live_streamer.py dan live_studio_gui.py.
"""
import os
import sys
import time
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def build_endpoints(cfg):
    """Build full hostnames dari config (['a','b'] -> ['a.rtmp.youtube.com','b.rtmp.youtube.com'])."""
    hosts = cfg.get("livestream", {}).get("ingest_endpoints", ["a", "b"])
    return [h if "." in h else f"{h}.rtmp.youtube.com" for h in hosts]


def next_endpoint(cfg, current_host):
    hosts = build_endpoints(cfg)
    if current_host not in hosts:
        return hosts[0] if hosts else "a.rtmp.youtube.com"
    idx = (hosts.index(current_host) + 1) % len(hosts)
    return hosts[idx]


def exponential_delay(attempt, base=5, cap=60):
    return min(cap, base * (2 ** max(0, attempt - 1)))


def stream_with_failover(
    cfg,
    source_video,
    stream_key,
    target_duration_seconds=None,
    log_callback=print,
    should_continue=lambda: True,
):
    """Push RTMP ke YouTube dengan failover + reconnect.

    Yields event dicts: {type: 'reconnecting'|'switch'|'stopped'|'fatal'|'progress', ...}
    Caller iterates dan tetap manages FFmpeg subprocess lifecycle.
    """
    hosts = build_endpoints(cfg)
    if not hosts:
        yield {"type": "fatal", "error": "Tidak ada ingest endpoint di config"}
        return

    initial_delay = cfg.get("livestream", {}).get("reconnect_initial_delay_seconds", 5)
    max_attempts = cfg.get("livestream", {}).get("max_reconnect_attempts", 5)

    current = hosts[0]
    attempt = 0
    proc = None

    while should_continue():
        attempt += 1
        rtmp_url = f"rtmp://{current}/live2/{stream_key}"

        cmd = [
            "ffmpeg", "-re",
            "-stream_loop", "-1",
            "-i", source_video,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-f", "flv",
            "-flvflags", "no_duration_filesize",
            rtmp_url,
        ]

        log_callback(f"[FFmpeg] Push ke {current} (attempt {attempt}/{max_attempts})...")
        try:
            proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, bufsize=1)
        except Exception as e:
            log_callback(f"[FFmpeg] Gagal spawn: {e}")
            yield {"type": "fatal", "error": str(e)}
            return

        rc = proc.wait()
        if not should_continue():
            yield {"type": "stopped"}
            return

        if rc == 0:
            log_callback("[FFmpeg] Exit clean — stopping live")
            yield {"type": "stopped"}
            return

        if attempt >= max_attempts:
            yield {"type": "fatal", "error": f"Reached max attempts ({max_attempts})"}
            return

        next_host = next_endpoint(cfg, current)
        delay = exponential_delay(attempt, base=initial_delay)
        log_callback(f"[FFmpeg] Disconnected dari {current} (rc={rc}). Switch ke {next_host} dalam {delay}s...")
        yield {"type": "switch", "from": current, "to": next_host, "delay": delay}

        time.sleep(delay)
        current = next_host