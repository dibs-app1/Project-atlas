"""Animal sounds kids love to copy: MOO, BAA, OINK, NEIGH, CLUCK, QUACK, TWEET, WOOF, MEOW...

Synthesized from scratch (no samples), the same way as the vehicle noises: a voice-like source (a buzzy
tone whose pitch glides the way the animal's call does) shaped by mouth resonances (formants). Every call
is soft and friendly: rounded attacks (30 ms or more), no screeches, barks are gentle "woofs", and the
final mix is limited. Each sound comes with the word shown on screen when it plays.
"""
import numpy as np

from engine2.noises import SR, _bandpass, _env, _formant, _norm, _rng, _saw, _seq, _t


def _glide(points, dur):
    """Pitch track through (time fraction, Hz) points."""
    t = np.linspace(0, 1, int(dur * SR))
    xs, ys = zip(*points)
    return np.interp(t, xs, ys)


def _voice(f, formants, breath=0.08, rng=None, vib=(5.0, 0.012), q=5.0):
    rng = rng or np.random.default_rng(0)
    t = np.arange(len(f)) / SR
    f = f * (1 + vib[1] * np.sin(2 * np.pi * vib[0] * t))
    x = _saw(f) + breath * rng.standard_normal(len(f))
    return _formant(x, formants, q=q, base=0.05)


def _soft(x, attack=0.03, release=0.12):
    return x * _env(len(x), attack, release)


def moo(seed=0):
    r = _rng(seed)
    f = _glide([(0, 105), (0.25, 128), (0.7, 122), (1, 92)], 1.5 + r.uniform(-0.1, 0.2))
    x = _voice(f, [(330, 1.0), (750, 0.5), (2300, 0.08)], breath=0.06, rng=r, vib=(4.0, 0.015))
    return _norm(_soft(x, 0.12, 0.35))


def baa(seed=0, goat=False):
    r = _rng(seed)
    base = 330 if goat else 280
    f = _glide([(0, base * 0.9), (0.15, base * 1.05), (1, base * 0.92)], 0.9 + r.uniform(0, 0.15))
    t = np.arange(len(f)) / SR
    trem = 1 - 0.35 * (0.5 + 0.5 * np.sin(2 * np.pi * 22 * t))       # the bleat's flutter
    x = _voice(f, [(850, 1.0), (1250, 0.6), (2600, 0.12)], breath=0.1, rng=r, vib=(6.0, 0.02)) * trem
    return _norm(_soft(x, 0.05, 0.2))


def maa(seed=0):
    return baa(seed, goat=True)


def oink(seed=0, n=2):
    r = _rng(seed)
    parts = []
    for k in range(n):
        f = _glide([(0, 160), (0.5, 200), (1, 150)], 0.2 + r.uniform(0, 0.05))
        x = _voice(f, [(600, 1.0), (1500, 0.5)], breath=0.35, rng=r, q=4)
        parts.append(_soft(x, 0.03, 0.06))
    return _norm(_seq(parts, [0.16] * (n - 1)))


def neigh(seed=0):
    r = _rng(seed)
    f = _glide([(0, 520), (0.15, 820), (0.5, 640), (1, 360)], 1.3)
    t = np.arange(len(f)) / SR
    f = f * (1 + 0.05 * np.sin(2 * np.pi * 11 * t) * np.clip(t / 0.3, 0, 1))      # the whinny's wobble
    x = _voice(f, [(900, 1.0), (1700, 0.5)], breath=0.12, rng=r, vib=(1, 0))
    snort = _bandpass(r.standard_normal(int(0.3 * SR)), 300, 1600) * 0.4
    return _norm(_seq([_soft(x, 0.06, 0.3), _soft(snort, 0.03, 0.12)], [0.15]))


def cluck(seed=0, n=4):
    r = _rng(seed)
    parts = []
    for k in range(n):
        f = _glide([(0, 380), (1, 330)], 0.11 + r.uniform(0, 0.03))
        parts.append(_soft(_voice(f, [(1000, 1.0), (2200, 0.4)], breath=0.2, rng=r), 0.02, 0.04))
    return _norm(_seq(parts, [r.uniform(0.12, 0.2) for _ in range(n - 1)]))


