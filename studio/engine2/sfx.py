"""Sound effects for engine 2, synthesized from scratch and timed to each scene's events.

Beds follow a level/speed over time (engine hum, rain, waves, wind, clickety-clack);
one-shots fire at moments in the scene (bump, splash, whistle, chime, door...).
Everything is soft: no sudden loud sounds, peaks are limited before the final mix.
"""
import math

import numpy as np

SR = 44100


def _env_from(fn, D, rate=50):
    ts = np.arange(0, D + 1.0 / rate, 1.0 / rate)
    vals = np.array([float(fn(t)) for t in ts])
    n = int(D * SR)
    return np.interp(np.arange(n) / SR, ts, vals)


def _lowpass(x, k):
    k = max(1, int(k))
    c = np.cumsum(np.insert(x, 0, 0.0))
    y = (c[k:] - c[:-k]) / k
    return np.concatenate([y, np.full(len(x) - len(y), y[-1] if len(y) else 0.0)])


def _noise(n, rng):
    return rng.standard_normal(n)


def _tone(freqs, dur, decay=0.6, attack=0.01, vib=0.0):
    t = np.arange(int(dur * SR)) / SR
    s = sum(np.sin(2 * np.pi * f * t * (1 + vib * np.sin(2 * np.pi * 5.5 * t))) for f in freqs) / len(freqs)
    env = np.minimum(1, t / attack) * np.exp(-t / decay)
    return s * env


def one_shot(kind, rng):
    if kind == "bump":
        t = np.arange(int(0.35 * SR)) / SR
        return np.sin(2 * np.pi * (70 - 30 * t) * t) * np.exp(-t / 0.08) * 0.9
    if kind == "splash":
        n = int(1.2 * SR)
        t = np.arange(n) / SR
        return _lowpass(_noise(n, rng), 6) * np.exp(-t / 0.35) * 0.6
    if kind == "door":
        n = int(0.9 * SR)
        t = np.arange(n) / SR
        return (_noise(n, rng) - _lowpass(_noise(n, rng), 30)) * np.minimum(1, t / 0.05) * np.exp(-t / 0.3) * 0.25
    if kind == "beep":
        a = _tone([1046], 0.18, decay=0.2, attack=0.01)
        return np.concatenate([a, np.zeros(int(0.12 * SR)), a]) * 0.25
    if kind == "lift":
        t = np.arange(int(2.5 * SR)) / SR
        return np.sin(2 * np.pi * (120 + 40 * t) * t) * np.minimum(1, t / 0.3) * np.minimum(1, (2.5 - t) / 0.4) * 0.18
    if kind == "horn":       # soft two-note toot
        a = _tone([392, 494], 0.35, decay=0.5, attack=0.03)
        return np.concatenate([a, np.zeros(int(0.1 * SR)), a]) * 0.3
    if kind == "whistle":    # steam whistle chord
        return _tone([523, 659, 784], 1.4, decay=1.2, attack=0.08, vib=0.004) * 0.3
    if kind == "chime":      # station ding-dong
        a = _tone([659, 1318], 0.9, decay=0.6)
        b = _tone([523, 1046], 1.2, decay=0.8)
        return np.concatenate([a[: int(0.45 * SR)], b]) * 0.3
    return np.zeros(1)


