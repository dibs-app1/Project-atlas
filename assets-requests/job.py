"""Fetch Quaternius CC0 animal packs (glTF), list Poly Haven nature models and skies."""
import glob
import json
import os
import re
import shutil
import subprocess
import zipfile

import requests

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (studio asset librarian)"
out = {}
os.makedirs("assets-requests/out", exist_ok=True)


def get(url, **kw):
    try:
        r = S.get(url, timeout=60, **kw)
        print("GET", url, r.status_code, len(r.content))
        return r
    except Exception as e:
        print("GET", url, "ERR", e)
        return None


home = get("https://quaternius.com/")
packs = sorted(set(re.findall(r'href="(/?packs/[^"]+\.html)"', home.text)))
print("PACKS", packs)
out["packs"] = packs
want = [p for p in packs if any(k in p.lower() for k in ("animal", "fish", "bird", "farm", "nature", "pet", "dog", "cat"))]
print("WANT", want)
for p in want:
    u = "https://quaternius.com/" + p.lstrip("/")
    r = get(u)
    if r is None:
        continue
    links = sorted(set(re.findall(r'href="([^"]+)"', r.text)))
    lic = re.findall(r'(CC0[^<]{0,80}|[Pp]ublic [Dd]omain[^<]{0,60})', r.text)[:3]
    title = re.findall(r'<title>([^<]+)</title>', r.text)
    print("PAGE", u, title, lic)
    for l in links:
        print("   LINK", l)
    out.setdefault("pages", {})[u] = dict(links=links, license=lic, title=title)
    name = os.path.basename(p).replace(".html", "")
    drive = [l for l in links if "drive.google" in l or "dropbox" in l or l.endswith(".zip")]
    for k, l in enumerate(drive[:2]):
        dest = f"/tmp/dl/{name}_{k}"
        os.makedirs(dest, exist_ok=True)
        try:
            if "drive.google" in l:
                subprocess.run(["gdown", "--fuzzy", l, "-O", dest + "/"], check=False, timeout=900)
            else:
                rr = get(l)
                open(dest + "/pack.zip", "wb").write(rr.content)
        except Exception as e:
            print("DL ERR", e)
        for z in glob.glob(dest + "/*.zip"):
            try:
                with zipfile.ZipFile(z) as zf:
                    names = zf.namelist()
                    print("ZIP", z, len(names), os.path.getsize(z))
                    for n in names[:400]:
                        print("    ", n)
                    zf.extractall(dest + "/x")
            except Exception as e:
                print("ZIP ERR", z, e)
        # keep only glTF / glb files (and their textures/bins) in the repo
        for f in glob.glob(dest + "/x/**/*", recursive=True):
            low = f.lower()
            if os.path.isfile(f) and ("gltf" in low or low.endswith(".glb")) and os.path.getsize(f) < 30e6:
                rel = os.path.relpath(f, dest + "/x")
                to = os.path.join("studio/assets/quaternius", name, rel)
                os.makedirs(os.path.dirname(to), exist_ok=True)
                shutil.copy(f, to)

# Poly Haven: nature models (trees, rocks, plants, grass) and skies
r = get("https://api.polyhaven.com/assets?t=models")
if r is not None and r.ok:
    d = r.json()
    out["polyhaven_models"] = {k: v.get("categories") for k, v in d.items()}
    for k, v in sorted(d.items()):
        print("PH", k, v.get("categories"))
r = get("https://api.polyhaven.com/assets?t=hdris&c=skies")
if r is not None and r.ok:
    out["polyhaven_skies"] = sorted(r.json().keys())
    print("SKIES", out["polyhaven_skies"])
r = get("https://api.polyhaven.com/files/tree_small_02")
if r is not None and r.ok:
    print("FILES", json.dumps(r.json())[:3000])
json.dump(out, open("assets-requests/out/explore.json", "w"), indent=1)
print("TOTAL", subprocess.run(["du", "-sh", "studio/assets"], capture_output=True, text=True).stdout)
print("done")
