"""
Live Broadcast Manager - Idempotent broadcast lifecycle for YouTube Live Streaming.

Why this exists:
  Bot lo sebelumnya push RTMP (bagus) tapi TIDAK PERNAH create broadcast.
  Stream tanpa broadcast -> YouTube tetep outflow RTMP, tapi viewer count
  cuma di internal stats, video nggak punya URL publik, nggak di-index
  search, nggak masuk recommendation. Itu sebab 8 jam bisa cuma 6 viewer.

  File ini handle:
    1. Create broadcast dari credentials/token.json (OAuth, sudah ada)
    2. Bind stream ke broadcast (`/liveBroadcasts/bind` di YouTube API)
    3. Patch description + hashtags (yang sebelumnya unused di config)
    4. Periodic monitor: kalau broadcast stuck di 'ready', transition ke
       'live' begitu stream RTMP awal connect detected.
    5. Saat sumber rotasi, broadcast tetap aktif (YouTube nggak end stream).

API endpoint path: youtube/v3/liveBroadcasts dan liveStreams.
OAuth scope yang dibutuhin: youtube.force-ssl.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TOKEN_PATH = BASE_DIR / "credentials" / "token.json"
CONFIG_PATH = BASE_DIR / "config.json"

API_BASE = "https://www.googleapis.com/youtube/v3"


def load_credentials() -> str:
    """Baca access_token dari token.json. Refresh kalau udah expired."""
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(f"missing {TOKEN_PATH} - run oauth_init.py dulu")
    data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    token = data.get("token")
    expiry = data.get("expiry", "")

    # Paksa refresh kalau expiry <5 menit dari sekarang atau invalid.
    expired = True
    if expiry:
        try:
            exp = time.mktime(time.strptime(expiry.rstrip("Z"), "%Y-%m-%dT%H:%M:%S"))
            expired = (exp - time.time()) < 300
        except Exception:
            expired = True

    if expired and data.get("refresh_token") and data.get("client_id") and data.get("client_secret"):
        body = urllib.parse.urlencode({
            "client_id": data["client_id"],
            "client_secret": data["client_secret"],
            "refresh_token": data["refresh_token"],
            "grant_type": "refresh_token",
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            fresh = json.loads(r.read().decode("utf-8"))
        token = fresh["access_token"]
        data["token"] = token
        if "expires_in" in fresh:
            data["expiry"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + int(fresh["expires_in"]))
            )
        TOKEN_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return token


def api_get(path: str, token: str, params: dict) -> dict:
    url = f"{API_BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def api_post(path: str, token: str, params: dict, body: dict | None = None,
             method: str = "POST") -> dict:
    url = f"{API_BASE}/{path}?{urllib.parse.urlencode(params)}"
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def get_active_broadcast(token: str) -> dict | None:
    """Return broadcast yang sedang LIVE atau READY.

    Catatan: broadcastStatus=active HANYA mengembalikan broadcast yang
    liveStream-nya punya 'activeBroadcast' reference. Broadcast yang
    dibuat manual via Studio (RTMP paste langsung) sering punya status
    'ready' atau null lifecycleStatus meskipun sudah live. Jadi kita
    cek 3 status: active, ready, AND semua broadcast tanpa filter lalu
    filter manual berdasarkan concurrentViewers/actualStartTime.
    """
    # broadcastStatus hanya menerima: active|all|completed|id
    # 'ready'/'testing' TIDAK valid -> 400. Ambil 'all' lalu filter sendiri.
    try:
        data = api_get("liveBroadcasts", token, {
            "part": "id,snippet,status,contentDetails",
            "broadcastStatus": "all",
            "maxResults": 25,
            "order": "date",
        })
    except Exception:
        return None

    # API field = lifeCycleStatus (kapital C di 'Cycle')
    for it in data.get("items", []):
        st = it.get("status", {})
        if st.get("lifeCycleStatus") in ("live", "ready", "testing") \
                and st.get("privacyStatus") == "public":
            return it
    return None


def find_live_video_id(token: str) -> str | None:
    """Cari videoId dari broadcast yang sedang live (has activeStream)."""
    try:
        data = api_get("liveBroadcasts", token, {
            "part": "id,snippet,status,contentDetails",
            "broadcastStatus": "all",
            "maxResults": 10,
            "order": "date",
        })
        for it in data.get("items", []):
            cd = it.get("contentDetails", {})
            if cd.get("activeLiveChatId") or it.get("id"):
                # Actual start time ada = sudah live
                print(f"[BCAST] candidate: {it['id']} - {it['snippet']['title']}")
    except Exception as e:
        print(f"[BCAST] error: {e}")
    return None


def _tok(token):
    """Pakai token yang diberi, atau load sendiri kalau None."""
    return token if token else load_credentials()


CACHE_PATH = os.path.join(os.path.dirname(str(CONFIG_PATH)), ".stream_cache.json")


def _load_stream_cache() -> dict:
    """Cache {broadcast_id: {scheduledStartTime, streamId}} -广播 immutable field."""
    try:
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_stream_cache(bid: str, info: dict) -> None:
    c = _load_stream_cache()
    c[bid] = info
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(c, f, indent=2)
    except Exception:
        pass


def get_stream_key_for_broadcast(token: str, broadcast: dict) -> str:
    """Ambil stream key (ingestionStreamName) milik broadcast tertentu.

    Broadcast punya resourceId = liveStream id. Dari situ kita baca
    cdn.ingestionStreamName, yaitu key yang WAJIB dipakai untuk push RTMP.
    Ini kunci supaya FFmpeg connect ke broadcast yang bot baru create,
    bukan ke stream key lama yang lo paste manual.
    """
    token = _tok(token)
    res_id = broadcast.get("resourceId")
    if not res_id:
        # Fallback: ambil dari list berdasarkan id broadcast
        try:
            data = api_get("liveStreams", token, {
                "part": "id,cdn",
                "mine": "true",
                "maxResults": 10,
            })
            for it in data.get("items", []):
                cdn = it.get("cdn", {})
                # Cocokkan lewat title stream atau ambil yang paling baru
                if cdn.get("ingestionStreamName"):
                    return cdn["ingestionStreamName"]
        except Exception:
            return ""
        return ""

    try:
        data = api_get("liveStreams", token, {
            "part": "cdn",
            "id": res_id,
        })
        items = data.get("items", [])
        if items:
            return items[0].get("cdn", {}).get("ingestionStreamName", "")
    except Exception as e:
        print(f"[KEY] Gagal ambil stream key: {e}")
    return ""


def get_ingest_url(token: str, broadcast: dict) -> str:
    """Ambil ingestion URL lengkap (rtmp://host/app/key) dari broadcast."""
    token = _tok(token)
    res_id = broadcast.get("resourceId")
    if not res_id:
        return ""
    try:
        data = api_get("liveStreams", token, {"part": "cdn", "id": res_id})
        items = data.get("items", [])
        if items:
            cdn = items[0].get("cdn", {})
            addr = cdn.get("ingestionAddress", "")
            name = cdn.get("ingestionStreamName", "")
            if addr and name:
                return f"{addr}/{name}"
    except Exception as e:
        print(f"[KEY] Gagal ambil ingest URL: {e}")
    return ""


def get_resumable_stream(token: str) -> dict | None:
    """Stream key + RTMP URL disimpan di liveStream resource. Return kalau ada."""
    try:
        data = api_get("liveStreams", token, {
            "part": "id,cdn,snippet,status",
            "mine": "true",
            "maxResults": 50,
            "order": "date",
        })
    except Exception:
        return None
    items = data.get("items", [])
    # Prioritaskan "Default stream key" milik user, kalau ada.
    for it in items:
        t = it.get("snippet", {}).get("title", "")
        if t.lower().startswith("default"):
            return it
    return items[0] if items else None


def upsert_stream(token: str, stream_key: str) -> str:
    """Buat / ambil liveStream object sesuai stream_key config.

    YouTube per stream cuma boleh 1 liveStream aktif. Kita cek existing
    dulu; kalau stream key sama, reuse. Kalau beda, create baru dan biar
    yang lama kadaluarsa natural.
    """
    # REUSE SELALU kalau ada stream milik channel ini.
    # YouTube tidak pernah mengembalikan cdn.ingestionStreamName lewat API
    # (selalu null), jadi membandingkan key tidak akan pernah cocok --
    # sebelumnya itu menyebabkan create stream baru setiap run dan numpuk
    # di Studio > Stream keys.
    existing = get_resumable_stream(token)
    if existing and existing.get("id"):
        print(f"[STREAM] Reuse stream: {existing['id']}")
        return existing["id"]

    body = {
        "snippet": {
            "title": "Cozy Mood Lounge Ingest",
            "description": "Permanent ingest for cozy rain + piano live streams.",
        },
        "cdn": {
            "frameRate": "30fps",
            "ingestionType": "rtmp",
            "resolution": "1080p",
            "format": "1080p",
        },
        "contentDetails": {
            "isReusable": True,   # 1 stream dipakai semua broadcast = ga ada dobel
        },
    }
    res = api_post("liveStreams", token, {"part": "snippet,cdn,contentDetails"}, body)
    stream_id = res["id"]
    # Bikin ingestionAddress + StreamName jadi config snapshot
    cdn_info = res.get("cdn", {})
    return stream_id


def create_broadcast(token: str, title: str, description: str) -> dict:
    """Create broadcast dengan slug deskripsi + hashtag."""
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    formula = cfg.get("livestream", {}).get("active_formula", "3")
    formula_name = cfg.get("formulas", {}).get(formula, formula)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            # WAJIB ada (API 400 kalau kosong). Pakai waktu LAMPAU supaya
            # YouTube anggap sudah mulai = langsung LIVE, bukan "Mendatang".
            "scheduledStartTime": time.strftime(
                "%Y-%m-%dT%H:%M:%S.000Z",
                time.gmtime(time.time() - 120),
            ),
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "latencyPreference": "normal",     # /ultra-low juga oke
        },
        "contentDetails": {
            "enableAutoStart": True,
            "enableAutoStop": False,
            "monitorStream": {"enableMonitorStream": True, "broadcastStreamDelayMs": 0},
        },
    }
    res = api_post("liveBroadcasts", token,
                   {"part": "snippet,status,contentDetails"}, body)
    # Simpan scheduledStartTime - field ini immutable di sisi YouTube dan
    # TIDAK dikembalikan di response GET, jadi tanpa cache, update title
    # bakal 403 "Modification of scheduledStartTime is not allowed".
    try:
        _save_stream_cache(res["id"], {
            "scheduledStartTime": body["snippet"]["scheduledStartTime"],
        })
    except Exception:
        pass
    return res


