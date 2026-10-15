# Studio team briefs

The Studio Manager (`studio/manager.py`) delegates each stage to one of these roles. Each brief says
what the role owns, what it hands on, and the gate its work must pass. The code that does each job is
named in each brief, so a human freelancer or an AI sub-agent can take any role over.

| Stage | Role | Code | Gate |
|---|---|---|---|
| 1 | Producer | `studio/plan/manifest.json` | `manager.producer_gate` |
| 2 | Safety Reviewer | `studio/scenes.py: safety_review` | no scene with an issue |
| 3 | Continuity Clerk | `studio/manager.py: continuity_gate` + `plan/scene_ledger.json` | no repeated scene, ever |
| 4 | Animator | `studio/art.py`, `settings.py`, `scenes.py` | renders cleanly |
| 4 | Sound Designer | `studio/music.py` | calm, peaks under -1 dBFS |
| 4 | Editor | `studio/produce.py` | exact 10:00, 3 s crossfades |
| 5 | QA Inspector | `studio/qa.py` | every check PASS |
| 6 | Publisher | `.github/workflows/calm-videos.yml`, `studio/upload.py` | private upload, human spot-check |
