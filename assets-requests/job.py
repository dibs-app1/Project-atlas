"""Explore the free CC0 model libraries: what animal / nature models exist and how to download them."""
import json
import re

import requests

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (studio asset librarian)"
out = {}


def get(url, **kw):
    try:
        r = S.get(url, timeout=40, **kw)
        print("GET", url, r.status_code, len(r.content))
        return r
    except Exception as e:
        print("GET", url, "ERR", e)
        return None


# 1. Poly Haven (CC0): models and skies
r = get("https://api.polyhaven.com/assets?t=models")
if r is not None and r.ok:
    d = r.json()
    out["polyhaven_models"] = {k: v.get("categories") for k, v in d.items()}
    print("polyhaven models:", len(d))
r = get("https://api.polyhaven.com/assets?t=hdris&c=skies")
if r is not None and r.ok:
    out["polyhaven_skies"] = sorted(r.json().keys())
r = get("https://api.polyhaven.com/files/tree_small_02")
if r is not None and r.ok:
    out["polyhaven_files_example"] = r.json()

# 2. Poly Pizza search pages (many Quaternius CC0 animated animals)
pp = {}
for q in ["cow", "pig", "sheep", "horse", "chicken", "duck", "dog", "cat", "fish", "bird", "parrot", "penguin", "owl", "goat",
          "donkey", "dolphin", "whale", "turtle", "crab", "jellyfish", "seagull", "eagle", "swan", "flamingo", "pigeon", "shark",
          "octopus", "rooster", "quaternius animal", "animated animal"]:
    r = get("https://poly.pizza/search/" + q.replace(" ", "%20"))
    if r is not None and r.ok:
        html = r.text
        pp[q] = {"models": sorted(set(re.findall(r'/m/([A-Za-z0-9_-]{6,})', html)))[:40],
                 "glb": sorted(set(re.findall(r'https://static\.poly\.pizza/[^"\' ]+', html)))[:40],
                 "snippet": html[:1500] if q == "cow" else ""}
out["polypizza"] = pp
r = get("https://poly.pizza/m/" + (pp.get("cow", {}).get("models") or ["x"])[0])
if r is not None:
    out["polypizza_model_page"] = r.text[:20000]

# 3. Quaternius packs
r = get("https://quaternius.com/")
if r is not None and r.ok:
    out["quaternius_links"] = sorted(set(re.findall(r'href="([^"]+)"', r.text)))
    for link in out["quaternius_links"]:
        if "pack" in link and ("animal" in link.lower() or "farm" in link.lower() or "fish" in link.lower() or "bird" in link.lower()):
            u = link if link.startswith("http") else "https://quaternius.com/" + link.lstrip("/")
            rr = get(u)
            if rr is not None:
                out.setdefault("quaternius_pages", {})[u] = sorted(set(re.findall(r'href="([^"]+)"', rr.text)))

# 4. Kenney
r = get("https://kenney.nl/assets/category:3D")
if r is not None:
    out["kenney"] = sorted(set(re.findall(r'href="(https://kenney\.nl/assets/[^"]+)"', r.text)))

json.dump(out, open("assets-requests/out/explore.json", "w"), indent=1)
print("done")
