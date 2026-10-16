"""OpenGameArt: more CC0 animals (birds, duck, hen, penguin, turtle, crab, goat, rabbit, butterfly, frog, angelfish)."""
import glob
import os
import re
import shutil
import zipfile

import requests

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
BASE = "https://opengameart.org"


def grab(name, path):
    r = S.get(BASE + path, timeout=60)
    html = r.text
    files = sorted(set(re.findall(r'href="(https://opengameart\.org/sites/default/files/[^"]+)"', html)))
    lic = sorted(set(re.findall(r'(CC0|CC-BY-SA \d\.\d|CC-BY \d\.\d|GPL \d\.\d|OGA-BY \d\.\d)', html)))
    author = re.findall(r'Author:.*?<a[^>]*>([^<]+)</a>', html, re.S)[:1]
    print("PAGE", path, lic, author, len(files))
    if lic != ["CC0"]:
        print("    skip: licence", lic)
        return
    for f in files:
        print("    FILE", f)
        if f.lower().endswith((".png", ".jpg", ".gif")) and "preview" in f.lower() or "capture" in f.lower():
            continue
        rr = S.get(f, timeout=300)
        print("    DL", f, rr.status_code, len(rr.content))
        if not rr.ok or len(rr.content) > 60e6:
            continue
        d = f"/tmp/oga/{name}"
        os.makedirs(d, exist_ok=True)
        fn = os.path.join(d, os.path.basename(f))
        open(fn, "wb").write(rr.content)
        if fn.endswith(".zip"):
            try:
                with zipfile.ZipFile(fn) as z:
                    z.extractall(fn[:-4])
            except Exception as e:
                print("    ZIP ERR", e)
        elif fn.lower().endswith((".7z", ".rar", ".tar.gz", ".tgz")):
            os.system(f'7z x -y -o"{fn}_x" "{fn}" > /dev/null')
    for f in sorted(glob.glob(f"/tmp/oga/{name}/**/*", recursive=True)):
        if os.path.isfile(f) and not f.endswith(".zip"):
            low = f.lower()
            print("      ", os.path.relpath(f, f"/tmp/oga/{name}"), os.path.getsize(f))
            if low.endswith((".gltf", ".glb", ".bin", ".fbx", ".blend", ".png", ".jpg", ".obj", ".mtl", ".dae")) and os.path.getsize(f) < 30e6:
                to = os.path.join("studio/assets/oga", name, os.path.relpath(f, f"/tmp/oga/{name}"))
                os.makedirs(os.path.dirname(to), exist_ok=True)
                shutil.copy(f, to)


for name, path in [("penguin", "/content/penguin-low-poly-animated-3d-model"), ("pinguin", "/content/pinguin-low-poly"),
                   ("turtle", "/content/turtle-low-poly"), ("goat", "/content/goat"), ("frog", "/content/frog-low-poly-animated-3d-model"),
                   ("bird1", "/content/bird-1")]:
    try:
        grab(name, path)
    except Exception as e:
        print("ERR", name, e)
