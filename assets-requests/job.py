"""Download the Quaternius CC0 packs (Google Drive folders) and keep their glTF models in studio/assets."""
import glob
import os
import shutil
import subprocess
import zipfile

PACKS = {
    "farmanimal": "1is1ax2V0mIEDS7BbbzBV_x2Pabya1dVJ",
    "ultimateanimatedanimals": "1uJ3N5HfB7jKTseJUNQr3N4YaN0UuEtHk",
    "animatedfish": "1SvlOveJJjmhSn-FgCRyojc1T5QHjjGkF",
    "cutefish": "1QK5NCgIxUZ1cYGzVwaNfcfEiQhvczqUB",
    "ultimatestylizednature": "1IV3bXHzkNvuNWFHPi4KPx-G4ghuxIuT-",
    "farmbuildings": "1gdZ39vcLML_ULU5sHirkKQ-gEkk458Ak",
}
for name, fid in PACKS.items():
    dest = f"/tmp/dl/{name}"
    os.makedirs(dest, exist_ok=True)
    print("=====", name, flush=True)
    subprocess.run(["gdown", "--folder", "--remaining-ok", f"https://drive.google.com/drive/folders/{fid}", "-O", dest],
                   check=False, timeout=1500)
    for z in glob.glob(dest + "/**/*.zip", recursive=True):
        try:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(z[:-4])
            print("unzipped", z)
        except Exception as e:
            print("ZIP ERR", z, e)
    files = sorted(f for f in glob.glob(dest + "/**/*", recursive=True) if os.path.isfile(f))
    print("FILES", len(files))
    for f in files[:600]:
        print("   ", os.path.relpath(f, dest), os.path.getsize(f))
    kept = 0
    for f in files:
        low = f.lower()
        if ("gltf" in low or low.endswith(".glb")) and not low.endswith(".zip") and os.path.getsize(f) < 40e6:
            rel = os.path.relpath(f, dest)
            to = os.path.join("studio/assets/quaternius", name, rel)
            os.makedirs(os.path.dirname(to), exist_ok=True)
            shutil.copy(f, to)
            kept += 1
    print("KEPT", name, kept, flush=True)
print(subprocess.run(["du", "-sh", "studio/assets"], capture_output=True, text=True).stdout)
