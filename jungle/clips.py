"""Turns the 4 shots of an episode into 4 video clips (Veo, inbox from Google Flow, or stills)."""
import subprocess
import time
from io import BytesIO
from pathlib import Path

from PIL import Image

from . import config
from .retry import with_fallback, with_retry

NEGATIVE = "text, subtitles, captions, letters, words, watermark, logo, extra characters, deformed hands, blurry"


def image_prompt(shot: dict) -> str:
    look = config.CAST_LOOK[shot["character"]]
    return (
        f"Vertical 9:16 frame from a {config.STYLE}. The only character in frame is {look}. "
        f"Match the attached reference image exactly for this character's design, colors, outfit and proportions. "
        f"Scene: {shot['first_frame']} The character is large in frame and clearly readable on a phone. "
        "No text, letters, logos or watermarks anywhere."
    )


def video_prompt(shot: dict) -> str:
    look = config.CAST_LOOK[shot["character"]]
    return (
        f"{config.STYLE}. {look}, keeping exactly the same design as in the first frame. "
        f"{shot['motion']} Sound effects: {shot['sound']}. No speech, no music lyrics, no on-screen text."
    )


def _cover(img: Image.Image, w: int = 1080, h: int = 1920) -> Image.Image:
    img = img.convert("RGB")
    s = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


# --- first frames (Nano Banana) -------------------------------------------------------------
def make_frame(client, shot: dict, out: Path) -> Path:
    from google.genai import types

    ref = Image.open(config.CAST_DIR / f"{shot['character']}.png")

    def call(model: str):
        try:
            cfg = types.GenerateContentConfig(
                response_modalities=["IMAGE"], image_config=types.ImageConfig(aspect_ratio="9:16")
            )
            return client.models.generate_content(model=model, contents=[image_prompt(shot), ref], config=cfg)
        except Exception as err:  # older image models reject image_config
            if "aspect" not in str(err).lower() and "image_config" not in str(err).lower():
                raise
            cfg = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])
            return client.models.generate_content(model=model, contents=[image_prompt(shot), ref], config=cfg)

    res = with_fallback(f"frame {shot['character']}", [config.GEMINI_IMAGE_MODEL, config.GEMINI_IMAGE_FALLBACK], call)
    for cand in res.candidates or []:
        for part in (cand.content.parts if cand.content else []) or []:
            if part.inline_data and part.inline_data.data:
                _cover(Image.open(BytesIO(part.inline_data.data))).save(out, quality=94)
                return out
    raise RuntimeError(f"Image model returned no image for {shot['character']}.")


# --- Veo -------------------------------------------------------------------------------------
def _start_veo(client, model: str, shot: dict, frame: Path, minimal: bool = False):
    from google.genai import types

    img = types.Image(image_bytes=frame.read_bytes(), mime_type="image/jpeg")
    if minimal:
        cfg = types.GenerateVideosConfig(aspect_ratio="9:16", number_of_videos=1)
    else:
        cfg = types.GenerateVideosConfig(
            aspect_ratio="9:16",
            number_of_videos=1,
            duration_seconds=config.SHOT_SECONDS,
            resolution=config.VEO_RESOLUTION,
            negative_prompt=NEGATIVE,
        )
    return client.models.generate_videos(model=model, prompt=video_prompt(shot), image=img, config=cfg)


def _start(client, shot, frame):
    def go(model):
        try:
            return _start_veo(client, model, shot, frame)
        except Exception as err:  # noqa: BLE001
            if "INVALID_ARGUMENT" in str(err) or "400" in str(err):
                print(f"  Veo rejected the full config ({str(err)[:120]}); retrying with defaults")
                return _start_veo(client, model, shot, frame, minimal=True)
            raise

    return with_fallback(f"veo {shot['character']}", [config.VEO_MODEL, config.VEO_FALLBACK], go)


def veo_clips(episode: dict, work: Path) -> list[Path]:
    from google import genai

    client = genai.Client(api_key=config.req("GEMINI_API_KEY"))
    frames = []
    for i, shot in enumerate(episode["shots"], 1):
        print(f"Frame {i}/4: {shot['character']}")
        frames.append(make_frame(client, shot, work / f"frame{i}.jpg"))

    # Start all four Veo jobs at once, then wait for them together.
    ops = {}
    for i, (shot, frame) in enumerate(zip(episode["shots"], frames), 1):
        print(f"Veo {i}/4: {shot['character']} started")
        ops[i] = _start(client, shot, frame)

    clips: dict[int, Path] = {}
    deadline = time.time() + 20 * 60
    while len(clips) < len(ops):
        if time.time() > deadline:
            raise TimeoutError("Veo took longer than 20 minutes.")
        time.sleep(15)
        for i, op in list(ops.items()):
            if i in clips:
                continue
            op = with_retry("veo poll", lambda op=op: client.operations.get(op))
            ops[i] = op
            if not op.done:
                continue
            out = work / f"clip{i}.mp4"
            vids = getattr(op.response, "generated_videos", None) if op.response else None
            if op.error or not vids:
                reason = op.error or getattr(op.response, "rai_media_filtered_reasons", None)
                print(f"  ! Veo shot {i} failed ({reason}); using a still zoom of the first frame instead")
                still_clip(frames[i - 1], out)
            else:
                client.files.download(file=vids[0].video)
                vids[0].video.save(str(out))
                print(f"Veo {i}/4 done")
            clips[i] = out
    return [clips[i] for i in sorted(clips)]


# --- stills & inbox ------------------------------------------------------------------------
def still_clip(image: Path, out: Path, seconds: float | None = None) -> Path:
    seconds = seconds or config.SHOT_SECONDS
    _cover(Image.open(image)).save(out.with_suffix(".src.jpg"), quality=94)
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(out.with_suffix(".src.jpg")),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-vf", "zoompan=z='min(zoom+0.0011,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30",
            "-t", str(seconds), "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(out),
        ],
        check=True,
    )
    return out


def still_clips(frames: list[Path], work: Path) -> list[Path]:
    return [still_clip(f, work / f"clip{i}.mp4") for i, f in enumerate(frames, 1)]


def inbox_clips(day_dir: Path) -> list[Path] | None:
    """shot1..shot4 (.mp4/.mov) uploaded from Google Flow, or None if not all there yet."""
    found = []
    for i in range(1, 5):
        hits = sorted(p for p in day_dir.glob(f"shot{i}.*") if p.suffix.lower() in (".mp4", ".mov", ".m4v"))
        if not hits:
            return None
        found.append(hits[0])
    return found


def write_prompts(episode: dict, day_dir: Path) -> Path:
    lines = [
        f"# {episode['title']}",
        "",
        f"Theme: **{episode['theme']}**",
        "",
        "Make these 4 clips in Google Flow (Veo 3.1 Lite, 9:16, 1 output each). For each shot, add the cast",
        "image named below as an ingredient / first frame so the character looks right, paste the prompt,",
        "download the clip and upload it to this folder as `shot1.mp4` ... `shot4.mp4`.",
        "When all 4 are here, the reel is assembled and uploaded automatically.",
        "",
    ]
    for i, shot in enumerate(episode["shots"], 1):
        lines += [
            f"## shot{i}.mp4 — {config.CAST_NAMES[shot['character']]}",
            f"Reference image: `cast/{shot['character']}.png`",
            "",
            "First frame (image prompt):",
            "```",
            image_prompt(shot),
            "```",
            "Video prompt:",
            "```",
            video_prompt(shot),
            "```",
            f"Caption: _{shot['caption']}_",
            "",
        ]
    path = day_dir / "PROMPTS.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

