"""
Preview & Test Thumbnail Generator v4
Render ulang semua 5 formula sekaligus.
Output: output/thumbnail_preview/
"""
import os
import glob
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
from thumbnail_gen import generate_thumbnail

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACCENT   = "#F5C518"
BRAND    = "Cozy Mood Lounge"
OUT_DIR  = os.path.join(BASE_DIR, "output", "thumbnail_preview")
os.makedirs(OUT_DIR, exist_ok=True)

# Semua formula — intent sinkron, tidak ada kontradiksi
TEST_CASES = [
    {
        "name" : "1_piano_rain_sleep",
        "title": "Fall Asleep in Peace Cozy Rain & Piano [432Hz / Deep Sleep]",
    },
    {
        "name" : "2_bossa_nova_chill",
        "title": "Sunny Morning Bossa Nova & Coffee Cafe [Lofi Chill / Good Morning Vibes]",
    },
    {
        "name" : "3_lofi_focus",
        "title": "Lofi Chillhop & Cozy Midnight Room [Deep Focus / No Distractions]",
    },
    {
        "name" : "4_dark_academia_study",
        "title": "Dark Academia & Victorian Library [Study Session / Classical Ambience]",
    },
    {
        "name" : "5_acoustic_relax",
        "title": "Peaceful Acoustic Guitar & Forest Stream [Stress Relief / Nature Sounds]",
    },
]


def main():
    bg_dir = os.path.join(BASE_DIR, "assets", "backgrounds")
    bgs = sorted([
        f for ext in ("*.jpg", "*.jpeg", "*.png", "*.jfif", "*.webp")
        for f in glob.glob(os.path.join(bg_dir, ext))
        if not os.path.basename(f).startswith("thumb_")
    ])

    if not bgs:
        print("[!] Tidak ada background di assets/backgrounds/")
        return

    print(f"[*] {len(bgs)} background ditemukan.")
    print(f"[*] Render ulang {len(TEST_CASES)} thumbnail (v4)...\n")

    results = []
    for i, case in enumerate(TEST_CASES):
        bg       = bgs[i % len(bgs)]
        out_path = os.path.join(OUT_DIR, f"{case['name']}.jpg")

        print(f"[{i+1}/{len(TEST_CASES)}] {case['name']}")
        print(f"    Judul : {case['title']}")
        print(f"    BG    : {os.path.basename(bg)}")

        result = generate_thumbnail(
            background_path=bg,
            title=case["title"],
            output_path=out_path,
            accent=ACCENT,
            brand=BRAND
        )
        if result:
            kb = os.path.getsize(result) / 1024
            print(f"    Size  : {kb:.1f} KB")
            results.append(result)
        print()

    print(f"[DONE] {len(results)}/{len(TEST_CASES)} thumbnail selesai.")
    print(f"Folder: {OUT_DIR}\n")
    try:
        os.startfile(OUT_DIR)
    except Exception:
        pass


if __name__ == "__main__":
    main()
