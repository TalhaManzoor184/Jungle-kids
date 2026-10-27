"""Writes today's episode with Gemini as JSON."""
import json

from . import config
from .retry import with_fallback

SHOT = {
    "type": "object",
    "required": ["character", "first_frame", "motion", "sound", "caption"],
    "properties": {
        "character": {"type": "string", "enum": config.CAST},
        "first_frame": {
            "type": "string",
            "description": "English. The opening still of this shot: where the character is, pose, facial expression, "
            "props and setting in the jungle. Vertical framing, character large in frame. 25-45 words.",
        },
        "motion": {
            "type": "string",
            "description": "English. ONE clear funny action that happens in the next 5 seconds, plus the camera move. "
            "Exaggerated cartoon timing. 20-40 words.",
        },
        "sound": {"type": "string", "description": "English. Sound effects only, no speech or words. 5-15 words."},
        "caption": {
            "type": "string",
            "description": "Roman Urdu caption shown on screen for this character, 3-8 words, a funny line in his voice.",
        },
    },
}

EPISODE_SCHEMA = {
    "type": "object",
    "required": ["theme", "title", "hook", "cta", "description", "tags", "pinned_comment", "shots"],
    "properties": {
        "theme": {"type": "string", "description": "The everyday situation, 2-5 words, e.g. 'bijli chali gayi'."},
        "title": {
            "type": "string",
            "description": "YouTube title in Roman Urdu (English words allowed), max 70 characters, ends with 1-2 emojis.",
        },
        "hook": {"type": "string", "description": "Roman Urdu hook shown in the first 2 seconds, 4-8 words, no emoji."},
        "cta": {
            "type": "string",
            "description": "Roman Urdu question for the final screen asking which of the 4 they are, max 7 words, "
            "e.g. 'Is garmi mein TUM kaun ho?'",
        },
        "description": {"type": "string", "description": "2-3 short funny Roman Urdu sentences. No links."},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "8-12 search tags, mixed Roman Urdu/English."},
        "pinned_comment": {
            "type": "string",
            "description": "A first comment the creator pins, Roman Urdu, picks one number, e.g. 'Main to 2 hoon, fridge nahi chhorna'.",
        },
        "shots": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "description": "Exactly 4 shots in cast order: sher, bhaalu, hathi, chill_bhai. Chill Bhai is the unbothered twist.",
            "items": SHOT,
        },
    },
}


def _prompt(history: list[dict]) -> str:
    bible = config.BIBLE.read_text(encoding="utf-8")
    recent = "\n".join(f"- {h['date']}: {h.get('theme', '')} | {h.get('title', '')}" for h in history[-40:]) or "- none yet"
    return f"""You write a daily YouTube Shorts / Instagram Reels comedy episode for a Pakistani audience.

<series_bible>
{bible}
</series_bible>

<recent_episodes>
{recent}
</recent_episodes>

Write today's episode.
- Pick an everyday situation Pakistanis instantly relate to that is NOT in the recent episodes (vary the family of
  situations too: weather, electricity, food, school, family, festivals, travel, phones, cricket, weddings, etc.).
  Keep it light; no politics, religion jokes, brands or real people.
- Shot 1-3: Sher, Bhaalu and Hathi each suffer or react to the situation in their own personality, one clear
  visual gag each. Shot 4: Chill Bhai appears totally unbothered, the punchline.
- The jokes must work with NO spoken dialogue: action, faces, sound effects and the captions.
- Captions are short, punchy Roman Urdu in the character's voice.
- first_frame and motion describe ONLY that shot's character (no other cast members in frame) so the video model
  keeps the character design accurate.
"""


def write_episode(history: list[dict]) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.req("GEMINI_API_KEY"))
    prompt = _prompt(history)

    def call(model: str):
        return client.models.generate_content(
            model=model,
            contents=prompt + "\nReturn the episode as JSON matching the schema.",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=EPISODE_SCHEMA,
                temperature=1.0,
            ),
        )

    last_err = None
    for attempt in range(1, 4):
        try:
            res = with_fallback("script", [config.GEMINI_TEXT_MODEL, config.GEMINI_TEXT_FALLBACK], call)
            ep = json.loads(res.text or "")
            validate(ep)
            return ep
        except (ValueError, KeyError) as err:
            last_err = err
            print(f"Script attempt {attempt} invalid: {err}")
    raise RuntimeError(f"No valid episode after 3 attempts: {last_err}")


def validate(ep: dict) -> None:
    for key in EPISODE_SCHEMA["required"]:
        if not ep.get(key):
            raise ValueError(f"missing {key}")
    shots = ep["shots"]
    if [s.get("character") for s in shots] != config.CAST:
        # Put them in cast order if the model shuffled them; fail if someone is missing.
        by = {s.get("character"): s for s in shots}
        if set(by) != set(config.CAST):
            raise ValueError(f"shots must be exactly {config.CAST}")
        ep["shots"] = [by[c] for c in config.CAST]
    for s in ep["shots"]:
        for k in SHOT["required"]:
            if not str(s.get(k, "")).strip():
                raise ValueError(f"shot {s.get('character')} missing {k}")
    ep["title"] = ep["title"][:100]
    ep["tags"] = [t for t in ep["tags"] if isinstance(t, str)][:15]
