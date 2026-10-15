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

## Batch 2: livelier, more detailed, more educational (engine 2)

Batch 1 is calm and lullaby-paced. Batch 2 (`plan/batch2.json`, rendered by `produce2.py` with
`engine2/`) is busier and more realistic:

| # | Video | Scenes |
|---|---|---|
| 11 | Cars and Trucks | highway with traffic both ways, speed bumps (slow down, bounce, count), construction (excavator, dump truck tipping, cement mixer, flagger STOP/SLOW), city bus in the rain then a rainbow, garbage truck lifting bins, car carrier (count 6 cars), school bus stop arm (every car waits), car wash, snowplow spreading salt, taxi at red and green lights at night |
| 12 | Boats | sailboat with jumping dolphins, container port with a working crane (count containers), river kayaks, speedboat with wake and spray past red and green buoys, rain rings on the lake and a rainbow, car ferry (count cars), trawler with gulls at sunset, paddle steamer, sailing race, night harbour |
| 13 | Airplanes | ground crew at the gate (baggage train, fuel, catering lift, marshaller), pushback and taxi, take-off with landing gear folding up, climbing through clouds, jumbo jet above the clouds with contrails, rainy landing with tyre smoke, seaplane splashdown, de-icing in snow, farm flight, night cargo loading (count boxes) |
| 14 | Trains | steam train with moving driving rods and smoke, bullet train under catenary wires, freight train counting 1 to 10, station stop (doors open, stand behind the yellow line), level crossing gates, mountain tunnel cutaway, red river bridge with boats below, snow plough train, elevated city metro, night sleeper |

What engine 2 adds:
- **Motion**: a camera that rides along with the vehicle; endless, never-repeating scenery generated in chunks;
  parallax at five depths; traffic in both directions; birds and gulls; smooth physics for braking and accelerating.
- **Detail**: spinning wheels, suspension bounce over speed bumps, dump beds, mixer drums, garbage arms, excavator
  buckets, landing gear and flaps, propellers, paddle wheels, steam-engine rods, doors, stop arms, crossing gates.
- **Weather**: rain (streaks, splashes, rings on water, darker sky) that can clear into a rainbow, snow, fog, drifting clouds.
- **Water**: real moving waves that boats ride and tilt on, wakes, bow spray, dolphins, splashes.
- **Sound**: upbeat original music plus sound effects timed to the picture: engine hum, clickety-clack, steam chuffs,
  waves, rain, wind, bumps, splashes, whistles, station chimes, crossing bells, bus doors.
- **Learning**: captions for safety rules and facts, and counting pop-ups (bumps, cars, containers, freight cars, bins, boxes).

```bash
python studio/manager.py --manifest studio/plan/batch2.json --out output/batch2     # all 4 videos
python studio/produce2.py 14-trains-on-the-tracks --seconds 90 --out /tmp/preview   # quick preview
```

`studio/plan/ACTIVE` names the manifest the GitHub workflow renders on each push.

## Batch 3: sing-along songs with real vehicle noises

Batch 3 (`plan/batch3.json`) gives each video its own **original, catchy kids' song** that is sung, plus the
**noises the vehicles make**, on top of the engine-2 animation:

| # | Video | Song | Scenes |
|---|---|---|---|
| 15 | Cars and Trucks | *Beep Beep, Here We Go!* | **ice cream truck**, **tow truck** (overtakes, reverses, lifts the car), **delivery truck**, night highway, speed bumps at sunset, diggers, car wash, garbage day in the rain, car carrier, school bus home |
| 16 | Boats | *Toot Toot, Off We Float!* | **tugboat pushes a container ship to the dock**, **fireboat water show with a rainbow**, **lighthouse in the fog**, dolphins at sunset, busy port, kayaks, speedboat and buoys, car ferry, paddle steamer, sailing race |
| 17 | Airplanes | *Zoom Zoom, Up So High!* | **air show with coloured smoke and loops**, **small, big and biggest take off**, **glider on tow**, airport helpers, pushback, take-off at sunset, cloud climb, seaplane, farm flight, above the clouds |
| 18 | Trains | *Choo Choo, Clickety-Clack!* | **city tram**, **two trains passing on two tracks**, **steam train at the water tower**, steam train at sunset, bullet train, count the freight cars, station, level crossing, mountain tunnel, river bridge |

(**Bold** scenes are brand new; the others are new takes of engine-2 scenes in a different light, weather or vehicle.)

Each scene is one round of the song: a verse about that scene, the chorus, then the **noise game**:
"What does the tow truck say?" → the real noise (the band stops for it) with a big BEEP BEEP! burst and
sound waves from the vehicle → the choir copies it. Lyrics are on screen with a bouncing ball, and the full
lyrics are in each video's description. See `team/songwriter.md`.

```bash
pip install piper-tts pyworld          # the singing voice (downloads ~60 MB the first time)
python studio/produce2.py 15-cars-and-trucks-song --manifest studio/plan/batch3.json --out output
```

## The richer look (engine 2)

`engine2/look.py` gives every engine-2 frame a richer, more 3D, more colourful finish:
deep-blue gradient skies with a soft sun glow, shaded fluffy clouds, vehicles with lit tops, shaded
undersides and a glossy highlight, tyres with tread and shiny rims, soft blurred shadows, fine texture
on grass, roads and hills, slightly soft distant hills (depth), sparkles on the water, and a final
colour grade (vibrance, gentle contrast, warm bloom, soft vignette).

## YouTube Shorts

`shorts.py` makes vertical 1080x1920 Shorts (about 40 seconds) from fresh engine-2 scenes:
a hook question in the first second, five quick action shots framed vertically, big bold pop-in text,
counting pop-ups, faster upbeat music with the scene sound effects, and a goodbye card.
Plans live in `plan/shorts*.json`; `qa_shorts.py` checks size, length (< 60 s), loudness, peaks,
flashing and safety. The **Shorts studio** workflow renders them and publishes a Release.

```bash
python studio/shorts.py --out output/shorts         # all Shorts in plan/shorts1.json
python studio/qa_shorts.py output/shorts
```

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
