#!/usr/bin/env python3
"""
Push portal files to client GitHub repos.
Usage:  GITHUB_TOKEN=ghp_xxx python3 scripts/push_portals.py
        GITHUB_TOKEN=ghp_xxx python3 scripts/push_portals.py tgpscripture

If no slug is given, pushes all slugs listed in SLUGS below.
"""

import os, sys, base64, json, urllib.request

OWNER  = "cosmicwombat"
# Slugs whose portals need pushing — edit this list as needed
SLUGS  = ["thegatheringplace", "tgpscripture", "theghostinterpreter"]

def get_token():
    t = os.environ.get("GITHUB_TOKEN", "").strip()
    if not t:
        print("❌  Set GITHUB_TOKEN env var first.")
        print("    Example: GITHUB_TOKEN=ghp_xxx python3 scripts/push_portals.py")
        sys.exit(1)
    return t

def gh_get_sha(owner, repo, path, token):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())["sha"]
    except:
        return None

def gh_put(owner, repo, path, content, message, token):
    sha  = gh_get_sha(owner, repo, path, token)
    body = {"message": message, "content": base64.b64encode(content.encode()).decode()}
    if sha:
        body["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
        data=json.dumps(body).encode(),
        headers={
            "Authorization":  f"Bearer {token}",
            "Accept":         "application/vnd.github+json",
            "Content-Type":   "application/json"
        },
        method="PUT"
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def push_portal(slug, token):
    repo = f"client-{slug}"
    print(f"\n→ [{slug}] pushing to {OWNER}/{repo} ...")

    for filename in ["index.html", "customer-config.js"]:
        local_path = f"builds/{slug}/portal/{filename}"
        if not os.path.exists(local_path):
            print(f"  ⚠  {local_path} not found — skipping")
            continue
        with open(local_path) as f:
            content = f.read()
        gh_put(owner=OWNER, repo=repo, path=f"portal/{filename}",
               content=content, message=f"Update portal/{filename}", token=token)
        print(f"  ✓  portal/{filename}")

    print(f"  ✅  https://{slug}.appsforhire.app/portal/ (live in ~60s)")

def main():
    token = get_token()
    slugs = sys.argv[1:] if len(sys.argv) > 1 else SLUGS
    print(f"Pushing portals for: {', '.join(slugs)}")
    for slug in slugs:
        push_portal(slug, token)
    print("\nDone.")

if __name__ == "__main__":
    main()