def rooster(seed=0):
    """Cock-a-doodle-doo, gentle: four rounded notes, the last one long."""
    r = _rng(seed)
    notes = [(0.16, 520), (0.14, 640), (0.2, 700), (0.8, 640)]
    parts = []
    for d, hz in notes:
        f = _glide([(0, hz * 0.95), (0.3, hz * 1.04), (1, hz * (0.85 if d > 0.5 else 1.0))], d)
        parts.append(_soft(_voice(f, [(1100, 1.0), (2300, 0.3)], breath=0.08, rng=r, vib=(7, 0.02)), 0.03, 0.08))
    return _norm(_seq(parts, [0.04, 0.04, 0.05]))


def quack(seed=0, n=2):
    r = _rng(seed)
    parts = []
    for k in range(n):
        f = _glide([(0, 260), (0.4, 300), (1, 220)], 0.22)
        parts.append(_soft(_voice(f, [(1100, 1.0), (2600, 0.6)], breath=0.15, rng=r, q=3), 0.03, 0.08))
    return _norm(_seq(parts, [0.18] * (n - 1)))


def peep(seed=0, n=3):
    r = _rng(seed)
    parts = []
    for k in range(n):
        d = 0.12
        tt = _t(d)
        f = 3200 + 900 * tt / d
        parts.append(_soft(np.sin(2 * np.pi * np.cumsum(f) / SR), 0.02, 0.04))
    return _norm(_seq(parts, [0.1] * (n - 1)), 0.6)


def tweet(seed=0):
    """A songbird's little tune: quick bright chirps and a trill."""
    r = _rng(seed)
    parts = []
    for k in range(3):
        d = r.uniform(0.07, 0.11)
        tt = _t(d)
        f0, f1 = r.uniform(3000, 3600), r.uniform(4200, 5000)
        f = f0 + (f1 - f0) * tt / d
        parts.append(_soft(np.sin(2 * np.pi * np.cumsum(f) / SR), 0.015, 0.03))
    tt = _t(0.45)
    f = 3800 + 500 * np.sin(2 * np.pi * 24 * tt)
    parts.append(_soft(np.sin(2 * np.pi * np.cumsum(f) / SR), 0.03, 0.1))
    return _norm(_seq(parts, [0.06, 0.06, 0.1]), 0.55)


def gull(seed=0, n=3):
    r = _rng(seed)
    parts = []
    for k in range(n):
        f = _glide([(0, 1200), (0.25, 1500), (1, 850)], 0.35)
        parts.append(_soft(_voice(f, [(1600, 1.0), (3000, 0.3)], breath=0.05, rng=r), 0.03, 0.1))
    return _norm(_seq(parts, [0.12] * (n - 1)), 0.7)


def hoot(seed=0):
    r = _rng(seed)
    parts = []
    for d, hz in ((0.35, 390), (0.2, 360), (0.55, 380)):
        f = _glide([(0, hz * 0.97), (0.3, hz), (1, hz * 0.94)], d)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.15 * np.sin(4 * np.pi * np.cumsum(f) / SR)
        parts.append(_soft(x + 0.04 * r.standard_normal(len(x)), 0.06, 0.12))
    return _norm(_seq(parts, [0.12, 0.08]), 0.8)


def coo(seed=0):
    r = _rng(seed)
    parts = []
    for d, hz in ((0.3, 300), (0.45, 270)):
        f = _glide([(0, hz), (0.4, hz * 1.08), (1, hz * 0.92)], d)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * (1 + 0.3 * np.sin(2 * np.pi * 30 * _t(d)))
        parts.append(_soft(x, 0.05, 0.1))
    return _norm(_seq(parts, [0.1]), 0.8)


def honk(seed=0, n=2):
    """A swan's (or goose's) soft trumpet honk."""
    r = _rng(seed)
    parts = []
    for k in range(n):
        f = _glide([(0, 420), (0.3, 460), (1, 400)], 0.3)
        parts.append(_soft(_voice(f, [(900, 1.0), (1800, 0.4)], breath=0.08, rng=r, q=4), 0.04, 0.1))
    return _norm(_seq(parts, [0.2] * (n - 1)), 0.8)


def squawk(seed=0):
    """A parrot's friendly call, rounded so it never shrieks."""
    r = _rng(seed)
    f = _glide([(0, 700), (0.3, 950), (1, 650)], 0.45)
    x = _voice(f, [(1300, 1.0), (2400, 0.4)], breath=0.15, rng=r, q=4)
    x = _bandpass(x, 300, 3200)
    return _norm(_soft(x, 0.04, 0.12), 0.75)


