import os
import sys
import json
import time

# Tambahkan direktori scripts ke sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "scripts"))

from ai_service import AIService
from audio_composer import AudioComposer
from video_engine import VideoEngine
from youtube_uploader import YouTubeUploader

def print_banner():
    banner = r"""
  __   _______      _____ ____  _   _ _____ _____ _   _ _____ 
  \ \ / /_   _|    / ____/ __ \| \ | |_   _| ____| \ | |_   _|
   \ V /  | |_____| |   | |  | |  \| | | | | |__ |  \| | | |  
    | |   | |_____| |   | |  | | . ` | | | |  __|| . ` | | |  
    | |   | |     | |___| |__| | |\  | | | | |___| |\  | | |  
    |_|   |_|      \_____\____/|_| \_| |_| |_____|_| \_| |_|  
              [ FACTORY & AUTO COMPOSER v1.0 ]
    """
    print(banner)
    print("=" * 66)
    print("  Engine: FFmpeg Stream-Loop | AI: Gemini 9router + Pollinations Flux")
    print("  Uploader: Official YouTube Data API v3 (Auto-Schedule)")
    print("=" * 66)

def load_config():
    cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_test_connection():
    print("\n--- [ PEMERIKSAAN SISTEM & KONEKSI ] ---")
    config = load_config()
    
    # 1. Cek FFmpeg
    try:
        import subprocess
        res = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0:
            print(" [✓] FFmpeg Engine        : TERPASANG & AKTIF")
        else:
            print(" [x] FFmpeg Engine        : ERROR")
    except Exception as e:
        print(f" [x] FFmpeg Engine        : GAGAL ({e})")

    # 2. Cek 9router
    ai = AIService()
    try:
        res = ai.query_llm("Ping test. Reply with: OK")
        print(f" [✓] 9router (Gemini)     : TERHUBUNG ({res[:20]})")
    except Exception as e:
        print(f" [x] 9router (Gemini)     : GAGAL TERHUBUNG ({e})")

    # 3. Cek Musik & Ambience
    composer = AudioComposer()
    music_files = composer.get_music_files("1", shuffle=False)
    ambience_file = composer.get_ambience_file("1")
    print(f" [✓] Koleksi Musik        : {len(music_files)} trek di Formula 1")
    if ambience_file:
        print(f" [✓] Audio Ambience       : Ditemukan ({os.path.basename(ambience_file)})")
    else:
        print(" [!] Audio Ambience       : Belum ada (opsional, musik tetap jalan)")

    # 4. Cek Kredensial YouTube
    uploader = YouTubeUploader()
    if os.path.exists(uploader.token_file):
        print(" [✓] Akun YouTube         : TERAUTORISASI (Siap Upload)")
    elif os.path.exists(uploader.client_secret_file):
        print(" [!] Akun YouTube         : Kredensial ada, perlu login sekali via menu [3]")
    else:
        print(" [?] Akun YouTube         : Belum ada client_secret.json (lihat panduan menu [3])")

    print("-" * 66)

def list_ready_videos():
    print("\n--- [ DAFTAR VIDEO DI FOLDER OUTPUT ] ---")
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    files = [f for f in os.listdir(output_dir) if f.endswith(".mp4")]
    
    if not files:
        print("Belum ada video di folder output. Silakan generate terlebih dahulu.")
        return []

    video_items = []
    for idx, vid in enumerate(files, 1):
        vid_path = os.path.join(output_dir, vid)
        meta_path = os.path.splitext(vid_path)[0] + ".json"
        size_mb = os.path.getsize(vid_path) / (1024 * 1024)
        
        title = "Tidak ada judul"
        status = "ready_for_upload"
        yt_url = ""
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    title = meta.get("title", title)
                    status = meta.get("status", status)
                    yt_url = meta.get("youtube_url", "")
            except (json.JSONDecodeError, OSError) as e:
                print(f"    [!] Metadata rusak di {meta_path}: {e}. Fallback ke default.")
                
        status_label = "✅ UPLOADED" if status == "uploaded" else "⏳ READY TO UPLOAD"
        print(f"[{idx}] {vid} ({size_mb:.2f} MB) - {status_label}")
        print(f"    Judul : {title}")
        if yt_url:
            print(f"    Link  : {yt_url}")
            
        video_items.append({
            "index": idx,
            "filename": vid,
            "vid_path": vid_path,
            "meta_path": meta_path,
            "title": title,
            "status": status
        })
    print("-" * 66)
    return video_items