def update_metadata(token: str, broadcast_id: str, title: str | None = None,
                    description: str | None = None) -> dict:
    """PATCH ke snippet broadcast. Digunakan tiap rotasi title."""
    current = api_get("liveBroadcasts", token, {
        "part": "snippet,status", "id": broadcast_id,
    })
    items = current.get("items", [])
    if not items:
        raise RuntimeError(f"broadcast {broadcast_id} not found")
    snippet = items[0]["snippet"]
    if title is not None:
        snippet["title"] = title
    if description is not None:
        snippet["description"] = description
    # PUT butuh scheduledStartTime, TAPI broadcast yang sudah ada punya nilai
    # immutable -> "Modification of scheduledStartTime is not allowed".
    # SOLUSI: ambil dari liveBroadcast tersimpan di .stream_cache.json (kita
    # yang saat create), atau kalau ga ada, broadcast ini tidak bisa di-update
    # -> lempar error supaya caller create broadcast baru.
    sst = snippet.get("scheduledStartTime")
    if not sst:
        cached = _load_stream_cache().get(broadcast_id)
        sst = cached.get("scheduledStartTime") if cached else None
    if not sst:
        raise RuntimeError(
            f"broadcast {broadcast_id} tidak bisa di-update "
            f"(scheduledStartTime immutable & tidak tersimpan) - buat broadcast baru")
    snippet["scheduledStartTime"] = sst
    return api_post("liveBroadcasts", token, {"part": "snippet"},
                    {"id": broadcast_id, "snippet": snippet}, method="PUT")


