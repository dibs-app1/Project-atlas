"""Real-sound soundtrack: recorded music tracks and recorded animal calls (no synthesised song or noises).

A video opts in with "soundtrack" in its manifest entry:

    "soundtrack": {"music": ["km__Fluffing_a_Duck.mp3", ...], "credits": ["..."], "music_level": 0.55}

and each scene names its animal sound with "sound": "cow" (studio/assets/sounds/cow/*.wav, cut by
`python studio/soundtrack.py cut ...`). The animal is heard right after its name appears on screen at the start of
each camera angle, and once more mid-angle; the music dips a little under every call so the call is clear.
"""
import glob
import random
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
SR = 44100
SOUNDS = ROOT / "assets" / "sounds"
MUSIC = ROOT / "assets" / "music"


def load(path, sr=SR):
    """Any audio file as mono float in -1..1 (decoded by ffmpeg)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def _env(x, win):
    k = max(1, int(win * SR))
    return np.sqrt(np.convolve(x * x, np.ones(k) / k, mode="same") + 1e-12)


def cut_calls(path, max_calls=6, min_len=0.35, max_len=3.2, gap=0.12, level=0.18):
    """The loudest separate calls in a field recording, each trimmed to its own sound with soft edges. Sounds closer
    together than `gap` seconds stay one call (a hen's cackle, a run of peeps)."""
    x = load(path)
    x = x - np.convolve(x, np.ones(441) / 441, mode="same")        # remove rumble / DC
    e = _env(x, 0.05)
    floor = np.percentile(e, 30)
    peak = e.max()
    thr = floor + level * (peak - floor)
    on = e > thr
    calls = []
    i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and (on[j] or (j + int(gap * SR) < len(on) and on[j:j + int(gap * SR)].any())):
                j += 1
            a, b = max(0, i - int(0.06 * SR)), min(len(x), j + int(0.12 * SR))
            if min_len * SR <= b - a:
                b = min(b, a + int(max_len * SR))
                calls.append((float(e[a:b].max()), a, b))
            i = j
        i += 1
    calls.sort(reverse=True)
    out = []
    for _, a, b in calls[:max_calls]:
        y = x[a:b].copy()
        f = min(len(y) // 4, int(0.04 * SR))
        y[:f] *= np.linspace(0, 1, f)
        y[-f:] *= np.linspace(1, 0, f)
        y /= np.sqrt(np.mean(y ** 2)) + 1e-9
        out.append(y)
    return out


def calls_for(kind):
    files = sorted(glob.glob(str(SOUNDS / kind / "*.wav")))
    if not files:
        raise SystemExit(f"no recorded sounds for '{kind}' in {SOUNDS / kind}")
    out = []
    for f in files:
        y = load(f)
        out.append(y / (np.sqrt(np.mean(y ** 2)) + 1e-9))       # same loudness for every call (RMS 1)
    return out


def music_bed(names, N, fade=4.0):
    """The music tracks one after another (looping the list), joined with gentle crossfades, N samples long."""
    tracks = [load(MUSIC / n) for n in names]
    out = np.zeros(N)
    pos, k, F = 0, 0, int(fade * SR)
    while pos < N:
        y = tracks[k % len(tracks)].copy()
        y /= np.sqrt(np.mean(y ** 2)) + 1e-9
        y[:F] *= np.linspace(0, 1, F)
        y[-F:] *= np.linspace(1, 0, F)
        end = min(N, pos + len(y))
        out[pos:end] += y[: end - pos]
        pos += len(y) - F
        k += 1
    return out


def mix(video, scene_t0, scene_len, shots_per_scene, total, seed=0):
    """The whole soundtrack: music bed, plus each scene's animal calls timed to the on-screen names."""
    st = video["soundtrack"]
    N = int(total * SR)
    bed = music_bed(st["music"], N)
    calls = np.zeros(N)
    duck = np.zeros(N)
    r = random.Random(seed)
    for k, sc in enumerate(video["scenes"]):
        kind = sc.get("sound")
        if not kind:
            continue
        clips = calls_for(kind)
        order = list(range(len(clips)))
        r.shuffle(order)
        n_sh = shots_per_scene
        times = []
        for j in range(n_sh):
            a = scene_t0[k] + scene_len * j / n_sh
            b = scene_t0[k] + scene_len * (j + 1) / n_sh
            times += [a + 1.8, a + (b - a) * 0.6]
        for q, t in enumerate(times):
            y = clips[order[q % len(order)]] * st.get("call_level", 1.0)
            i0 = int(t * SR)
            i1 = min(N, i0 + len(y))
            if i0 >= N:
                continue
            calls[i0:i1] += y[: i1 - i0]
            duck[max(0, i0 - int(0.25 * SR)):min(N, i1 + int(0.3 * SR))] = 1.0
    k = int(0.3 * SR)
    duck = np.convolve(duck, np.ones(k) / k, mode="same")
    # the music sits under each call (dips to half) and the call is clearly louder than it (about +7 dB)
    music = bed * st.get("music_level", 0.5) * (1.0 - 0.5 * duck)
    m = music + st.get("call_mix", 0.55) * calls
    return m / (np.max(np.abs(m)) + 1e-9) * 0.9


# how each animal's calls are cut from field recordings (seconds)
CUT = {"cow": dict(max_len=3.6), "horse": dict(max_len=2.8), "rooster": dict(max_len=4.8, min_len=0.9),
       "chicken": dict(max_len=3.0, gap=0.45, min_len=1.0, level=0.05), "chick": dict(max_len=2.2, gap=0.3, min_len=0.6),
       "duck": dict(max_len=2.6, gap=0.3, min_len=0.5), "goose": dict(max_len=2.6, gap=0.3, min_len=0.5)}


def main():
    """python studio/soundtrack.py cut KIND FILE [FILE ...]   -> studio/assets/sounds/KIND/KIND_NN.wav"""
    import wave
    if len(sys.argv) < 4 or sys.argv[1] != "cut":
        print(main.__doc__)
        return
    kind, files = sys.argv[2], sys.argv[3:]
    kw = CUT.get(kind, {})
    d = SOUNDS / kind
    d.mkdir(parents=True, exist_ok=True)
    n = len(glob.glob(str(d / "*.wav")))
    for f in files:
        for y in cut_calls(f, max_calls=kw.get("max_calls", 3 if len(files) > 2 else 8), **{k: v for k, v in kw.items() if k != "max_calls"}):
            y = y / (np.max(np.abs(y)) + 1e-9) * 0.9
            with wave.open(str(d / f"{kind}_{n:02d}.wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SR)
                w.writeframes((y * 32767).astype("<i2").tobytes())
            print(d / f"{kind}_{n:02d}.wav", f"{len(y) / SR:.2f}s")
            n += 1


if __name__ == "__main__":
    main()