def bed(kind, spec, D, rng):
    n = int(D * SR)
    t = np.arange(n) / SR
    if kind in ("engine", "motor", "traffic"):
        lvl = _env_from(spec.get("level", lambda tt: 0.5), D)
        truck = spec.get("kind2") in ("truck", "bus")
        f0 = (38 if truck else 48) + 40 * lvl
        ph = np.cumsum(2 * np.pi * f0 / SR)
        hum = np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph)
        if kind == "motor":
            hum = hum + 0.3 * np.sign(np.sin(ph * 2))
        hum = _lowpass(hum, 12)
        rumble = _lowpass(_noise(n, rng), 200)
        return (0.18 * hum + 0.8 * rumble / (np.abs(rumble).max() + 1e-9) * 0.2) * (0.3 + 0.7 * lvl)
    if kind == "rain":
        lvl = _env_from(spec.get("level", lambda tt: 1.0), D)
        hiss = _noise(n, rng) - _lowpass(_noise(n, rng), 8)
        drops = (rng.random(n) < 0.0008) * rng.uniform(0.2, 1.0, n)
        drops = np.convolve(drops, np.exp(-np.arange(400) / 60.0), mode="same")
        return (0.05 * hiss + 0.25 * drops) * lvl
    if kind in ("waves", "water", "wind"):
        lvl = _env_from(spec.get("level", lambda tt: 0.5), D)
        k = {"waves": 60, "water": 6, "wind": 160}[kind]
        x = _lowpass(_noise(n, rng), k)
        x /= np.abs(x).max() + 1e-9
        per = {"waves": 6.0, "water": 2.0, "wind": 9.0}[kind]
        swell = 0.55 + 0.45 * np.sin(2 * np.pi * t / per + rng.uniform(0, 6))
        return 0.3 * x * swell * lvl
    if kind in ("jet", "prop"):
        lvl = _env_from(spec.get("level", lambda tt: 0.5), D)
        whoosh = _lowpass(_noise(n, rng), 20 if kind == "jet" else 40)
        whoosh /= np.abs(whoosh).max() + 1e-9
        out = 0.3 * whoosh
        if kind == "prop":
            out = out * (0.6 + 0.4 * np.sin(2 * np.pi * 28 * t))
        return out * lvl
    if kind == "train":       # clickety-clack: two quick thumps each time a wheel set crosses a rail joint
        sp = _env_from(spec.get("speed", lambda tt: 200), D)
        joint = 520.0
        pos = np.cumsum(sp / SR)
        idx = np.nonzero(np.diff(np.floor(pos / joint)) > 0)[0]
        out = np.zeros(n)
        click = one_shot("bump", rng)[: int(0.12 * SR)] * 0.5
        gap = int(0.11 * SR)
        for i in idx:
            for off in (0, gap):
                j = i + off
                if j + len(click) < n:
                    out[j:j + len(click)] += click
        rumble = _lowpass(_noise(n, rng), 150)
        rumble /= np.abs(rumble).max() + 1e-9
        return out + 0.12 * rumble * np.clip(sp / 300, 0.1, 1.0)
    if kind == "chug":        # steam: four chuffs per wheel turn
        sp = _env_from(spec.get("speed", lambda tt: 200), D)
        wheel = spec.get("wheel", 290.0)
        pos = np.cumsum(sp / SR) / (wheel / 4)
        idx = np.nonzero(np.diff(np.floor(pos)) > 0)[0]
        out = np.zeros(n)
        puff = _lowpass(_noise(int(0.16 * SR), rng), 10) * np.exp(-np.arange(int(0.16 * SR)) / (0.05 * SR))
        for i in idx:
            if i + len(puff) < n:
                out[i:i + len(puff)] += 0.35 * puff
        return out
    if kind == "bell":        # crossing bell, steady rhythm while the gate is down
        lvl = _env_from(spec.get("level", lambda tt: 0.0), D)
        out = np.zeros(n)
        ding = _tone([1318, 2637], 0.4, decay=0.25) * 0.25
        for k in range(int(D * 2)):
            i = int(k * SR / 2)
            if i + len(ding) < n:
                out[i:i + len(ding)] += ding
        return out * lvl
    return np.zeros(n)


def render_scene(sounds, D, seed):
    rng = np.random.default_rng(seed)
    n = int(D * SR)
    out = np.zeros(n)
    for snd in sounds:
        k = snd["kind"]
        if "at" in snd:
            s = one_shot(k, rng)
            i = int(snd["at"] * SR)
            if 0 <= i < n:
                m = min(len(s), n - i)
                out[i:i + m] += s[:m]
        else:
            out += bed(k, snd, D, rng)
    return out
