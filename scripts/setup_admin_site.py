#!/usr/bin/env python3
"""
setup_admin_site.py
AppsForHire — One-Time Admin Site Setup

Creates the appsforhire-admin GitHub repo, pushes the admin dashboard files,
and enables GitHub Pages at admin.appsforhire.app — protected by Cloudflare
Access so only you can reach it.

Run this ONCE. After that, use update_admin_data.py to keep the dashboard
current (it pushes data.json directly to this repo).

Usage:
    python scripts/setup_admin_site.py

Requirements:
    pip install PyGithub requests --break-system-packages
"""

import os
import sys
import time
import base64
import subprocess
from pathlib import Path

try:
    from github import Github, GithubException
except ImportError:
    print("Installing PyGithub...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyGithub", "--break-system-packages", "-q"])
    from github import Github, GithubException

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "--break-system-packages", "-q"])
    import requests

# ── Config ─────────────────────────────────────────────────────────────────
GITHUB_USERNAME  = "cosmicwombat"
REPO_NAME        = "appsforhire-admin"
ADMIN_SUBDOMAIN  = "admin.appsforhire.app"
ADMIN_SITE_DIR   = Path(__file__).parent.parent / "admin-site"
SCRIPTS_DIR      = Path(__file__).parent


def get_token():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("\n🔑 GitHub Personal Access Token needed.")
        print("   (Set GITHUB_TOKEN env var to skip this prompt)\n")
        token = input("   Paste your GitHub token: ").strip()
    return token


def read_file_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def push_file(repo, path_in_repo, local_path, message):
    """Push a single file to GitHub, updating if it already exists."""
    with open(local_path, "rb") as f:
        content = f.read()
    try:
        existing = repo.get_contents(path_in_repo)
        repo.update_file(path_in_repo, message, content, existing.sha)
    except GithubException:
        repo.create_file(path_in_repo, message, content)


