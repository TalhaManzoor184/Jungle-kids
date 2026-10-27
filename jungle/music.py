"""Small synthesized soundtrack: ukulele-style strums, soft bass and sound effects. No licensing issues."""
import numpy as np

SR = 44100

PROGRESSIONS = [
    [[60, 64, 67, 72], [55, 59, 62, 67], [57, 60, 64, 69], [53, 57, 60, 65]],  # C G Am F
    [[62, 66, 69, 74], [57, 61, 64, 69], [59, 62, 66, 71], [55, 59, 62, 67]],  # D A Bm G
    [[60, 64, 67, 72], [57, 60, 64, 69], [53, 57, 60, 65], [55, 59, 62, 67]],  # C Am F G
    [[65, 69, 72, 77], [60, 64, 67, 72], [62, 65, 69, 74], [58, 62, 65, 70]],  # F C Dm Bb
]


def _note(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def _pluck(rng, f: float, dur: float, amp: float) -> np.ndarray:
    n = int(SR / f)
    buf = rng.uniform(-1, 1, n)
    length = int(SR * dur)
    out = np.empty(length)
    # Karplus-Strong, vectorised one period at a time
    pos = 0
    while pos < length:
        k = min(n, length - pos)
        out[pos:pos + k] = buf[:k]
        buf = 0.497 * (buf + np.roll(buf, -1))
        pos += k
    return out * amp


def _add(track: np.ndarray, sig: np.ndarray, t: float) -> None:
    i = int(t * SR)
    if i >= len(track):
        return
    j = min(len(track), i + len(sig))
    track[i:j] += sig[: j - i]


def music(seconds: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    track = np.zeros(int(SR * seconds) + SR)
    prog = PROGRESSIONS[seed % len(PROGRESSIONS)]
    bpm = [112, 120, 126][seed % 3]
    beat = 60 / bpm
    pattern = [0, 1, 1.5, 2.5, 3, 3.5]
    cache: dict = {}
    t, bar = 0.0, 0
    while t < seconds:
        chord = prog[bar % 4]
        for b in pattern:
            down = b % 1 == 0
            notes = chord if down else chord[::-1]
            for k, m in enumerate(notes):
                key = (m, down)
                if key not in cache:
                    cache[key] = _pluck(rng, _note(m), 0.9, 0.11 if down else 0.07)
                _add(track, cache[key], t + b * beat + k * 0.012)
        bt = np.arange(int(SR * beat * 1.8)) / SR
        bass = np.sin(2 * np.pi * _note(chord[0] - 24) * bt) * np.exp(-bt * 2.5)
        _add(track, 0.22 * bass, t)
        _add(track, 0.18 * bass, t + 2 * beat)
        t += 4 * beat
        bar += 1
    track = track[: int(SR * seconds)]
    fade = int(SR * 0.8)
    track[-fade:] *= np.linspace(1, 0, fade)
    return track / (np.abs(track).max() + 1e-9)


def pop() -> np.ndarray:
    t = np.arange(int(SR * 0.12)) / SR
    f = 900 * np.exp(-t * 18) + 250
    return 0.35 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 30)


def whoosh(seed: int = 0, dur: float = 0.4) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(SR * dur)
    x = rng.normal(0, 1, n)
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    y = np.zeros(n)
    a = 0.0
    for i in range(n):
        a += (0.02 + 0.25 * i / n) * (x[i] - a)
        y[i] = a
    return 0.45 * y * env


def chime() -> np.ndarray:
    t = np.arange(int(SR * 1.2)) / SR
    return sum(0.1 / k * np.sin(2 * np.pi * f * t) * np.exp(-t * 3) for k, f in enumerate([1760, 2217, 2637, 3520], 1))


def add(track: np.ndarray, sig: np.ndarray, t: float) -> None:
    _add(track, sig, t)
