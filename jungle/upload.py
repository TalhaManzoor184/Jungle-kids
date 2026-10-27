from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

FOOTER = """

Sher, Bhaalu, Hathi aur Chill Bhai — roz ek nayi jungle comedy.

#Shorts #JungleKids #FunnyAnimals #Cartoon #PakistaniReels #Comedy"""


def youtube():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=config.req("YOUTUBE_REFRESH_TOKEN"),
        client_id=config.req("YOUTUBE_CLIENT_ID"),
        client_secret=config.req("YOUTUBE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def publish_at_iso(now: datetime | None = None) -> str:
    """Next PUBLISH_TIME (local, PUBLISH_UTC_OFFSET) PUBLISH_DELAY_DAYS from now, as UTC ISO; never in the past."""
    now = now or datetime.now(timezone.utc)
    off = timedelta(hours=config.PUBLISH_UTC_OFFSET)
    hh, mm = (int(x) for x in config.PUBLISH_TIME.split(":"))
    local = now + off
    target = datetime(local.year, local.month, local.day, hh, mm, tzinfo=timezone.utc) - off
    target += timedelta(days=config.PUBLISH_DELAY_DAYS)
    while target < now + timedelta(minutes=15):
        target += timedelta(days=1)
    return target.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def upload(video: Path, episode: dict, mode: str | None = None) -> dict:
    from googleapiclient.http import MediaFileUpload

    mode = mode or config.UPLOAD_MODE
    status = {
        "privacyStatus": "public" if mode == "public" else "private",
        "selfDeclaredMadeForKids": config.MADE_FOR_KIDS,
        "embeddable": True,
    }
    publish_at = None
    if mode == "schedule":
        publish_at = publish_at_iso()
        status["publishAt"] = publish_at
    body = {
        "snippet": {
            "title": episode["title"][:100],
            "description": (episode["description"] + FOOTER)[:4900],
            "tags": episode.get("tags", [])[:15],
            "categoryId": config.YOUTUBE_CATEGORY,
            "defaultLanguage": config.LANGUAGE,
            "defaultAudioLanguage": config.LANGUAGE,
        },
        "status": status,
    }
    req = youtube().videos().insert(
        part="snippet,status",
        body=body,
        notifySubscribers=True,
        media_body=MediaFileUpload(str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True),
    )
    res = None
    while res is None:
        _, res = req.next_chunk()
    return {"videoId": res["id"], "publishAt": publish_at, "privacy": status["privacyStatus"]}
