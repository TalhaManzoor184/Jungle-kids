"""Daily Jungle Kids reel.

python -m jungle.run                      # full: script -> clips -> reel -> YouTube
python -m jungle.run --if-slot-free       # same, but skip if today's reel is already uploaded
python -m jungle.run --sample --clips still --no-upload   # offline test, needs no keys
python -m jungle.run --plan               # inbox mode: write today's script + Flow prompts to inbox/<date>/
python -m jungle.run --from-inbox         # inbox mode: assemble + upload any day whose 4 clips have arrived
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from . import assemble, clips, config, history


def summary(text: str) -> None:
    print(text)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def get_episode(sample: bool, entries: list[dict]) -> dict:
    if sample:
        return json.loads(config.SAMPLE.read_text(encoding="utf-8"))
    from .script import write_episode

    return write_episode(entries)


def make_clips(source: str, episode: dict, work: Path, sample: bool) -> list[Path]:
    if source == "veo":
        return clips.veo_clips(episode, work)
    if source == "still":
        if sample:
            frames = [config.SAMPLE_FRAMES / f"shot{i}.jpg" for i in range(1, 5)]
        else:
            from google import genai

            client = genai.Client(api_key=config.req("GEMINI_API_KEY"))
            frames = [clips.make_frame(client, s, work / f"frame{i}.jpg") for i, s in enumerate(episode["shots"], 1)]
        return clips.still_clips(frames, work)
    raise SystemExit(f"Unknown clip source {source!r} (use veo, still or inbox).")


def finish(day: str, episode: dict, reel: Path, entries: list[dict], no_upload: bool, mode: str | None) -> None:
    (reel.parent / "episode.json").write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
    summary(f"## {episode['title']}\n\nTheme: {episode['theme']}\n\nReel: `{reel}`\n")
    if no_upload:
        summary("Upload skipped (--no-upload).")
        return
    from .upload import upload

    res = upload(reel, episode, mode)
    url = f"https://youtube.com/shorts/{res['videoId']}"
    when = f"goes public at {res['publishAt']} (UTC)" if res.get("publishAt") else res["privacy"]
    summary(f"Uploaded: {url} — {when}\n\nSuggested pinned comment: **{episode.get('pinned_comment', '')}**")
    if mode != "private":  # private test uploads do not take the day's slot
        history.add(entries, {"date": day, "theme": episode["theme"], "title": episode["title"], "videoId": res["videoId"]})


def run_full(args) -> None:
    entries = history.load()
    day = history.local_today()
    if args.if_slot_free and history.slot_taken(entries, day):
        summary(f"Reel for {day} already uploaded; nothing to do.")
        return
    work = config.OUT / day
    work.mkdir(parents=True, exist_ok=True)
    episode = get_episode(args.sample, entries)
    print(f"Episode: {episode['title']} ({episode['theme']})")
    found = make_clips(args.clips, episode, work, args.sample)
    reel = assemble.build(episode, found, work / "reel.mp4", seed=sum(map(ord, day)))
    finish(day, episode, reel, entries, args.no_upload, args.upload_mode)


def run_plan(args) -> None:
    entries = history.load()
    day = history.local_today()
    day_dir = config.INBOX / day
    if (day_dir / "episode.json").exists():
        summary(f"Plan for {day} already exists: {day_dir / 'PROMPTS.md'}")
        return
    if history.slot_taken(entries, day):
        summary(f"Reel for {day} already uploaded; no plan needed.")
        return
    day_dir.mkdir(parents=True, exist_ok=True)
    episode = get_episode(args.sample, entries)
    (day_dir / "episode.json").write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
    prompts = clips.write_prompts(episode, day_dir)
    summary(f"## Today's plan: {episode['title']}\n\nMake the 4 clips from `{prompts.relative_to(config.ROOT)}` "
            f"and upload them to `inbox/{day}/` as shot1.mp4 ... shot4.mp4.")


def run_inbox(args) -> None:
    entries = history.load()
    ready = []
    for day_dir in sorted(p for p in config.INBOX.glob("*") if p.is_dir()):
        found = clips.inbox_clips(day_dir)
        if found and (day_dir / "episode.json").exists():
            ready.append((day_dir, found))
    if not ready:
        summary("No inbox day has all 4 clips yet.")
        return
    for day_dir, found in ready:
        day = day_dir.name
        episode = json.loads((day_dir / "episode.json").read_text(encoding="utf-8"))
        work = config.OUT / day
        work.mkdir(parents=True, exist_ok=True)
        reel = assemble.build(episode, found, work / "reel.mp4", seed=sum(map(ord, day)))
        finish(day, episode, reel, entries, args.no_upload, args.upload_mode)
        if not args.no_upload:
            shutil.rmtree(day_dir)  # keep the repo small; history.json keeps the record


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Make today's Jungle Kids reel.")
    ap.add_argument("--sample", action="store_true", help="use data/sample-episode.json instead of Gemini")
    ap.add_argument("--clips", default=config.CLIP_SOURCE, help="veo, still or inbox")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--if-slot-free", action="store_true")
    ap.add_argument("--upload-mode", choices=["schedule", "private", "public"])
    ap.add_argument("--plan", action="store_true", help="inbox mode: write today's script and Flow prompts")
    ap.add_argument("--from-inbox", action="store_true", help="inbox mode: assemble and upload ready days")
    args = ap.parse_args(argv)

    if args.from_inbox:
        run_inbox(args)
    elif args.plan or args.clips == "inbox":
        run_plan(args)
    else:
        run_full(args)


if __name__ == "__main__":
    sys.exit(main())
