# 🎵 YT-Content-Factory

**Bot produksi konten YouTube otomatis penuh** — dari SEO, audio looping, render video, hingga upload terjadwal. Zero budget, ringan di RAM, dan siap jalan 24/7.

---

## ✨ Fitur Utama

| Fitur | Keterangan |
|---|---|
| 🤖 **AI SEO** | Judul, deskripsi, tag, thumbnail prompt via Gemini (9router) |
| 🎨 **AI Image** | Generate background 1920×1080 via Pollinations Flux (gratis) |
| 🎵 **Smart Audio** | Shuffle + loop musik, mix ambience, 432Hz tuning, warm reverb |
| 🎬 **Video Render** | FFmpeg — Ken Burns multi-scene, 8 overlay efek cinemagraph |
| 📤 **Auto Upload** | YouTube Data API v3 — scheduled, private, unlisted, atau public |
| 🖼️ **Thumbnail** | Auto-generate High-CTR thumbnail via Pillow |
| 📱 **Auto Shorts** | Teaser 9:16 otomatis dari video utama |
| 🔁 **Daemon Mode** | Produksi & upload 3 video/hari tanpa intervensi manusia |
| 📺 **Live Stream** | GUI + headless streamer RTMP 24/7 ke YouTube Live |
| ⬇️ **Suno DL** | Download & dekripsi lagu Suno AI ke MP3 320kbps |

---

## 📁 Struktur Folder

```
YT-bot-main/
├── main.py                   ← Launcher menu interaktif
├── daemon.py                 ← Mode auto 24/7 (3 video/hari)
├── config.json               ← Semua pengaturan bot
│
├── scripts/
│   ├── ai_service.py         ← SEO + image via Gemini & Pollinations
│   ├── audio_composer.py     ← Shuffle, loop, 432Hz, mix ambience
│   ├── video_engine.py       ← Render FFmpeg (Ken Burns + overlay)
│   ├── youtube_uploader.py   ← Upload + thumbnail via YouTube API v3
│   ├── thumbnail_gen.py      ← Generate thumbnail 1280×720 (Pillow)
│   ├── shorts_gen.py         ← Teaser Shorts 1080×1920
│   ├── suno_downloader.py    ← Download + dekripsi lagu Suno AI
│   ├── live_studio_gui.py    ← GUI live stream (CustomTkinter)
│   ├── live_streamer.py      ← Headless live streamer CLI
│   ├── live_bot_runner.py    ← Audience bot 5 akun Chrome
│   └── live_accounts.py      ← Manajemen profil Chrome
│
├── assets/
│   ├── backgrounds/          ← 19 gambar HD estetik (per formula)
│   ├── music/
│   │   ├── 1_piano_rain/     ← 18 trek  (Piano + Hujan)
│   │   ├── 2_bossa_nova/     ← 22 trek  (Gitar Jazz + Kafe)
│   │   ├── 3_lofi_chill/     ← 16 trek  (Lofi Malam)
│   │   ├── 4_dark_academia/  ← 20 trek  (Klasik + Perpustakaan)
│   │   └── 5_acoustic_guitar/← 31 trek  (Gitar Alam)
│   ├── ambience/             ← Sound ambience per formula
│   └── overlays/             ← 7 video overlay efek (rain, dust, dst.)
│
├── credentials/
│   ├── client_secret.json    ← OAuth2 Google (dari Google Cloud Console)
│   └── token.json            ← Token refresh (auto-generate saat login)
│
├── data/
│   └── live_accounts.json    ← Data 5 akun live + custom chat
│
├── output/                   ← Hasil render video + metadata JSON
│   ├── daemon.log            ← Log aktivitas daemon
│   ├── daemon_state.json     ← Status terakhir daemon
│   ├── rekap_harian.json     ← Rekap produksi harian
│   └── master_livestream_loop.mp4 ← Video loop untuk live stream
│
├── _bench/                   ← File benchmark encode (internal)
├── _ab_test.py               ← A/B test kualitas encode
├── _run_production.py        ← Runner non-interaktif (CLI args)
├── _smoke_test.py            ← 10 automated smoke test
│
├── START_BOT.bat             ← Jalankan menu interaktif
├── START_DAEMON.bat          ← Jalankan mode daemon 24/7
└── START_LIVESTREAM.bat      ← Jalankan studio live stream
```

---

## 🎯 Formula Konten (6 Niche)

| # | Formula | Folder Musik |
|---|---|---|
| 1 | Acoustic Warm Piano & Soft Rain | `1_piano_rain/` |
| 2 | Sunny Morning Bossa Nova & Coffee Cafe | `2_bossa_nova/` |
| 3 | Lofi Chillhop & Cozy Midnight Room | `3_lofi_chill/` |
| 4 | Dark Academia & Victorian Library | `4_dark_academia/` |
| 5 | Peaceful Acoustic Guitar & Forest Stream | `5_acoustic_guitar/` |
| 6 | Pomodoro 25/5 Study Timer & Lofi Beats | `3_lofi_chill/` *(shared)* |

---

## 🚀 Quick Start

### Prasyarat
- Python 3.11+
- FFmpeg (sudah di PATH)
- 9router berjalan di `localhost:20128`
- Pillow, google-auth, google-api-python-client, customtkinter