def screech(seed=0):
    """An eagle's call: a thin, high, descending whistle (gentle, not piercing)."""
    r = _rng(seed)
    parts = []
    for d in (0.18, 0.18, 0.5):
        f = _glide([(0, 2200), (1, 1600)], d)
        parts.append(_soft(np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.03 * r.standard_normal(int(d * SR)), 0.03, 0.08))
    return _norm(_seq(parts, [0.06, 0.06]), 0.5)


def penguin(seed=0):
    """A penguin's braying call: soft rising honks."""
    r = _rng(seed)
    parts = []
    for k, hz in enumerate((300, 340, 380, 420)):
        f = _glide([(0, hz), (1, hz * 1.1)], 0.18)
        parts.append(_soft(_voice(f, [(800, 1.0), (1600, 0.4)], breath=0.1, rng=r, q=4), 0.03, 0.06))
    return _norm(_seq(parts, [0.07] * 3), 0.8)


def woof(seed=0, n=2, puppy=False):
    """A friendly 'woof' (rounded, low, never a sharp bark)."""
    r = _rng(seed)
    parts = []
    for k in range(n):
        hz = 420 if puppy else 230
        f = _glide([(0, hz * 0.9), (0.3, hz * 1.1), (1, hz * 0.8)], 0.2 if puppy else 0.26)
        x = _voice(f, [(550 if not puppy else 900, 1.0), (1300, 0.4)], breath=0.3, rng=r, q=3)
        parts.append(_soft(_bandpass(x, 120, 2600), 0.035, 0.1))
    return _norm(_seq(parts, [0.24] * (n - 1)), 0.85)


def yip(seed=0):
    return woof(seed, n=3, puppy=True)


def meow(seed=0, kitten=False):
    r = _rng(seed)
    hz = 640 if kitten else 470
    f = _glide([(0, hz * 0.9), (0.35, hz * 1.25), (1, hz * 0.8)], 0.6 if kitten else 0.8)
    n = len(f)
    t = np.linspace(0, 1, n)
    # the mouth opens (ee -> aa -> oo): two formants that glide
    x = _saw(f) + 0.05 * r.standard_normal(n)
    a = _formant(x, [(500, 1.0), (1800, 0.5)], q=5)
    b = _formant(x, [(900, 1.0), (1300, 0.5)], q=5)
    c = _formant(x, [(450, 1.0), (900, 0.4)], q=5)
    w1 = np.clip(1 - t * 3, 0, 1)
    w3 = np.clip(t * 2 - 1, 0, 1)
    y = a * w1 + b * (1 - w1 - w3).clip(0) + c * w3
    return _norm(_soft(y, 0.05, 0.18), 0.85)


def mew(seed=0):
    return meow(seed, kitten=True)


def purr(seed=0):
    r = _rng(seed)
    d = 1.6
    t = _t(d)
    x = _bandpass(r.standard_normal(len(t)), 40, 400) * (0.5 + 0.5 * np.sin(2 * np.pi * 24 * t)) ** 2
    x *= 0.6 + 0.4 * np.sin(2 * np.pi * t / 0.8) ** 2
    return _norm(_soft(x, 0.2, 0.4), 0.8)


def hee_haw(seed=0):
    r = _rng(seed)
    parts = []
    for k in range(2):
        hi = _soft(_voice(_glide([(0, 600), (1, 660)], 0.32), [(1000, 1.0), (2200, 0.4)], breath=0.1, rng=r, q=4), 0.04, 0.06)
        lo = _soft(_voice(_glide([(0, 260), (1, 230)], 0.38), [(600, 1.0), (1200, 0.4)], breath=0.2, rng=r, q=4), 0.04, 0.1)
        parts += [_bandpass(hi, 150, 3000), _bandpass(lo, 100, 2400)]
    return _norm(_seq(parts, [0.04, 0.12, 0.04]), 0.8)


