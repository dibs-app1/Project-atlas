"""Vehicle noises kids know and love to copy: BEEP BEEP, HONK, VROOM, CHOO CHOO, TOOT TOOT, ZOOM...

Synthesized from scratch (no samples): horns are stacks of buzzy tones shaped by a resonant filter,
whistles are breathy pipe chords, engines are revving sawtooth growls. Each noise comes with the word
shown on screen when it plays. Levels are lively but soft-edged (no sudden clicks, short attacks of
20 ms or more) and the final mix is limited, so nothing is harsh.
"""
import numpy as np

SR = 44100


def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _fft_filter(x, shape):
    """Filter by multiplying the spectrum with shape(freqs)."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    return np.fft.irfft(X * shape(f), n)


def _bandpass(x, lo, hi, soft=1.6):
    return _fft_filter(x, lambda f: 1 / (1 + (lo / np.maximum(f, 1)) ** (2 * soft)) / (1 + (f / hi) ** (2 * soft)))


def _formant(x, centres, q=6.0, base=0.15):
    def shape(f):
        g = np.full_like(f, base)
        for c, a in centres:
            g += a / (1 + ((f - c) / (c / q)) ** 2)
        return g
    return _fft_filter(x, shape)


def _saw(freq_track):
    ph = np.cumsum(freq_track / SR) % 1.0
    return 2 * ph - 1


def _square(freq_track, duty=0.5):
    ph = np.cumsum(freq_track / SR) % 1.0
    return np.where(ph < duty, 1.0, -1.0)


def _env(n, attack=0.02, release=0.06):
    t = np.arange(n) / SR
    d = n / SR
    return np.minimum(1, t / attack) * np.clip((d - t) / release, 0, 1)


def _norm(x, peak=0.9):
    return x / (np.max(np.abs(x)) + 1e-9) * peak


def _seq(parts, gaps):
    out = []
    for i, p in enumerate(parts):
        out.append(p)
        if i < len(gaps):
            out.append(np.zeros(int(gaps[i] * SR)))
    return np.concatenate(out)


def _rng(seed):
    return np.random.default_rng(seed)


# ------------------------------------------------------------------ horns

def car_horn(seed=0, n=2):
    """BEEP BEEP: two disc horns a third apart, bright and buzzy."""
    def blast(d):
        t = _t(d)
        f = np.ones_like(t)
        x = 0.6 * _square(420 * f, 0.4) + 0.5 * _square(512 * f, 0.38)
        x = _formant(x, [(2400, 1.0), (3300, 0.6), (1100, 0.4)], q=4)
        return x * _env(len(t), 0.02, 0.04)
    return _norm(_seq([blast(0.22)] * (n - 1) + [blast(0.32)], [0.1] * (n - 1)))


def truck_horn(seed=0, n=2):
    """HONK HONK: a deep air-horn chord with a little pitch scoop at the start."""
    def blast(d):
        t = _t(d)
        scoop = 1 - 0.04 * np.exp(-t / 0.05)
        x = sum(a * _saw(f * scoop) for f, a in ((233, 1.0), (294, 0.8), (349, 0.7)))
        x = _formant(x, [(900, 1.0), (1800, 0.6)], q=3, base=0.25)
        return x * _env(len(t), 0.03, 0.08)
    return _norm(_seq([blast(0.45)] * (n - 1) + [blast(0.7)], [0.12] * (n - 1)))


def bus_horn(seed=0, n=2):
    """BEEP BEEP, but rounder and lower than a car."""
    def blast(d):
        t = _t(d)
        x = 0.7 * _square(330 * np.ones_like(t), 0.42) + 0.6 * _square(392 * np.ones_like(t), 0.4)
        x = _formant(x, [(1600, 1.0), (2600, 0.5)], q=4, base=0.2)
        return x * _env(len(t), 0.025, 0.06)
    return _norm(_seq([blast(0.28)] * (n - 1) + [blast(0.4)], [0.12] * (n - 1)))


def reverse_beeper(seed=0, n=4):
    """BEEP... BEEP... BEEP: the big truck backing up."""
    t = _t(0.32)
    b = np.sin(2 * np.pi * 1050 * t) + 0.25 * np.sin(2 * np.pi * 3150 * t)
    b *= _env(len(t), 0.02, 0.03)
    return _norm(_seq([b] * n, [0.32] * (n - 1)), 0.75)


def vroom(seed=0, n=2):
    """VROOM VROOM: the engine revs up and settles back down."""
    rng = _rng(seed)
    parts = []
    for _ in range(n):
        d = 1.0
        t = _t(d)
        rpm = 38 + 92 * np.sin(np.pi * np.clip(t / 0.75, 0, 1)) ** 0.8
        x = _saw(rpm) + 0.5 * _saw(rpm * 2.01) + 0.3 * _square(rpm * 0.5, 0.3)
        cut = 300 + 1500 * np.sin(np.pi * np.clip(t / 0.75, 0, 1))
        # time-varying lowpass, done in short blocks
        y = np.zeros_like(x)
        blk = 2048
        for i in range(0, len(x), blk // 2):
            seg = x[i:i + blk]
            if len(seg) < 16:
                break
            c = cut[min(i + len(seg) // 2, len(cut) - 1)]
            w = np.hanning(len(seg))
            y[i:i + len(seg)] += _fft_filter(seg * w, lambda f, c=c: 1 / (1 + (f / c) ** 4))
        y += 0.15 * _bandpass(rng.standard_normal(len(t)), 200, 2500) * (rpm / 130)
        parts.append(y * _env(len(t), 0.05, 0.2))
    return _norm(_seq(parts, [0.1] * (n - 1)))


def ice_cream(seed=0):
    """Ding-a-ling: the ice-cream truck's music-box tune."""
    melody = [(76, 0.18), (79, 0.18), (84, 0.18), (79, 0.18), (81, 0.18), (84, 0.36), (88, 0.5)]
    out = []
    for m, d in melody:
        f = 440 * 2 ** ((m - 69) / 12)
        t = _t(d + 0.3)
        x = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2 * t) + 0.12 * np.sin(2 * np.pi * f * 4.2 * t))
        x *= np.minimum(1, t / 0.005) * np.exp(-t / 0.35)
        out.append((x, d))
    total = sum(d for _, d in out) + 0.4
    y = np.zeros(int(total * SR))
    pos = 0.0
    for x, d in out:
        i = int(pos * SR)
        y[i:i + len(x)] += x[: len(y) - i]
        pos += d
    return _norm(y, 0.7)


