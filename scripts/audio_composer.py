import os
import json
import subprocess
import glob
import random
from typing import List, Optional

class AudioComposer:
    def __init__(self, config_path: str = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.json")
            
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
            
        self.base_dir = os.path.dirname(config_path)
        self.music_dir = os.path.join(self.base_dir, self.config["paths"]["assets_music"])
        self.ambience_dir = os.path.join(self.base_dir, self.config["paths"]["assets_ambience"])
        self.output_dir = os.path.join(self.base_dir, self.config["paths"]["output_dir"])
        os.makedirs(self.output_dir, exist_ok=True)

        # Mapping key formula ke subfolder
        self.formula_folders = {
            "1": "1_piano_rain",
            "2": "2_bossa_nova",
            "3": "3_lofi_chill",
            "4": "4_dark_academia",
            "5": "5_acoustic_guitar",
            "6": "3_lofi_chill"
        }

    def get_duration(self, file_path: str) -> float:
        """Mengambil durasi file audio secara presisi via ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            print(f"Warning: gagal membaca durasi {file_path}: {e}")
            return 0.0

    def get_music_files(self, formula_key: str = "1", shuffle: bool = True) -> List[str]:
        """
        Mencari lagu di subfolder tema terkait (misal: assets/music/1_piano_rain/).
        Jika subfolder kosong, otomatis fallback ke folder root assets/music/.
        """
        subfolder = self.formula_folders.get(str(formula_key), "1_piano_rain")
        target_dir = os.path.join(self.music_dir, subfolder)
        
        exts = ["*.mp3", "*.wav", "*.m4a", "*.aac", "*.ogg", "*.flac"]
        files = []
        
        # 1. Cek di subfolder tema dulu
        if os.path.exists(target_dir):
            for ext in exts:
                files.extend(glob.glob(os.path.join(target_dir, ext)))
                
        # 2. Kalau subfolder kosong, fallback ke root assets/music/
        if not files and os.path.exists(self.music_dir):
            for ext in exts:
                files.extend(glob.glob(os.path.join(self.music_dir, ext)))

        # Saring agar semua file berformat seragam (prioritas .mp3 agar demuxer concat 100% stabil)
        if files:
            mp3_only = [f for f in files if f.lower().endswith(".mp3")]
            if mp3_only:
                files = mp3_only

        # 3. Fitur Smart Shuffle (Acak urutan lagu agar variatif di setiap video)
        if shuffle and len(files) > 1:
            random.shuffle(files)

        return files

    def get_ambience_file(self, formula_key: str = "1") -> Optional[str]:
        """
        Mencari file ambience yang cocok dengan tema.
        Prioritas: subfolder tema -> subfolder fallback tema lain -> root.
        Mapping tema agar tiap formula dapat ambience relevan (bukan semua pakai rain).
        """
        # Tema -> [subfolder tema, fallback] urutan prioritas
        theme_ambience = {
            "1": ["1_piano_rain"],                              # hujan
            "2": ["2_bossa_nova", "1_piano_rain"],              # kafe -> hujan
            "3": ["3_lofi_chill", "1_piano_rain", "2_bossa_nova"],  # lofi city night -> kafe -> hujan
            "4": ["4_dark_academia", "1_piano_rain", "3_lofi_chill"],  # dark academia -> hujan
            "5": ["5_acoustic_guitar", "1_piano_rain", "3_lofi_chill"],  # acoustic nature -> hujan -> lofi
        }

        candidates = theme_ambience.get(str(formula_key), ["1_piano_rain"])
        exts = ["*.mp3", "*.wav", "*.m4a", "*.aac", "*.ogg", "*.flac"]

        for sub in candidates:
            target_dir = os.path.join(self.ambience_dir, sub)
            if os.path.exists(target_dir):
                for ext in exts:
                    files = glob.glob(os.path.join(target_dir, ext))
                    if files:
                        return files[0]

        # Fallback terakhir: scan root assets/ambience/
        if os.path.exists(self.ambience_dir):
            for ext in exts:
                files = glob.glob(os.path.join(self.ambience_dir, ext))
                if files:
                    return files[0]

        return None

    def compose_master_audio(
        self,
        target_duration_seconds: int,
        output_filename: str = "master_audio.m4a",
        formula_key: str = "1",
        shuffle: bool = True
    ) -> str:
        """
        Menggabungkan dan me-looping trek musik dari subfolder tema terpilih
        dengan fitur Smart Shuffle otomatis dan ambience layering.
        """
        music_files = self.get_music_files(formula_key=formula_key, shuffle=shuffle)
        if not music_files:
            subfolder = self.formula_folders.get(str(formula_key), "")
            raise FileNotFoundError(
                f"Tidak ada file musik ditemukan di {os.path.join(self.music_dir, subfolder)} "
                f"maupun di {self.music_dir}! Silakan taruh file MP3 di folder tersebut."
            )

        print(f"    * Ditemukan {len(music_files)} lagu tema di bensin audio.")
        if shuffle and len(music_files) > 1:
            print("    * Smart Shuffle: Urutan lagu berhasil diacak otomatis!")

        dest_audio = os.path.join(self.output_dir, output_filename)
        
        # 1. Hitung durasi per trek
        durations = [self.get_duration(f) for f in music_files]
        total_sample_len = sum(durations)
        if total_sample_len <= 0:
            raise ValueError("File musik berdurasi 0 atau korup.")

        # 2. Buat concat list text file untuk FFmpeg
        concat_txt = os.path.join(self.output_dir, f"concat_{os.getpid()}_{int(random.random()*10000)}.txt")
        current_len = 0.0
        
        # Looping berulang sampai durasi target terpenuhi (diberi buffer 10% agar filter pitch shift tidak kekurangan sampel)
        buffer_target = int(target_duration_seconds * 1.10)
        with open(concat_txt, "w", encoding="utf-8") as f:
            while current_len < buffer_target:
                for idx, mf in enumerate(music_files):
                    safe_path = mf.replace("\\", "/")
                    f.write(f"file '{safe_path}'\n")
                    current_len += durations[idx]
                    if current_len >= buffer_target:
                        break

        # 3. Cek file ambience yang cocok
        ambience_file = self.get_ambience_file(formula_key=formula_key)
        if ambience_file:
            print(f"    * Layering Ambience: {os.path.basename(ambience_file)} (-16dB)")

        # Cek fitur 432Hz tuning & warm reverb dari config
        video_cfg = self.config.get("video_settings", {})
        tuning_432 = video_cfg.get("tuning_432hz", True)
        warm_reverb = video_cfg.get("warm_reverb", True)

        music_filters = []
        if tuning_432:
            print("    * Frequency Tuning: 432Hz Harmonic Miracle Tone")
            music_filters.append("asetrate=47127,aresample=48000")
        if warm_reverb:
            print("    * Spatial Audio: Warm Ambient Room Reverb")
            music_filters.append("aecho=0.85:0.7:35|55:0.18|0.12")
        music_filters.append(f"volume=1.0,atrim=0:{target_duration_seconds}")
        m_filter_str = ",".join(music_filters)

        # 4. Bangun perintah FFmpeg streaming
        if ambience_file:
            safe_amb = ambience_file.replace("\\", "/")
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_txt,
                "-stream_loop", "-1", "-i", safe_amb,
                "-filter_complex",
                f"[0:a]{m_filter_str}[m];"
                f"[1:a]volume=0.20,atrim=0:{target_duration_seconds}[amb];"
                f"[m][amb]amix=inputs=2:duration=first:dropout_transition=2[out]",
                "-map", "[out]",
                "-c:a", "aac", "-b:a", self.config["video_settings"]["audio_bitrate"],
                dest_audio
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_txt,
                "-filter_complex", f"[0:a]{m_filter_str}[out]",
                "-map", "[out]",
                "-c:a", "aac", "-b:a", self.config["video_settings"]["audio_bitrate"],
                dest_audio
            ]

        # Eksekusi FFmpeg
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        
        # Bersihkan temporary concat list
        if os.path.exists(concat_txt):
            os.remove(concat_txt)

        # Validasi durasi hasil render audio
        actual_dur = self.get_duration(dest_audio)
        if actual_dur < target_duration_seconds * 0.90:
            raise RuntimeError(
                f"Audio output terpotong! Target {target_duration_seconds}s ({target_duration_seconds/60:.1f}m), "
                f"tapi hasil hanya {actual_dur:.1f}s ({actual_dur/60:.1f}m)."
            )
            
        return dest_audio
