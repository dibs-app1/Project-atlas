"""Third pass: real pig recordings (CC0 / public domain only): BigSoundBank under its French and English words,
Wikimedia Commons, OpenGameArt."""
import html
import json
import os
import re
from urllib.parse import quote

import requests

S = requests.Session()
S.headers["User-Agent"] = "TheCalmLittleWorldStudio/1.0 (asset librarian; https://github.com/dibs-app1/TheCalmLittleWorld)"
OUT = "assets-requests/out/sound3"
os.makedirs(OUT, exist_ok=True)
rep = {"bsb": {}, "commons": [], "oga": []}


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


slugs = {}
for q in ["cochon", "cochons", "truie", "porcelet", "porc", "sow", "grunt", "grunting", "pigsty", "piggery", "hog", "swine", "oink", "farm animals"]:
    for base in ("https://bigsoundbank.com/search?q=", "https://bruitages.bigsoundbank.com/search?q=", "https://bigsoundbank.com/fr/search?q="):
        r = get(base + quote(q))
        if r is not None and r.ok:
            for slug, i in re.findall(r"href='/([a-z0-9-]+-s(\d{4})\.html)'", r.text):
                slugs[i] = (base.split("/search")[0], slug)
for i, (base, slug) in sorted(slugs.items()):
    r = get(f"{base}/{slug}")
    if r is None or not r.ok:
        continue
    h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", r.text, re.S)
    title = clean(h1[0]) if h1 else slug
    desc = re.findall(r'<meta name="description" content="([^"]*)"', r.text)
    rep["bsb"][i] = {"slug": slug, "title": title, "desc": html.unescape(desc[0]) if desc else ""}
    print("BSB", i, title, "|", rep["bsb"][i]["desc"][:200], flush=True)
    if re.search(r"pig|cochon|truie|porc|sow|hog|swine|grunt", (slug + " " + title).lower()):
        a = get(f"https://bigsoundbank.com/UPLOAD/mp3/{i}.mp3", timeout=120)
        if a is not None and a.ok and len(a.content) < 20e6:
            open(f"{OUT}/bsb_{i}.mp3", "wb").write(a.content)

API = "https://commons.wikimedia.org/w/api.php"
seen = []
for q in ["pig", "pigs", "piglet", "domestic pig sound", "pig grunting", "pig squeal", "sow grunt", "Sus domesticus", "Sus scrofa domesticus",
          "oink", "pig farm sound", "hog"]:
    r = get(API, params={"action": "query", "format": "json", "list": "search", "srnamespace": 6, "srlimit": 25,
                         "srsearch": f"{q} filetype:audio"})
    if r is not None and r.ok:
        seen += [h["title"] for h in r.json().get("query", {}).get("search", []) if h["title"] not in seen]
for tchunk in [seen[i:i + 20] for i in range(0, len(seen), 20)]:
    r = get(API, params={"action": "query", "format": "json", "titles": "|".join(tchunk), "prop": "imageinfo",
                         "iiprop": "url|extmetadata|size", "iiextmetadatafilter": "LicenseShortName|Artist|ImageDescription"})
    if r is None or not r.ok:
        continue
    for p in r.json().get("query", {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata", {})
        lic = md.get("LicenseShortName", {}).get("value", "")
        e = {"title": p.get("title"), "lic": lic, "url": ii.get("url"), "size": ii.get("size"),
             "desc": clean(md.get("ImageDescription", {}).get("value", ""))[:200]}
        rep["commons"].append(e)
        print("COMMONS", lic, e["title"], "|", e["desc"][:120], flush=True)
        if re.search(r"public domain|cc0|^pd", lic, re.I) and re.search(r"pig|sus |hog|swine|sow|piglet|oink", (e["title"] + e["desc"]).lower()) \
                and (e["size"] or 0) < 15e6:
            a = get(e["url"], timeout=120)
            if a is not None and a.ok:
                open(f"{OUT}/commons_" + re.sub(r"[^A-Za-z0-9._-]", "_", e["title"][5:])[-60:], "wb").write(a.content)

for q in ["pig", "pigs", "oink", "grunt", "farm animals"]:
    r = get("https://opengameart.org/art-search-advanced?keys=" + quote(q) + "&field_art_type_tid%5B%5D=13")
    if r is None or not r.ok:
        continue
    for h in list(dict.fromkeys(re.findall(r'href="(/content/[^"]+)"', r.text)))[:8]:
        if h == "/content/faq":
            continue
        rp = get("https://opengameart.org" + h)
        if rp is None or not rp.ok:
            continue
        lic = sorted(set(re.findall(r'(CC0|CC-BY-SA \d\.\d|CC-BY \d\.\d|GPL \d\.\d|OGA-BY \d\.\d)', rp.text)))
        files = [f for f in re.findall(r'href="(https://opengameart\.org/sites/default/files/[^"]+)"', rp.text) if f.lower().endswith((".mp3", ".ogg", ".wav", ".flac"))]
        rep["oga"].append({"page": h, "lic": lic, "files": files[:5]})
        print("OGA", h, lic, files[:5], flush=True)
        if lic == ["CC0"] and re.search(r"pig|oink|grunt|farm", h):
            for f in files[:4]:
                a = get(f, timeout=120)
                if a is not None and a.ok and len(a.content) < 15e6:
                    open(f"{OUT}/oga_" + re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(f))[-60:], "wb").write(a.content)
json.dump(rep, open("assets-requests/out/sound3.json", "w"), indent=1)
print(os.listdir(OUT))
