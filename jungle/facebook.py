"""Facebook Page Reels (Reels Publishing API).

Needs FACEBOOK_PAGE_ID and a never-expiring FACEBOOK_PAGE_TOKEN (see scripts/facebook_auth.py).
The Meta app must be in Live mode, or Reels are visible only to people with a role on the app.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import config

GRAPH = "https://graph.facebook.com"
RUPLOAD = "https://rupload.facebook.com/video-upload"
TAGS = "#junglekids #funnyanimals #cartoon #comedy #reels #pakistanireels"


def configured() -> bool:
    if config.opt("FACEBOOK_ENABLED", "true") == "false":
        return False
    return bool(config.opt("FACEBOOK_PAGE_ID") and config.opt("FACEBOOK_PAGE_TOKEN"))


def _call(method: str, url: str, params: dict | None = None, data: bytes | None = None, headers: dict | None = None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=300) as res:
            return json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", "replace")
        raise RuntimeError(f"Facebook {url.split('?')[0]} failed: {err.code} {body[:300]}") from None


def _graph(method: str, path: str, params: dict):
    return _call(method, f"{GRAPH}/{config.opt('FACEBOOK_GRAPH_VERSION', 'v26.0')}/{path}", params, data=b"" if method == "POST" else None)


def upload_reel(video: Path, episode: dict, publish_at: str | None = None, draft: bool = False) -> dict:
    page = config.req("FACEBOOK_PAGE_ID")
    token = config.req("FACEBOOK_PAGE_TOKEN")
    version = config.opt("FACEBOOK_GRAPH_VERSION", "v26.0")

    start = _graph("POST", f"{page}/video_reels", {"upload_phase": "start", "access_token": token})
    vid = start["video_id"]

    data = video.read_bytes()
    up = _call("POST", f"{RUPLOAD}/{version}/{vid}", data=data, headers={
        "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data)),
        "Content-Type": "application/octet-stream",
    })
    if not up.get("success"):
        raise RuntimeError(f"Facebook upload failed: {up}")

    when = 0
    if publish_at:
        when = int(datetime.strptime(publish_at, "%Y-%m-%dT%H:%M:%S.000Z").replace(tzinfo=timezone.utc).timestamp())
    schedule = not draft and when > time.time() + 11 * 60  # Facebook needs 10 min - 29 days ahead
    params = {
        "access_token": token,
        "video_id": vid,
        "upload_phase": "finish",
        "video_state": "DRAFT" if draft else "SCHEDULED" if schedule else "PUBLISHED",
        "description": f"{episode['title']}\n\n{episode['description']}\n\n{TAGS}",
        "title": episode["title"],
        "is_ai_generated": "true",
    }
    if schedule:
        params["scheduled_publish_time"] = str(when)
    _graph("POST", f"{page}/video_reels", params)

    state = "draft" if draft else f"scheduled for {publish_at}" if schedule else "published"
    for _ in range(30):
        time.sleep(10)
        st = (_graph("GET", vid, {"fields": "status", "access_token": token}) or {}).get("status", {})
        phases = [st.get("processing_phase", {}), st.get("publishing_phase", {})]
        if st.get("video_status") == "error" or any(p.get("status") == "error" for p in phases):
            raise RuntimeError(f"Facebook processing failed: {st}")
        pub = st.get("publishing_phase", {}).get("publish_status")
        if st.get("video_status") == "ready" or pub in ("published", "scheduled", "draft"):
            break
    return {"videoId": vid, "state": state}
