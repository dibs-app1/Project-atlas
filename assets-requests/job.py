"""OpenGameArt: download CC0 3D packs (Quaternius mirrors and more) and search for the animals still missing."""
import glob
import os
import re
import shutil
import zipfile

import requests

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
BASE = "https://opengameart.org"


def page(path):
    r = S.get(BASE + path, timeout=60)
    html = r.text
    files = sorted(set(re.findall(r'href="(https://opengameart\.org/sites/default/files/[^"]+)"', html)))
    lic = sorted(set(re.findall(r'(CC0|CC-BY-SA \d\.\d|CC-BY \d\.\d|GPL \d\.\d|OGA-BY \d\.\d)', html)))
    title = re.findall(r'<title>([^<]+)</title>', html)
    author = re.findall(r'Author:.*?<a[^>]*>([^<]+)</a>', html, re.S)[:1]
    return dict(files=files, lic=lic, title=title, author=author)


def grab(name, path):
    info = page(path)
    print("PAGE", path, info["title"], info["lic"], info["author"])
    for f in info["files"]:
        print("    FILE", f)
    if "CC0" not in info["lic"]:
        print("    skip: not CC0")
        return
    for f in info["files"]:
        if not f.lower().endswith((".zip", ".glb", ".gltf", ".fbx", ".blend")):
            continue
        r = S.get(f, timeout=300)
        print("    DL", f, r.status_code, len(r.content))
        if not r.ok or len(r.content) > 120e6:
            continue
        d = f"/tmp/oga/{name}"
        os.makedirs(d, exist_ok=True)
        fn = os.path.join(d, os.path.basename(f))
        open(fn, "wb").write(r.content)
        if fn.endswith(".zip"):
            try:
                with zipfile.ZipFile(fn) as z:
                    z.extractall(fn[:-4])
            except Exception as e:
                print("    ZIP ERR", e)
    for f in sorted(glob.glob(f"/tmp/oga/{name}/**/*", recursive=True)):
        if os.path.isfile(f):
            low = f.lower()
            print("      ", os.path.relpath(f, f"/tmp/oga/{name}"), os.path.getsize(f))
            if low.endswith((".gltf", ".glb", ".bin", ".fbx")) or ("gltf" in low and low.endswith((".png", ".jpg"))) or \
                    ("textures" in low and low.endswith((".png", ".jpg"))):
                if os.path.getsize(f) < 40e6:
                    to = os.path.join("studio/assets/oga", name, os.path.relpath(f, f"/tmp/oga/{name}"))
                    os.makedirs(os.path.dirname(to), exist_ok=True)
                    shutil.copy(f, to)


for name, path in [("farm_animals", "/content/lowpoly-animated-farm-animal-pack"), ("fish", "/content/animated-fish"),
                   ("animals5", "/content/5-low-poly-animals"), ("animales", "/content/animated-animales-low-poly"),
                   ("nature", "/content/lowpoly-nature-pack"), ("nature_megakit", "/content/stylized-nature-megakit"),
                   ("nature1", "/content/low-poly-nature-pack-1")]:
    try:
        grab(name, path)
    except Exception as e:
        print("ERR", name, e)

# search for the rest (3D art, CC0)
for q in ["cat", "kitten", "dog", "puppy", "bird", "chicken", "hen", "duck", "penguin", "owl", "parrot", "seagull", "eagle",
          "swan", "flamingo", "pigeon", "dolphin", "whale", "turtle", "crab", "jellyfish", "goat", "rabbit", "butterfly",
          "quaternius", "animated animal", "low poly animal"]:
    try:
        r = S.get(BASE + "/art-search-advanced?keys=" + q.replace(" ", "+") + "&field_art_type_tid%5B%5D=10&field_art_licenses_tid%5B%5D=4&sort_by=count&sort_order=DESC", timeout=60)
        hits = sorted(set(re.findall(r'href="(/content/[^"]+)"', r.text)) - {"/content/faq", "/content/october-2026-art-challenge-phobias"})
        print("SEARCH", q, hits[:25])
    except Exception as e:
        print("SEARCH ERR", q, e)