def generate_video_flow():
    config = load_config()
    composer = AudioComposer()
    print("\n--- [ PILIH FORMULA KONTEN ] ---")
    formulas = config.get("formulas", {})
    for key, name in formulas.items():
        files_count = len(composer.get_music_files(formula_key=key, shuffle=False))
        if files_count > 0:
            status_tag = f"✅ ({files_count} lagu siap)"
        else:
            status_tag = "⚠️ (KOSONG - belum ada lagu)"
        print(f" [{key}] {name} {status_tag}")
        
    choice = input("\nPilih nomor formula (1-5, default: 1): ").strip() or "1"
    formula_name = formulas.get(choice, formulas.get("1"))
    
    # Cek ketersediaan lagu sebelum lanjut
    music_files = composer.get_music_files(formula_key=choice, shuffle=False)
    if not music_files:
        subfolder = composer.formula_folders.get(choice, "")
        print(f"\n[x] PERINGATAN: Folder 'assets/music/{subfolder}' masih KOSONG!")
        print("    Silakan pilih formula yang bertanda ✅ atau download lagu via Menu [3] terlebih dahulu.")
        return

    dur_input = input("Masukkan durasi video dalam MENIT (misal: 60, default: 60): ").strip()
    try:
        duration_minutes = int(dur_input)
        if duration_minutes < 1 or duration_minutes > 600:
            print(f" [!] Durasi {duration_minutes}m di luar jangkauan (1-600). Pakai default 60.")
            duration_minutes = 60
    except ValueError:
        print(" [!] Input tidak valid. Pakai default 60.")
        duration_minutes = 60
        
    duration_seconds = duration_minutes * 60
    print(f"\n[*] Memulai produksi konten:")
    print(f"    • Tema    : {formula_name}")
    print(f"    • Durasi  : {duration_minutes} Menit ({duration_seconds} detik)")
    print("-" * 66)

    ai = AIService()
    engine = VideoEngine()

    # Langkah 1: Generate SEO via 9router
    print("[1/4] Menghubungi Gemini (9router) untuk membuat SEO Metadata...")
    seo = ai.generate_seo_metadata(formula_name, duration_minutes)
    print(f" [✓] Judul: {seo.get('title')}")
    print(f" [✓] Prompt Gambar Terbuat")

    # Langkah 2: Pilihan Sumber Visual (Bank Stok vs AI Generate)
    print("\n--- [ PILIH SUMBER GAMBAR LATAR ] ---")
    print(" [1] Bank Stok Gambar Pilihan (Acak otomatis dari assets/backgrounds) [Rekomendasi]")
    print(" [2] Generate Gambar AI Baru via Pollinations Flux")
    bg_choice = input("Pilih sumber visual (1-2, default: 1): ").strip() or "1"

    timestamp = int(time.time())
    if bg_choice == "1":
        # Ambil gambar berkualitas dari bank stok
        import random
        bg_dir = os.path.join(engine.base_dir, "assets", "backgrounds")
        valid_exts = (".jpg", ".jpeg", ".png", ".jfif", ".webp")
        # Filter gambar berkualitas (abaikan file test_)
        candidates = [
            f for f in os.listdir(bg_dir) 
            if f.lower().endswith(valid_exts) and not f.startswith("test_")
        ]
        if not candidates:
            candidates = [f for f in os.listdir(bg_dir) if f.lower().endswith(valid_exts)]
        
        selected_bg_file = random.choice(candidates)
        img_path = os.path.join(bg_dir, selected_bg_file)
        print(f" [✓] Memilih gambar estetik dari bank stok: {selected_bg_file}")
    else:
        print("\n[2/4] Merender gambar 1080p via Pollinations Flux...")
        img_filename = f"bg_{choice}_{timestamp}.jpg"
        img_path = ai.generate_and_download_image(seo.get("image_prompt"), img_filename)
        print(f" [✓] Gambar tersimpan di: {img_path}")

    # Pilihan Efek Cinemagraph Motion
    print("\n--- [ PILIH EFEK GERAK (CINEMAGRAPH MOTION) ] ---")
    print(" [1] Rain on Window Glass  (Rintik & Aliran Air di Kaca Jendela) [Rekomendasi]")
    print(" [2] Golden Dust Particles (Partikel Debu Emas Hangat & Bokeh)")
    print(" [3] Morning Sunlight Beam (Sinar Matahari Pagi Menembus Jendela)")
    print(" [4] Cozy Fireplace Embers (Percikan Bara Api & Sparks)")
    print(" [5] Soft Snow Falling     (Rintik Salju Dingin)")
    print(" [6] Heavy Rain Downpour   (Curahan Hujan Lebat Luar Ruangan)")
    print(" [7] Coffee Steam Vapor    (Kepulan Uap Panas Cangkir)")
    print(" [8] Tanpa Efek Gerak      (Still Image Full HD 1080p Kilat 1 Detik)")
    
    fx_choice = input("Pilih efek gerak (1-8, default: 1): ").strip() or "1"
    fx_map = {
        "1": ("rain_glass", True),
        "2": ("dust", True),
        "3": ("sunlight", True),
        "4": ("embers", True),
        "5": ("snow", True),
        "6": ("rain_downpour", True),
        "7": ("steam", True),
        "8": ("none", False)
    }
    overlay_type, motion_mode = fx_map.get(fx_choice, ("rain_glass", True))

    # Langkah 3: Compose Audio Looper
    print(f"\n[3/4] Menggabungkan dan me-looping audio hingga {duration_minutes} Menit...")
    audio_filename = f"master_audio_{timestamp}.m4a"
    audio_path = composer.compose_master_audio(duration_seconds, audio_filename, formula_key=choice, shuffle=True)
    print(f" [✓] Master audio siap: {audio_path}")

    # Langkah 4: Render Video Final
    print(f"\n[4/4] Memproses render video final dengan FFmpeg ultralight...")
    video_filename = f"video_{choice}_{timestamp}.mp4"
    seo["duration_seconds"] = duration_seconds
    seo["thumbnail_image"] = img_path
    video_path = engine.render_video(
        img_path, 
        audio_path, 
        video_filename, 
        metadata=seo, 
        motion_mode=motion_mode,
        overlay_type=overlay_type
    )
    
    # Hapus audio master sementara untuk menghemat ruang disk
    if os.path.exists(audio_path):
        os.remove(audio_path)

    print("\n" + "=" * 66)
    print(" [🎉] VIDEO BERHASIL DIBUAT DENGAN SEMPURNA!")
    print(f" File Video : {video_path}")
    print(f" Metadata   : {os.path.splitext(video_path)[0] + '.json'}")
    print("=" * 66)

    # Opsi Upload Langsung
    ask_upload = input("\nMau langsung upload video ini ke YouTube sekarang? (y/n, default: n): ").strip().lower()
    if ask_upload == "y":
        do_upload_video(video_path, os.path.splitext(video_path)[0] + ".json", img_path)

