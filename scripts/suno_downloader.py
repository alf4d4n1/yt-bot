import os
import sys
import json
import base64
import hashlib
import subprocess
import requests
from typing import Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

API_RIGHTS = "https://studio-api.prod.suno.com/api/mango/rights"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://suno.com"
}

def unwrap(wrapped_b64: str, clip_id: str, user_key: bytes) -> bytes:
    w = base64.b64decode(wrapped_b64)
    nonce, ct, tag = w[:12], w[12:-16], w[-16:]
    dec = Cipher(algorithms.AES(user_key), modes.GCM(nonce, tag)).decryptor()
    dec.authenticate_additional_data(clip_id.encode())
    return dec.update(ct) + dec.finalize()

def decrypt_bytes(data: bytes, clip_id: str, rights: dict) -> bytes:
    user_key = hashlib.sha256(rights["glt"].encode()).digest()
    key = unwrap(rights["key"], clip_id, user_key)
    counter = unwrap(rights["iv"], clip_id, user_key)
    dec = Cipher(algorithms.AES(key), modes.CTR(counter)).decryptor()
    return dec.update(data) + dec.finalize()

def extract_clip_id(url: str) -> Optional[str]:
    """Mengambil UUID clip dari berbagai format link Suno."""
    import re
    # Format /song/<uuid>
    m = re.search(r"suno\.com/song/([0-9a-fA-F-]{32,36})", url)
    if m:
        return m.group(1).lower()
        
    # Format /s/<shortcode> -> redirect ke /song/<uuid>
    if "suno.com/s/" in url:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            m = re.search(r"suno\.com/song/([0-9a-fA-F-]{32,36})", r.url)
            if m:
                return m.group(1).lower()
        except:
            pass
            
    # Direct UUID
    m = re.fullmatch(r"[0-9a-fA-F-]{32,36}", url.strip())
    if m:
        return url.strip().lower()
        
    return None

def download_suno_song(url_or_id: str, target_formula: str = "1", custom_title: str = None) -> str:
    """Download audio asli Suno secara gratis dan otomatis decrypt ke folder tema."""
    clip_id = extract_clip_id(url_or_id)
    if not clip_id:
        raise ValueError(f"Link atau ID Suno tidak valid: {url_or_id}")

    formula_folders = {
        "1": "1_piano_rain",
        "2": "2_bossa_nova",
        "3": "3_lofi_chill",
        "4": "4_dark_academia",
        "5": "5_acoustic_guitar"
    }
    
    subfolder = formula_folders.get(str(target_formula), "1_piano_rain")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dest_dir = os.path.join(base_dir, "assets", "music", subfolder)
    os.makedirs(dest_dir, exist_ok=True)
    
    filename = f"{custom_title if custom_title else clip_id[:8]}.m4a"
    dest_path = os.path.join(dest_dir, filename)

    print(f"[*] Menghubungi hak stream Suno untuk Clip ID: {clip_id}...")
    # 1. Fetch Mango Rights
    body = {"content_params": {"content_id": clip_id, "content_type": "clip"}}
    r = requests.post(API_RIGHTS, json=body, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"Gagal mengambil hak audio dari Suno (Status: {r.status_code})")
    rights = r.json()

    # 2. Download encrypted stream
    audio_url = f"https://d2lwuy8qc234o3.cloudfront.net/1/clip/{clip_id}.m4a"
    print(f"[*] Mengunduh stream audio CloudFront...")
    enc_data = requests.get(audio_url, headers=HEADERS, timeout=30).content

    # 3. Decrypt bytes secara lokal
    print(f"[*] Melakukan dekripsi audio lokal (100% loss-free)...")
    clean_audio = decrypt_bytes(enc_data, clip_id, rights)

    # Simpan sementara sebagai M4A
    tmp_m4a = dest_path + ".tmp.m4a"
    with open(tmp_m4a, "wb") as f:
        f.write(clean_audio)

    # Otomatis convert ke Studio-Quality MP3 320kbps 48kHz via FFmpeg
    final_mp3 = os.path.splitext(dest_path)[0] + ".mp3"
    print(f"[*] Melakukan remastering ke Studio MP3 320kbps...")
    cmd = [
        "ffmpeg", "-y",
        "-i", tmp_m4a,
        "-c:a", "libmp3lame",
        "-b:a", "320k",
        "-ar", "48000",
        final_mp3
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    if os.path.exists(tmp_m4a):
        os.remove(tmp_m4a)

    sz_mb = os.path.getsize(final_mp3) / (1024 * 1024)
    print(f"[✓] LAGU SUKSES TERSIMPAN: {os.path.basename(final_mp3)} ({sz_mb:.2f} MB)")
    print(f"    Lokasi: {final_mp3}")
    return final_mp3

if __name__ == "__main__":
    if len(sys.argv) > 1:
        download_suno_song(sys.argv[1])
    else:
        print("Penggunaan: python suno_downloader.py <link_suno>")