def bind_broadcast(token: str, broadcast_id: str, stream_id: str) -> None:
    """Bind liveStream ke liveBroadcast (1-time per stream)."""
    api_post("liveBroadcasts/bind", token,
             {"part": "id,contentDetails", "id": broadcast_id,
              "streamId": stream_id})


def transition(token: str, broadcast_id: str, status: str) -> dict:
    """Pindah life cycle broadcast.

    YouTube cuma menerima transisi di jalur ini:
        created -> testing -> live -> complete
    Melompat dari 'created' langsung ke 'live' = 403 invalidTransition,
    karena stream belum bound. Jadi kita jalanin step-by-step.
    """
    order = ["created", "testing", "live", "complete"]
    try:
        cur = api_get("liveBroadcasts", token,
                      {"part": "status", "id": broadcast_id}).get("items", [{}])[0]
        cur = cur.get("status", {}).get("lifeCycleStatus", "") or \
              cur.get("status", {}).get("lifecycleStatus", "")
    except Exception:
        cur = ""

    steps = []
    if cur in order and status in order and order.index(status) > order.index(cur):
        steps = order[order.index(cur) + 1: order.index(status) + 1]
    else:
        steps = [status]

    last_err = ""
    for step in steps:
        try:
            api_post("liveBroadcasts/transition", token,
                     {"part": "status", "id": broadcast_id, "broadcastStatus": step},
                     {"id": broadcast_id, "broadcastStatus": step})
        except Exception as e:
            last_err = str(e)
            break
    return {"id": broadcast_id, "requested": status, "from": cur,
            "steps": steps, "error": last_err}


