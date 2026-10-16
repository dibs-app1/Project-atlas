"""Engine 3 sound: every vehicle is a sound source in 3D. Its engine gets louder as it comes closer to the
camera and drops in pitch as it passes (Doppler), just like a real pass-by. Each vehicle has its own
synthesized engine character (car, bus, truck, tractor, diesel and electric trains with clickety-clack,
steam chuffs in time with the wheels, boat motors, propeller, jet, helicopter rotor, cable car hum),
plus the setting's ambience (waves and gulls, city hum, farm birds, mountain wind).
"""
import math

import numpy as np

SR = 44100
RATE = 50          # control rate for positions (Hz)
C_SOUND = 343.0


def _lp(x, k):
    k = max(1, int(k))
    c = np.cumsum(np.insert(x, 0, 0.0))
    y = (c[k:] - c[:-k]) / k
    return np.concatenate([y, np.full(len(x) - len(y), y[-1] if len(y) else 0.0)])


def _ctl(vals, n):
    t = np.arange(n) / SR
    tc = np.arange(len(vals)) / RATE
    return np.interp(t, tc, vals)


def _osc(freq, harmonics=((1, 1.0), (2, 0.5), (3, 0.3), (4, 0.15))):
    ph = 2 * np.pi * np.cumsum(freq) / SR
    return sum(a * np.sin(k * ph) for k, a in harmonics)


def _pulses(rate, width=0.25):
    ph = np.cumsum(rate) / SR
    frac = ph % 1.0
    return np.clip(1 - frac / width, 0, 1) ** 2


def _clacks(dist, n, joint=25.0, spacing=(0.0, 2.6), rng=None):
    """Clickety-clack: a pair of knocks each time a wheel pair crosses a rail joint."""
    out = np.zeros(n)
    click = np.sin(2 * np.pi * 90 * np.arange(int(0.07 * SR)) / SR) * np.exp(-np.arange(int(0.07 * SR)) / (0.015 * SR))
    pos = dist
    for off in spacing:
        idx = np.nonzero(np.diff(np.floor((pos - off) / joint)) != 0)[0]
        for i in idx:
            if i + len(click) < n:
                out[i:i + len(click)] += click * 0.6
    return out


