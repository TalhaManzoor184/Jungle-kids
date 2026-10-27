"""One-time helper: prints FACEBOOK_PAGE_ID and a never-expiring FACEBOOK_PAGE_TOKEN.

1. At developers.facebook.com create an app (use case: "Manage everything on your Page") or reuse Sunny's app.
2. In Graph API Explorer pick the app, "Get User Access Token" with pages_show_list,
   pages_read_engagement, pages_manage_posts; approve it for the Jungle Kids Page; copy the token.
3. python scripts/facebook_auth.py APP_ID APP_SECRET   and paste the token.
"""
import json
import sys
import urllib.parse
import urllib.request

V = "v26.0"


def get(path: str, params: dict) -> dict:
    url = f"https://graph.facebook.com/{V}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url) as res:
        return json.loads(res.read())


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("Usage: python scripts/facebook_auth.py APP_ID APP_SECRET")
    app_id, app_secret = sys.argv[1:]
    short = input("Paste the user access token from Graph API Explorer: ").strip()
    long = get("oauth/access_token", {"grant_type": "fb_exchange_token", "client_id": app_id,
                                      "client_secret": app_secret, "fb_exchange_token": short})
    pages = get("me/accounts", {"access_token": long["access_token"], "fields": "id,name,access_token"})["data"]
    if not pages:
        sys.exit("No Pages found. Select the Page when approving the token.")
    for i, p in enumerate(pages, 1):
        print(f"  {i}. {p['name']} ({p['id']})")
    pick = 1 if len(pages) == 1 else int(input("Which Page is Jungle Kids? Number: "))
    page = pages[pick - 1]
    print(f"\nFACEBOOK_PAGE_ID={page['id']}\nFACEBOOK_PAGE_TOKEN={page['access_token']}\n")
    print("Add both as GitHub repository secrets. Keep the token private.")


if __name__ == "__main__":
    main()
