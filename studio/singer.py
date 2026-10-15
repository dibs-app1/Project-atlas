"""The Singer: turns lyrics + a melody into a sung vocal track.

A neural text-to-speech voice (Piper) says each word; the WORLD vocoder (pyworld) then re-sings it:
the word is stretched to the length of its notes (consonants kept crisp, vowels held), its pitch is
replaced by the melody (with a little glide and vibrato), and the voice is brightened a touch so it
sounds like a friendly children's singer. A few slightly different copies make a small choir.

    python studio/singer.py            # sings a test line into /tmp/singer_test.wav
"""
import functools
import io
import re
import tarfile
import urllib.request
import wave
from pathlib import Path

import numpy as np

SR = 44100
VOICE_DIR = Path(__file__).resolve().parent / "voices"
VOICE = "en-us-lessac-medium"
VOICE_URL = f"https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-{VOICE}.tar.gz"
FP = 5.0  # WORLD frame period, ms


def ensure_voice():
    model = VOICE_DIR / f"{VOICE}.onnx"
    if not model.exists():
        VOICE_DIR.mkdir(parents=True, exist_ok=True)
        data = urllib.request.urlopen(VOICE_URL, timeout=120).read()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            for m in tf.getmembers():
                if m.name.endswith((".onnx", ".onnx.json")):
                    m.name = Path(m.name).name
                    tf.extract(m, VOICE_DIR)
    return model


@functools.lru_cache(maxsize=1)
def _voice():
    from piper import PiperVoice
    return PiperVoice.load(str(ensure_voice()))


@functools.lru_cache(maxsize=4096)
def speak(word, rate=1.0):
    """One word, spoken. Returns (float64 samples, sample rate)."""
    from piper.config import SynthesisConfig
    v = _voice()
    cfg = SynthesisConfig(length_scale=rate, noise_scale=0.5, noise_w_scale=0.6)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        v.synthesize_wav(word, w, syn_config=cfg)
    buf.seek(0)
    with wave.open(buf, "rb") as w:
        fs = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768
    # trim silence
    env = np.convolve(np.abs(x), np.ones(160) / 160, mode="same")
    on = np.where(env > 0.02 * env.max())[0]
    if len(on):
        x = x[max(0, on[0] - 80): on[-1] + 160]
    return x, fs


