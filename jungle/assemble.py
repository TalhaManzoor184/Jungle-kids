"""Joins the 4 clips into the final reel: hook, character captions, flash cuts, CTA grid and a mixed soundtrack."""
import json
import math
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import config, music

W, H, FPS = 1080, 1920, 30
SR = music.SR


# --- captions --------------------------------------------------------------------------------
def _back(x: float) -> float:  # easeOutBack
    x = min(max(x, 0.0), 1.0)
    c1 = 1.70158
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def caption(text: str, label: str | None = None, color=(255, 196, 0), size: int = 80) -> Image.Image:
    font = ImageFont.truetype(str(config.FONT), size)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if probe.textlength(trial, font=font) > 900 and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    lines.append(cur)
    while size > 48 and len(lines) > 3:  # very long text: shrink instead of overflowing
        return caption(text, label, color, size - 8)
    lh = int(size * 1.22)
    lab_h = 0
    if label:
        lfont = ImageFont.truetype(str(config.FONT), 48)
        lw = int(probe.textlength(label, font=lfont)) + 56
        lab_h = 96
    img = Image.new("RGBA", (W, lab_h + lh * len(lines) + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if label:
        lx = (W - lw) // 2
        d.rounded_rectangle((lx, 0, lx + lw, 76), 22, fill=color + (255,), outline=(0, 0, 0, 255), width=5)
        d.text((W // 2, 38), label, font=lfont, fill=(20, 20, 20), anchor="mm")
    tw = max(d.textlength(line, font=font) for line in lines)
    d.rounded_rectangle(
        ((W - tw) // 2 - 34, lab_h - 14, (W + tw) // 2 + 34, lab_h + lh * len(lines) + 14), 34, fill=(0, 0, 0, 150)
    )
    for i, line in enumerate(lines):
        d.text((W // 2, lab_h + i * lh + lh // 2), line, font=font, fill=(255, 255, 255), anchor="mm",
               stroke_width=10, stroke_fill=(0, 0, 0))
    return img


def pop_in(frame: Image.Image, cap: Image.Image, t: float, y: int, dur: float = 0.32) -> None:
    if t < 0:
        return
    s = max(_back(t / dur) if t < dur else 1.0, 0.05)
    c = cap if s == 1.0 else cap.resize((max(1, int(cap.width * s)), max(1, int(cap.height * s))), Image.BICUBIC)
    frame.alpha_composite(c, ((W - c.width) // 2, int(y + (cap.height - c.height) / 2)))


# --- media helpers ---------------------------------------------------------------------------
def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def frames(path: Path, seconds: float):
    p = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(path), "-t", f"{seconds:.3f}", "-vf",
         f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE,
    )
    size = W * H * 3
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        yield Image.frombuffer("RGB", (W, H), buf).convert("RGBA")
    p.wait()


def audio(path: Path, seconds: float) -> np.ndarray:
    """Clip audio as mono float array of exactly `seconds` (silence if the clip has none)."""
    n = int(SR * seconds)
    res = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-t", f"{seconds:.3f}", "-vn", "-ac", "1", "-ar", str(SR),
         "-f", "s16le", "-"],
        capture_output=True,
    )
    a = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float64) / 32768 if res.returncode == 0 else np.zeros(0)
    out = np.zeros(n)
    out[: min(n, len(a))] = a[:n]
    return out


def grab(path: Path, at: float, out: Path) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.2f}", "-i", str(path), "-frames:v", "1",
         "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", str(out)],
        check=True,
    )
    return out


def _rounded(img: Image.Image, r: int) -> Image.Image:
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, *img.size), r, fill=255)
    img = img.convert("RGBA")
    img.putalpha(m)
    return img


