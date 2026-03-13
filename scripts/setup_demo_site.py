#!/usr/bin/env python3
"""
setup_demo_site.py
AppsForHire — One-Time Demo Site Setup

Creates the appsforhire-demo GitHub repo, pushes all demo app files,
and enables GitHub Pages at demo.appsforhire.app.

Run this ONCE to stand up the demo site. After that, use:
  - provision_demo.py  to grant a prospect demo access
  - expire_demos.py    to revoke expired access

Usage:
    python scripts/setup_demo_site.py

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
GITHUB_USERNAME = "cosmicwombat"
REPO_NAME       = "appsforhire-demo"
DEMO_SUBDOMAIN  = "demo.appsforhire.app"
DEMO_DIR        = Path(__file__).parent.parent / "demo"
SCRIPTS_DIR     = Path(__file__).parent


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
    content = read_file_b64(local_path)
    try:
        existing = repo.get_contents(path_in_repo)
        repo.update_file(path_in_repo, message, base64.b64decode(content), existing.sha)
    except GithubException:
        repo.create_file(path_in_repo, message, base64.b64decode(content))


def collect_demo_files(demo_dir):
    """
    Walk the demo directory and return a list of (relative_path, absolute_path).
    """
    files = []
    for path in sorted(demo_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(demo_dir)
            files.append((str(rel), path))
    return files


def enable_github_pages(token, repo_full_name):
    """Enable GitHub Pages on the main branch via REST API."""
    url = f"https://api.github.com/repos/{repo_full_name}/pages"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {"source": {"branch": "main", "path": "/"}}
    r = requests.post(url, headers=headers, json=payload)
    if r.status_code in (201, 409):  # 409 = already enabled
        return True
    print(f"   ⚠️  Pages API returned {r.status_code}: {r.text[:120]}")
    return False


def main():
    print("\n══════════════════════════════════════════════════════════════")
    print("  AppsForHire — Demo Site Setup")
    print("══════════════════════════════════════════════════════════════\n")

    if not DEMO_DIR.exists():
        print(f"❌ Demo directory not found at {DEMO_DIR}")
        print("   Run this script from the app_for_hire root, or check that")
        print("   the demo/ folder exists.")
        return

    token = get_token()
    g     = Github(token)
    user  = g.get_user()

    # ── 1. Create repo ──────────────────────────────────────────────────────
    print(f"📁 Creating GitHub repo: {GITHUB_USERNAME}/{REPO_NAME}...")
    try:
        repo = user.create_repo(
            REPO_NAME,
            description="AppsForHire demo site — demo.appsforhire.app",
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

    # ── 2. Push all demo files ──────────────────────────────────────────────
    demo_files = collect_demo_files(DEMO_DIR)
    print(f"\n📤 Pushing {len(demo_files)} files to repo...")

    for i, (rel_path, abs_path) in enumerate(demo_files, 1):
        # Normalize path separators for GitHub
        github_path = rel_path.replace("\\", "/")
        print(f"   [{i:02d}/{len(demo_files):02d}] {github_path}")
        try:
            push_file(repo, github_path, abs_path, f"Setup demo site: {github_path}")
            time.sleep(0.25)  # avoid rate limit
        except Exception as e:
            print(f"         ❌ Error: {e}")

    print("   ✅ All files pushed.")

    # ── 3. Enable GitHub Pages ──────────────────────────────────────────────
    print(f"\n🌐 Enabling GitHub Pages...")
    time.sleep(2)  # Give GitHub a moment after pushes
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
    print(f"    Name:    demo")
    print(f"    Target:  {GITHUB_USERNAME}.github.io")
    print(f"    Proxy:   🟠 ON  ← MUST be proxied for Access to work")
    print()
    print("  ── Step 2: Cloudflare SSL ──────────────────────────────────")
    print("  SSL/TLS → Overview → Mode: Full  (not Flexible, not Full Strict)")
    print("  (Should already be set from your customer subdomains.)")
    print()
    print("  ── Step 3: Cloudflare Access Application ───────────────────")
    print("  Zero Trust → Access → Applications → Add an application")
    print()
    print("    Type:             Self-hosted")
    print("    App name:         AppsForHire Demo")
    print("    Session duration: 7 days")
    print(f"    Domain:          {DEMO_SUBDOMAIN}")
    print()
    print("  ── Step 4: Policy (INSIDE the app — not standalone!) ───────")
    print("  After saving the app → go to its Policies tab → Add policy:")
    print()
    print("    Policy name:  Allow Demo Customers")
    print("    Action:       Allow")
    print("    Include:      Emails → add YOUR email first (for testing)")
    print()
    print("  ⚠️  IMPORTANT: The policy MUST be created inside the app's")
    print("     Policies tab. A standalone reusable policy will NOT work.")
    print()
    print("  ── Step 5: Note the IDs for provision_demo.py ──────────────")
    print("  After saving:")
    print("  • App ID:    Zero Trust → Access → Applications →")
    print(f"               click '{DEMO_SUBDOMAIN}' → Edit → URL will show:")
    print("               .../apps/<APP_ID>/edit")
    print("  • Policy ID: Policies tab → click the policy → URL shows:")
    print("               .../policies/<POLICY_ID>")
    print()
    print("  Set these as environment variables (or enter when prompted):")
    print("    export CF_API_TOKEN='your_token'")
    print("    export CF_ACCOUNT_ID='your_account_id'")
    print(f"    export CF_DEMO_APP_ID='<APP_ID>'")
    print(f"    export CF_DEMO_POLICY_ID='<POLICY_ID>'")
    print()
    print("  ── Step 6: Verify ──────────────────────────────────────────")
    print(f"  Visit https://{DEMO_SUBDOMAIN}")
    print("  You should be prompted for your email + OTP code.")
    print("  After entering the code, you should see the demo portal.")
    print()
    print("  Then run:  python scripts/provision_demo.py")
    print("  to grant a prospect access.")
    print("══════════════════════════════════════════════════════════════\n")


if __name__ == "__main__":
    main()