def set_thumbnail(token: str, broadcast_id: str, image_path: str) -> bool:
    """Upload thumbnail ke YouTube via Data API v3 thumbnails.set().

    YouTube Data API v3 DOES support thumbnails.set() untuk liveBroadcasts.
    Endpoint: POST https://www.googleapis.com/upload/youtube/v3/thumbnails/set
    """
    if not image_path or not os.path.exists(image_path):
        return False
    try:
        token = _tok(token)
        size = os.path.getsize(image_path)
        if size < 5000:
            print(f"[THUMB] File terlalu kecil ({size}B), skip")
            return False

        # Determine content type
        ext = os.path.splitext(image_path)[1].lower()
        ct_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
        ct = ct_map.get(ext, "image/jpeg")

        with open(image_path, "rb") as f:
            img_data = f.read()

        url = (
            f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
            f"?videoId={broadcast_id}&uploadType=media"
        )
        req = urllib.request.Request(
            url, data=img_data, method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": ct,
                "Content-Length": str(len(img_data)),
            },
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            json.loads(r.read().decode("utf-8"))

        print(f"[THUMB] Uploaded {size // 1024}KB -> broadcast {broadcast_id}")

        # Save reference ke config
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        lc = cfg.setdefault("livestream", {})
        lc["last_thumbnail"] = image_path
        lc["last_thumbnail_broadcast"] = broadcast_id
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception as e:
        print(f"[THUMB] Upload gagal ({e}), simpan path saja")
        # Fallback: simpan path aja biar user bisa manual upload
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            lc = cfg.setdefault("livestream", {})
            lc["last_thumbnail"] = image_path
            lc["last_thumbnail_broadcast"] = broadcast_id
            CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        return False


