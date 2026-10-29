import os
import sys
import json
import time
import subprocess
from typing import Dict, Any

class VideoEngine:
    def __init__(self, config_path: str = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.json")
            
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
            
        self.base_dir = os.path.dirname(config_path)
        self.output_dir = os.path.join(self.base_dir, self.config["paths"]["output_dir"])
        os.makedirs(self.output_dir, exist_ok=True)

    @staticmethod
    def _clean_tags_str(tags_input):
        if not tags_input:
            return ""
        if isinstance(tags_input, str):
            items = [t.strip() for t in tags_input.split(",") if t.strip()]
        elif isinstance(tags_input, list):
            items = [str(t).strip() for t in tags_input if str(t).strip()]
        else:
            return ""
        _ILLEGAL = str.maketrans("", "", "<>\"'&+=@")
        clean = []
        total = 0
        for t in items:
            t = t.translate(_ILLEGAL).strip().strip("#")
            if not t or len(t) > 30:
                continue
            cost = len(t) + (2 if " " in t else 0) + (1 if clean else 0)
            if total + cost > 490:
                break
            clean.append(t)
            total += cost
        return ", ".join(clean)

    def _run_ffmpeg(self, cmd, target_dur=0.0, label="Render"):
        """Jalanin FFmpeg dengan progress bar + capture stderr. Return (elapsed, dest)."""
        print(f"[*] Memulai proses FFmpeg -> {label} ...")
        start_time = time.time()

        cmd_with_progress = cmd[:-1] + ["-progress", "pipe:1", cmd[-1]]

        process = subprocess.Popen(
            cmd_with_progress,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        stderr_chunks = []
        import threading
        def capture_stderr():
            for err_line in process.stderr:
                stderr_chunks.append(err_line)
        err_thread = threading.Thread(target=capture_stderr, daemon=True)
        err_thread.start()

        current_time_s = 0.0
        current_speed = "1.0x"
        current_fps = "30"

        for line in process.stdout:
            line = line.strip()
            if line.startswith("out_time_ms="):
                try:
                    current_time_s = int(line.split("=")[1]) / 1_000_000.0
                except ValueError:
                    pass
            elif line.startswith("fps="):
                current_fps = line.split("=")[1].strip() or current_fps
            elif line.startswith("speed="):
                current_speed = line.split("=")[1].strip() or current_speed
            elif line.startswith("progress="):
                if target_dur > 0:
                    pct = min(100.0, (current_time_s / target_dur) * 100.0)
                    cur_m, cur_s = int(current_time_s // 60), int(current_time_s % 60)
                    tot_m, tot_s = int(target_dur // 60), int(target_dur % 60)
                    bar_len = 25
                    filled_len = int(bar_len * (pct / 100.0))
                    bar = "#" * filled_len + "-" * (bar_len - filled_len)
                    sys.stdout.write(
                        f"\r  >> {label}: [{bar}] {pct:5.1f}% | {cur_m:02d}:{cur_s:02d}/{tot_m:02d}:{tot_s:02d} | {current_speed} | {current_fps}  "
                    )
                else:
                    cur_m, cur_s = int(current_time_s // 60), int(current_time_s % 60)
                    sys.stdout.write(
                        f"\r  >> {label}: {cur_m:02d}:{cur_s:02d} rendered | {current_speed} | {current_fps}  "
                    )
                sys.stdout.flush()

        process.wait()
        err_thread.join(timeout=2)
        stderr_output = "".join(stderr_chunks)
        print()

        if process.returncode != 0:
            tail_err = stderr_output[-1000:] if len(stderr_output) > 1000 else stderr_output
            raise RuntimeError(f"FFmpeg render error:\n{tail_err}")

        return time.time() - start_time

    @staticmethod
    def free_ram_gb() -> float:
        """Cek RAM bebas (Windows) tanpa dependency tambahan."""
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return stat.ullAvailPhys / (1024 ** 3)
        except Exception:
            pass
        return 99.0

    # Mapping formula -> overlay yang paling cocok secara visual & mood
    FORMULA_OVERLAY = {
        "1": "rain_glass",    # Piano Rain    -> hujan di kaca jendela
        "2": "sunlight",      # Bossa Nova    -> sinar matahari pagi
        "3": "dust",          # Lofi Chill    -> partikel debu emas hangat
        "4": "embers",        # Dark Academia -> percikan bara api
        "5": "sunlight",      # Acoustic      -> cahaya matahari menembus hutan
        "6": "dust",          # Pomodoro      -> partikel emas fokus
    }

    def _get_overlay_path(self, overlay_type: str) -> str:
        """Return path overlay MP4. Return None kalau file tidak ada."""
        overlay_map = {
            "rain_glass"   : "overlay_rain_window_glass.mp4",
            "rain_downpour": "overlay_rain_downpour.mp4",
            "dust"         : "overlay_golden_dust.mp4",
            "sunlight"     : "overlay_sunlight_beam.mp4",
            "embers"       : "overlay_embers_sparks.mp4",
            "snow"         : "overlay_snow_falling.mp4",
            "steam"        : "overlay_steam.mp4",
        }
        fname = overlay_map.get(overlay_type)
        if not fname:
            return None
        path = os.path.join(self.base_dir, "assets", "overlays", fname)
        return path if os.path.exists(path) else None

    def render_multiscene(
        self,
        image_paths: list,
        audio_path: str,
        output_filename: str = None,
        metadata: Dict[str, Any] = None,
        scene_seconds: int = 180,
        transition_seconds: float = 1.0,
        watermark_text: str = None,
        watermark_opacity: float = 0.30,
        formula_key: str = "1"
    ) -> str:
        """
        Multi-scene render: banyak background + Ken Burns pan/zoom + crossfade antar scene
        + cinemagraph overlay per formula (rain/dust/sunlight/embers).

        Overlay dipilih otomatis berdasarkan formula_key sehingga setiap tema
        punya efek "gambar hidup" yang relevan tanpa input manual.
        """
        if not image_paths:
            raise ValueError("image_paths kosong")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio tidak ditemukan: {audio_path}")

        images = [p for p in image_paths if p and os.path.exists(p)]
        if not images:
            raise FileNotFoundError("Tidak ada gambar valid untuk scene.")

        total_dur = self.get_dur(audio_path)
        if total_dur <= 0:
            raise ValueError("Audio durasi 0/korup.")

        n = len(images)
        t = transition_seconds
        seg = (total_dur + (n - 1) * t) / n
        frames_per_scene = max(30, int(round(seg * 30)))

        if output_filename is None:
            output_filename = f"video_{int(time.time())}.mp4"
        dest_video = os.path.join(self.output_dir, output_filename)

        # ── Watermark ──
        if watermark_text is None:
            branding = self.config.get("branding", {})
            watermark_text    = branding.get("watermark_text", "© Cozy Mood Lounge")
            watermark_opacity = branding.get("watermark_opacity", 0.30)

        font_candidate = "C:/Windows/Fonts/arial.ttf"
        if not os.path.exists(font_candidate):
            font_candidate = "C:/Windows/Fonts/calibri.ttf"
        if os.path.exists(font_candidate):
            safe_font = font_candidate.replace("\\", "/").replace(":", "\\:")
            wm = (f"drawtext=text='{watermark_text}':fontfile='{safe_font}'"
                  f":x=w-tw-40:y=h-th-30:fontsize=22:fontcolor=white@{watermark_opacity}"
                  f":shadowcolor=black@0.25:shadowx=1:shadowy=1")
        else:
            safe_font = None
            wm = (f"drawtext=text='{watermark_text}':x=w-tw-40:y=h-th-30:fontsize=22"
                  f":fontcolor=white@{watermark_opacity}:shadowcolor=black@0.25")

        # ── Top Badge (432Hz / Pomodoro) ──
        badge_text = ""
        if metadata:
            if metadata.get("is_pomodoro") or "pomodoro" in str(metadata.get("title", "")).lower():
                badge_text = "POMODORO 25/5 FOCUS SESSION"
            elif self.config.get("video_settings", {}).get("tuning_432hz", True):
                badge_text = "432Hz HARMONIC AUDIO"

        top_badge = ""
        if badge_text and safe_font:
            top_badge = (
                f",drawtext=text='{badge_text}':fontfile='{safe_font}':x=w-tw-40:y=35:"
                f"fontsize=20:fontcolor=white@0.85:box=1:boxcolor=black@0.45:boxborderw=10"
            )

        # ── Pilih overlay per formula ──
        overlay_type = self.FORMULA_OVERLAY.get(str(formula_key), "dust")
        overlay_path = self._get_overlay_path(overlay_type)
        use_overlay  = overlay_path is not None
        if use_overlay:
            print(f"[*] Cinemagraph Overlay [{overlay_type.upper()}] aktif untuk Formula {formula_key}")
        else:
            print(f"[!] Overlay '{overlay_type}' tidak ditemukan, render tanpa overlay.")

        # ── Build filter_complex ──
        # Input index:
        #   0..n-1  = gambar background
        #   n       = overlay video (kalau ada)
        #   n atau n+1 = audio

        parts  = []
        labels = []

        # Ken Burns per scene — zoom in/out berselang-seling + pan halus
        for i in range(n):
            if i % 2 == 0:
                zexpr = "min(zoom+0.00045,1.26)"
                xpos  = "(iw-iw/zoom)*(0.5+0.45*sin(on/260))"
                ypos  = "(ih-ih/zoom)*(0.5+0.40*cos(on/300))"
            else:
                zexpr = "if(eq(on,1),1.26,max(1.0,zoom-0.00045))"
                xpos  = "(iw-iw/zoom)*(0.5+0.45*cos(on/240))"
                ypos  = "(ih-ih/zoom)*(0.5+0.40*sin(on/280))"
            lbl = f"s{i}"
            parts.append(
                f"[{i}:v]scale=2688:1512:force_original_aspect_ratio=increase,"
                f"crop=2688:1512,setsar=1,"
                f"zoompan=z='{zexpr}':x='{xpos}':y='{ypos}'"
                f":d={frames_per_scene}:s=1920x1080:fps=30[{lbl}]"
            )
            labels.append(lbl)

        # Xfade berantai antar scene
        prev = labels[0]
        for k in range(1, n):
            offset  = k * (seg - t)
            out_lbl = f"x{k}"
            parts.append(
                f"[{prev}][{labels[k]}]xfade=transition=fade:"
                f"duration={transition_seconds}:offset={offset:.3f}[{out_lbl}]"
            )
            prev = out_lbl

        # Blend overlay cinemagraph di atas hasil xfade
        ov_idx = n   # index input overlay
        if use_overlay:
            parts.append(
                f"[{prev}]format=gbrp[base];"
                f"[{ov_idx}:v]scale=1920:1080:force_original_aspect_ratio=increase,"
                f"crop=1920:1080,format=gbrp,setsar=1[ov];"
                f"[base][ov]blend=all_mode='screen':all_opacity=0.60[blended];"
                f"[blended]format=yuv420p,{wm}{top_badge}[v]"
            )
            audio_idx = n + 1
        else:
            parts.append(f"[{prev}]format=yuv420p,{wm}{top_badge}[v]")
            audio_idx = n

        # ── Bangun command FFmpeg ──
        cmd = ["ffmpeg", "-y"]
        for p in images:
            cmd += ["-i", p]
        if use_overlay:
            cmd += ["-stream_loop", "-1", "-i", overlay_path]
        cmd += ["-i", audio_path]
        cmd += [
            "-filter_complex", ";".join(parts),
            "-map", "[v]",
            "-map", f"{audio_idx}:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
            "-r", "30", "-c:a", "copy",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-shortest",
            dest_video
        ]

        print(f"[*] Multi-scene: {n} scene x {seg/60:.1f} menit | overlay: {overlay_type} | xfade: {transition_seconds}s")
        target_dur = float(metadata.get("duration_seconds", 0)) if metadata else total_dur
        if not target_dur:
            target_dur = total_dur

        try:
            elapsed = self._run_ffmpeg(cmd, target_dur, "Render")
        except RuntimeError as e:
            print(f"    [!] Multi-scene gagal ({e}), fallback ke single-scene + overlay...")
            return self.render_video(
                images[0], audio_path, output_filename,
                metadata=metadata, motion_mode=True, overlay_type=overlay_type
            )

        video_size_mb = os.path.getsize(dest_video) / (1024 * 1024)
        print(f"[OK] Render sukses dalam {elapsed:.2f} detik! Ukuran: {video_size_mb:.2f} MB")

        if metadata:
            self._write_meta(dest_video, metadata)
        return dest_video

    @staticmethod
    def get_dur(path: str) -> float:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
            )
            return float(r.stdout.strip())
        except Exception:
            return 0.0

    @staticmethod
    def _write_meta(dest_video: str, metadata: Dict[str, Any]):
        meta_path = os.path.splitext(dest_video)[0] + ".json"
        meta_data = {
            "video_file": os.path.basename(dest_video),
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "tags": VideoEngine._clean_tags_str(metadata.get("tags", "")),
            "thumbnail_image": metadata.get("thumbnail_image", ""),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": metadata.get("duration_seconds", 0),
            "status": "ready_for_upload"
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=2, ensure_ascii=False)
        print(f"[OK] Metadata YouTube tersimpan: {os.path.basename(meta_path)}")

    def render_video(
        self,
        image_path: str,
        audio_path: str,
        output_filename: str = None,
        metadata: Dict[str, Any] = None,
        motion_mode: bool = True,
        overlay_type: str = "dust"
    ) -> str:
        """
        Merender video MP4 dengan stream-processing FFmpeg ultralight.
        - Mendukung watermark transparan kecil elegan di pojok kanan bawah.
        - Mendukung live motion overlay (dust particles / steam / sunlight / embers / snow / rain)
          yang diblend halus (screen mode) sehingga gambar tetap hidup & lolos monetisasi YouTube.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"File gambar latar tidak ditemukan: {image_path}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"File audio master tidak ditemukan: {audio_path}")

        timestamp = int(time.time())
        if output_filename is None:
            output_filename = f"video_{timestamp}.mp4"

        dest_video = os.path.join(self.output_dir, output_filename)
        
        # Pengaturan Watermark dari config
        # Menggunakan fontfile langsung ke font Windows agar tidak crash/segmentation fault di FFmpeg Gyan WinGet
        branding = self.config.get("branding", {})
        watermark_text = branding.get("watermark_text", "© Cozy Mood Lounge")
        watermark_opacity = branding.get("watermark_opacity", 0.30)
        
        # Cari file font sistem Windows
        font_candidate = "C:/Windows/Fonts/arial.ttf"
        if not os.path.exists(font_candidate):
            font_candidate = "C:/Windows/Fonts/calibri.ttf"

        if os.path.exists(font_candidate):
            safe_font = font_candidate.replace("\\", "/").replace(":", "\\:")
            watermark_filter = f"drawtext=text='{watermark_text}':fontfile='{safe_font}':x=w-tw-40:y=h-th-30:fontsize=22:fontcolor=white@{watermark_opacity}:shadowcolor=black@0.25:shadowx=1:shadowy=1"
        else:
            # Tanpa font system: gunakan default FFmpeg (Libavfilter default font)
            print("    [!] Font Windows tidak ditemukan, pakai default font ffmpeg.")
            watermark_filter = f"drawtext=text='{watermark_text}':x=w-tw-40:y=h-th-30:fontsize=22:fontcolor=white@{watermark_opacity}:shadowcolor=black@0.25:shadowx=1:shadowy=1"

        # Cek ketersediaan file overlay
        overlay_map = {
            "rain": os.path.join(self.base_dir, "assets", "overlays", "overlay_rain_window_glass.mp4"),
            "rain_glass": os.path.join(self.base_dir, "assets", "overlays", "overlay_rain_window_glass.mp4"),
            "rain_downpour": os.path.join(self.base_dir, "assets", "overlays", "overlay_rain_downpour.mp4"),
            "dust": os.path.join(self.base_dir, "assets", "overlays", "overlay_golden_dust.mp4"),
            "sunlight": os.path.join(self.base_dir, "assets", "overlays", "overlay_sunlight_beam.mp4"),
            "embers": os.path.join(self.base_dir, "assets", "overlays", "overlay_embers_sparks.mp4"),
            "snow": os.path.join(self.base_dir, "assets", "overlays", "overlay_snow_falling.mp4"),
            "steam": os.path.join(self.base_dir, "assets", "overlays", "overlay_steam.mp4")
        }

        active_overlay = overlay_map.get(overlay_type)
        use_motion = motion_mode and active_overlay and os.path.exists(active_overlay)

        if use_motion:
            print(f"[*] Mengaktifkan Cinemagraph Motion [{overlay_type.upper()}]: Blending efek partikel hidup...")
            # Filter complex dengan format=gbrp agar blending screen mempertahankan warna asli 100% tanpa distorsi ungu
            # force_original_aspect_ratio=increase + crop=1920:1080 menjaga aspek rasio overlay agar tidak gepeng/terdistorsi
            filter_complex = (
                f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=gbrp[bg];"
                f"[1:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=gbrp[ov];"
                f"[bg][ov]blend=all_mode='screen':all_opacity=0.65[blended];"
                f"[blended]format=yuv420p,{watermark_filter}[v]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-framerate", "30",
                "-i", image_path,
                "-stream_loop", "-1",
                "-i", active_overlay,
                "-i", audio_path,
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-map", "2:a",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
                "-c:a", "copy",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-shortest",
                dest_video
            ]
        else:
            print(f"[*] Rendering video Full HD 1080p dengan Watermark transparan...")
            vf_chain = f"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,{watermark_filter}"
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-framerate", "30",
                "-i", image_path,
                "-i", audio_path,
                "-vf", vf_chain,
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-preset", "veryfast",
                "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
                "-c:a", "copy",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-shortest",
                dest_video
            ]

        target_dur = float(metadata.get("duration_seconds", 0)) if metadata else 0.0
        elapsed = self._run_ffmpeg(cmd, target_dur, output_filename)
        video_size_mb = os.path.getsize(dest_video) / (1024 * 1024)
        print(f"[OK] Render sukses dalam {elapsed:.2f} detik! Ukuran file: {video_size_mb:.2f} MB")

        # Simpan metadata JSON berpasangan untuk auto-uploader nanti
        if metadata:
            meta_path = os.path.splitext(dest_video)[0] + ".json"
            meta_data = {
                "video_file": os.path.basename(dest_video),
                "title": metadata.get("title", ""),
                "description": metadata.get("description", ""),
                "tags": self._clean_tags_str(metadata.get("tags", "")),
                "thumbnail_image": metadata.get("thumbnail_image", ""),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_seconds": metadata.get("duration_seconds", 0),
                "status": "ready_for_upload"
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, indent=2, ensure_ascii=False)
            print(f"[OK] Metadata YouTube tersimpan: {os.path.basename(meta_path)}")

        return dest_video

if __name__ == "__main__":
    engine = VideoEngine()
    test_img = os.path.join(engine.base_dir, "assets", "backgrounds", "test_formula1.jpg")
    test_aud = os.path.join(engine.output_dir, "test_audio_30s.m4a")
    
    if os.path.exists(test_img) and os.path.exists(test_aud):
        print("Mengetes render video 30 detik ultralight...")
        dummy_meta = {
            "title": "Test 30s Relaxation Video",
            "description": "Test description from engine.",
            "tags": "test, relaxation",
            "duration_seconds": 30
        }
        res = engine.render_video(test_img, test_aud, "test_video_30s.mp4", metadata=dummy_meta)
        print("Test Render Sukses:", res)
    else:
        print("File test belum lengkap.")
