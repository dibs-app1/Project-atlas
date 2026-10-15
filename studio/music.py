"""Calm background music, synthesized from scratch (no samples, no licensing).

Each video gets its own key, tempo, chord progression, melody and lead instrument.
Slow tempo, soft attacks, no drums, no vocals, peaks kept well below full scale.
"""
import random
import wave

import numpy as np

SR = 44100
PENTA = [0, 2, 4, 7, 9]
PROGRESSIONS = [
    [0, 5, 3, 4],   # I vi IV V
    [0, 3, 5, 4],   # I IV vi V
    [0, 4, 5, 3],   # I V vi IV
    [5, 3, 0, 4],   # vi IV I V
    [0, 3, 0, 4],   # I IV I V
    [0, 2, 3, 0],   # I iii IV I
]
MAJOR = [0, 2, 4, 5, 7, 9, 11]

INSTRUMENTS = {
    # name: (partials [(ratio, amp)], decay seconds, attack seconds)
    "music_box": ([(1, 1.0), (2, 0.25), (4.2, 0.12)], 1.6, 0.004),
    "piano": ([(1, 1.0), (2, 0.4), (3, 0.15), (4, 0.06)], 2.2, 0.008),
    "harp": ([(1, 1.0), (2, 0.35), (3, 0.1)], 2.6, 0.006),
    "marimba": ([(1, 1.0), (3.9, 0.18), (9.2, 0.04)], 1.0, 0.003),
    "flute": ([(1, 1.0), (2, 0.12), (3, 0.04)], 0.0, 0.12),
    "guitar": ([(1, 1.0), (2, 0.5), (3, 0.22), (4, 0.1)], 1.9, 0.005),
    "bells": ([(1, 1.0), (2.76, 0.3), (5.4, 0.1)], 2.4, 0.003),
}


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def note(freq, dur, inst, vel, rng):
    partials, decay, attack = INSTRUMENTS[inst]
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    vib = 1 + (0.003 * np.sin(2 * np.pi * 4.5 * t) if inst == "flute" else 0)
    for ratio, amp in partials:
        sig += amp * np.sin(2 * np.pi * freq * ratio * vib * t + rng.uniform(0, 6.28))
    env = np.minimum(1.0, t / attack)
    if decay:
        env *= np.exp(-t / decay)
    else:  # sustained (flute): soft swell and release
        env *= np.minimum(1.0, (dur - t) / 0.4).clip(0, 1)
    rel = np.minimum(1.0, (dur - t) / 0.05).clip(0, 1)
    return sig * env * rel * vel


def pad(freqs, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for f in freqs:
        for det in (-0.6, 0.0, 0.7):
            sig += np.sin(2 * np.pi * (f + det) * t) + 0.12 * np.sin(2 * np.pi * 2 * (f + det) * t)
    a = min(2.5, dur / 3)
    env = np.minimum(1.0, t / a) * np.minimum(1.0, (dur - t) / a)
    return sig * env / (len(freqs) * 3)


def reverb(x, seconds=2.8, mix=0.28, seed=0):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / (SR * seconds / 5))
    ir = np.convolve(ir, np.ones(24) / 24, mode="same")  # darken the tail
    ir /= np.sqrt(np.sum(ir ** 2))
    out = np.zeros(len(x) + n)
    block = 1 << 17
    nfft = 1 << int(np.ceil(np.log2(block + n)))
    IR = np.fft.rfft(ir, nfft)
    for s in range(0, len(x), block):
        seg = x[s:s + block]
        y = np.fft.irfft(np.fft.rfft(seg, nfft) * IR, nfft)[:len(seg) + n]
        out[s:s + len(y)] += y
    wet = out[:len(x)]
    return (1 - mix) * x + mix * wet * 0.5


def ambience(kind, n, rng):
    if not kind:
        return np.zeros(n)
    noise = rng.standard_normal(n)
    k = {"water": 400, "wind": 900, "rain": 120}.get(kind, 600)
    smooth = np.convolve(noise, np.ones(k) / k, mode="same")  # heavy low-pass
    t = np.arange(n) / SR
    swell = 0.6 + 0.4 * np.sin(2 * np.pi * t / rng.uniform(9, 15))
    sig = smooth * swell
    return sig / (np.max(np.abs(sig)) + 1e-9)


def compose(seed, seconds, root=None, bpm=None, inst=None, amb=None):
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    root = root if root is not None else rng.choice([53, 55, 57, 58, 60, 62])  # F3..D4
    bpm = bpm or rng.choice([58, 62, 66, 70, 74])
    inst = inst or rng.choice(list(INSTRUMENTS))
    prog = rng.choice(PROGRESSIONS)
    beat = 60.0 / bpm
    bar = beat * 4
    n = int(seconds * SR)
    mix_ = np.zeros(n + SR * 4)

    def add(sig, at):
        i = int(at * SR)
        if i >= len(mix_):
            return
        sig = sig[:len(mix_) - i]
        mix_[i:i + len(sig)] += sig

    t, k = 0.0, 0
    phrase = [rng.choice(range(len(PENTA) * 2)) for _ in range(8)]
    while t < seconds:
        degree = prog[k % len(prog)]
        chord_root = root + MAJOR[degree]
        third = root + MAJOR[(degree + 2) % 7] + (12 if (degree + 2) >= 7 else 0)
        fifth = root + MAJOR[(degree + 4) % 7] + (12 if (degree + 4) >= 7 else 0)
        chord = [chord_root - 12, chord_root, third, fifth]
        add(pad([midi_hz(m) for m in chord[1:]], bar * 2 + 1.5) * 0.22, t)
        add(note(midi_hz(chord_root - 12), bar * 2, "harp", 0.18, rng), t)  # soft bass
        # sparse melody: a gently varied repeating phrase, with long rests
        if k % 4 != 3:
            if k % 8 == 0:
                phrase = [p if rng.random() < 0.7 else rng.choice(range(len(PENTA) * 2)) for p in phrase]
            for j in range(8):
                if rng.random() < 0.45:
                    continue
                step = phrase[j]
                midi = root + 12 + PENTA[step % 5] + 12 * (step // 5)
                dur = beat * rng.choice([1, 1, 2]) + (1.2 if INSTRUMENTS[inst][1] == 0 else 2.5)
                add(note(midi_hz(midi), dur, inst, rng.uniform(0.12, 0.2), rng), t + j * beat)
        t += bar * 2
        k += 1

    out = mix_[:n]
    out = reverb(out, seed=seed)
    if amb:
        out += 0.05 * ambience(amb, n, nrng)
    # fades and level: peaks at about -6 dBFS before loudness normalisation
    tt = np.arange(n) / SR
    out *= np.minimum(1.0, tt / 4.0) * np.minimum(1.0, (seconds - tt) / 8.0).clip(0, 1)
    out /= np.max(np.abs(out)) + 1e-9
    out *= 0.5
    return out, dict(root=root, bpm=bpm, instrument=inst, progression=prog)


def write_wav(path, mono):
    st = np.stack([mono, mono], axis=1)
    data = (st * 32767).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data)