# ------------------------------------------------------------------ trains

def steam_whistle(seed=0, n=2):
    """CHOO CHOO (whoo-whoo): three breathy pipes, a little bend at the end of each toot."""
    rng = _rng(seed)
    def toot(d):
        t = _t(d)
        bend = 1 - 0.025 * np.clip((t - d + 0.15) / 0.15, 0, 1)
        x = sum(a * np.sin(2 * np.pi * np.cumsum(f * bend / SR)) for f, a in ((440, 1.0), (554, 0.8), (659, 0.7)))
        x += 0.3 * sum(a * np.sin(2 * np.pi * np.cumsum(2 * f * bend / SR)) for f, a in ((440, 1.0), (554, 0.6)))
        breath = _bandpass(rng.standard_normal(len(t)), 900, 3200) * 0.35
        return (x * 0.5 + breath) * _env(len(t), 0.06, 0.12)
    return _norm(_seq([toot(0.42)] * (n - 1) + [toot(0.75)], [0.1] * (n - 1)))


def chugga(seed=0, beats=8, beat=0.27):
    """chugga-chugga: steam puffs, strong-weak."""
    rng = _rng(seed)
    out = np.zeros(int((beats * beat + 0.5) * SR))
    for k in range(beats):
        n = int(0.2 * SR)
        p = _bandpass(rng.standard_normal(n), 150, 1800) * np.exp(-np.arange(n) / (0.055 * SR))
        i = int(k * beat * SR)
        out[i:i + n] += p * (1.0 if k % 2 == 0 else 0.6)
    return _norm(out, 0.8)


def diesel_horn(seed=0, n=2):
    """HOOOONK: the five-chime horn of a diesel or electric train."""
    def blast(d):
        t = _t(d)
        x = sum(_saw(f * np.ones_like(t)) * a for f, a in ((311, 1.0), (370, 0.9), (415, 0.8), (494, 0.7), (554, 0.6)))
        x = _formant(x, [(1100, 1.0), (2200, 0.5)], q=3, base=0.25)
        return x * _env(len(t), 0.04, 0.12)
    return _norm(_seq([blast(0.5)] * (n - 1) + [blast(0.9)], [0.15] * (n - 1)))


def tram_bell(seed=0, n=2):
    """DING DING: the tram's bell."""
    def ding():
        t = _t(0.9)
        x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / dcy) for f, a, dcy in
                ((1568, 1.0, 0.5), (3920, 0.5, 0.25), (5300, 0.25, 0.12), (784, 0.2, 0.6)))
        return x * np.minimum(1, t / 0.002 + 0.0)
    a = ding()
    y = np.zeros(int((0.28 * (n - 1) + 0.9) * SR))
    for k in range(n):
        i = int(k * 0.28 * SR)
        y[i:i + len(a)] += a[: len(y) - i]
    return _norm(y, 0.75)


# ------------------------------------------------------------------ boats

def ship_horn(seed=0, n=1):
    """BWOOOOM: a big ship's deep horn."""
    def blast(d):
        t = _t(d)
        x = _saw(98 * np.ones_like(t)) + 0.7 * _saw(147 * np.ones_like(t))
        x = _formant(x, [(300, 1.0), (620, 0.7), (1200, 0.25)], q=3, base=0.1)
        return x * _env(len(t), 0.12, 0.35)
    return _norm(_seq([blast(1.8)] * n, [0.3] * (n - 1)))


