import os
import io
import re
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional


try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ─── Seasonal Context ────────────────────────────────────────────────────────
# Otomatis deteksi musim berdasarkan bulan — untuk keyword & mood yang relevan

def _get_seasonal_context() -> Dict[str, str]:
    now = datetime.now(timezone.utc) + timedelta(hours=7)
    m = now.month
    if m in (9, 10, 11):
        return {
            "season"  : "Autumn / Fall",
            "keywords": "autumn lofi, cozy fall study, october rain, november chill, fall coffee shop",
            "mood"    : "cozy, warm, falling leaves, misty rain, pumpkin spice, amber golden",
            "visual"  : "autumn leaves falling outside window, warm amber candlelight, misty forest, golden hour"
        }
    elif m in (12, 1, 2):
        return {
            "season"  : "Winter / Holiday",
            "keywords": "cozy winter jazz, snowy cabin music, christmas cafe ambience, new year focus music",
            "mood"    : "warm fireplace, snowy window, holiday cozy, peaceful winter night",
            "visual"  : "snow falling outside window, fireplace glow, pine trees, winter cabin"
        }
    elif m in (3, 4, 5):
        return {
            "season"  : "Spring / Exam Season",
            "keywords": "spring morning study, exam focus music, fresh coffee piano, bloom season lofi",
            "mood"    : "fresh, blooming, hopeful, morning light, exam season energy",
            "visual"  : "cherry blossoms, morning sunlight, fresh coffee, open window spring breeze"
        }
    else:
        return {
            "season"  : "Summer / Retreat",
            "keywords": "sunset acoustic guitar, summer breeze lofi, peaceful holiday relaxing, beach house study",
            "mood"    : "breezy, warm sunset, peaceful retreat, golden summer afternoon",
            "visual"  : "sunset veranda, warm golden light, seaside view, summer afternoon"
        }


# ─── Per-Formula SEO Data ────────────────────────────────────────────────────
# Setiap formula punya persona, keyword pool, dan emotional hook sendiri

