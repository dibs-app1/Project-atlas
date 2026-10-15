# TheCalmLittleWorld Studio

An automated "studio" that produces calm, low-stimulation, 10-minute vehicle videos for toddlers:
original animation, original music, safe driving, and no reused clips, ever.

## Where the finished videos are

Every push to `studio/` runs the **Calm videos studio** GitHub Actions workflow. It renders all ten
videos in parallel and publishes a **GitHub Release** (repo → *Releases*) containing, for each video:

| File | What it is |
|---|---|
| `NN-name.mp4` | the 10:00 video, 1080p, H.264 + AAC, ready for YouTube |
| `NN-name.jpg` | a 1280x720 thumbnail |
| `NN-name.txt` | title, description (with chapters) and tags to paste into YouTube Studio |
| `qa_report.json` | every check each video passed |

In YouTube Studio set **Audience → Yes, it's made for kids** and **Category → Education**.

## This batch

| # | Video | Vehicle | Setting | Scenes |
|---|---|---|---|---|
| 1 | Sailboats and Rowboats, Mountain Lake | boats | alpine lake, sunrise → dusk | 8 |
| 2 | Tugboats and Ferries, Harbor | boats | harbor + lighthouse, morning → night | 8 |
| 3 | Little Airplanes, Airfield | airplanes | country airfield: take offs, landings, taxiing | 8 |
| 4 | Airplanes Above the Clouds | airplanes | above the clouds + over ocean islands | 8 |
| 5 | Cars in the Snowy Village | cars | winter village, snowplow, morning → night | 8 |
| 6 | Cars at the Traffic Light | cars | autumn town crossroads: red stop, green go, crosswalk | 8 |
| 7 | Trains in the Desert | trains | red-rock desert + canyon trestle bridge | 8 |
| 8 | Trains in Spring | trains | windmills, tulips, level crossing with barrier down | 8 |
| 9 | Hot Air Balloons | hot air balloons | lavender fields, dawn → dusk | 8 |
| 10 | Helicopters on the Coast | helicopters | green coastal hills, landings on a helipad | 8 |

Each vehicle type has its own settings: no landscape is shared between two vehicle types.

## The team (how the work is delegated)

`studio/manager.py` is the Studio Manager. It never draws anything; it hands work to specialists and only
lets work move on when a gate passes. See `team/` for each role's brief.

1. **Producer**: `plan/manifest.json` must hold 10 videos, cover all six vehicle types, keep titles within
   YouTube's 100 characters, and give each vehicle type its own settings.
2. **Safety Reviewer**: every scene is checked by `scenes.safety_review`: speed limits per vehicle,
   gentle acceleration (every speed change takes at least 6 s), cars stop for red lights and wait for the
   pedestrian, trains pass with the crossing barrier down, helicopters land only on a marked helipad,
   balloons never fly at night. People on boats always wear orange life jackets (built into the drawings).
3. **Continuity Clerk**: every scene gets a fingerprint (setting + time of day + vehicle + action). A scene
   may not repeat inside the batch, and `plan/scene_ledger.json` remembers every scene ever published, so
   future batches can't reuse one either.
4. **Crews** (Animator + Sound Designer + Editor) via `produce.py`: draw every frame from scratch at
   1920x1080/24fps, compose an original soundtrack (own key, tempo and instrument per video, no drums, no
   vocals), crossfade scenes slowly over 3 s, and write the thumbnail and YouTube text.
5. **QA Inspector** (`qa.py`): exact 10:00 length, 1080p H.264/AAC, loudness about -18 LUFS with peaks
   under -1 dBFS, a frame-by-frame **flash scan** (no sudden brightness jumps), a visual comparison of
   every scene against every other scene, and YouTube limits on title, description and tags.
6. **Publisher** (`upload.py`): uploads QA-passed videos to YouTube as **private** and made for kids, for a
   final human look before they go public.

## Running it yourself

```bash
pip install numpy pillow          # plus ffmpeg on the PATH
python studio/manager.py          # all 10 videos into output/ (~50 min on 4 cores)
python studio/manager.py --plan-only
python studio/produce.py 06-cars-town-traffic-lights --seconds 60 --out /tmp/preview   # quick preview
python studio/qa.py output
```

To make the next batch, add new videos (or new scenes) to `plan/manifest.json`. The Continuity Clerk
rejects anything that was already made.

## Uploading straight to YouTube (optional)

1. In Google Cloud Console, create a project, enable **YouTube Data API v3**, and create an OAuth client ID
   of type *Desktop app*. Download it as `studio/client_secret.json` (never commit it).
2. `pip install google-api-python-client google-auth-oauthlib`
3. `python studio/upload.py --dry-run`, then `python studio/upload.py`. A browser opens once to sign in
   to the TheCalmLittleWorld channel.

Videos land as **private**. Uploads from an unverified Google Cloud app stay locked to private until
the app passes Google's audit, so manual upload in YouTube Studio is the simplest route.
The default API quota allows about 6 uploads per day, so the script stops cleanly and resumes the next day.
