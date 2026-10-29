"""
Shorts Generator — Bikin video YouTube Shorts vertikal (1080x1920, 9:16)
sebagai teaser 'Traffic Siphon' berdurasi 30-45 detik yang mengarahkan
penonton ke video utama (Full 1-Hour Version).
"""
import os
import json
import time
import subprocess
from typing import Dict, Any, Optional, Tuple


class ShortsGenerator:
    def __init__(self, config_path: str = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.json")

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.base_dir = os.path.dirname(config_path)
        self.output_dir = os.path.join(self.base_dir, self.config["paths"]["output_dir"])
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_teaser_shorts(
        self,
        background_path: str,
        audio_path: str,
        main_title: str,
        main_video_id: Optional[str] = None,
        duration_seconds: int = 35,
        output_filename: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Render video Shorts vertikal 1080x1920 dan buat file metadata JSON pendukung.
        Returns: (shorts_video_path, shorts_meta_path)
        """
        if not os.path.exists(background_path):
            raise FileNotFoundError(f"Background tidak ditemukan: {background_path}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio tidak ditemukan: {audio_path}")

        timestamp = int(time.time())
        if output_filename is None:
            output_filename = f"shorts_{timestamp}.mp4"

        dest_video = os.path.join(self.output_dir, output_filename)
        dest_meta = os.path.splitext(dest_video)[0] + ".json"

        # Font Windows
        f_bold = "C:/Windows/Fonts/arialbd.ttf"
        if not os.path.exists(f_bold):
            f_bold = "C:/Windows/Fonts/calibrib.ttf"
        f_reg = "C:/Windows/Fonts/arial.ttf"
        if not os.path.exists(f_reg):
            f_reg = "C:/Windows/Fonts/calibri.ttf"

        safe_bold = f_bold.replace("\\", "/").replace(":", "\\:")
        safe_reg = f_reg.replace("\\", "/").replace(":", "\\:")

        branding = self.config.get("branding", {})
        channel_name = branding.get("channel_name", "Cozy Mood Lounge")

        # Filter: Crop ke 9:16 vertikal + Teks Hook atas & bawah
        filter_str = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"drawtext=text='🎧 432Hz SPATIAL AUDIO':fontfile='{safe_bold}':x=(w-tw)/2:y=240:fontsize=46:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=16,"
            f"drawtext=text='FULL VERSION ON CHANNEL':fontfile='{safe_bold}':x=(w-tw)/2:y=h-360:fontsize=42:fontcolor=0xF5C518:box=1:boxcolor=black@0.65:boxborderw=18,"
            f"drawtext=text='© {channel_name}':fontfile='{safe_reg}':x=(w-tw)/2:y=h-260:fontsize=28:fontcolor=white@0.85,"
            f"format=yuv420p[v]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", "30", "-i", background_path,
            "-i", audio_path,
            "-filter_complex", filter_str,
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(duration_seconds),
            "-movflags", "+faststart",
            dest_video
        ]

        print(f"[*] Rendering Teaser Shorts 9:16 ({duration_seconds}s)...")
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        # Metadata Shorts
        # Format judul Shorts yang viral
        short_title = main_title.split("|")[0].split("☕")[0].split("🌧️")[0].strip()
        if len(short_title) > 60:
            short_title = short_title[:57].rstrip() + "..."
        shorts_title = f"{short_title} 🎧 #Shorts #Lofi #432Hz"

        link_text = f"https://youtu.be/{main_video_id}" if main_video_id else "Check our channel videos"
        shorts_desc = (
            f"Immerse in gentle 432Hz acoustic relaxation.\n\n"
            f"🔗 Full 1-Hour Extended Version:\n{link_text}\n\n"
            f"🎧 Use headphones for optimal spatial experience.\n"
            f"Subscribe to @{channel_name.replace(' ', '')} for daily peaceful sessions!\n\n"
            f"#Shorts #LofiBeats #DeepFocus #432Hz #SleepAmbience #RelaxingMusic"
        )

        meta_data = {
            "video_file": os.path.basename(dest_video),
            "title": shorts_title,
            "description": shorts_desc,
            "tags": "shorts, youtube shorts, lofi shorts, 432hz, relaxing music shorts, study with me, deep focus",
            "is_shorts": True,
            "duration_seconds": duration_seconds,
            "main_video_id": main_video_id,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "ready_for_upload"
        }

        with open(dest_meta, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=2, ensure_ascii=False)

        print(f"    [✓] Teaser Shorts siap: {os.path.basename(dest_video)} ({os.path.getsize(dest_video)/1024:.1f} KB)")
        return dest_video, dest_meta


if __name__ == "__main__":
    import glob
    gen = ShortsGenerator()
    bg_dir = os.path.join(gen.base_dir, "assets", "backgrounds")
    bgs = [f for f in glob.glob(os.path.join(bg_dir, "*.jp*"))]
    music_dir = os.path.join(gen.base_dir, "assets", "music", "1_piano_rain")
    songs = [f for f in glob.glob(os.path.join(music_dir, "*.mp3"))]

    if bgs and songs:
        v, m = gen.generate_teaser_shorts(
            background_path=bgs[0],
            audio_path=songs[0],
            main_title="Fall Asleep in 10 Minutes 🌧️ Soft Piano & Rain [432Hz]",
            main_video_id="demo12345",
            duration_seconds=15
        )
        print("Success:", v, m)