def start_broadcast_now(stream_key: str, title: str = None, description: str = None) -> dict:
    """One-shot: get/create broadcast, bind stream, kasih balik ID publik.

    Kalau title/description None -> auto-generate SEO via live_seo.gen_live_metadata()
    """
    token = load_credentials()
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    lc = cfg.get("livestream", {})

    # Auto-generate SEO metadata kalau tidak disupply manual
    auto_seo = lc.get("auto_seo", True)
    thumb_path = None
    if title is None or description is None or auto_seo:
        try:
            from live_seo import gen_live_metadata, gen_live_thumbnail
            formula_key = lc.get("active_formula", "3")
            formula_name = cfg.get("formulas", {}).get(formula_key, "Relaxing Music")
            dur = int(lc.get("auto_stop_hours", 5) or 5)
            seo = gen_live_metadata(formula_name, dur, formula_key=formula_key)

            if title is None or auto_seo:
                title = seo["title"]
            if description is None or auto_seo:
                description = seo["description"]

            # Thumbnail: generate kalau enabled
            if lc.get("auto_thumbnail", True):
                thumb_path = gen_live_thumbnail(
                    seo["image_prompt"],
                    title=title,
                    formula_key=formula_key
                )
                if thumb_path:
                    print(f"[SEO] Thumbnail generated: {thumb_path}")
        except Exception as e:
            print(f"[SEO] Auto-generate gagal, pakai nilai lama: {e}")

    title = title or "Cozy Mood Lounge Live"
    description = description or "Live relaxing ambience. Subscribe for daily sessions."

    hashtags = lc.get("hashtag_pool", [])
    if hashtags:
        # Sisipin 8 hashtag acak di akhir description
        import random
        chosen = random.sample(hashtags, min(8, len(hashtags)))
        description = description.rstrip() + "\n\n" + " ".join(chosen)

    # PENTING: hanya CREATE broadcast baru kalau tidak ada yang reusable.
    # Kalau ada, JANGAN create - ini yang bikin 4-5 broadcast numpuk tadi.
    existing = get_active_broadcast(token)
    if existing:
        # Update metadata. Kalau broadcast lama immutable (403), jangan
        # paksa - buat broadcast baru yang punya schedule sendiri.
        try:
            update_metadata(token, existing["id"], title=title,
                            description=description)
        except Exception as e:
            print(f"[BCAST] Update metadata gagal, buat broadcast baru: {e}")
            existing = None

    if existing:
        if thumb_path:
            try:
                set_thumbnail(token, existing["id"], thumb_path)
            except Exception as e:
                print(f"[THUMB] Gagal: {e}")
        # WAJIB bind stream kalau belum, else created->testing = 403
        try:
            detail = api_get("liveBroadcasts", token, {
                "part": "contentDetails", "id": existing["id"]
            })
            bound = detail.get("items", [{}])[0].get("contentDetails", {}) \
                .get("boundStreamId", "")
            if not bound:
                try:
                    sid = upsert_stream(token, stream_key)
                    bind_broadcast(token, existing["id"], sid)
                    existing["resourceId"] = sid
                    print(f"[BCAST] Stream bound: {sid}")
                except Exception as e:
                    print(f"[BCAST] Bind gagal: {e}")
            else:
                existing["resourceId"] = bound
                print(f"[BCAST] Stream already bound: {bound}")
        except Exception as e:
            print(f"[BCAST] Gagal bind: {e}")
        try:
            tr_res = transition(token, existing["id"], "live")
            if tr_res.get("error"):
                print(f"[BCAST] Transition live: {tr_res}")
            else:
                print(f"[BCAST] Transition live OK: {tr_res}")
        except Exception as e:
            print(f"[BCAST] Transition live gagal (tidak fatal): {e}")
        # Ambil resourceId kalau ada, supaya caller bisa dapet stream key
        if "resourceId" not in existing:
            try:
                detail = api_get("liveBroadcasts", token, {
                    "part": "contentDetails", "id": existing["id"]
                })
                if detail.get("items", []):
                    existing["resourceId"] = detail["items"][0] \
                        .get("contentDetails", {}).get("boundStreamId", "")
            except Exception:
                pass
        return existing

    # Bener-bener nggak ada → create baru + bind + transition
    bc = create_broadcast(token, title, description)
    stream_id = upsert_stream(token, stream_key)
    bind_broadcast(token, bc["id"], stream_id)
    if thumb_path:
        set_thumbnail(token, bc["id"], thumb_path)
    transition(token, bc["id"], "live")
    # Tambahin resourceId = stream_id ke return supaya GUI bisa dapet key
    bc["resourceId"] = stream_id
    return bc