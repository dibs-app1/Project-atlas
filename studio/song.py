"""The Songwriter: one original, catchy sing-along song per video, built around the scenes.

Every scene is one song "round" of 28 bars, locked to the picture:

    bars  0-1   instrumental (the picture crossfades in)
    bars  2-9   VERSE   four lines about what this scene shows (its own words)
    bars 10-17  CHORUS  the same four lines every time, so kids learn it and sing along
    bars 18-25  NOISE GAME  "What does the dump truck say?" -> the real vehicle noise (music stops for it)
                -> the choir copies it ("Beep beep!") -> "One more time!" -> noise -> copy
    bars 26-27  instrumental (crossfade to the next scene)

Melodies are generated per video from a seed, but each line position always uses the same tune,
so lines with different words still sound like the same song. Lyrics (and when each word is sung)
are handed to the scene so the picture can show sing-along words with a bouncing ball.
Everything is original: no existing songs, no samples.

By default the tune is played by a soft, warm whistle-like lead (no synthetic voice: a computer voice
can sound robotic and unsettling to small children). The words are on screen with a bouncing ball, so
kids and grown-ups sing along. `"voice": "sung"` in the plan switches the Singer back on.
"""
import random

import numpy as np

import music
import singer
from engine2 import noises
from music import SR, midi_hz, note

BARS = 28
MAJOR = [0, 2, 4, 5, 7, 9, 11]
# chord (scale degree of its root) for each bar of each line, by section
PROG = {
    "verse": [(0, 3), (4, 0), (0, 3), (4, 0)],
    "chorus": [(3, 0), (4, 0), (3, 0), (4, 4)],
    "game": [(5, 3), (4, 4), (5, 3), (4, 0)],
}
ECHO_WORDS = {
    "car_horn": "beep beep", "bus_horn": "beep beep", "truck_horn": "honk honk", "reverse": "beep beep beep",
    "vroom": "vroom vroom", "ice_cream": "ding a ling", "steam_whistle": "choo choo", "chugga": "chug a chug",
    "diesel_horn": "honk honk", "tram_bell": "ding ding", "ship_horn": "toot toot", "tug_toot": "toot toot",
    "outboard": "vroom vroom", "splash": "splish splash", "jet_zoom": "zoom zoom", "prop_buzz": "buzz buzz",
}


def deg_midi(tonic, d):
    o, k = divmod(int(d), 7)
    return tonic + 12 * o + MAJOR[k]


def _triad(c):
    return {c % 7, (c + 2) % 7, (c + 4) % 7}


