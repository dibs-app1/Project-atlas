"""Second pass on real sound for the farm video.
1. BigSoundBank (CC0): read every candidate recording's own page (title, description) so imitations are left out.
2. Wikimedia Commons: animal recordings with their licences (goose, pig, hen, duck ...).
3. Music: Kevin MacLeod's catalogue (incompetech.com, CC BY 4.0: free for monetised video with a credit line),
   cheerful/bright pieces; and CC0 music from OpenGameArt. Candidates are saved as 128 kb/s mp3."""
import glob
import html
import json
import os
import re
import subprocess
from urllib.parse import quote

import requests

S = requests.Session()
S.headers["User-Agent"] = "TheCalmLittleWorldStudio/1.0 (asset librarian; https://github.com/dibs-app1/TheCalmLittleWorld)"
OUT = "assets-requests/out/sound2"
for d in ("bsb", "commons", "music"):
    os.makedirs(f"{OUT}/{d}", exist_ok=True)
subprocess.run("sudo apt-get install -y -qq ffmpeg > /dev/null", shell=True)
rep = {"bsb": {}, "commons": {}, "incompetech": [], "oga_music": []}


def get(url, **k):
    try:
        r = S.get(url, timeout=k.pop("timeout", 60), **k)
        print("GET", r.status_code, url[:150], len(r.content), flush=True)
        return r
    except Exception as e:
        print("ERR", url[:150], e, flush=True)
        return None


def clean(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


# 1. BigSoundBank detail pages
slugs = {}
for f in glob.glob("assets-requests/out/pages/bsb_*.html"):
    for slug, i in re.findall(r"href='/([a-z0-9-]+-s(\d{4})\.html)'", open(f).read()):
        slugs[i] = slug
for q in ["goose", "geese", "piglet", "pigs", "lamb", "quack", "moo", "cackle", "chicks"]:
    r = get(f"https://bigsoundbank.com/search?q={q}")
    if r is not None and r.ok:
        for slug, i in re.findall(r"href='/([a-z0-9-]+-s(\d{4})\.html)'", r.text):
            slugs[i] = slug
print("BSB candidates", len(slugs), flush=True)
for i, slug in sorted(slugs.items()):
    r = get(f"https://bigsoundbank.com/{slug}")
    if r is None or not r.ok:
        continue
    t = r.text
    h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", t, re.S)
    desc = re.findall(r'<meta name="description" content="([^"]*)"', t)
    body = re.findall(r"<div class=['\"]description['\"][^>]*>(.*?)</div>", t, re.S)
    dur = re.findall(r"(\d+:\d\d)", clean(t))
    tags = re.findall(r"href='/[a-z-]*tag[^']*'>([^<]+)<", t)
    rep["bsb"][i] = {"slug": slug, "title": clean(h1[0]) if h1 else "", "desc": html.unescape(desc[0]) if desc else "",
                     "body": clean(body[0])[:600] if body else "", "dur": dur[:3], "tags": tags[:15],
                     "mp3": f"https://bigsoundbank.com/UPLOAD/mp3/{i}.mp3"}
    print("BSB", i, rep["bsb"][i]["title"], "|", rep["bsb"][i]["desc"][:160], flush=True)
    if re.search(r"goose|geese|pig|piglet|lamb|duck|hen\b|chick|moo|cow|sheep|goat|neigh|cock|crow", (slug + rep["bsb"][i]["title"]).lower()) \
            and not os.path.exists(f"{OUT}/bsb/{i}.mp3"):
        a = get(rep["bsb"][i]["mp3"], timeout=120)
        if a is not None and a.ok and len(a.content) < 20e6:
            open(f"{OUT}/bsb/{i}.mp3", "wb").write(a.content)

# 2. Wikimedia Commons
API = "https://commons.wikimedia.org/w/api.php"
for kind, qs in {"goose": ["goose honk", "geese honking", "Anser anser call"], "pig": ["pig grunt", "pig oink", "Sus domesticus sound"],
                 "hen": ["hen clucking", "chicken clucking"], "duck": ["duck quack", "mallard quack"], "cow": ["cow moo"],
                 "sheep": ["sheep bleat"], "goat": ["goat bleat"], "horse": ["horse neigh", "horse whinny"],
                 "rooster": ["rooster crow"], "chick": ["chick peep", "chicks peeping"]}.items():
    seen = []
    for q in qs:
        r = get(API, params={"action": "query", "format": "json", "list": "search", "srnamespace": 6, "srlimit": 15,
                             "srsearch": f"{q} filetype:audio"})
        if r is None or not r.ok:
            continue
        for hit in r.json().get("query", {}).get("search", []):
            if hit["title"] not in seen:
                seen.append(hit["title"])
    infos = []
    for tchunk in [seen[i:i + 20] for i in range(0, len(seen), 20)]:
        r = get(API, params={"action": "query", "format": "json", "titles": "|".join(tchunk), "prop": "imageinfo",
                             "iiprop": "url|extmetadata|size|mime", "iiextmetadatafilter": "LicenseShortName|Artist|ImageDescription"})
        if r is None or not r.ok:
            continue
        for p in r.json().get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            md = ii.get("extmetadata", {})
            lic = md.get("LicenseShortName", {}).get("value", "")
            ent = {"title": p.get("title"), "url": ii.get("url"), "lic": lic, "size": ii.get("size"),
                   "artist": clean(md.get("Artist", {}).get("value", ""))[:80],
                   "desc": clean(md.get("ImageDescription", {}).get("value", ""))[:200]}
            infos.append(ent)
            print("COMMONS", kind, lic, ent["title"], ent["size"], "|", ent["desc"][:100], flush=True)
            ok = re.search(r"public domain|cc0|^pd", lic, re.I) or re.search(r"^cc[- ]by(?!.*(nc|nd))", lic, re.I)
            if ok and ent["url"] and (ent["size"] or 0) < 15e6:
                fn = f"{OUT}/commons/{kind}__" + re.sub(r"[^A-Za-z0-9._-]", "_", p["title"][5:])[-60:]
                a = get(ent["url"], timeout=120)
                if a is not None and a.ok:
                    open(fn, "wb").write(a.content)
                    ent["file"] = fn
    rep["commons"][kind] = infos

# 3a. Kevin MacLeod (incompetech), CC BY 4.0
r = get("https://incompetech.com/music/royalty-free/pieces.json")
pieces = []
if r is not None and r.ok:
    try:
        pieces = r.json()
    except Exception as e:
        print("pieces.json not json", e, r.text[:300])
print("INCOMPETECH pieces", len(pieces), flush=True)
if pieces:
    print("keys", list(pieces[0].keys()))
want = []
for p in pieces:
    feel = (str(p.get("feel", "")) + " " + str(p.get("genre", "")) + " " + str(p.get("instruments", ""))).lower()
    bpm = int(p.get("bpm") or 0) if str(p.get("bpm", "")).isdigit() else 0
    if re.search(r"bright|happy|playful|uplifting|light|whimsical|bouncy|calm|relaxed|peaceful|humorous", feel) \
            and not re.search(r"dark|tense|scary|ominous|action|aggressive|horror|epic|grim|unnerving|mysterious|suspense", feel) \
            and (80 <= bpm <= 135 or bpm == 0) and re.search(r"children|kids|easy|pop|folk|world|jazz|unclassifiable|classical|soundtrack", feel):
        want.append(p)
rep["incompetech"] = [{k: p.get(k) for k in p} for p in want]
print("INCOMPETECH chosen", len(want), [p.get("title") for p in want][:80], flush=True)
named = ["Fluffing a Duck", "Carefree", "Wallpaper", "Happy Alley", "Pixel Peeker Polka - faster", "Pixel Peeker Polka - slower",
         "Monkeys Spinning Monkeys", "Sneaky Snitch", "Life of Riley", "Cheery Monday", "Bossa Antigua", "Daily Beetle",
         "Merry Go", "Hyperfun", "Easy Lemon", "Easy Lemon 60 Second", "Lobby Time", "Investigations", "Funkorama",
         "The Builder", "Wholesome", "Spring In My Step", "Happy Boy End Theme", "Sunshine A", "Fig Leaf Times Two", "Pinball Spring",
         "Amazing Plan", "Breaktime", "Airport Lounge", "Bushwick Tarantella", "Circus Waltz", "Dreamer", "Overworld"]
titles = list(dict.fromkeys(named + [p.get("title") for p in want if p.get("title")]))[:60]
for t in titles:
    fn = f"{OUT}/music/km__" + re.sub(r"[^A-Za-z0-9._-]", "_", t) + ".mp3"
    a = get("https://incompetech.com/music/royalty-free/mp3-royaltyfree/" + quote(t) + ".mp3", timeout=180)
    if a is not None and a.ok and a.content[:3] in (b"ID3", b"\xff\xfb", b"\xff\xf3") and len(a.content) < 25e6:
        open("/tmp/m.mp3", "wb").write(a.content)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "/tmp/m.mp3", "-b:a", "128k", fn])

