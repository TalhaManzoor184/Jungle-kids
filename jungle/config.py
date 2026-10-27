"""All settings come from environment variables (GitHub secrets/variables, or a local .env file)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def opt(name: str, default: str = "") -> str:
    v = os.environ.get(name, "").strip()
    return v or default


def req(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise SystemExit(f"Missing {name}. Add it to .env (local) or the GitHub repository secrets.")
    return v


# --- Models -------------------------------------------------------------------------------
GEMINI_TEXT_MODEL = opt("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
GEMINI_TEXT_FALLBACK = opt("GEMINI_TEXT_FALLBACK", "gemini-3.5-flash-lite")
# First frames for each shot (Nano Banana). Used only when CLIP_SOURCE=veo.
GEMINI_IMAGE_MODEL = opt("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")
GEMINI_IMAGE_FALLBACK = opt("GEMINI_IMAGE_FALLBACK", "gemini-2.5-flash-image")
VEO_MODEL = opt("VEO_MODEL", "veo-3.1-lite-generate-preview")
# Optional second Veo model when the first one is out of quota. Costs more, so empty by default.
VEO_FALLBACK = opt("VEO_FALLBACK", "")
VEO_RESOLUTION = opt("VEO_RESOLUTION", "720p")

# --- Clips --------------------------------------------------------------------------------
# veo   = fully automatic: Gemini makes first frames, Veo animates them (paid Gemini API).
# inbox = free: the daily run writes PROMPTS.md to inbox/<date>/, you make the 4 clips in
#         Google Flow and upload them there; pushing them assembles and uploads the reel.
# still = no video model, slow zoom on still frames (tests only).
CLIP_SOURCE = opt("CLIP_SOURCE", "veo")
SHOT_SECONDS = int(opt("SHOT_SECONDS", "6"))  # Veo 3.1 accepts 4, 6 or 8
CTA_SECONDS = float(opt("CTA_SECONDS", "3.5"))
MUSIC_VOLUME = float(opt("MUSIC_VOLUME", "0.22"))

# --- Upload -------------------------------------------------------------------------------
# schedule = private now, goes public at PUBLISH_TIME · private = you publish by hand · public = now
UPLOAD_MODE = opt("UPLOAD_MODE", "schedule")
PUBLISH_TIME = opt("PUBLISH_TIME", "18:00")
PUBLISH_UTC_OFFSET = float(opt("PUBLISH_UTC_OFFSET", "5"))
PUBLISH_DELAY_DAYS = int(opt("PUBLISH_DELAY_DAYS", "0"))
# Must honestly match the content. The bible describes a general-audience family comedy.
MADE_FOR_KIDS = opt("MADE_FOR_KIDS", "false") == "true"
YOUTUBE_CATEGORY = opt("YOUTUBE_CATEGORY", "23")  # 23 = Comedy
LANGUAGE = opt("VIDEO_LANGUAGE", "ur")

# --- Paths --------------------------------------------------------------------------------
BIBLE = ROOT / "cast" / "bible.md"
CAST_DIR = ROOT / "cast"
HISTORY = ROOT / "data" / "history.json"
SAMPLE = ROOT / "data" / "sample-episode.json"
SAMPLE_FRAMES = ROOT / "data" / "sample"
INBOX = ROOT / "inbox"
OUT = ROOT / "out"
FONT = ROOT / "assets" / "fonts" / "Poppins-Bold.ttf"

CAST = ["sher", "bhaalu", "hathi", "chill_bhai"]
CAST_NAMES = {"sher": "SHER", "bhaalu": "BHAALU", "hathi": "HATHI", "chill_bhai": "CHILL BHAI"}
CAST_COLORS = {
    "sher": (255, 196, 0),
    "bhaalu": (120, 200, 255),
    "hathi": (255, 140, 190),
    "chill_bhai": (60, 230, 200),
}
# One fixed description per character, pasted into every image and video prompt for consistency.
CAST_LOOK = {
    "sher": "Sher, a big lazy cartoon lion with a huge fluffy orange-brown mane, golden fur, droopy tired eyes and thick dark eyebrows",
    "bhaalu": "Bhaalu, a round chubby cartoon brown bear with a cream muzzle, small round ears and a sleepy happy face",
    "hathi": "Hathi, a cheerful cartoon baby elephant with light grey skin, big floppy pink-lined ears and rosy cheeks",
    "chill_bhai": (
        "Chill Bhai, a cool cartoon teal-green lizard with yellow spots, orange sunglasses, a turquoise Hawaiian "
        "shirt with pink and orange hibiscus flowers, a flower lei, yellow palm-print shorts, orange flip-flops "
        "and a long curled teal tail with yellow bands"
    ),
}
STYLE = (
    "Polished 3D animated family comedy, Pixar-like quality, original characters, bright tropical jungle, "
    "soft cinematic sunlight, saturated colors, exaggerated funny cartoon expressions"
)