def do_upload_video(video_path: str, meta_path: str, thumbnail_path: str = None):
    uploader = YouTubeUploader()
    print("\n--- [ PENGATURAN STATUS UPLOAD ] ---")
    print(" [1] Scheduled (Jadwal Tayang Otomatis jam 15:00 WIB / Prime US) [Rekomendasi]")
    print(" [2] Private   (Hanya Anda yang bisa lihat di YouTube Studio)")
    print(" [3] Unlisted  (Bisa ditonton hanya lewat link)")
    print(" [4] Public    (Langsung tayang saat ini juga)")
    
    opt = input("\nPilih status (1-4, default: 1): ").strip() or "1"
    
    privacy = "private"
    publish_at = None
    
    if opt == "1":
        # Jadwalkan ke prime time US (15:00 WIB = 03:00 EST / 04:00 EDT)
        # Cari slot 15:00 WIB pada hari ini, atau besok jika sudah lewat
        import datetime
        now_wib = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
        target_wib = now_wib.replace(hour=15, minute=0, second=0, microsecond=0)
        if now_wib >= target_wib:
            target_wib = target_wib + datetime.timedelta(days=1)
        # Konversi WIB -> UTC untuk publishAt
        target_utc = target_wib - datetime.timedelta(hours=7)
        publish_at = target_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"    Jadwal tayang (Prime US): {target_wib.strftime('%Y-%m-%d %H:%M WIB')}")
    elif opt == "2":
        privacy = "private"
    elif opt == "3":
        privacy = "unlisted"
    elif opt == "4":
        privacy = "public"
        
    try:
        uploader.upload_video(
            video_path=video_path,
            meta_path=meta_path,
            thumbnail_path=thumbnail_path,
            privacy_status=privacy,
            publish_at_iso=publish_at
        )
    except Exception as e:
        print(f"\n[x] Gagal upload video: {e}")

def upload_menu_flow():
    videos = list_ready_videos()
    if not videos:
        return
        
    idx_input = input("\nPilih nomor video yang mau diupload (misal: 1): ").strip()
    try:
        selected_idx = int(idx_input)
        target = next((v for v in videos if v["index"] == selected_idx), None)
        if not target:
            print("Nomor video tidak ditemukan.")
            return
            
        # Cari thumbnail image dari metadata
        thumb = None
        if os.path.exists(target["meta_path"]):
            with open(target["meta_path"], "r", encoding="utf-8") as f:
                thumb = json.load(f).get("thumbnail_image")
                
        do_upload_video(target["vid_path"], target["meta_path"], thumb)
    except ValueError:
        print("Input harus berupa angka.")