def blub(seed=0, n=4):
    """Bubbles: little rising 'bloop' pops."""
    r = _rng(seed)
    parts = []
    for k in range(n):
        d = r.uniform(0.06, 0.1)
        tt = _t(d)
        f = r.uniform(400, 700) * (1 + 3 * tt / d)
        parts.append(_soft(np.sin(2 * np.pi * np.cumsum(f) / SR), 0.008, 0.03))
    return _norm(_seq(parts, [r.uniform(0.06, 0.14) for _ in range(n - 1)]), 0.6)


def dolphin(seed=0):
    """Clicks and a happy whistle."""
    r = _rng(seed)
    clicks = np.zeros(int(0.35 * SR))
    for k in range(9):
        i = int(k * 0.035 * SR)
        n = int(0.004 * SR)
        clicks[i:i + n] += np.hanning(n) * r.uniform(0.5, 1)
    clicks = _bandpass(clicks, 1500, 7000)
    tt = _t(0.7)
    f = 5000 + 2500 * np.sin(np.pi * tt / 0.7) + 600 * np.sin(2 * np.pi * 6 * tt)
    whistle = _soft(np.sin(2 * np.pi * np.cumsum(f) / SR), 0.04, 0.1)
    return _norm(_seq([_norm(clicks, 0.3), whistle * 0.5], [0.1]), 0.55)


def whale(seed=0):
    """Whale song: a long, low, smooth glide."""
    r = _rng(seed)
    f = _glide([(0, 140), (0.3, 260), (0.6, 220), (1, 120)], 2.4)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)
    return _norm(_soft(x, 0.3, 0.6), 0.85)


def click_clack(seed=0, n=4):
    """A crab's claws: little clicks."""
    r = _rng(seed)
    parts = []
    for k in range(n):
        x = _bandpass(r.standard_normal(int(0.03 * SR)), 1500, 5000)
        parts.append(_soft(x, 0.002, 0.02))
    return _norm(_seq(parts, [0.14] * (n - 1)), 0.6)


def splash_small(seed=0):
    r = _rng(seed)
    d = 0.7
    t = _t(d)
    x = _bandpass(r.standard_normal(len(t)), 400, 5000) * np.exp(-t / 0.18)
    return _norm(_soft(x, 0.01, 0.2), 0.7)


ANIMAL_NOISES = {
    # name: (function, word on screen, colour)
    "moo": (moo, "MOO!", (255, 236, 200)),
    "baa": (baa, "BAA!", (250, 250, 250)),
    "maa": (maa, "MAA!", (240, 230, 200)),
    "oink": (oink, "OINK OINK!", (255, 170, 190)),
    "neigh": (neigh, "NEIGH!", (230, 190, 140)),
    "cluck": (cluck, "CLUCK CLUCK!", (255, 210, 120)),
    "rooster": (rooster, "COCK-A-DOODLE-DOO!", (255, 140, 100)),
    "quack": (quack, "QUACK QUACK!", (140, 230, 160)),
    "peep": (peep, "PEEP PEEP!", (255, 236, 110)),
    "tweet": (tweet, "TWEET TWEET!", (255, 200, 140)),
    "gull": (gull, "KEE-OW!", (220, 236, 255)),
    "hoot": (hoot, "HOO HOO!", (220, 200, 255)),
    "coo": (coo, "COO COO!", (200, 210, 236)),
    "honk": (honk, "HONK HONK!", (255, 236, 200)),
    "squawk": (squawk, "SQUAWK!", (120, 230, 140)),
    "screech": (screech, "SCREE!", (255, 220, 150)),
    "penguin": (penguin, "HONK HONK!", (200, 230, 255)),
    "woof": (woof, "WOOF WOOF!", (255, 200, 120)),
    "yip": (yip, "YIP YIP!", (255, 220, 140)),
    "meow": (meow, "MEOW!", (255, 190, 220)),
    "mew": (mew, "MEW MEW!", (255, 200, 230)),
    "purr": (purr, "PURRRR...", (240, 200, 250)),
    "hee_haw": (hee_haw, "HEE-HAW!", (220, 220, 220)),
    "blub": (blub, "BLUB BLUB!", (140, 220, 255)),
    "dolphin": (dolphin, "EEE-EEE!", (170, 230, 255)),
    "whale": (whale, "WOOOOO!", (150, 190, 255)),
    "click_clack": (click_clack, "CLICK CLACK!", (255, 150, 120)),
    "splash_small": (splash_small, "SPLASH!", (120, 200, 255)),
}
