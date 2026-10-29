# -*- coding: utf-8 -*-
"""
Live Telemetry — Parser stderr FFmpeg untuk monitoring real-time.

Mengubah output progress FFmpeg ("frame= 1234 fps= 30 q=28.0 size= ...")
menjadi dict metrics yang bisa ditampilkan di GUI dan disimpan ke log.
"""
import os
import re
import time

# Regex parser untuk baris progress FFmpeg
_RE_FRAME = re.compile(r"frame=\s*(\d+)")
_RE_FPS = re.compile(r"fps=\s*([\d.]+)")
_RE_SPEED = re.compile(r"speed=\s*([\d.]+)")
_RE_SIZE = re.compile(r"size=\s*(\S+)")
_RE_BITRATE = re.compile(r"bitrate=\s*([\d.]+)\s*k?b")
_RE_DROP = re.compile(r"drop=\s*(\d+)")
_RE_DUP = re.compile(r"dup=\s*(\d+)")
_RE_Q = re.compile(r"q=\s*([\d.]+)")


def parse_progress_line(line):
    """Parse satu baris stderr FFmpeg. Return dict metrics (boleh kosong)."""
    if not line:
        return {}

    m = {}
    if (mm := _RE_FRAME.search(line)):
        m["frame"] = int(mm.group(1))
    if (mm := _RE_FPS.search(line)):
        m["fps"] = float(mm.group(1))
    if (mm := _RE_SPEED.search(line)):
        m["speed"] = float(mm.group(1))
    if (mm := _RE_SIZE.search(line)):
        m["size"] = mm.group(1)
    if (mm := _RE_BITRATE.search(line)):
        m["bitrate_kbps"] = float(mm.group(1))
    if (mm := _RE_DROP.search(line)):
        m["dropped"] = int(mm.group(1))
    if (mm := _RE_DUP.search(line)):
        m["dup"] = int(mm.group(1))
    if (mm := _RE_Q.search(line)):
        m["q"] = float(mm.group(1))
    return m


class Telemetry:
    """Akumulator metrics + deteksi anomali (drop/fps/bitrate/speed)."""

    def __init__(self, target_fps=30.0, min_bitrate_kbps=4000.0, log_path=None):
        self.target_fps = target_fps
        self.min_bitrate_kbps = min_bitrate_kbps
        self.log_path = log_path
        self.latest = {}
        self.dropped_total = 0
        self.dup_total = 0
        self.anomalies = []
        self._last_log = 0.0

    def update(self, line):
        """Feed satu baris stderr. Return metrics dict kalau ada yang berubah."""
        m = parse_progress_line(line)
        if not m:
            return {}

        if "dropped" in m:
            self.dropped_total = max(self.dropped_total, m["dropped"])
            m["dropped_total"] = self.dropped_total
        if "dup" in m:
            self.dup_total = max(self.dup_total, m["dup"])
            m["dup_total"] = self.dup_total

        self.latest.update(m)
        self._check_anomalies(m)
        return self.latest

    def _check_anomalies(self, m):
        def flag(msg):
            if msg not in self.anomalies:
                self.anomalies.append(msg)
            self._write_log(f"[WARN] {msg}")

        if "fps" in m and m["fps"] < self.target_fps * 0.8:
            flag(f"FPS turun: {m['fps']:.1f} (target {self.target_fps:.0f}) — stream Possibly buffering")

        if "speed" in m and m["speed"] < 1.0:
            flag(f"Encode speed {m['speed']:.2f}x (< 1.0x) — YouTube backpressure, stream akan drop")

        if "bitrate_kbps" in m and m["bitrate_kbps"] < self.min_bitrate_kbps:
            flag(f"Bitrate rendah: {m['bitrate_kbps']:.0f} kbps (min {self.min_bitrate_kbps:.0f})")

        if self.dropped_total > 0:
            flag(f"Dropped frames: {self.dropped_total} — keyframe/GOP problem probable")

    def summary(self):
        """Ringkasan satu baris untuk display GUI."""
        l = self.latest
        bits = []
        if "fps" in l:
            bits.append(f"FPS {l['fps']:.1f}")
        if "bitrate_kbps" in l:
            bits.append(f"{l['bitrate_kbps']:.0f} kbps")
        if "speed" in l:
            bits.append(f"speed {l['speed']:.2f}x")
        if self.dropped_total:
            bits.append(f"drop {self.dropped_total}")
        if "size" in l:
            bits.append(f"size {l['size']}")
        return " | ".join(bits) if bits else "menunggu data..."

    def _write_log(self, msg):
        if not self.log_path:
            return
        try:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        except Exception:
            pass
