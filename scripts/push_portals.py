#!/usr/bin/env python3
"""
Push build files to client GitHub repos.

Pushes all text files for a slug: index.html, manifest.json, sw.js,
portal/index.html, portal/customer-config.js.
(Icons are binary and only pushed during the initial publish — skip here.)

Usage:
  GITHUB_TOKEN=ghp_xxx python3 scripts/push_portals.py            # all slugs
  GITHUB_TOKEN=ghp_xxx python3 scripts/push_portals.py theghostkitchen
  GITHUB_TOKEN=ghp_xxx python3 scripts/push_portals.py tgpscripture thegatheringplace
"""

import os, sys, base64, json, urllib.request, urllib.error

OWNER = "cosmicwombat"
# All published client slugs — add new ones here after publishing
SLUGS = [
    "thegatheringplace",
    "tgpscripture",
    "tgpquake",
    "isitopen",
    "theghostinterpreter",
    "tgihorror",
    "theghostkitchen",
]

# Files to push from builds/{slug}/ → client-{slug}/
# Paths are relative to builds/{slug}/
APP_FILES    = ["index.html", "manifest.json", "sw.js"]
PORTAL_FILES = ["portal/index.html", "portal/customer-config.js"]
ALL_FILES    = APP_FILES + PORTAL_FILES


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
    except urllib.error.HTTPError:
        return None


def gh_put(owner, repo, path, content_bytes, message, token):
    sha  = gh_get_sha(owner, repo, path, token)
    body = {"message": message, "content": base64.b64encode(content_bytes).decode()}
    if sha:
        body["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept":        "application/vnd.github+json",
            "Content-Type":  "application/json",
        },
        method="PUT",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def push_slug(slug, token):
    repo = f"client-{slug}"
    print(f"\n→ [{slug}]  {OWNER}/{repo}")
    pushed = 0

    for rel_path in ALL_FILES:
        local_path = os.path.join("builds", slug, rel_path)
        if not os.path.exists(local_path):
            print(f"  –  {rel_path}  (not found, skipped)")
            continue
        with open(local_path, "rb") as f:
            content = f.read()
        try:
            gh_put(OWNER, repo, rel_path, content,
                   f"Update {rel_path} — push_portals.py", token)
            print(f"  ✓  {rel_path}")
            pushed += 1
        except Exception as e:
            print(f"  ✗  {rel_path}  ({e})")

    if pushed:
        print(f"  ✅  https://{slug}.appsforhire.app  (live in ~60s)")
    else:
        print(f"  ⚠   Nothing pushed for {slug}")


def main():
    token = get_token()
    slugs = sys.argv[1:] if len(sys.argv) > 1 else SLUGS
    print(f"Pushing files for: {', '.join(slugs)}")
    for slug in slugs:
        push_slug(slug, token)
    print("\nDone.")


if __name__ == "__main__":
    main()
