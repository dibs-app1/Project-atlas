# QA Inspector
Run `python studio/qa.py output`. A video ships only if it is exactly 10:00, 1080p H.264/AAC, about -18
LUFS with peaks under -1 dBFS, passes the frame-by-frame flash scan, has all scenes safety-approved, and
fits YouTube's limits on title, description and tags. Also confirm no two scenes in the batch look alike.
