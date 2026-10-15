# Continuity Clerk
No clip is ever reused. Each scene is fingerprinted by setting, time of day, vehicle and action.
Duplicates inside a batch are rejected, and `studio/plan/scene_ledger.json` keeps every published scene
so future batches can't repeat one. QA also compares the middle frame of every scene against every
other scene.
