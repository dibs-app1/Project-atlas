# Songwriter and Singer (sing-along batches)
Each sing-along video gets one original, catchy song (`studio/song.py`). Every scene is one 28-bar
round locked to the picture: instrumental, a VERSE about what this scene shows, the CHORUS (the same
every time, so children learn it), and the NOISE GAME ("What does the dump truck say?", then the real
vehicle noise while the band stops, then the choir copies it, twice), then instrumental.

Lyrics live in the plan (`plan/batch3.json`): the chorus per video, and `verse`, `ask` and `noise` per
scene. Mark extra syllables with hyphens (`yel-low`, `ev-ery`) so each one gets its own note. The
Safety Reviewer rejects lines that are too long to sing (more than 13 syllables) and unknown noises.

The Singer (`studio/singer.py`) sings the words: a neural text-to-speech voice (Piper, "lessac") says
each word, then the WORLD vocoder holds the vowel for the note's length and sets the pitch to the
melody with a gentle vibrato. The chorus and the copy-the-noise lines are sung by a small choir (three
slightly different voices). No existing songs or recordings are used.

Vehicle noises (`engine2/noises.py`) are synthesized: BEEP BEEP, HONK HONK, VROOM, DING-A-LING, CHOO
CHOO, TOOT TOOT, BWOOOM, ZOOM, BRRRR, SPLASH. All are levelled to the same loudness, and the final mix
goes through a limiter.

On screen (`engine2/singalong.py`): sing-along lyrics with a bouncing ball and words that fill with
gold as they are sung, comic-book noise bursts and sound waves coming from the vehicle, a gentle camera
push-in on the vehicle while it makes its noise, and music notes floating up during the chorus.
