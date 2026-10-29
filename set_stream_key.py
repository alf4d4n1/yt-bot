"""
Pre-start stream key manager.

Usage:
    python set_stream_key.py                 # interactive prompt
    python set_stream_key.py --key ABC123    # set dari argumen
    python set_stream_key.py --show          # cek key sekarang (masked)
    python set_stream_key.py --clear         # kosongin key

Nulis ke DUA tempat biar semua runner konsisten:
  1. config.json  -> livestream.stream_key
  2. .env         -> STREAM_KEY=
"""

import os
import sys
import json
import argparse

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT, "config.json")
ENV_PATH = os.path.join(ROOT, ".env")


def read_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def write_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def write_env(key):
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

    replaced = False
    for i, line in enumerate(lines):
        if line.startswith("STREAM_KEY="):
            lines[i] = "STREAM_KEY=%s" % key
            replaced = True
            break

    if not replaced:
        lines.append("STREAM_KEY=%s" % key)

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def get_key():
    cfg = read_config()
    key = cfg.get("livestream", {}).get("stream_key", "").strip()
    if not key and os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("STREAM_KEY=") and not line.startswith("#"):
                    key = line.split("=", 1)[1].strip()
                    break
    return key


def set_key(key):
    cfg = read_config()
    cfg.setdefault("livestream", {})["stream_key"] = key
    write_config(cfg)
    write_env(key)


def mask(key):
    if not key:
        return "(kosong)"
    if len(key) <= 8:
        return key[0] + "..." + key[-1]
    return key[:4] + "..." + key[-4:]


def main():
    ap = argparse.ArgumentParser(description="Kelola YouTube stream key")
    ap.add_argument("--key", help="stream key (raw, tanpa prefix rtmp://)")
    ap.add_argument("--show", action="store_true", help="tampilkan key tersimpan")
    ap.add_argument("--clear", action="store_true", help="kosongkan stream key")
    args = ap.parse_args()

    if args.show:
        print("stream_key sekarang: %s" % mask(get_key()))
        return

    if args.clear:
        set_key("")
        print("[OK] stream key dikosongkan (config.json + .env)")
        return

    key = (args.key or "").strip().strip('"').strip("'")
    if not key:
        key = input("Masukkan YouTube stream key: ").strip().strip('"').strip("'")

    if not key:
        print("[x] Key kosong. Dibatalkan.")
        sys.exit(1)

    # Normalisasi: buang prefix RTMP kalau user paste full URL
    for prefix in ("rtmp://", "rtmps://"):
        if key.startswith(prefix):
            key = key.split("/", 3)[-1] if key.count("/") >= 3 else key[len(prefix):]

    # Ambil bagian terakhir setelah slash (live2/xxxx -> xxxx)
    if "/" in key:
        key = key.rsplit("/", 1)[-1]

    set_key(key)
    print("[OK] stream key disimpan: %s" % mask(key))
    print("     -> %s" % CONFIG_PATH)
    print("     -> %s" % ENV_PATH)


if __name__ == "__main__":
    main()