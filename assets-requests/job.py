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
        if not f.lower().endswith((".zip", ".glb", ".gltf", ".fbx", ".blend", ".png", ".jpg", ".bin", ".rar")):
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
    for f in sorted(glob.glob(f"/tmp/oga/{name}/**/*", recursive=True)):
        if os.path.isfile(f) and not f.endswith(".zip"):
            low = f.lower()
            print("      ", os.path.relpath(f, f"/tmp/oga/{name}"), os.path.getsize(f))
            if low.endswith((".gltf", ".glb", ".bin", ".fbx", ".blend", ".png", ".jpg")) and os.path.getsize(f) < 30e6:
                to = os.path.join("studio/assets/oga", name, os.path.relpath(f, f"/tmp/oga/{name}"))
                os.makedirs(os.path.dirname(to), exist_ok=True)
                shutil.copy(f, to)


for name, path in [("duck", "/content/rigged-duck"), ("duckling", "/content/rigged-duckling"), ("chicken", "/content/chicken-animated"),
                   ("rooster", "/content/rooster-animated"), ("penguin", "/content/penguin-low-poly-animated-3d-model"),
                   ("pinguin", "/content/pinguin-low-poly"), ("pigeon", "/content/low-poly-3d-pigeon-model-rigged-animated-untextured"),
                   ("turtle", "/content/turtle-low-poly"), ("turtle0", "/content/turtle-0"),
                   ("crab", "/content/crab-low-poly-animated-3d-model"), ("goat", "/content/goat"),
                   ("goat2", "/content/3d-goat-animation-for-game"), ("rabbit", "/content/rabbit-0"),
                   ("butterfly", "/content/butterfly-animated"), ("frog", "/content/frog-low-poly-animated-3d-model"),
                   ("angelfish", "/content/low-poly-angel-fish"), ("fish_animated", "/content/fish-animated"),
                   ("esox", "/content/esox-animated-fish"), ("bird", "/content/bird"), ("bird1", "/content/bird-1"),
                   ("blackbird", "/content/black-bird"), ("shrike", "/content/bird-yellow-billed-shrike"),
                   ("pond_kit", "/content/free-lowpoly-pond-kit"), ("cube_pets", "/content/cube-pets"),
                   ("dog_rigged", "/content/dog-low-poly-rigged"), ("simple_cat", "/content/simple-cat"),
                   ("crops", "/content/lowpoly-crops-pack"), ("farm_buildings", "/content/lowpoly-buildings"),
                   ("whale_lp", "/content/whale-lowpoly"), ("manatee", "/content/low-poly-manatee-with-hand-painted-textures")]:
    try:
        grab(name, path)
    except Exception as e:
        print("ERR", name, e)