def enable_github_pages(token, repo_full_name):
    url = f"https://api.github.com/repos/{repo_full_name}/pages"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {"source": {"branch": "main", "path": "/"}}
    r = requests.post(url, headers=headers, json=payload)
    if r.status_code in (201, 409):
        return True
    print(f"   ⚠️  Pages API returned {r.status_code}: {r.text[:120]}")
    return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="AppsForHire admin site setup")
    parser.add_argument("--force-data", action="store_true",
                        help="Force-push local admin-site/data.json to the admin repo "
                             "(use when the live copy is corrupt or missing)")
    args = parser.parse_args()

    print("\n══════════════════════════════════════════════════════════════")
    print("  AppsForHire — Admin Site Setup")
    print("══════════════════════════════════════════════════════════════\n")

    if not ADMIN_SITE_DIR.exists():
        print(f"❌ Admin-site directory not found at {ADMIN_SITE_DIR}")
        return

    token = get_token()
    g     = Github(token)
    user  = g.get_user()

    # ── 1. Create repo ──────────────────────────────────────────────────────
    print(f"📁 Creating GitHub repo: {GITHUB_USERNAME}/{REPO_NAME}...")
    try:
        repo = user.create_repo(
            REPO_NAME,
            description="AppsForHire admin dashboard — admin.appsforhire.app",
            private=False,   # GitHub Pages free tier requires public
            auto_init=False
        )
        print(f"   ✅ Repo created: {repo.html_url}")
    except GithubException as e:
        if "already exists" in str(e):
            print(f"   ⚠️  Repo already exists — pushing to existing repo.")
            repo = user.get_repo(REPO_NAME)
        else:
            print(f"   ❌ GitHub error: {e}")
            return

    # ── 2. Push admin files ─────────────────────────────────────────────────
    files = [f for f in sorted(ADMIN_SITE_DIR.rglob("*")) if f.is_file()]
    print(f"\n📤 Pushing {len(files)} files to repo...")

    for i, abs_path in enumerate(files, 1):
        github_path = str(abs_path.relative_to(ADMIN_SITE_DIR)).replace("\\", "/")

        # data.json is owned by the publish flow — only seed it if it doesn't
        # exist yet in the repo (first-time setup). Never overwrite a live copy
        # unless --force-data is passed (recovery from corrupt/missing file).
        if github_path == "data.json":
            if args.force_data:
                print(f"   [{i:02d}/{len(files):02d}] {github_path} (force-push)")
            else:
                try:
                    repo.get_contents("data.json")
                    print(f"   [skip] data.json — live version preserved (use --force-data to override)")
                    continue
                except GithubException:
                    print(f"   [{i:02d}/{len(files):02d}] {github_path} (first-time seed)")
        else:
            print(f"   [{i:02d}/{len(files):02d}] {github_path}")

        try:
            push_file(repo, github_path, abs_path, f"Setup admin site: {github_path}")
            time.sleep(0.25)
        except Exception as e:
            print(f"         ❌ Error: {e}")

    print("   ✅ All files pushed.")

    # ── 3. Enable GitHub Pages ──────────────────────────────────────────────
    print(f"\n🌐 Enabling GitHub Pages...")
    time.sleep(2)
    ok = enable_github_pages(token, repo.full_name)
    if ok:
        print(f"   ✅ GitHub Pages enabled.")
    else:
        print(f"   ⚠️  Enable Pages manually: repo → Settings → Pages → main branch")

    # ── 4. Print Cloudflare instructions ───────────────────────────────────
    print()
    print("══════════════════════════════════════════════════════════════")
    print("  ✅ DONE — Complete these steps in Cloudflare:")
    print("══════════════════════════════════════════════════════════════")
    print()
    print("  ── Step 1: Cloudflare DNS ──────────────────────────────────")
    print(f"  Dashboard → appsforhire.app → DNS → Add record:")
    print()
    print(f"    Type:    CNAME")
    print(f"    Name:    admin")
    print(f"    Target:  {GITHUB_USERNAME}.github.io")
    print(f"    Proxy:   🟠 ON  ← required for Access to intercept")
    print()
    print("  ── Step 2: Cloudflare SSL ──────────────────────────────────")
    print("  SSL/TLS → Overview → Mode: Full  (not Flexible)")
    print()
    print("  ── Step 3: Cloudflare Access Application ───────────────────")
    print("  Zero Trust → Access → Applications → Add an application")
    print()
    print("    Type:             Self-hosted")
    print("    App name:         AppsForHire Admin")
    print("    Session duration: 24 hours  (or longer if you prefer)")
    print(f"    Domain:          {ADMIN_SUBDOMAIN}")
    print()
    print("  ── Step 4: Policy (INSIDE the app — not standalone!) ───────")
    print("  After saving the app → go to its Policies tab → Add policy:")
    print()
    print("    Policy name:  Allow Admin")
    print("    Action:       Allow")
    print("    Include:      Emails → cosmicwombat@gmail.com")
    print()
    print("  ⚠️  IMPORTANT: Policy must be inside the app's Policies tab.")
    print("     Standalone policies will NOT gate the login correctly.")
    print()
    print("  ── Step 5: Verify ──────────────────────────────────────────")
    print(f"  Visit https://{ADMIN_SUBDOMAIN}")
    print("  You should be prompted for your email + OTP.")
    print("  After login, the admin dashboard should load.")
    print()
    print("  ── Step 6: Update your workflow ────────────────────────────")
    print("  From now on, use update_admin_data.py to refresh the")
    print(f"  dashboard — it will push data.json directly to the")
    print(f"  {REPO_NAME} repo, no manual git push needed.")
    print()
    print(f"  GitHub repo: https://github.com/{GITHUB_USERNAME}/{REPO_NAME}")
    print(f"  Live URL:    https://{ADMIN_SUBDOMAIN}")
    print("══════════════════════════════════════════════════════════════\n")


if __name__ == "__main__":
    main()