def engine(kind, speed, n, rng, dop):
    """Synthesize one source's engine/motion sound. speed and dop are audio-rate arrays."""
    sp = speed
    noise = rng.standard_normal(n)
    if kind == "car":
        f = (26 + 2.0 * sp) * dop
        x = 0.5 * _osc(f) + 0.35 * _lp(noise, 40) * (0.3 + sp / 25)
        return x * (0.5 + 0.5 * np.clip(sp / 20, 0, 1))
    if kind in ("bus", "truck"):
        f = (18 + 1.3 * sp) * dop
        x = 0.55 * _osc(f, ((1, 1), (2, .7), (3, .5), (5, .3))) + 0.25 * _pulses(f * 2) + 0.3 * _lp(noise, 30) * (0.3 + sp / 20)
        return x
    if kind == "tractor":
        f = (12 + 2.2 * sp) * dop
        return 0.6 * _pulses(f, 0.3) * _lp(noise, 6) * 3 + 0.4 * _osc(f * 2)
    if kind in ("diesel", "electric", "steam"):
        dist = np.cumsum(sp) / SR
        x = 0.8 * _clacks(dist, n, rng=rng) + 0.2 * _lp(noise, 60) * np.clip(sp / 20, 0.2, 1)
        if kind == "diesel":
            x += 0.4 * _osc(38 * dop, ((1, 1), (2, .6), (3, .5), (4, .3)))
        elif kind == "electric":
            x += 0.08 * np.sin(2 * np.pi * np.cumsum((500 + 18 * sp) * dop) / SR) + 0.2 * _osc(30 * dop)
        else:
            rate = sp / (2 * math.pi * 0.9) * 4 * dop      # four chuffs per turn of the driving wheels
            x += 0.9 * _pulses(rate, 0.35) * _lp(noise, 8) * 2.5
        return x
    if kind == "boat":
        f = (40 + 3 * sp) * dop
        return 0.35 * _osc(f, ((1, 1), (2, .8), (3, .4))) + 0.5 * _lp(noise, 25) * (0.4 + sp / 15)
    if kind == "sail":
        return 0.4 * _lp(noise, 50) * (0.5 + 0.5 * np.sin(2 * np.pi * np.arange(n) / SR / 3.0))
    if kind == "prop":
        f = 95 * dop
        return 0.5 * _osc(f, ((1, 1), (2, .7), (3, .4), (4, .3))) * (0.75 + 0.25 * np.sin(np.cumsum(f) / SR * np.pi)) + \
            0.2 * _lp(noise, 20)
    if kind == "jet":
        whine = 0.12 * np.sin(2 * np.pi * np.cumsum(2400 * dop) / SR)
        return 0.7 * _lp(noise, 4) + whine
    if kind == "heli":
        thump = _pulses(np.full(n, 7.0) * dop, 0.2) * _lp(noise, 10) * 3
        return 0.8 * thump + 0.08 * np.sin(2 * np.pi * np.cumsum(1800 * dop) / SR) + 0.15 * _osc(42 * dop)
    if kind == "cable":
        return 0.2 * _osc(np.full(n, 110.0)) * 0.3 + 0.1 * _lp(noise, 80)
    if kind in ("paws", "hooves"):          # footsteps in time with the walk: soft pads, or clip-clop hooves
        dist = np.cumsum(sp) / SR
        step = 0.35 if kind == "paws" else 0.8
        out = np.zeros(n)
        L = int((0.05 if kind == "paws" else 0.07) * SR)
        tt = np.arange(L) / SR
        if kind == "paws":
            click = _lp(rng.standard_normal(L), 6) * np.exp(-tt / 0.012)
        else:
            click = (np.sin(2 * np.pi * 900 * tt) * 0.6 + _lp(rng.standard_normal(L), 3)) * np.exp(-tt / 0.015)
        idx = np.nonzero(np.diff(np.floor(dist / (step / 2))) != 0)[0]
        for i in idx:
            if i + L < n:
                out[i:i + L] += click * rng.uniform(0.6, 1.0)
        return out * (1.0 if kind == "hooves" else 0.5)
    if kind == "wings":                     # soft wing beats (whooshes)
        rate = np.clip(6.0 - sp * 0.3, 2.0, 6.0)
        return 0.6 * _pulses(rate, 0.5) * _lp(noise, 20) * 2.0
    if kind == "swim":                      # gentle water: bubbles and a slow swish
        t = np.arange(n) / SR
        return 0.25 * _lp(noise, 60) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 3.0)) + 0.15 * _pulses(np.full(n, 1.3), 0.08) * _lp(noise, 4)
    return np.zeros(n)


