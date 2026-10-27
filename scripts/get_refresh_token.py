"""One-time helper: prints a YouTube refresh token for the channel you pick in the browser.

    pip install google-auth-oauthlib
    python scripts/get_refresh_token.py client_secret.json

client_secret.json is the "Desktop app" OAuth client you download from Google Cloud Console
(APIs & Services -> Credentials). When the browser asks which account/channel to use, pick the
Jungle Kids channel (if it is a Brand Account, choose the channel, not your personal profile).
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/get_refresh_token.py client_secret.json")
    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    info = json.load(open(sys.argv[1]))
    client = info.get("installed") or info.get("web") or {}
    print("\nAdd these three as GitHub repository secrets:\n")
    print(f"YOUTUBE_CLIENT_ID={client.get('client_id')}")
    print(f"YOUTUBE_CLIENT_SECRET={client.get('client_secret')}")
    print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
