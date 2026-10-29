"""
End-to-end probe: cek live bot siap apa belum, TANPA FFmpeg.

Dijalankan:
    python scripts/verify_live_ready.py

Output = fakta terverifikasi dari API YouTube asli, bukan asumsi.
"""
import os
import sys
import json
import time
import urllib.request
import urllib.parse
import urllib.error

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
os.chdir(BASE)

TOKEN_FILE = os.path.join(BASE, "credentials", "token.json")


def refresh_token():
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
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
    return json.loads(urllib.request.urlopen(req, timeout=30).read())["access_token"]


def api(tok, method, path, params=None, body=None):
    url = f"https://www.googleapis.com/youtube/v3/{path}?" + urllib.parse.urlencode(params or {})
    rq = urllib.request.Request(url, method=method, headers={
        "Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    try:
        raw = urllib.request.urlopen(
            rq, data=json.dumps(body).encode() if body else None, timeout=30).read()
        return 200, json.loads(raw or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def main():
    ok = True

    print("=== 1. TOKEN ===")
    try:
        tok = refresh_token()
        print(f"  refresh OK (len {len(tok)})")
    except Exception as e:
        print("  FAIL:", e)
        return 1

    print("\n=== 2. CHANNEL ===")
    c, ch = api(tok, "GET", "channels", {"part": "snippet", "mine": "true"})
    if c == 200 and ch.get("items"):
        it = ch["items"][0]
        print(f"  {it['id']} | {it['snippet']['title']}")
    else:
        print("  FAIL:", ch)
        ok = False

    print("\n=== 3. STREAM KEY ===")
    sys.path.insert(0, BASE)
    from set_stream_key import get_key
    k = get_key()
    print(f"  {k[:8]}...{k[-4:] if k else ''} ({'OK' if k else 'KOSONG'})")
    if not k:
        ok = False

    print("\n=== 4. SOURCE VIDEO ===")
    import glob
    vids = glob.glob(os.path.join(BASE, "output", "*.mp4"))
    print(f"  {len(vids)} mp4 di output/")
    for v in vids[:3]:
        print("   ", os.path.basename(v))
    if not vids:
        print("  (tidak ada - render dulu, atau bot fallback ke master_livestream_loop.mp4)")

    print("\n=== 5. BROADCAST PIPELINE ===")
    import live_broadcast_manager as m
    try:
        bc = m.start_broadcast_now(k)
        bid = bc.get("id")
        title = bc.get("snippet", {}).get("title", "")
        desc = bc.get("snippet", {}).get("description", "")
        print(f"  broadcast : {bid}")
        print(f"  title     : {title[:70]}")
        print(f"  desc      : {len(desc)} chars")

        c2, st = api(tok, "GET", "liveBroadcasts",
                     {"part": "status,contentDetails", "id": bid})
        lc = st["items"][0]["status"]["lifeCycleStatus"] if c2 == 200 else "?"
        bound = st["items"][0].get("contentDetails", {}).get("boundStreamId", "") if c2 == 200 else ""
        print(f"  lifecycle : {lc}")
        print(f"  boundStream: {bound or '(none)'}")

        if not title or title.startswith("Cozy Mood Lounge Live"):
            print("  FAIL: judul bukan AI-generated")
            ok = False
        if len(desc) < 100:
            print("  FAIL: deskripsi kosong")
            ok = False
    except Exception as e:
        print("  FAIL:", e)
        ok = False

    print("\n=== 6. TITLE ROTATION LOOKUP ===")
    import live_title_rotation as tr
    cfg = tr.load_config()
    rb, err = tr.get_broadcast_id(cfg)
    print(f"  sees broadcast: {rb} | err: {err}")
    if rb:
        o, res = tr.update_broadcast_title(cfg, rb, cfg.get("livestream", {}).get("titles", ["AI TEST"])[0])
        print(f"  rotation update: {'OK' if o else 'FAIL'}")
        if not o:
            ok = False
    else:
        ok = False

    print("\n=== 7. BROADCAST LIST ===")
    c3, bl = api(tok, "GET", "liveBroadcasts", {
        "part": "id,snippet,status", "broadcastStatus": "all",
        "maxResults": 25, "order": "date"})
    for it in bl.get("items", []):
        s = it.get("status", {})
        print(f"  {it['id']} | {s.get('lifeCycleStatus','?'):9} | "
              f"{s.get('privacyStatus','?'):8} | {it['snippet']['title'][:45]}")

    print("\n=== 8. LIVE STREAMS ===")
    c4, ls = api(tok, "GET", "liveStreams",
                 {"part": "id,snippet,status", "mine": "true", "maxResults": 20, "order": "date"})
    for it in ls.get("items", []):
        print(f"  {it['id']} | {it.get('snippet',{}).get('title','')[:40]}")

    print("\n" + ("=== READY ===" if ok else "=== NOT READY ==="))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
