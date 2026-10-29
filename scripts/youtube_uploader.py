import os
import sys
import json
import time
from typing import Dict, Any, Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Scopes yang dibutuhkan untuk upload video dan set thumbnail
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube"
]

class YouTubeUploader:
    def __init__(self, config_path: str = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.json")
            
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
            
        self.base_dir = os.path.dirname(config_path)
        self.credentials_dir = os.path.join(self.base_dir, "credentials")
        os.makedirs(self.credentials_dir, exist_ok=True)
        
        self.client_secret_file = os.path.join(self.credentials_dir, "client_secret.json")
        self.token_file = os.path.join(self.credentials_dir, "token.json")

    def get_authenticated_service(self):
        """Autentikasi OAuth 2.0 resmi Google dengan auto-refresh token."""
        creds = None
        
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            except Exception as e:
                print(f"[!] Token rusak, perlu login ulang: {e}")
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None

            if not creds:
                if not os.path.exists(self.client_secret_file):
                    raise FileNotFoundError(
                        f"File 'client_secret.json' belum ada di folder:\n{self.credentials_dir}\n"
                        "Harap unduh OAuth Client ID dari Google Cloud Console dan simpan sebagai 'client_secret.json'."
                    )
                    
                print("\n[*] Membuka browser untuk otorisasi akun YouTube channel Anda...")
                flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_file, SCOPES)
                creds = flow.run_local_server(port=0)

            # Simpan token permanen
            with open(self.token_file, "w", encoding="utf-8") as token:
                token.write(creds.to_json())
                print(f"[✓] Token akses tersimpan permanen di: {os.path.basename(self.token_file)}")

        return build("youtube", "v3", credentials=creds, static_discovery=False)

    def upload_video(
        self,
        video_path: str,
        meta_path: str = None,
        thumbnail_path: str = None,
        privacy_status: str = "private",
        publish_at_iso: str = None
    ) -> Dict[str, Any]:
        """
        Mengupload video MP4 ke YouTube dengan resumable chunking.
        Mendukung custom thumbnail dan auto-schedule jadwal tayang.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"File video tidak ditemukan: {video_path}")

        # Baca metadata jika ada
        metadata = {}
        if meta_path and os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

        title = metadata.get("title", os.path.splitext(os.path.basename(video_path))[0])
        description = metadata.get("description", "Uploaded by YT-Content-Factory.")
        raw_tags = metadata.get("tags", "")
        parsed_tags = [t.strip() for t in raw_tags.split(",") if t.strip()] if isinstance(raw_tags, str) else (raw_tags if isinstance(raw_tags, list) else [])

        # YouTube: max 500 karakter total tags, tiap tag max 30 karakter, max 500 tag
        # Karakter ilegal: < > " ' & + = @ # (selain yang sudah disaring)
        _ILLEGAL = str.maketrans("", "", "<>\"'&+=@")
        clean_tags = []
        total_chars = 0
        for t in parsed_tags:
            t = t.translate(_ILLEGAL).strip().strip("#")
            if not t or len(t) > 30:
                continue
            cost = len(t) + (2 if " " in t else 0) + (1 if clean_tags else 0)
            if total_chars + cost > 490:  # batas aman 490 dari limit 500
                break
            clean_tags.append(t)
            total_chars += cost

        youtube = self.get_authenticated_service()

        # Status video
        status_body = {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
        
        # Jika ada jadwal tayang (ISO 8601 string: 2026-10-16T15:00:00Z)
        if publish_at_iso:
            status_body["privacyStatus"] = "private"
            status_body["publishAt"] = publish_at_iso

        body = {
            "snippet": {
                "title": title[:100], # Batas judul YT max 100 char
                "description": description[:5000],
                "tags": clean_tags,
                "categoryId": "10" # Kategori 10 = Music
            },
            "status": status_body
        }

        print(f"\n[*] Mengupload video ke YouTube:")
        print(f"    • File   : {os.path.basename(video_path)}")
        print(f"    • Judul  : {title}")
        print(f"    • Status : {privacy_status if not publish_at_iso else f'Scheduled ({publish_at_iso})'}")

        media = MediaFileUpload(video_path, chunksize=1024 * 1024 * 5, resumable=True)
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        retry_count = 0
        max_retries = 10
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    print(f"    Progress upload: {int(status.progress() * 100)}%")
                retry_count = 0
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    raise RuntimeError(f"Upload terputus setelah {max_retries}x percobaan koneksi: {e}")
                wait_s = retry_count * 3
                print(f"    [!] Koneksi internet terganggu ({e}). Menghubungkan ulang dalam {wait_s}s (Percobaan {retry_count}/{max_retries})...")
                time.sleep(wait_s)

        video_id = response.get("id")
        video_url = f"https://youtu.be/{video_id}"
        print(f"\n[🎉] VIDEO SUKSES TERUPLOAD!")
        print(f"    • Video ID : {video_id}")
        print(f"    • URL Tonton: {video_url}")

        # Set Custom Thumbnail jika ada
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                print(f"[*] Memasang Custom Thumbnail dari {os.path.basename(thumbnail_path)}...")
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path)
                ).execute()
                print(" [✓] Thumbnail resmi berhasil terpasang!")
            except Exception as e:
                print(f" [!] Gagal memasang thumbnail (pastikan channel sudah verifikasi nomor HP): {e}")

        # Perbarui metadata JSON lokal
        if meta_path and os.path.exists(meta_path):
            metadata["status"] = "uploaded"
            metadata["youtube_video_id"] = video_id
            metadata["youtube_url"] = video_url
            metadata["uploaded_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

        return {"video_id": video_id, "url": video_url}

if __name__ == "__main__":
    uploader = YouTubeUploader()
    print("YouTube Uploader Module Ready!")
    print("Credentials dir:", uploader.credentials_dir)
    print("Client secret exists:", os.path.exists(uploader.client_secret_file))