FORMULA_SEO = {
    "1": {
        "persona"     : "Piano Rain",
        "hook_pool"   : [
            "Fall Asleep to Gentle Piano & Rain",
            "Stress Melts Away with Soft Piano Rain",
            "The Perfect Rain & Piano Mix for Deep Sleep",
            "Drift into Deep Sleep with Rainy Piano Melodies",
            "Calm Your Mind — Piano & Rain for Anxiety Relief",
        ],
        "bracket_pool": ["432Hz / Deep Sleep", "Slowed + Reverb", "Rain ASMR / Sleep Music", "Binaural Beats / Insomnia Relief"],
        "tags_base"   : "soft piano rain, relaxing piano music, rain sounds sleep, piano for deep sleep, stress relief piano, calm piano music, rain ambience study, piano sleep 1 hour, cozy rain music, anxiety relief music, rain on window sounds, sleep music piano, focus music piano rain, 432hz piano, peaceful piano",
        "emoji"       : "🌧️🎹",
        "intent"      : "sleep"
    },
    "2": {
        "persona"     : "Bossa Nova Cafe",
        "hook_pool"   : [
            "Your Perfect Morning Coffee Companion",
            "Start Your Day Right — Bossa Nova & Coffee",
            "Work Smarter with Sunny Bossa Nova Vibes",
            "The Ultimate Cafe Music for Focus & Productivity",
            "Feel Good & Get Things Done — Morning Bossa Nova",
        ],
        "bracket_pool": ["Cafe Music / Work BGM", "Morning Vibes / No Ads", "Positive Energy / Focus Boost", "Coffee Shop Ambience"],
        "tags_base"   : "bossa nova cafe music, morning coffee jazz, coffee shop music, work from home music, background cafe music, bossa nova relaxing, positive morning music, productivity music, coffee music focus, cafe ambience music, jazz cafe morning, feel good music work, bossa nova guitar, sunny morning music, lofi cafe vibes",
        "emoji"       : "☕🎸",
        "intent"      : "focus"
    },
    "3": {
        "persona"     : "Lofi Chillhop",
        "hook_pool"   : [
            "Late Night Lofi for Deep Focus & Study",
            "The Ultimate Lofi Mix for Coders & Students",
            "Midnight Lofi Beats — Study Without Distraction",
            "Lofi Hip Hop Radio to Code & Study To",
            "Chill & Focus — Lofi Beats for Long Study Sessions",
        ],
        "bracket_pool": ["Lofi Hip Hop / Study Beats", "No Ads / No Interruptions", "Chill Vibes / Deep Focus", "Slowed + Reverb / Night Study"],
        "tags_base"   : "lofi hip hop study, lofi beats study, lofi music for focus, chill lofi beats, lofi chill relax, study with me lofi, lofi coding music, midnight lofi beats, lofi girl radio, lofi sleep music, beats to study to, lofi hip hop radio, cozy lofi vibes, lofi music no ads, night study lofi",
        "emoji"       : "🌙🎧",
        "intent"      : "study"
    },
    "4": {
        "persona"     : "Dark Academia",
        "hook_pool"   : [
            "Study Like a Victorian Scholar — Dark Academia Music",
            "Read Deeper, Think Clearer — Dark Academia Ambience",
            "The Ultimate Dark Academia Playlist for Focus",
            "Classical Music for Deep Study & Intellectual Work",
            "Focus Mode ON — Victorian Library Ambience & Music",
        ],
        "bracket_pool": ["Dark Academia / Classical Focus", "432Hz / Concentration Boost", "Victorian Library / Study Music", "Deep Work / No Distractions"],
        "tags_base"   : "dark academia music, dark academia study, classical music study, victorian library ambience, focus music classical, dark academia aesthetic, study music classical, cello music focus, deep focus classical, intellectual music, piano cello study, dark academia vibes, writing music, essay writing music, classical ambient study",
        "emoji"       : "📚🕯️",
        "intent"      : "study"
    },
    "5": {
        "persona"     : "Acoustic Guitar Nature",
        "hook_pool"   : [
            "Let Nature Heal Your Mind — Acoustic Guitar & Forest",
            "Anxiety Relief in 5 Minutes — Guitar & Nature Sounds",
            "The Most Peaceful Guitar Music You'll Ever Hear",
            "Unwind & Breathe — Acoustic Guitar & Forest Stream",
            "Escape the Noise — Peaceful Guitar & Nature Ambience",
        ],
        "bracket_pool": ["Nature Sounds / Stress Relief", "432Hz / Anxiety Relief", "Acoustic Guitar / Meditation", "Forest ASMR / Peaceful Mind"],
        "tags_base"   : "acoustic guitar relaxing, nature sounds guitar, peaceful guitar music, stress relief music, anxiety relief music, acoustic guitar meditation, forest stream sounds, nature music relax, fingerstyle guitar calm, guitar for sleep, nature ambience music, peaceful nature sounds, guitar meditation music, calm acoustic music, forest therapy music",
        "emoji"       : "🌿🎸",
        "intent"      : "relax"
    },
    "6": {
        "persona"     : "Pomodoro Study Timer",
        "hook_pool"   : [
            "Study With Me — Pomodoro 25/5 Timer & Lofi",
            "Get More Done Today — Pomodoro Focus Session",
            "The Productive Student's Pomodoro Study Companion",
            "25 Minutes Focus, 5 Minutes Rest — Lofi Pomodoro",
            "Beat Procrastination — Structured Pomodoro Study",
        ],
        "bracket_pool": ["Pomodoro 25/5 / Study Timer", "No Ads / Deep Focus", "Study With Me / Accountability", "Lofi Timer / Beat Procrastination"],
        "tags_base"   : "pomodoro study timer, pomodoro technique music, study with me timer, 25 minute study timer, study timer lofi, pomodoro lofi music, study accountability, focus timer music, pomodoro timer video, deep work timer, study session timer, productive study music, no distraction study, lofi study timer, pomodoro method music",
        "emoji"       : "⏱️📖",
        "intent"      : "study"
    }
}