def setup_youtube_auth():
    print("\n--- [ SETUP OTORISASI AKUN YOUTUBE ] ---")
    uploader = YouTubeUploader()
    
    if not os.path.exists(uploader.client_secret_file):
        print("File 'client_secret.json' BELUM DITEMUKAN di:")
        print(f"-> {uploader.credentials_dir}\n")
        print("Langkah Mudah Membuatnya (Cuma 2 Menit):")
        print("1. Buka https://console.cloud.google.com/ dan login akun Google.")
        print("2. Buat Project baru (misal: 'YT-Bot').")
        print("3. Buka menu 'APIs & Services' -> 'Enable APIs' -> cari 'YouTube Data API v3' -> klik Enable.")
        print("4. Buka menu 'Credentials' -> 'Create Credentials' -> 'OAuth client ID'.")
        print("5. Pilih Application Type: 'Desktop App' -> klik Create.")
        print("6. Download file JSON-nya, lalu ganti namanya menjadi 'client_secret.json'.")
        print(f"7. Pindahkan file tersebut ke folder: {uploader.credentials_dir}")
        return

    print("File client_secret.json ditemukan!")
    print("Membuka browser untuk otorisasi akun YouTube...")
    try:
        uploader.get_authenticated_service()
        print("\n[🎉] SELAMAT! Akun YouTube Anda berhasil terhubung 100%!")
        print("Mulai sekarang bot bisa upload video otomatis tanpa perlu login lagi.")
    except Exception as e:
        print(f"Gagal otorisasi: {e}")

def download_suno_menu():
    from suno_downloader import download_suno_song
    print("\n--- [ DOWNLOAD LAGU DARI LINK SUNO (GRATIS) ] ---")
    link = input("Masukkan Link Share Suno (misal: https://suno.com/s/...): ").strip()
    if not link:
        return
        
    print("\nPilih Kategori Lagu:")
    print(" [1] 1_piano_rain       (Piano Santai & Hujan)")
    print(" [2] 2_bossa_nova       (Gitar Jazz & Kafe)")
    print(" [3] 3_lofi_chill       (Lofi Beat Malam)")
    print(" [4] 4_dark_academia    (Klasik / Cello)")
    print(" [5] 5_acoustic_guitar  (Gitar Akustik Alam)")
    cat = input("\nPilih kategori (1-5, default: 1): ").strip() or "1"
    
    title = input("Beri nama judul lagu (opsional, tekan Enter untuk default): ").strip()
    try:
        download_suno_song(link, target_formula=cat, custom_title=title if title else None)
    except Exception as e:
        print(f"[x] Gagal download: {e}")

def main():
    while True:
        print_banner()
        print(" MENU PILIHAN:")
        print(" [1] Mulai Produksi 1 Video (Otomatis Penuh)")
        print(" [2] Upload Video ke YouTube Studio")
        print(" [3] Download Lagu dari Link Suno (Jebol Gratis)")
        print(" [4] Setup / Cek Otorisasi Akun YouTube")
        print(" [5] Periksa Kesiapan Sistem & Koneksi AI")
        print(" [6] Lihat Daftar Video di Folder Output")
        print(" [7] Keluar")
        
        pilihan = input("\nMasukkan pilihan (1-7): ").strip()
        
        if pilihan == "1":
            generate_video_flow()
            input("\nTekan Enter untuk kembali ke menu...")
        elif pilihan == "2":
            upload_menu_flow()
            input("\nTekan Enter untuk kembali ke menu...")
        elif pilihan == "3":
            download_suno_menu()
            input("\nTekan Enter untuk kembali ke menu...")
        elif pilihan == "4":
            setup_youtube_auth()
            input("\nTekan Enter untuk kembali ke menu...")
        elif pilihan == "5":
            run_test_connection()
            input("\nTekan Enter untuk kembali ke menu...")
        elif pilihan == "6":
            list_ready_videos()
            input("\nTekan Enter untuk kembali ke menu...")
        elif pilihan == "7":
            print("\nTerima kasih! Sampai jumpa lagi bang.")
            break
        else:
            print("\nPilihan tidak valid. Silakan coba lagi.")
            time.sleep(1)

if __name__ == "__main__":
    main()