# 3b. OpenGameArt CC0 music (type 12), most favourited
for q in ["happy", "cheerful", "kids", "children", "farm", "playful", "whimsical", "calm happy", "ukulele", "acoustic happy"]:
    r = get("https://opengameart.org/art-search-advanced?keys=" + quote(q) +
            "&field_art_type_tid%5B%5D=12&field_art_licenses_tid%5B%5D=4&sort_by=favorites&sort_order=DESC")
    if r is None or not r.ok:
        continue
    for h in list(dict.fromkeys(re.findall(r'href="(/content/[^"]+)"', r.text)))[:6]:
        if h == "/content/faq" or any(e["page"] == h for e in rep["oga_music"]):
            continue
        rp = get("https://opengameart.org" + h)
        if rp is None or not rp.ok:
            continue
        lic = sorted(set(re.findall(r'(CC0|CC-BY-SA \d\.\d|CC-BY \d\.\d|GPL \d\.\d|OGA-BY \d\.\d)', rp.text)))
        files = [f for f in re.findall(r'href="(https://opengameart\.org/sites/default/files/[^"]+)"', rp.text) if f.lower().endswith((".mp3", ".ogg", ".wav", ".flac"))]
        ent = {"page": h, "q": q, "lic": lic, "files": files[:3], "saved": []}
        if lic == ["CC0"]:
            for f in files[:1]:
                a = get(f, timeout=180)
                if a is not None and a.ok and len(a.content) < 40e6:
                    ext = os.path.splitext(f)[1]
                    open("/tmp/o" + ext, "wb").write(a.content)
                    fn = f"{OUT}/music/oga__" + re.sub(r"[^A-Za-z0-9._-]", "_", h.split("/")[-1])[:50] + ".mp3"
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "/tmp/o" + ext, "-b:a", "128k", fn])
                    ent["saved"].append(fn)
        rep["oga_music"].append(ent)

json.dump(rep, open("assets-requests/out/sound2.json", "w"), indent=1)
print(subprocess.run(f"du -sh {OUT}/*; ls {OUT}/music | head -100", shell=True, capture_output=True, text=True).stdout)