# --- the reel --------------------------------------------------------------------------------
def build(episode: dict, clips: list[Path], out: Path, seed: int = 0) -> Path:
    work = out.parent
    lengths = [min(duration(c), float(config.SHOT_SECONDS)) for c in clips]
    starts = np.cumsum([0.0] + lengths[:-1]).tolist()
    total = sum(lengths) + config.CTA_SECONDS

    hook = caption(episode["hook"], size=86)
    caps = [
        caption(s["caption"], config.CAST_NAMES[s["character"]], config.CAST_COLORS[s["character"]])
        for s in episode["shots"]
    ]
    hook_end = min(2.2, lengths[0] - 1.5)
    cap_start = [hook_end if i == 0 else 0.25 for i in range(4)]

    # CTA panels from a moment inside each clip
    stills = [grab(c, min(1.2, L - 0.2), work / f"still{i}.jpg") for i, (c, L) in enumerate(zip(clips, lengths), 1)]
    pw, ph = 470, 600
    panels = []
    for s in stills:
        im = Image.open(s).convert("RGB")
        scale = max(pw / im.width, ph / im.height)
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
        x, y = (im.width - pw) // 2, int((im.height - ph) * 0.35)
        panels.append(_rounded(im.crop((x, y, x + pw, y + ph)), 36))
    cta_top = caption(episode["cta"], size=82)
    cta_bottom = caption("Comment mein number likho!", size=60)
    grad = np.zeros((H, W, 4), np.uint8)
    g = np.linspace(0, 1, H)[:, None]
    grad[..., 0], grad[..., 1], grad[..., 2], grad[..., 3] = 20 + 10 * g, 90 - 50 * g, 50 - 20 * g, 255
    cta_bg = Image.fromarray(grad, "RGBA")
    num_font = ImageFont.truetype(str(config.FONT), 58)
    lab_font = ImageFont.truetype(str(config.FONT), 46)

    def cta_frame(t: float) -> Image.Image:
        fr = cta_bg.copy()
        pop_in(fr, cta_top, t - 0.05, 110)
        d = ImageDraw.Draw(fr)
        for i, (p, (px, py)) in enumerate(zip(panels, [(55, 380), (555, 380), (55, 1040), (555, 1040)])):
            k = (t - 0.25 - i * 0.18) / 0.35
            if k < 0:
                continue
            s = max(_back(k) if k < 1 else 1.0, 0.05)
            im = p.resize((int(pw * s), int(ph * s)), Image.BICUBIC)
            fr.alpha_composite(im, (px + (pw - im.width) // 2, py + (ph - im.height) // 2))
            if k >= 1:
                d.rounded_rectangle((px, py, px + pw, py + ph), 36, outline=(255, 255, 255), width=6)
                d.ellipse((px + 18, py + 18, px + 108, py + 108), fill=(255, 196, 0), outline=(0, 0, 0), width=5)
                d.text((px + 63, py + 63), str(i + 1), font=num_font, fill=(0, 0, 0), anchor="mm")
                name = config.CAST_NAMES[episode["shots"][i]["character"]].title()
                d.text((px + pw // 2, py + ph - 45), name, font=lab_font, fill=(255, 255, 255), anchor="mm",
                       stroke_width=7, stroke_fill=(0, 0, 0))
        pop_in(fr, cta_bottom, t - 1.3, 1680)
        if t > 1.6:
            by = 1860 - int(abs(math.sin((t - 1.6) * 5)) * 25)
            d.polygon([(W // 2 - 40, by - 30), (W // 2 + 40, by - 30), (W // 2, by + 25)], fill=(255, 196, 0),
                      outline=(0, 0, 0))
        return fr

    # --- video ---
    silent = work / "video.mp4"
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(silent)],
        stdin=subprocess.PIPE,
    )
    for i, (clip, length) in enumerate(zip(clips, lengths)):
        count = 0
        last = None
        for n, fr in enumerate(frames(clip, length)):
            t = n / FPS
            if i == 0 and t < hook_end:
                pop_in(fr, hook, t - 0.15, 1350)
            if t >= cap_start[i]:
                pop_in(fr, caps[i], t - cap_start[i], 160)
            if i > 0 and t < 0.18:  # flash cut
                a = int(255 * (1 - t / 0.18))
                fr.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, a)))
            enc.stdin.write(fr.convert("RGB").tobytes())
            last, count = fr, n + 1
        # pad if the clip was a little shorter than reported
        for _ in range(max(0, int(round(length * FPS)) - count)):
            enc.stdin.write(last.convert("RGB").tobytes())
    for n in range(int(config.CTA_SECONDS * FPS)):
        fr = cta_frame(n / FPS)
        if n < 5:
            fr.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - n / 5)))))
        enc.stdin.write(fr.convert("RGB").tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        raise RuntimeError("ffmpeg failed while encoding the reel.")

    # --- audio ---
    track = np.zeros(int(SR * total) + SR)
    for clip, start, length in zip(clips, starts, lengths):
        music.add(track, audio(clip, length) * 0.95, start)
    track += np.pad(music.music(total, seed) * config.MUSIC_VOLUME, (0, len(track) - int(SR * total)))
    cta_start = sum(lengths)
    for i, start in enumerate(starts):
        music.add(track, music.pop(), start + cap_start[i])
        if i:
            music.add(track, music.whoosh(seed + i), start - 0.12)
    music.add(track, music.pop(), 0.15)
    music.add(track, music.whoosh(seed + 9), cta_start - 0.12)
    for i in range(4):
        music.add(track, music.pop() * 0.8, cta_start + 0.25 + i * 0.18)
    music.add(track, music.chime(), cta_start + 1.3)
    track = track[: int(SR * total)]
    track = track / max(1.0, np.abs(track).max() / 0.9)
    wav = work / "mix.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((track * 32767).astype(np.int16).tobytes())

    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(wav), "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
         "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2", "-shortest", "-movflags", "+faststart", str(out)],
        check=True,
    )
    return out