def make_tune(rng, prog_line, lo=-2, hi=8, start=None):
    """16 eighth-note slots of scale degrees over a two-bar line: chord tones on the beats, steps between."""
    cur = start if start is not None else rng.choice([0, 2, 4])
    tune = []
    for slot in range(16):
        tones = _triad(prog_line[slot // 8])
        if slot % 4 == 0:
            cands = sorted((d for d in range(lo, hi + 1) if d % 7 in tones), key=lambda d: (abs(d - cur), rng.random()))
            cur = cands[0] if rng.random() < 0.55 else cands[min(1, len(cands) - 1)]
        else:
            cur = int(np.clip(cur + rng.choice([0, 0, 1, -1, 1, -1, 2, -2]), lo, hi))
        tune.append(cur)
    return tune


def rhythm(n):
    """Start slot and length (in eighths) of each of n syllables in a two-bar line; the last one is held."""
    n = max(1, min(n, 13))
    if n == 1:
        return [(0, 12)]
    k = n - 1
    if k <= 6:
        durs = [2] * k
    else:
        q, e = max(0, 13 - n), 2 * n - 14
        durs = []
        while q or e:                       # groove: two quick ones, then a long one
            if e >= 2:
                durs += [1, 1]
                e -= 2
            if q:
                durs.append(2)
                q -= 1
            elif e:
                durs.append(1)
                e -= 1
    pos, out = 0, []
    for d in durs:
        out.append((pos, d))
        pos += d
    out.append((pos, max(2, 14 - pos)))
    return out


def line_events(text, tune, tonic, eighth, end_deg=None):
    """Turn a lyric line into sung word events: [(start_s, word, [(midi, dur_s)...], shown_text)]."""
    toks = singer.tokens(text)
    shown = [w for w in text.split() if any(c.isalpha() for c in w)]
    n = sum(k for _, k in toks)
    rh = rhythm(n)
    ev, i = [], 0
    for wi, (word, k) in enumerate(toks):
        notes, t0 = [], rh[i][0] * eighth
        for j in range(k):
            slot, ln = rh[i]
            d = tune[slot]
            if i == n - 1 and end_deg is not None:
                d = end_deg
            notes.append((deg_midi(tonic, d), ln * eighth))
            i += 1
        ev.append((t0, word, notes, shown[wi].replace("-", "") if wi < len(shown) else word))
    return ev


class Song:
    def __init__(self, video, seed):
        sp = video["song"]
        self.sp = sp
        self.rng = random.Random(seed)
        self.seed = seed
        self.root = sp.get("root", 60)           # key of the backing (C4 = 60)
        self.tonic = self.root + 12               # where the tune sits (a bright children's range)
        self.inst = sp.get("instrument", "marimba")
        r = self.rng
        v = PROG["verse"]
        a = make_tune(r, v[0])
        self.verse_tunes = [a, make_tune(r, v[1], start=a[-1]), a, make_tune(r, v[3], start=a[-1])]
        c = PROG["chorus"]
        ch = make_tune(r, c[0], lo=0, hi=9, start=4)
        self.chorus_tunes = [ch, make_tune(r, c[1], lo=0, hi=9), ch, make_tune(r, c[3], lo=0, hi=9)]
        g = PROG["game"]
        self.ask_tune = make_tune(r, g[0], lo=0, hi=8, start=2)
        self.echo_degs = r.choice([[4, 4, 4], [4, 2, 4], [7, 4, 7], [4, 7, 4]])

    def scene_plan(self, scene, bar):
        """Lyric lines (scene-local seconds) and noise moments for one scene."""
        eighth = bar / 8
        lines, noise_at = [], []

        def add_line(text, b0, tune, end_deg, part):
            ev = line_events(text, tune, self.tonic, eighth, end_deg)
            t0 = b0 * bar
            lines.append(dict(part=part, t0=t0, t1=t0 + 2 * bar,
                              words=[dict(text=sh, w=w, t=t0 + st, d=sum(d for _, d in nt), notes=nt)
                                     for st, w, nt, sh in ev]))
        verse = scene["verse"]
        for i, text in enumerate(verse):
            add_line(text, 2 + 2 * i, self.verse_tunes[i], 0 if i == 3 else (4 if i == 1 else None), "verse")
        for i, text in enumerate(self.sp["chorus"]):
            add_line(text, 10 + 2 * i, self.chorus_tunes[i], 0 if i == 3 else None, "chorus")
        nz = scene["noise"]
        echo = scene.get("echo") or ECHO_WORDS[nz]
        asks = [scene["ask"], scene.get("ask2") or self.sp.get("ask2", "Let's all say it one more time!")]
        for j, b0 in enumerate((18, 22)):
            add_line(asks[j], b0, self.ask_tune, 4, "ask")
            noise_at.append((b0 + 2) * bar)
            # the echo: one bar after the noise, short and punchy
            words = echo.split()
            t0 = (b0 + 3) * bar
            wl = []
            for k_, w in enumerate(words):
                d = self.echo_degs[min(k_, len(self.echo_degs) - 1)]
                dur = eighth * (2 if k_ < len(words) - 1 else 3)
                wl.append(dict(text=w.capitalize() + ("!" if k_ == len(words) - 1 else ""), w=w,
                               t=t0 + k_ * 2 * eighth, d=dur, notes=[(deg_midi(self.tonic, d), dur)]))
            lines.append(dict(part="echo", t0=t0, t1=t0 + bar, words=wl))
        return dict(lines=lines, noises=[dict(t=t, name=nz, word=noises.word(nz)) for t in noise_at])

    # ------------------------------------------------------------------ audio
    def vocal(self, plans, scene_starts, seconds):
        """Sing every line of every scene. scene_starts: global start (s) of each scene's song round."""
        events_solo, events_choir = [], []
        for plan, st in zip(plans, scene_starts):
            for ln in plan["lines"]:
                for w in ln["words"]:
                    e = (st + w["t"], w["w"], tuple(w["notes"]))
                    (events_choir if ln["part"] in ("chorus", "echo") else events_solo).append(e)
        solo = singer.sing(events_solo, seconds, voices=1, seed=self.seed)
        choir = singer.sing(events_choir, seconds, voices=3, seed=self.seed + 1)
        return 0.85 * solo + 0.7 * choir

    def lead(self, plans, scene_starts, seconds, inst="whistle"):
        """The tune of every line, played by an instrument (default: a warm whistle) with a glockenspiel sparkle
        on the chorus. inst: whistle, marimba, bells, flute, piano, guitar."""
        n = int(seconds * SR)
        out = np.zeros(n + SR * 2)
        rng = np.random.default_rng(self.seed + 5)
        for plan, st in zip(plans, scene_starts):
            for ln in plan["lines"]:
                chorus = ln["part"] in ("chorus", "echo")
                for w in ln["words"]:
                    at = st + w["t"]
                    for m, d in w["notes"]:
                        if inst == "whistle":
                            sig = _whistle(midi_hz(m), d * 0.94, rng)
                        else:
                            sig = note(midi_hz(m), max(0.18, d * 0.94) + (0.25 if inst != "flute" else 0.1), inst, 0.9,
                                       random.Random(int(at * 1000)))
                        if chorus:   # chorus and echoes: a glockenspiel an octave up joins in
                            g = _glock(midi_hz(m + 12), d)[: len(sig)]
                            sig = sig.copy()
                            sig[: len(g)] += 0.22 * g
                        i = int(at * SR)
                        if i < len(out):
                            seg = sig[: len(out) - i]
                            out[i:i + len(seg)] += seg
                        at += d
        out = music.reverb(out[:n], seconds=1.4, mix=0.14, seed=self.seed + 5)
        return out / (np.max(np.abs(out)) + 1e-9)

    def backing(self, scene_starts, bar, seconds, plans):
        """Drums, bass, chords and an instrument doubling the tune. The band stops for each vehicle noise."""
        rng = np.random.default_rng(self.seed)
        nr = random.Random(self.seed)
        n = int(seconds * SR)
        mix_ = np.zeros(n + SR * 6)
        beat = bar / 4

        def add(sig, at, g=1.0):
            i = int(at * SR)
            if i < 0 or i >= len(mix_):
                return
            sig = sig[: len(mix_) - i]
            mix_[i:i + len(sig)] += g * sig
        kick, shaker, clap = music._kick(rng), music._shaker(rng), music._clap(rng)
        root = self.root

        def chord_tones(c):
            return [deg_midi(root, c), deg_midi(root, c + 2), deg_midi(root, c + 4)]

        def bar_chord(b):
            if b < 2 or b >= 26:
                return [0, 4, 3, 4][b % 4] if b < 2 else [3, 0][b - 26]
            sec = "verse" if b < 10 else "chorus" if b < 18 else "game"
            base = {"verse": 2, "chorus": 10, "game": 18}[sec]
            li = (b - base) // 2
            return PROG[sec][li][(b - base) % 2]

        upbeat = bool(self.sp.get("upbeat"))

        def play_bar(t, b, quiet=False, last=False):
            c = bar_chord(b)
            ct = chord_tones(c)
            full = 10 <= b < 18
            for j in range(4):
                bt = t + j * beat
                if not quiet:
                    if j in (0, 2):
                        add(kick, bt, 0.38)
                    if j in (1, 3):
                        add(clap, bt, (0.08 if full else 0.06) if upbeat else (0.07 if full else 0.05))
                    add(shaker, bt + beat / 2, 0.05)
                    if full or upbeat:
                        add(shaker, bt, 0.035)
                    if upbeat:        # a gentle skip: soft marimba chords on every off-beat
                        for m in ct:
                            add(note(midi_hz(m + 12), beat * 0.3, "marimba", 0.035, nr), bt + beat / 2)
                        if full and j == 0:          # a little glockenspiel sparkle at the start of chorus bars
                            add(note(midi_hz(ct[2] + 24), beat, "bells", 0.04, nr), bt)
                bass = [ct[0] - 24, ct[2] - 24, ct[0] - 12, ct[1] - 24][j]
                add(note(midi_hz(bass), beat * (0.45 if upbeat else 0.85), "harp", 0.2 if not quiet else 0.12, nr), bt)
                if upbeat and not quiet:         # the bass hops up an octave on the "and" of each beat
                    add(note(midi_hz(bass + 12), beat * 0.35, "harp", 0.12, nr), bt + beat / 2)
                if j in (1, 3) and not quiet:
                    for m in ct:
                        add(note(midi_hz(m), beat * 0.45, "piano", 0.045 if not full else 0.06, nr), bt + beat / 2)
            if last:
                for m in ct + [ct[0] + 12]:
                    add(note(midi_hz(m), bar * 2, "piano", 0.09, nr), t)

        tune_inst = self.inst
        for k, st in enumerate(scene_starts):
            plan = plans[k]
            noise_bars = {int(round(x["t"] / bar)) for x in plan["noises"]}
            for b in range(BARS):
                t = st + b * bar
                if t > seconds:
                    break
                stop = b in noise_bars          # stop-time: the noise gets the stage
                if not stop:
                    play_bar(t, b, quiet=(b in {x + 1 for x in noise_bars}))
                # the instrument hums the tune in the instrumental bars (chorus melody), softly doubles the voice
                if b < 2 or b >= 26:
                    tune = self.chorus_tunes[0] if b in (0, 26) else self.chorus_tunes[1]
                    half = 0 if b in (0, 26) else 8
                    for s_ in range(0, 8, 2):
                        add(note(midi_hz(deg_midi(self.tonic, tune[(s_ + half) % 16])), beat * 0.9, tune_inst, 0.14, nr),
                            t + s_ * beat / 2)
            if self.sp.get("voice") == "sung":   # the instrument softly doubles the singer
                for ln in plan["lines"]:
                    for w in ln["words"]:
                        for j, (m, d) in enumerate(w["notes"]):
                            at = st + w["t"] + sum(dd for _, dd in w["notes"][:j])
                            add(note(midi_hz(m), min(d, beat * 1.5), tune_inst, 0.07, nr), at)
        # a pick-up bar before the first round and a final chord after the last
        if scene_starts:
            first = scene_starts[0]
            for j in range(4):
                if first - (4 - j) * beat >= 0:
                    add(shaker, first - (4 - j) * beat, 0.05)
            end = scene_starts[-1] + BARS * bar
            play_bar(end, 0, last=True)
        out = mix_[:n]
        out = music.reverb(out, seconds=1.6, mix=0.16, seed=self.seed)
        tt = np.arange(n) / SR
        out *= np.minimum(1.0, tt / 0.5) * np.clip((seconds - tt) / 3.0, 0, 1)
        return out / (np.max(np.abs(out)) + 1e-9)

    def noise_track(self, plans, scene_starts, seconds):
        n = int(seconds * SR)
        out = np.zeros(n + SR * 4)
        for k, (plan, st) in enumerate(zip(plans, scene_starts)):
            for j, nz in enumerate(plan["noises"]):
                x = noises.render(nz["name"], seed=self.seed + 31 * k + j)
                x = x / (np.sqrt(np.mean(x ** 2)) + 1e-9) * 0.22       # every noise equally loud
                x = np.clip(x, -0.95, 0.95)
                i = int((st + nz["t"]) * SR)
                if 0 <= i < len(out):
                    out[i:i + len(x)] += x[: len(out) - i]
        return out[:n]


def _whistle(freq, dur, rng):
    """A soft, round whistle/ocarina note: gentle attack, a little breath, vibrato that blooms late."""
    dur = max(0.12, dur)
    t = np.arange(int(dur * SR)) / SR
    vib = 1 + 0.004 * np.clip((t - 0.18) / 0.25, 0, 1) * np.sin(2 * np.pi * 5.2 * t)
    ph = 2 * np.pi * np.cumsum(freq * vib) / SR
    x = np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.05 * np.sin(3 * ph)
    breath = rng.standard_normal(len(t))
    breath = np.convolve(breath, np.ones(24) / 24, mode="same") * 0.05
    env = np.minimum(1, t / 0.03) * np.clip((dur - t) / 0.07, 0, 1) * (1 - 0.15 * t / dur)
    return (x + breath) * env


def _glock(freq, dur):
    t = np.arange(int(max(0.3, dur) * SR)) / SR
    x = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * freq * 2.76 * t)
    return x * np.minimum(1, t / 0.003) * np.exp(-t / 0.35)