def resample(x, fs_in, fs_out):
    n_out = int(round(len(x) * fs_out / fs_in))
    X = np.fft.rfft(x)
    Y = np.zeros(n_out // 2 + 1, dtype=complex)
    k = min(len(X), len(Y))
    Y[:k] = X[:k]
    return np.fft.irfft(Y, n_out) * (n_out / len(x))


@functools.lru_cache(maxsize=4096)
def _analyse(word):
    import pyworld as pw
    x, fs = speak(word)
    f0, t = pw.harvest(x, fs, f0_floor=70, f0_ceil=500, frame_period=FP)
    sp = pw.cheaptrick(x, f0, t, fs)
    ap = pw.d4c(x, f0, t, fs)
    return f0, sp, ap, fs


def _warp_formants(sp, k):
    """Shift the spectral envelope up by factor k (brighter, younger timbre)."""
    if abs(k - 1) < 1e-3:
        return sp
    n = sp.shape[1]
    src = np.arange(n) / k
    out = np.empty_like(sp)
    for i in range(sp.shape[0]):
        out[i] = np.interp(src, np.arange(n), sp[i])
    return out


def sing_word(word, notes, formant=1.1, detune=0.0, seed=0, hold=0.92):
    """Sing one word over notes [(midi, seconds), ...]. Returns samples at SR."""
    import pyworld as pw
    f0, sp, ap, fs = _analyse(word)
    n_in = len(f0)
    total = sum(d for _, d in notes) * hold
    n_out = max(4, int(total * 1000 / FP))
    voiced = np.where(f0 > 0)[0]
    if len(voiced) < 2:   # unvoiced word ("shh"): just stretch it
        a, b = 0, n_in
    else:
        a, b = voiced[0], voiced[-1] + 1
    onset = min(a, int(90 / FP))
    coda = min(n_in - b, int(120 / FP))
    a0, b0 = a - onset, b + coda
    mid_out = n_out - onset - coda
    if mid_out < (b - a) * 0.5:          # very short note: compress everything evenly
        idx = np.linspace(a0, b0 - 1, n_out)
    else:
        idx = np.concatenate([np.arange(a0, a), np.linspace(a, b - 1, max(1, mid_out)), np.arange(b, b0)])
    n_out = len(idx)
    ii = np.clip(np.round(idx).astype(int), 0, n_in - 1)
    sp2 = sp[ii].copy()
    ap2 = ap[ii].copy()
    voiced2 = f0[ii] > 0
    # in the stretched vowel make everything voiced so held notes stay sung
    vs, ve = onset, n_out - coda
    voiced2[vs:ve] = voiced2[vs:ve] | (f0[ii][vs:ve] > 0).any()
    # melody pitch track with glides between notes and gentle delayed vibrato
    times = np.arange(n_out) * FP / 1000
    bounds = np.cumsum([0] + [d * hold for _, d in notes])
    target = np.zeros(n_out)
    for j, (m, d) in enumerate(notes):
        sel = (times >= bounds[j]) & (times < bounds[j + 1] + 1e-9)
        target[sel] = m
    target[times >= bounds[-1]] = notes[-1][0]
    g = int(35 / FP)                      # 35 ms portamento
    if g > 1:
        target = np.convolve(np.pad(target, (g, g), mode="edge"), np.ones(g) / g, mode="same")[g:-g]
    rng = np.random.default_rng(seed)
    vib_depth = np.clip((times - 0.22) / 0.3, 0, 1) * 0.28
    vib = vib_depth * np.sin(2 * np.pi * 5.6 * times + rng.uniform(0, 6.28))
    drift = 0.05 * np.sin(2 * np.pi * 0.7 * times + rng.uniform(0, 6.28))
    hz = 440.0 * 2 ** ((target + vib + drift + detune / 100 - 69) / 12)
    new_f0 = np.where(voiced2, hz, 0.0)
    ap2[voiced2] = np.minimum(ap2[voiced2], 0.25)   # cleaner, more sung tone on voiced frames
    sp2 = _warp_formants(sp2, formant)
    y = pw.synthesize(np.ascontiguousarray(new_f0), np.ascontiguousarray(sp2), np.ascontiguousarray(ap2), fs,
                      frame_period=FP)
    y = resample(y, fs, SR)
    fade = min(len(y) // 4, int(0.012 * SR))
    if fade > 1:
        y[:fade] *= np.linspace(0, 1, fade)
        y[-fade:] *= np.linspace(1, 0, fade)
    return y


def tokens(line):
    """'The yel-low bus goes beep' -> [('the', 1), ('yellow', 2), ...]: word and how many notes it takes."""
    out = []
    for w in line.split():
        parts = w.split("-")
        word = re.sub(r"[^A-Za-z']", "", "".join(parts))
        if word:
            out.append((word, len(parts)))
    return out


def sing(events, seconds, voices=1, seed=0):
    """events: [(start_s, word, [(midi, dur_s), ...])]. Returns a mono vocal track at SR."""
    n = int(seconds * SR)
    out = np.zeros(n + SR * 2)
    copies = [(0.0, 1.10, 0.0, 1.0), (14.0, 1.14, 0.018, 0.7), (-11.0, 1.07, 0.031, 0.6)][:voices]
    for k, (st, word, notes) in enumerate(events):
        for c, (det, fm, delay, gain) in enumerate(copies):
            y = sing_word(word.lower(), tuple(notes), formant=fm, detune=det, seed=seed + 7 * k + c)
            i = int((st + delay) * SR)
            if i >= len(out):
                continue
            y = y[: len(out) - i]
            out[i:i + len(y)] += gain * y
    out = out[:n]
    peak = np.max(np.abs(out)) + 1e-9
    return out / peak


def _write(path, x):
    x = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


if __name__ == "__main__":
    beat = 60 / 112
    line = [("The", 67), ("yellow", (69, 71)), ("bus", 72), ("goes", 72), ("beep", 76), ("beep", 76), ("beep", 76)]
    ev, t = [], 0.3
    for w, m in line:
        ms = m if isinstance(m, tuple) else (m,)
        notes = [(mm, beat / 2 if w not in ("bus", "beep") else beat) for mm in ms]
        ev.append((t, w, notes))
        t += sum(d for _, d in notes)
    _write("/tmp/singer_test.wav", 0.8 * sing(ev, t + 1, voices=3))
    print("wrote /tmp/singer_test.wav")
