import json
from datetime import datetime, timedelta, timezone

from . import config


def load() -> list[dict]:
    if not config.HISTORY.exists():
        return []
    return json.loads(config.HISTORY.read_text(encoding="utf-8") or "[]")


def save(entries: list[dict]) -> None:
    config.HISTORY.parent.mkdir(parents=True, exist_ok=True)
    config.HISTORY.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def local_today() -> str:
    """Today's date in the channel's time zone (PUBLISH_UTC_OFFSET)."""
    return (datetime.now(timezone.utc) + timedelta(hours=config.PUBLISH_UTC_OFFSET)).strftime("%Y-%m-%d")


def slot_taken(entries: list[dict], day: str) -> bool:
    return any(e.get("date") == day and e.get("videoId") for e in entries)


def add(entries: list[dict], entry: dict) -> None:
    entries[:] = [e for e in entries if not (e.get("date") == entry["date"] and not e.get("videoId"))]
    entries.append(entry)
    save(entries)
