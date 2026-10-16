"""Save the Quaternius pack pages' HTML so the download links can be found."""
import os
import requests

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (studio asset librarian)"
os.makedirs("assets-requests/out/pages", exist_ok=True)
for p in ["farmanimal", "ultimateanimatedanimals", "animatedfish", "cutefish", "ultimatestylizednature", "stylizednaturemegakit",
          "farmbuildings", "ultimatenature"]:
    r = S.get(f"https://quaternius.com/packs/{p}.html", timeout=60)
    open(f"assets-requests/out/pages/{p}.html", "w").write(r.text)
    print(p, r.status_code, len(r.text))
r = S.get("https://quaternius.com/", timeout=60)
open("assets-requests/out/pages/index.html", "w").write(r.text)
for js in ["https://quaternius.com/assets/js/main.js", "https://quaternius.com/assets/js/script.js"]:
    try:
        r = S.get(js, timeout=30)
        print(js, r.status_code, len(r.text))
        if r.ok:
            open("assets-requests/out/pages/" + os.path.basename(js), "w").write(r.text)
    except Exception as e:
        print(js, e)
# run 3
