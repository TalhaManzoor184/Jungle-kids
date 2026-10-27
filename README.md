# Jungle Kids — daily AI jungle comedy reel

Every day GitHub Actions makes one 25–30 second vertical reel and uploads it to YouTube Shorts:

1. **Script** — Gemini writes today's episode (`jungle/script.py`): an everyday Pakistani situation
   (garmi, bijli chali gayi, exam ki raat, shaadi ka khana…), one gag each for **Sher**, **Bhaalu** and
   **Hathi**, and **Chill Bhai** as the unbothered twist. Captions in Roman Urdu. Past themes in
   `data/history.json` are avoided.
2. **First frames** — Gemini image (Nano Banana) draws each character's opening frame from the
   reference images in `cast/`, so the cast looks the same every day.
3. **Clips** — Veo 3.1 Lite animates each frame into a 6-second 9:16 clip with sound effects.
4. **Reel** — `jungle/assemble.py` adds the hook, character name tags and captions, flash cuts,
   a synthesized ukulele track, and the final **"Tum kaun ho? 1, 2, 3 ya 4?"** grid that drives comments.
5. **Upload** — YouTube Shorts (private, goes public at 6:00 PM Pakistan time, `PUBLISH_TIME`) and a
   Facebook Page Reel scheduled for the same time.

The series rules and cast descriptions live in `cast/bible.md`; the exact look sent with every
prompt is `CAST_LOOK` in `jungle/config.py`.

## Two ways to run it

| `CLIP_SOURCE` | How clips are made | Cost | You do |
|---|---|---|---|
| `veo` | Gemini API: Nano Banana frames + Veo 3.1 Lite | ≈ $1.5 per reel (4 × 6 s × $0.05 + 4 images), ≈ $45/month | nothing |
| `inbox` (default) | You make the 4 clips in Google Flow with your free daily credits | free | ~10 min a day |

**Inbox mode:** each day the scheduled run writes `inbox/<date>/PROMPTS.md` with the 4 image and
video prompts. Make the clips in Flow (Veo 3.1 Lite, 9:16, add the `cast/*.png` image as first frame),
then on GitHub open `inbox/<date>/` → **Add file → Upload files** and upload them named
`shot1.mp4`, `shot2.mp4`, `shot3.mp4`, `shot4.mp4`. The **Inbox reel** workflow assembles and uploads the
reel, then deletes the clips to keep the repo small.

Veo has no free API tier and Flow credits can't be used from the API, which is why the fully automatic
mode is paid. Prices change; check the Gemini API pricing page before switching it on.

## Daily routine (inbox mode)

1. Get today's prompts: `inbox/<date>/PROMPTS.md` (written every afternoon when `GEMINI_API_KEY` is set —
   the free tier is enough), or ask Claude in chat for today's Jungle Kids prompts.
2. In Google Flow make the 4 clips (Veo 3.1 Lite, 9:16, x1, cast image as first frame) — 40 of the 50 daily credits.
3. Upload `shot1.mp4` … `shot4.mp4` to `inbox/<date>/` on GitHub (or send them to Claude in chat, which
   pushes them there). The **Inbox reel** workflow assembles the reel and schedules it on YouTube and Facebook.

## Setup

### 1. Gemini API key
Create a key in Google AI Studio. Script writing works on the free tier; **Veo and image generation
need billing enabled** on the key's Google Cloud project (only for `CLIP_SOURCE=veo`).

### 2. YouTube upload access
You can reuse the OAuth client from the Sunny pipeline (same Google Cloud project), but you need a
**new refresh token for the Jungle Kids channel**:

```bash
pip install google-auth-oauthlib
python scripts/get_refresh_token.py client_secret.json
```

Pick the Jungle Kids channel in the browser. The script prints the three secrets.

> Videos uploaded through the API by an **unverified** Google Cloud project are locked to private.
> If uploads stay private, the project needs YouTube's API audit (Sunny's project already uploads, so
> reusing its client avoids this).

### 3. Facebook Page Reels (optional)
Reuse Sunny's Meta app or create one (use case *Manage everything on your Page*, app in Live mode). In
Graph API Explorer get a User token with `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`
for the Jungle Kids Page, then:

```bash
python scripts/facebook_auth.py APP_ID APP_SECRET
```

It prints `FACEBOOK_PAGE_ID` and a never-expiring `FACEBOOK_PAGE_TOKEN`. Run the workflow in
`facebook-test` mode to save the sample as a **draft** Reel. `FACEBOOK_ENABLED=false` pauses Facebook.

### 4. GitHub secrets (Settings → Secrets and variables → Actions → Secrets)
`GEMINI_API_KEY`, `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`,
`FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_TOKEN`

### 5. Optional variables (same page → Variables)
| Variable | Default | Meaning |
|---|---|---|
| `CLIP_SOURCE` | `inbox` | `inbox` or `veo` |
| `UPLOAD_MODE` | `schedule` | `schedule`, `private` (publish by hand) or `public` |
| `PUBLISH_TIME` | `18:00` | local time the reel goes public |
| `PUBLISH_UTC_OFFSET` | `5` | Pakistan |
| `MADE_FOR_KIDS` | `false` | must honestly match the content; `true` turns off comments |
| `SHOT_SECONDS` | `6` (`8` for inbox) | seconds used from each clip; Veo API accepts 4, 6 or 8 |
| `VEO_MODEL` | `veo-3.1-lite-generate-preview` | e.g. `veo-3.1-fast-generate-preview` for better motion |
| `GEMINI_TEXT_MODEL` / `GEMINI_IMAGE_MODEL` | see `jungle/config.py` | model overrides |

### 6. First runs (Actions → Daily Jungle Kids reel → Run workflow)
1. `test` — sample episode with still frames, no keys needed. Download the reel from the run's artifacts.
2. `upload-test` — same sample uploaded **private** to YouTube; checks the YouTube secrets.
3. `no-upload` — a real episode (uses Gemini + Veo), kept as an artifact so you can judge quality.
4. `full` — real episode, scheduled for 6 PM.

After that the schedule runs by itself every day (three tries between 1 and 4 PM PKT; only one reel per day).
Each run's summary shows the YouTube link and a suggested comment to pin.

## Local
```bash
pip install -r requirements.txt   # plus ffmpeg
python -m jungle.run --sample --clips still --no-upload   # offline test -> out/<date>/reel.mp4
python -m jungle.run --no-upload                         # real episode, needs GEMINI_API_KEY in .env
```

## Changing the show
- Cast looks: replace `cast/<name>.png` and update `CAST_LOOK` in `jungle/config.py`.
- Tone, rules, situations: `cast/bible.md` and the prompt in `jungle/script.py`.
- Caption style, CTA grid, music: `jungle/assemble.py`, `jungle/music.py`.