class AIService:
    def __init__(self, config_path: str = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.json")

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.base_dir   = os.path.dirname(config_path)
        self.router_url = f"{self.config['ai_settings']['router_base_url']}/chat/completions"
        self.text_model = self.config['ai_settings']['text_model']
        self.api_key    = self._resolve_api_key()

    def _resolve_api_key(self) -> str:
        try:
            import sqlite3
            appdata = os.environ.get("APPDATA", "")
            db_path = os.path.join(appdata, "9router", "db", "data.sqlite")
            if os.path.exists(db_path):
                con = sqlite3.connect(db_path)
                cur = con.cursor()
                row = cur.execute(
                    "SELECT key FROM apiKeys WHERE isActive = 1 ORDER BY createdAt DESC LIMIT 1"
                ).fetchone()
                con.close()
                if row and row[0]:
                    return row[0]
        except Exception:
            pass
        return os.environ.get("HERMES_CUSTOM_LOCALHOST_20128_API_KEY", "")

    def query_llm(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model"      : self.text_model,
            "messages"   : messages,
            "temperature": 0.75
        }

        req = urllib.request.Request(
            self.router_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type" : "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                full_text = []
                for line in resp:
                    line_str = line.decode("utf-8", errors="ignore").strip()
                    if line_str == "data: [DONE]":
                        break
                    if line_str.startswith("data: "):
                        try:
                            chunk   = json.loads(line_str[6:])
                            content = chunk["choices"][0].get("delta", {}).get("content", "")
                            if content:
                                full_text.append(content)
                        except Exception:
                            pass
                res_str = "".join(full_text).strip()
                if res_str:
                    return res_str
                raise ValueError("Respons Gemini kosong.")
        except Exception as e:
            print(f" [!] Gagal terhubung ke Gemini ({e}).")
            raise e

    def generate_seo_metadata(
        self,
        formula_name: str,
        duration_minutes: int = 60,
        formula_key: str = "1"
    ) -> Dict[str, Any]:
        """
        Generate SEO metadata yang unik per formula + seasonal aware.
        Setiap formula punya hook, bracket, dan tags sendiri.
        """
        import random

        season      = _get_seasonal_context()
        fdata       = FORMULA_SEO.get(str(formula_key), FORMULA_SEO["1"])
        hook        = random.choice(fdata["hook_pool"])
        bracket     = random.choice(fdata["bracket_pool"])
        emoji       = fdata["emoji"]
        intent      = fdata["intent"]
        tags_base   = fdata["tags_base"]

        system_prompt = (
            "You are a top YouTube SEO strategist and growth expert for aesthetic music channels "
            "like Lofi Girl, Chillhop Music, and Cozy Rain. "
            "You write highly clickable titles and rich descriptions that rank on YouTube search. "
            "Always respond in valid JSON only, no markdown fences."
        )

        prompt = f"""Generate complete YouTube metadata for this relaxing music video:

FORMULA    : {formula_name}
DURATION   : {duration_minutes} minutes
SEASON NOW : {season['season']} — incorporate this into the title & description naturally
HOOK IDEA  : "{hook}" (use this as inspiration, rewrite creatively)
BRACKET    : [{bracket}]
EMOJI STYLE: {emoji}
INTENT     : Primary viewer intent = {intent}

=== TITLE RULES (CRITICAL) ===
1. Max 90 characters. Start with an emotional hook then theme then bracket.
2. Include 1-2 emojis from: {emoji}
3. Must include the bracket [{bracket}] at the end.
4. Seasonal angle: "{season['mood']}" — weave this feeling into the title.
5. NEVER use: "Episode", "Track", "Volume", "Part", generic numbers.
6. Examples of GOOD title format:
   - "Rainy Autumn Evening ☕ Piano & Soft Rain [432Hz / Deep Sleep]"
   - "Late Night Coding Session 🌙 Lofi Beats [Deep Focus / No Ads]"

=== DESCRIPTION RULES ===
1. Opening: 2-3 sentences painting the {season['season']} atmosphere + emotional benefit.
2. This EXACT line (keep it): "🎧 Use headphones at 40-50% volume for the best spatial audio experience."
3. Timestamps: Generate realistic track listing for {duration_minutes} minutes.
   - Start at 00:00, space tracks 3-6 minutes apart.
   - Give each track an evocative name (e.g. "First Light", "Amber Glow", "Midnight Drift").
   - Format: "00:00 - Track Name"
4. Chapters: After tracklist, add "⏱️ CHAPTERS:" with 3 phase markers (e.g. 00:00 Opening, 20:00 Deep Focus, 40:00 Wind Down).
5. Outro: Ask viewers to like, subscribe to Cozy Mood Lounge, and share with a friend who needs peace.
6. Exactly 5 hashtags: mix of formula-specific + seasonal (e.g. #AutumnLofi #DeepSleep #432Hz #CozyVibes #StudyMusic).

=== TAGS RULES ===
Generate 20 comma-separated tags. Mix these base tags with seasonal variants:
Base: {tags_base}
Add: {season['keywords']}
Total must be under 490 characters.

=== IMAGE PROMPT RULES ===
30-45 words. Vivid Makoto Shinkai + Studio Ghibli style.
Scene must match: {formula_name} + {season['visual']}.
Props: warm desk lamp, steaming mug, {season['mood']} atmosphere.
Style: vibrant warm golden interior vs deep twilight/navy blue outside. No text. No people.

Return EXACTLY this JSON:
{{
  "title": "...",
  "description": "...",
  "tags": "...",
  "image_prompt": "..."
}}"""

        try:
            raw = self.query_llm(prompt, system_prompt=system_prompt)

            # Bersihkan JSON dari markdown fence kalau ada
            match = re.search(r'\{[\s\S]*\}', raw)
            clean = match.group(0).strip() if match else raw.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[-1]
            if clean.endswith("```"):
                clean = clean.rsplit("```", 1)[0]
            clean = clean.strip()

            data = json.loads(clean)

            # Pastikan spatial audio notice selalu ada
            notice = "🎧 Use headphones at 40-50% volume for the best spatial audio experience."
            if "headphones" not in data.get("description", "").lower():
                data["description"] = notice + "\n\n" + data.get("description", "")

            # Inject tags base kalau tags dari AI terlalu pendek
            ai_tags = data.get("tags", "")
            if len(ai_tags) < 100:
                data["tags"] = f"{ai_tags}, {tags_base}"

            return data

        except Exception as e:
            print(f" [!] Gemini SEO gagal ({e}), pakai fallback lokal.")
            return self._fallback_seo(formula_name, duration_minutes, fdata, season, hook, bracket, emoji)

    def _fallback_seo(
        self, formula_name, duration_minutes, fdata, season, hook, bracket, emoji
    ) -> Dict[str, Any]:
        """Fallback SEO lokal kalau Gemini tidak response — tetap unik per formula."""
        import random
        title = f"{emoji} {hook} [{bracket}]"
        if len(title) > 90:
            title = title[:87] + "..."

        # Generate tracklist realistis
        tracks = [
            "First Light", "Amber Glow", "Gentle Drift", "Midnight Whisper",
            "Soft Haze", "Warm Embers", "Golden Hour", "Still Waters",
            "Evening Mist", "Quiet Moments", "Deep Breath", "Final Peace"
        ]
        random.shuffle(tracks)
        tracklist = ""
        t = 0
        for i, name in enumerate(tracks[:max(4, duration_minutes // 5)]):
            m, s = divmod(t, 60)
            tracklist += f"{m:02d}:{s:02d} - {name}\n"
            t += random.randint(180, 360)
            if t >= duration_minutes * 60:
                break

        tags = f"{fdata['tags_base']}, {season['keywords']}"

        desc = (
            f"Immerse yourself in {duration_minutes} minutes of {formula_name.lower()} — "
            f"the perfect {season['season'].lower()} companion for {fdata['intent']}.\n\n"
            f"🎧 Use headphones at 40-50% volume for the best spatial audio experience.\n\n"
            f"🎵 TRACKLIST:\n{tracklist}\n"
            f"🔔 Subscribe to Cozy Mood Lounge for daily sessions.\n\n"
            f"#{season['season'].split('/')[0].strip().replace(' ', '')}Lofi "
            f"#CozyVibes #432Hz #{fdata['intent'].capitalize()}Music #RelaxingMusic"
        )

        return {
            "title"       : title,
            "description" : desc,
            "tags"        : tags[:490],
            "image_prompt": (
                f"cozy {formula_name.lower()} scene, {season['visual']}, "
                f"warm golden desk lamp, steaming coffee mug, Makoto Shinkai Studio Ghibli style, "
                f"vibrant colors, deep twilight blue outside, no text, no people"
            )
        }

    def generate_and_download_image(self, prompt: str, output_filename: str = None) -> str:
        """Download gambar Makoto Shinkai style dari Pollinations Flux + auto-crop watermark."""
        if output_filename is None:
            output_filename = f"bg_{int(time.time())}.jpg"

        bg_dir    = os.path.join(self.base_dir, self.config["paths"]["assets_backgrounds"])
        os.makedirs(bg_dir, exist_ok=True)
        dest_path = os.path.join(bg_dir, output_filename)

        target_w = int(self.config["ai_settings"]["image_resolution"]["width"])
        target_h = int(self.config["ai_settings"]["image_resolution"]["height"])

        req_w, req_h = 1280, 780   # 780px agar watermark ada di 60px terbawah

        clean_prompt = re.sub(
            r"\b(photorealistic|photography|photo)\b", "", prompt, flags=re.IGNORECASE
        ).strip(" ,.")

        style_lock = (
            "masterpiece anime background illustration by Makoto Shinkai and Studio Ghibli, "
            f"{clean_prompt}, cozy warm golden lamp glow contrasting with deep twilight blue atmosphere, "
            "lofi chillhop aesthetic, rich vibrant colors, crisp clean linework, everything in sharp focus, 8k"
        )

        encoded = urllib.parse.quote(style_lock)
        seed    = int(time.time()) % 100000
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?model=flux&width={req_w}&height={req_h}&seed={seed}&nologo=true&enhance=true"
        )

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )

        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(req, timeout=65) as resp:
                    img_data = resp.read()

                if len(img_data) > 10000:
                    if PIL_AVAILABLE:
                        raw_img = Image.open(io.BytesIO(img_data)).convert("RGB")
                        raw_img = raw_img.resize((req_w, req_h), Image.Resampling.LANCZOS)
                        # Potong 60px bawah = buang watermark Pollinations
                        cropped = raw_img.crop((0, 0, req_w, req_h - 60))
                        if (target_w, target_h) != (cropped.width, cropped.height):
                            cropped = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
                        cropped.save(dest_path, "JPEG", quality=95, optimize=True)
                    else:
                        with open(dest_path, "wb") as f:
                            f.write(img_data)
                    return dest_path
            except Exception as e:
                print(f" [!] Attempt {attempt}/3 gagal: {e}")
                time.sleep(3)

        raise RuntimeError("Gagal download gambar dari Pollinations Flux setelah 3x.")


if __name__ == "__main__":
    ai = AIService()
    print("=== Test SEO Generation per Formula ===\n")
    season = _get_seasonal_context()
    print(f"Musim sekarang: {season['season']}\n")

    for key, fdata in FORMULA_SEO.items():
        print(f"--- Formula {key}: {fdata['persona']} ---")
        seo = ai.generate_seo_metadata(fdata["persona"], 60, formula_key=key)
        print(f"Title : {seo.get('title')}")
        print(f"Tags  : {seo.get('tags', '')[:80]}...")
        print()