```bash
pip install pillow google-auth google-auth-oauthlib google-api-python-client customtkinter requests
```

---

### 1. Setup YouTube API (Sekali Saja)

1. Buka [Google Cloud Console](https://console.cloud.google.com/)
2. Buat project → aktifkan **YouTube Data API v3**
3. Buat credentials → **OAuth 2.0 Client ID** → Desktop App
4. Download JSON → rename jadi `client_secret.json` → taruh di `credentials/`
5. Jalankan `START_BOT.bat` → pilih menu **[4] Setup Otorisasi YouTube**
6. Login browser → token tersimpan otomatis di `credentials/token.json`

---

### 2. Tambah Lagu (Suno AI → Bot)

```
START_BOT.bat → Menu [3] → Paste link Suno → Pilih kategori formula
```

Bot otomatis download, dekripsi, dan simpan ke folder musik yang tepat.

---

### 3. Produksi Video (Mode Manual)

```
START_BOT.bat → Menu [1]
```

Ikuti prompt:
1. Pilih **formula** konten (1–6)
2. Masukkan **durasi** menit (1–600)
3. Pilih **sumber visual** (bank stok / AI generate)
4. Pilih **efek overlay** (8 pilihan)
5. Bot proses otomatis → tanya upload langsung atau tidak

---

### 4. Mode Daemon 24/7 (Auto Produksi + Upload)

```
START_DAEMON.bat
```

- Produksi **3 video/hari** secara otomatis
- Upload **scheduled** jam 08:00, 14:00, 21:00 WIB
- Log tersimpan di `output/daemon.log`
- Berhenti sendiri saat kuota harian terpenuhi, lanjut besok jam 08:00

---

### 5. Live Stream

```
START_LIVESTREAM.bat
```

- GUI live studio dengan timer otomatis
- 5-akun audience bot
- Headless mode: `python scripts/live_streamer.py`

---

## ⚙️ Konfigurasi (`config.json`)

```json
{
  "bot_name": "YT-Content-Factory",
  "ai_settings": {
    "router_base_url": "http://localhost:20128/v1",
    "text_model": "ag/gemini-3.8-flash-high"
  },
  "video_settings": {
    "default_duration_minutes": 60,
    "fps": 30,
    "tuning_432hz": true,
    "warm_reverb": true,
    "generate_shorts": true
  },
  "branding": {
    "channel_name": "Cozy Mood Lounge",
    "watermark_text": "© Cozy Mood Lounge"
  },
  "daemon": {
    "videos_per_day": 3,
    "publish_hours_wib": [8, 14, 21],
    "delete_after_upload": true,
    "max_disk_gb": 25
  }
}
```

---

## 🎬 Overlay Efek Tersedia

| # | Efek | File |
|---|---|---|
| 1 | Rain on Window Glass | `overlay_rain_window_glass.mp4` |
| 2 | Golden Dust Particles | `overlay_golden_dust.mp4` |
| 3 | Morning Sunlight Beam | `overlay_sunlight_beam.mp4` |
| 4 | Cozy Fireplace Embers | `overlay_embers_sparks.mp4` |
| 5 | Soft Snow Falling | `overlay_snow_falling.mp4` |
| 6 | Heavy Rain Downpour | `overlay_rain_downpour.mp4` |
| 7 | Coffee Steam Vapor | `overlay_steam.mp4` |
| 8 | Tanpa Efek (Still Image) | — |

---

## 📊 Performa & Batas

| Metrik | Nilai |
|---|---|
| RAM Usage | ~120–180 MB |
| CPU saat render | Sedang (FFmpeg veryfast) |
| Kuota YouTube API gratis | ~6 video/hari |
| Max video per hari (daemon) | 3 (bisa diubah di config) |
| Disk usage per video ~60 menit | ~800 MB |

---

## 🛠️ Developer Tools

```bash
# Smoke test (10 automated checks)
python _smoke_test.py

# A/B encode quality benchmark
python _ab_test.py

# Non-interactive production (CLI)
python _run_production.py [menit] [formula] [fx]
# Contoh:
python _run_production.py 60 4 rain_glass
```

---

## ⚠️ Catatan Penting

- File `credentials/client_secret.json` dan `token.json` **jangan di-share atau di-commit ke Git**
- Stream key di `config.json` → `livestream.stream_key` bersifat rahasia
- Daemon butuh minimal **2 GB RAM bebas** sebelum mulai produksi
- Tambah ambience di `assets/ambience/3_lofi_chill/`, `4_dark_academia/`, dan `5_acoustic_guitar/` untuk kualitas audio lebih baik

---

## 📚 Dokumen Panduan Tambahan

| File | Isi |
|---|---|
| `PANDUAN_PROMPT_DAN_ASET.txt` | Prompt AI image & Suno per formula |
| `PANDUAN_CARI_GAMBAR_PINTEREST.txt` | Tips cari gambar HD estetik dari Pinterest |
| `REKAP_IDE_DAN_KONSEP_UNIVERSAL.txt` | Playbook psikologi konten relax music |
| `STRATEGI_CHANNEL_DAN_MONETISASI.txt` | Roadmap 90 hari & multi-stream monetisasi |
| `TUTORIAL_MANUAL_CAPCUT_DAN_STRATEGI_BOT.txt` | Teknik cinemagraph CapCut vs bot pipeline |