def tug_toot(seed=0, n=2):
    """TOOT TOOT: a tugboat's cheerful horn."""
    def blast(d):
        t = _t(d)
        x = _saw(196 * np.ones_like(t)) + 0.6 * _saw(247 * np.ones_like(t))
        x = _formant(x, [(500, 1.0), (1000, 0.6), (2200, 0.2)], q=3, base=0.12)
        return x * _env(len(t), 0.04, 0.1)
    return _norm(_seq([blast(0.4)] * (n - 1) + [blast(0.65)], [0.14] * (n - 1)))


def outboard(seed=0):
    """BRRRRM: a speedboat's outboard motor buzzing past."""
    rng = _rng(seed)
    t = _t(2.2)
    f = 70 + 40 * np.sin(np.pi * np.clip(t / 1.4, 0, 1))
    x = _square(f, 0.3) + 0.4 * _saw(f * 2)
    x = _formant(x, [(700, 1.0), (1500, 0.5)], q=2, base=0.2)
    x += 0.25 * _bandpass(rng.standard_normal(len(t)), 800, 4000)
    return _norm(x * _env(len(t), 0.3, 0.6))


def splash(seed=0):
    """SPLASH!"""
    rng = _rng(seed)
    t = _t(1.3)
    x = _bandpass(rng.standard_normal(len(t)), 300, 6000) * np.exp(-t / 0.3) * np.minimum(1, t / 0.02)
    for k in range(10):       # bubbles
        st = rng.uniform(0.1, 0.9)
        f0 = rng.uniform(500, 1200)
        bt = np.clip(t - st, 0, None)
        x += 0.15 * np.sin(2 * np.pi * f0 * (1 + 2 * bt) * bt) * np.exp(-bt / 0.04) * (t > st)
    return _norm(x, 0.8)


# ------------------------------------------------------------------ planes

def jet_zoom(seed=0):
    """ZOOOOM: a jet whooshes past, its whine dropping as it goes."""
    rng = _rng(seed)
    d = 2.6
    t = _t(d)
    env = np.exp(-((t - 1.1) / 0.55) ** 2)
    noise = rng.standard_normal(len(t))
    y = np.zeros_like(t)
    blk = 4096
    for i in range(0, len(t), blk // 2):
        seg = noise[i:i + blk]
        if len(seg) < 64:
            break
        c = 500 + 2500 * env[min(i + len(seg) // 2, len(t) - 1)]
        y[i:i + len(seg)] += _fft_filter(seg * np.hanning(len(seg)), lambda f, c=c: 1 / (1 + ((f - c) / (c * 0.7)) ** 2))
    whine_f = 2200 * (1 + 0.12 * np.tanh((1.1 - t) * 3))
    whine = np.sin(2 * np.pi * np.cumsum(whine_f / SR)) * 0.25
    return _norm((y + whine) * env * np.minimum(1, t / 0.2))


def prop_buzz(seed=0):
    """BRRRRR: a little propeller plane flies over."""
    rng = _rng(seed)
    t = _t(2.6)
    env = np.exp(-((t - 1.2) / 0.7) ** 2)
    f = 95 * (1 + 0.06 * np.tanh((1.2 - t) * 2))
    x = _saw(f) + 0.6 * _square(f * 2, 0.35)
    x *= 0.7 + 0.3 * np.sin(2 * np.pi * np.cumsum(f * 0.5 / SR))
    x = _formant(x, [(600, 1.0), (1400, 0.4)], q=2, base=0.2)
    x += 0.1 * _bandpass(rng.standard_normal(len(t)), 300, 3000)
    return _norm(x * env)


NOISES = {
    # name: (function, word on screen, bubble colour)
    "car_horn": (car_horn, "BEEP BEEP!", (255, 214, 64)),
    "truck_horn": (truck_horn, "HONK HONK!", (255, 150, 60)),
    "bus_horn": (bus_horn, "BEEP BEEP!", (255, 214, 64)),
    "reverse": (reverse_beeper, "BEEP... BEEP... BEEP!", (255, 186, 70)),
    "vroom": (vroom, "VROOM VROOM!", (255, 110, 90)),
    "ice_cream": (ice_cream, "DING-A-LING!", (255, 160, 210)),
    "steam_whistle": (steam_whistle, "CHOO CHOO!", (255, 240, 120)),
    "chugga": (chugga, "CHUGGA CHUGGA!", (200, 230, 255)),
    "diesel_horn": (diesel_horn, "HOOONK!", (255, 170, 80)),
    "tram_bell": (tram_bell, "DING DING!", (255, 228, 120)),
    "ship_horn": (ship_horn, "BWOOOM!", (140, 210, 255)),
    "tug_toot": (tug_toot, "TOOT TOOT!", (120, 230, 200)),
    "outboard": (outboard, "BRRRRM!", (130, 220, 255)),
    "splash": (splash, "SPLASH!", (120, 200, 255)),
    "jet_zoom": (jet_zoom, "ZOOOOM!", (170, 210, 255)),
    "prop_buzz": (prop_buzz, "BRRRRR!", (190, 240, 160)),
}


def render(name, seed=0):
    fn = NOISES[name][0]
    return fn(seed=seed)


def word(name):
    return NOISES[name][1]


def colour(name):
    return NOISES[name][2]