def ambience(theme, n, rng, time="day"):
    t = np.arange(n) / SR
    out = np.zeros(n)
    noise = rng.standard_normal(n)
    if theme == "seaside":
        swell = 0.5 + 0.5 * np.sin(2 * np.pi * t / 7.0) ** 2
        out += 0.45 * _lp(noise, 40) * swell
        for k in range(int(n / SR / 6)):          # a gull now and then
            st = int(rng.uniform(0, n / SR - 1) * SR)
            d = int(0.35 * SR)
            tt = np.arange(d) / SR
            f = 1500 - 900 * tt / 0.35
            g = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / 0.35) * 0.12
            out[st:st + d] += g[: max(0, min(d, n - st))]
    elif theme == "city":
        out += 0.3 * _lp(noise, 120) + 0.1 * _lp(noise, 15)
    elif theme == "farm":
        out += 0.12 * _lp(noise, 60)
        if time != "night":
            for k in range(int(n / SR / 2.5)):    # little birds
                st = int(rng.uniform(0, n / SR - 1) * SR)
                d = int(0.12 * SR)
                tt = np.arange(d) / SR
                f = rng.uniform(2800, 4200) + 600 * np.sin(2 * np.pi * 18 * tt)
                g = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / 0.12) * 0.07
                out[st:st + d] += g[: max(0, min(d, n - st))]
    elif theme == "mountains":
        gust = 0.5 + 0.5 * np.sin(2 * np.pi * t / 11.0 + 1) ** 2
        out += 0.4 * _lp(noise, 160) * gust
    elif theme in ("park", "garden", "farmyard", "forest", "lagoon"):
        out += 0.08 * _lp(noise, 200) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 9.0) ** 2)      # a light breeze
        every = {"lagoon": 1.6, "forest": 2.2}.get(theme, 3.0)
        if time not in ("night", "dusk"):
            for k in range(int(n / SR / every)):        # little birds singing far away
                st = int(rng.uniform(0, n / SR - 1) * SR)
                d = int(0.12 * SR)
                tt = np.arange(d) / SR
                f = rng.uniform(2600, 4200) + 700 * np.sin(2 * np.pi * rng.uniform(12, 22) * tt)
                g = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / 0.12) * 0.05
                out[st:st + d] += g[: max(0, min(d, n - st))]
        if theme == "forest":
            out += 0.12 * _lp(noise, 30) * 0.5         # a stream
    elif theme == "beach":
        swell = 0.5 + 0.5 * np.sin(2 * np.pi * t / 6.0) ** 2
        out += 0.5 * _lp(noise, 40) * swell
    elif theme == "snowfield":
        gust = 0.5 + 0.5 * np.sin(2 * np.pi * t / 11.0 + 1) ** 2
        out += 0.3 * _lp(noise, 160) * gust
    elif theme in ("reef", "pond"):               # under the water: a deep hush and bubbles
        out += 0.35 * _lp(noise, 400)
        for k in range(int(n / SR / 1.2)):
            st = int(rng.uniform(0, n / SR - 1) * SR)
            d = int(0.06 * SR)
            tt = np.arange(d) / SR
            f = rng.uniform(500, 900) * (1 + 2.5 * tt / 0.06)
            g = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / 0.06) * 0.06
            out[st:st + d] += g[: max(0, min(d, n - st))]
    return out


def render_scene(stage, D, theme):
    rng = np.random.default_rng(stage.seed)
    n = int(D * SR)
    ts = np.arange(0, D + 2.0 / RATE, 1.0 / RATE)
    cams = np.array([stage.camera_at(min(t, D - 1e-3)).pos for t in ts])
    cam_v = np.gradient(cams, axis=0) * RATE
    out = np.zeros(n)
    for snd in stage.sounds:
        src = snd["src"]
        P = np.array([src.state(min(t, D - 1e-3))[0] + np.array([0, 0, 1.0]) for t in ts])
        sp = np.array([src.state(min(t, D - 1e-3))[5] for t in ts])
        V = np.gradient(P, axis=0) * RATE
        rel = P - cams
        d = np.linalg.norm(rel, axis=1) + 1e-6
        u = rel / d[:, None]
        v_r = -((V - cam_v) * u).sum(axis=1)               # positive when coming closer
        dop = C_SOUND / (C_SOUND - np.clip(v_r, -120, 120))
        ref = 14.0 if snd.get("hero") else 10.0
        gain = snd.get("level", 1.0) * np.clip(ref / (d + ref * 0.4), 0, 1.6)
        kind = snd["kind"]
        if kind == "boat" and src.model.name in ("sailboat", "rowboat", "canal"):
            kind = "sail" if src.model.name != "canal" else "boat"
        x = engine(kind, _ctl(sp, n), n, rng, _ctl(dop, n))
        x = x / (np.sqrt(np.mean(x ** 2)) + 1e-9) * (0.12 if kind not in ("paws", "hooves", "wings", "swim") else 0.06)
        g = _ctl(gain, n)
        out += x * g
        call = snd.get("call")
        if call and call != "none":          # the animal calls now and then (never during the song's noise game)
            from engine2 import noises
            if call in noises.NOISES:
                r = np.random.default_rng(stage.seed + 17 * len(str(call)))
                tcur = r.uniform(3, 9)
                while tcur < D - 3:
                    if not (38.0 < tcur < 56.0):
                        y = noises.render(call, seed=int(r.integers(1e6)))
                        y = y / (np.sqrt(np.mean(y ** 2)) + 1e-9) * (0.07 if snd.get("hero") else 0.035)
                        i0 = int(tcur * SR)
                        i1 = min(n, i0 + len(y))
                        out[i0:i1] += y[: i1 - i0] * g[i0:i1]
                    tcur += r.uniform(9, 16) if snd.get("hero") else r.uniform(14, 24)
    out += ambience(theme, n, rng, stage.time) * 0.5
    return out
