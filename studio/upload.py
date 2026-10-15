#!/usr/bin/env python3
"""Publisher: upload QA-passed videos to YouTube as PRIVATE, made for kids, category Education.

One-time setup (see studio/README.md, "Uploading straight to YouTube"):
    pip install google-api-python-client google-auth-oauthlib
    put your OAuth client file at studio/client_secret.json

    python studio/upload.py --dry-run     # show what would be uploaded
    python studio/upload.py               # upload (resumes safely; skips anything already uploaded)

YouTube's default API quota allows about 6 uploads per day. If the quota runs out the script
stops cleanly; run it again the next day to finish the rest.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def youtube():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token = ROOT / "token.json"
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(ROOT / "client_secret.json"), SCOPES)
            creds = flow.run_local_server(port=0)
        token.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT.parent / "output"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--privacy", default="private", choices=["private", "unlisted"])
    a = ap.parse_args()
    out = Path(a.out)
    report = json.loads((out / "qa_report.json").read_text())
    state_file = out / "uploaded.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    ready = [r["id"] for r in report["videos"] if r["pass"] and r["id"] not in state]
    print(f"{len(ready)} passed videos waiting to upload")
    if a.dry_run:
        for vid in ready:
            print("  would upload", vid, "as", a.privacy)
        return
    if not ready:
        return
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    yt = youtube()
    for vid in ready:
        meta = json.loads((out / f"{vid}.json").read_text())
        body = {
            "snippet": {"title": meta["title"], "description": meta["description"], "tags": meta["tags"],
                        "categoryId": meta["categoryId"], "defaultLanguage": "en"},
            "status": {"privacyStatus": a.privacy, "selfDeclaredMadeForKids": True, "embeddable": True},
        }
        try:
            req = yt.videos().insert(part="snippet,status", body=body,
                                     media_body=MediaFileUpload(str(out / meta["file"]), chunksize=-1, resumable=True))
            resp = None
            while resp is None:
                _, resp = req.next_chunk()
            yt_id = resp["id"]
            try:
                yt.thumbnails().set(videoId=yt_id, media_body=MediaFileUpload(str(out / meta["thumbnail"]))).execute()
            except HttpError as e:  # custom thumbnails need a phone-verified channel
                print(f"  thumbnail not set for {vid}: {e.reason}")
        except HttpError as e:
            if e.resp.status == 403 and "quota" in str(e).lower():
                print("Daily YouTube quota reached. Run this again tomorrow to upload the rest.")
                break
            raise
        state[vid] = yt_id
        state_file.write_text(json.dumps(state, indent=2))
        print(f"  uploaded {vid} -> https://youtu.be/{yt_id} ({a.privacy})")


if __name__ == "__main__":
    sys.exit(main())
