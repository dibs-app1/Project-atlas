"""Fetch the farm pig grunt by Erdie (Wikimedia Commons, CC BY 3.0) and its file page (licence and author)."""
import json
import os

import requests

S = requests.Session()
S.headers["User-Agent"] = "TheCalmLittleWorldStudio/1.0 (asset librarian; https://github.com/dibs-app1/TheCalmLittleWorld)"
OUT = "assets-requests/out/sound4"
os.makedirs(OUT, exist_ok=True)
API = "https://commons.wikimedia.org/w/api.php"
info = {}
for t in ["File:Pig grunt - Erdie.ogg"]:
    r = S.get(API, params={"action": "query", "format": "json", "titles": t, "prop": "imageinfo",
                           "iiprop": "url|extmetadata|size", "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist|Credit|ImageDescription"},
              timeout=60)
    p = list(r.json()["query"]["pages"].values())[0]
    ii = p["imageinfo"][0]
    info[t] = {"url": ii["url"], "meta": {k: v.get("value") for k, v in ii.get("extmetadata", {}).items()}}
    print(t, info[t], flush=True)
    a = S.get(ii["url"], timeout=120)
    open(os.path.join(OUT, "pig_grunt_erdie.ogg"), "wb").write(a.content)
    print("saved", len(a.content))
json.dump(info, open(OUT + "/info.json", "w"), indent=1)
