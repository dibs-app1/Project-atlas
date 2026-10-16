"""Quaternius CC0 packs: list Drive files, fetch the glTF ones via the direct endpoint; also look at OpenGameArt mirrors."""
import os
import re

import gdown
import requests

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
PACKS = {
    "farmanimal": "1is1ax2V0mIEDS7BbbzBV_x2Pabya1dVJ",
    "ultimateanimatedanimals": "1uJ3N5HfB7jKTseJUNQr3N4YaN0UuEtHk",
    "animatedfish": "1SvlOveJJjmhSn-FgCRyojc1T5QHjjGkF",
    "cutefish": "1QK5NCgIxUZ1cYGzVwaNfcfEiQhvczqUB",
    "ultimatestylizednature": "1IV3bXHzkNvuNWFHPi4KPx-G4ghuxIuT-",
    "farmbuildings": "1gdZ39vcLML_ULU5sHirkKQ-gEkk458Ak",
}


def direct(fid, to):
    for url in (f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t",
                f"https://drive.google.com/uc?export=download&id={fid}&confirm=t"):
        try:
            r = S.get(url, timeout=120)
            ct = r.headers.get("content-type", "")
            if r.ok and "text/html" not in ct and len(r.content) > 100:
                os.makedirs(os.path.dirname(to), exist_ok=True)
                open(to, "wb").write(r.content)
                return len(r.content)
            print("   miss", url[:60], r.status_code, ct, len(r.content))
        except Exception as e:
            print("   err", e)
    return 0


for name, fid in PACKS.items():
    print("=====", name, flush=True)
    try:
        files = gdown.download_folder(id=fid, skip_download=True, quiet=True)
    except Exception as e:
        print("LIST ERR", e)
        continue
    print("LISTED", len(files))
    for f in files:
        print("   ", f.path, f.id)
    for f in files:
        low = f.path.lower()
        if "gltf" in low or low.endswith(".glb") or low.endswith(".bin") and "gltf" in low:
            n = direct(f.id, os.path.join("studio/assets/quaternius", name, f.path))
            print("GOT" if n else "FAIL", f.path, n, flush=True)

# OpenGameArt mirrors of Quaternius packs
for q in ["quaternius animal", "quaternius fish", "quaternius farm", "quaternius nature"]:
    try:
        r = S.get("https://opengameart.org/art-search-advanced?keys=" + q.replace(" ", "+") + "&field_art_type_tid%5B%5D=10", timeout=60)
        print("OGA", q, r.status_code)
        for m in sorted(set(re.findall(r'href="(/content/[^"]+)"', r.text)))[:40]:
            print("   ", m)
    except Exception as e:
        print("OGA ERR", e)
