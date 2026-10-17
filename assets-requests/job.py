"""Real sound for the farm video: CC0 animal recordings (BigSoundBank, OpenGameArt) and public-domain music (FreePD).
Everything is listed in assets-requests/out/sound.json; audio lands in assets-requests/out/sound/ (music is
re-encoded to 128 kb/s so the candidates stay small)."""
import json
import os
import re
import subprocess
from urllib.parse import urljoin, quote

import requests

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
OUT = "assets-requests/out/sound"
os.makedirs(OUT + "/animals", exist_ok=True)
os.makedirs(OUT + "/music", exist_ok=True)
os.makedirs("assets-requests/out/pages", exist_ok=True)
subprocess.run("sudo apt-get install -y -qq ffmpeg > /dev/null", shell=True)
report = {"bigsoundbank": {}, "oga": {}, "freepd": {}}
AUDIO = (".mp3", ".wav", ".ogg", ".flac")


def get(url, **k):
    try:
        r = S.get(url, timeout=k.pop("timeout", 60), **k)
        print("GET", r.status_code, url, len(r.content), flush=True)
        return r
    except Exception as e:
        print("ERR", url, e, flush=True)
        return None


def save(url, path, max_mb=25):
    r = get(url, timeout=180)
    if r is not None and r.ok and len(r.content) < max_mb * 1e6:
        open(path, "wb").write(r.content)
        return True
    return False


ANIMALS = {"cow": ["cow"], "horse": ["horse", "neigh"], "pig": ["pig"], "sheep": ["sheep"], "goat": ["goat"],
           "chicken": ["hen", "chicken"], "rooster": ["rooster"], "chick": ["chick"], "duck": ["duck"], "goose": ["goose"]}

# BigSoundBank (Joseph Sardin): every sound is CC0
for kind, qs in ANIMALS.items():
    found = []
    for q in qs:
        r = get(f"https://bigsoundbank.com/search?q={quote(q)}")
        if r is None or not r.ok:
            continue
        open(f"assets-requests/out/pages/bsb_{q}.html", "w").write(r.text)
        pages = [urljoin(r.url, h) for h in re.findall(r'href="([^"]+)"', r.text)
                 if re.search(r"(sound-\d+|/detail-|\d+-[a-z0-9-]+\.html)", h)]
        direct = [urljoin(r.url, h) for h in re.findall(r'(?:href|src|data-src)="([^"]+)"', r.text) if h.lower().endswith(AUDIO)]
        for p in list(dict.fromkeys(pages))[:12]:
            rp = get(p)
            if rp is None or not rp.ok:
                continue
            title = re.findall(r"<title>([^<]+)", rp.text)
            links = [urljoin(rp.url, h) for h in re.findall(r'(?:href|src|data-src)="([^"]+)"', rp.text) if h.lower().split("?")[0].endswith(AUDIO)]
            found.append({"page": p, "title": title[0].strip() if title else "", "audio": list(dict.fromkeys(links))})
        for d in direct[:12]:
            found.append({"page": r.url, "title": os.path.basename(d), "audio": [d]})
    n = 0
    for it in found:
        if not re.search("|".join(qs), (it["title"] + " " + it["page"]).lower()):
            continue
        for a in it["audio"][:1]:
            fn = f"{OUT}/animals/bsb_{kind}_{n:02d}" + os.path.splitext(a.split("?")[0])[1]
            if save(a, fn):
                it["file"] = fn
                n += 1
        if n >= 6:
            break
    report["bigsoundbank"][kind] = found

# OpenGameArt: CC0 sound effects (type 13), most popular first
for kind, qs in ANIMALS.items():
    hits = []
    for q in qs:
        r = get("https://opengameart.org/art-search-advanced?keys=" + quote(q) +
                "&field_art_type_tid%5B%5D=13&field_art_licenses_tid%5B%5D=4&sort_by=count&sort_order=DESC")
        if r is not None and r.ok:
            hits += [h for h in re.findall(r'href="(/content/[^"]+)"', r.text) if h != "/content/faq"]
    hits = list(dict.fromkeys(hits))[:6]
    got = []
    for h in hits:
        rp = get("https://opengameart.org" + h)
        if rp is None or not rp.ok:
            continue
        lic = sorted(set(re.findall(r'(CC0|CC-BY-SA \d\.\d|CC-BY \d\.\d|GPL \d\.\d|OGA-BY \d\.\d)', rp.text)))
        files = [f for f in re.findall(r'href="(https://opengameart\.org/sites/default/files/[^"]+)"', rp.text) if f.lower().endswith(AUDIO)]
        ent = {"page": h, "licence": lic, "files": files[:6], "saved": []}
        if lic == ["CC0"]:
            for f in files[:4]:
                fn = f"{OUT}/animals/oga_{kind}_{len(got):02d}_" + re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(f))[-40:]
                if save(f, fn, 15):
                    ent["saved"].append(fn)
        got.append(ent)
    report["oga"][kind] = got

# FreePD: public-domain (CC0) music. Keep the upbeat / kids / light tracks as 128 kb/s candidates.
idx = get("https://freepd.com/")
cats = []
if idx is not None and idx.ok:
    open("assets-requests/out/pages/freepd_index.html", "w").write(idx.text)
    cats = list(dict.fromkeys(urljoin(idx.url, h) for h in re.findall(r'href="([^"]+\.php)"', idx.text)))
print("FREEPD categories", cats, flush=True)
for c in cats:
    r = get(c)
    if r is None or not r.ok:
        continue
    tracks = list(dict.fromkeys(urljoin(r.url, h) for h in re.findall(r'(?:href|src)="([^"]+\.mp3)"', r.text)))
    report["freepd"][c] = tracks
    print("FREEPD", c, len(tracks), [os.path.basename(t) for t in tracks], flush=True)
keep_cats = [c for c in report["freepd"] if re.search(r"upbeat|world|misc|comedy|kids|happy|light|piano|scoring", c, re.I)]
n = 0
for c in keep_cats:
    for t in report["freepd"][c]:
        if n >= 45:
            break
        name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(t).replace("%20", " "))
        tmp = f"/tmp/{name}"
        if save(t, tmp, 30):
            cat = os.path.basename(c).replace(".php", "")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-b:a", "128k", f"{OUT}/music/{cat}__{name}"])
            n += 1
json.dump(report, open("assets-requests/out/sound.json", "w"), indent=1)
print(subprocess.run(["du", "-sh", OUT + "/animals", OUT + "/music"], capture_output=True, text=True).stdout)
