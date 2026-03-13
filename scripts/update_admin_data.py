#!/usr/bin/env python3
"""
update_admin_data.py
AppsForHire — Refresh Admin Dashboard

Reads customers.json, recalculates MRR, and pushes data.json directly to
the appsforhire-admin GitHub repo so the live dashboard updates immediately.
No manual git push required.

Usage:
    python3 scripts/update_admin_data.py

Requirements:
    pip install PyGithub --break-system-packages
"""

import os
import sys
import json
import datetime
import subprocess
from pathlib import Path

try:
    from github import Github, GithubException
except ImportError:
    print("Installing PyGithub...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyGithub", "--break-system-packages", "-q"])
    from github import Github, GithubException

# ── Config ─────────────────────────────────────────────────────────────────
GITHUB_USERNAME = "cosmicwombat"
ADMIN_REPO_NAME = "appsforhire-admin"
DATA_FILE_PATH  = "data.json"   # path inside the admin repo

SCRIPTS_DIR = Path(__file__).parent
ROOT_DIR    = SCRIPTS_DIR.parent
ADMIN_DIR   = ROOT_DIR / "admin"       # local copy (kept in sync as backup)
ADMIN_SITE_DIR = ROOT_DIR / "admin-site"  # standalone admin repo source


def get_token():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("\n🔑 GitHub Personal Access Token needed.")
        print("   (Set GITHUB_TOKEN env var to skip this prompt)\n")
        token = input("   Paste your GitHub token: ").strip()
    return token


def build_data():
    """Load customers.json and compute dashboard data."""
    customers_file = SCRIPTS_DIR / "customers.json"
    if not customers_file.exists():
        print("❌ customers.json not found.")
        sys.exit(1)

    customers = json.loads(customers_file.read_text())
    hosting   = {'starter': 15, 'custom': 20, 'pro': 29}
    active    = [c for c in customers if c.get('status') == 'active']
    mrr       = sum(hosting.get(c.get('tier', ''), 0) for c in active)

    return {
        "customers": customers,
        "mrr":       mrr,
        "capacity":  100,
        "generated": datetime.date.today().isoformat(),
    }, active, mrr


def push_data_to_github(token, data_json):
    """Push data.json to the admin repo."""
    g    = Github(token)
    user = g.get_user()

    try:
        repo = user.get_repo(ADMIN_REPO_NAME)
    except GithubException:
        print(f"❌ Repo {GITHUB_USERNAME}/{ADMIN_REPO_NAME} not found.")
        print(f"   Run setup_admin_site.py first to create it.")
        return False

    try:
        existing = repo.get_contents(DATA_FILE_PATH)
        repo.update_file(
            DATA_FILE_PATH,
            f"Update admin data — {datetime.date.today().isoformat()}",
            data_json,
            existing.sha
        )
        print(f"   ✅ {DATA_FILE_PATH} updated in {ADMIN_REPO_NAME}")
    except GithubException:
        # File doesn't exist yet — create it
        repo.create_file(
            DATA_FILE_PATH,
            f"Initial admin data — {datetime.date.today().isoformat()}",
            data_json
        )
        print(f"   ✅ {DATA_FILE_PATH} created in {ADMIN_REPO_NAME}")

    return True


def main():
    print("\n── AppsForHire Admin Data Update ─────────────────────────────\n")

    # Build data
    data, active, mrr = build_data()
    data_json = json.dumps(data, indent=2)

    # Print summary
    tier_counts = {}
    for c in active:
        t = c.get('tier', 'unknown')
        tier_counts[t] = tier_counts.get(t, 0) + 1

    total = len(data["customers"])
    print(f"  Customers : {total} total  |  {len(active)} active")
    for tier, count in sorted(tier_counts.items()):
        print(f"              {count}x {tier}")
    print(f"  MRR       : ${mrr}/mo")
    print(f"  Capacity  : {len(active)}/100 slots ({round(len(active)/100*100)}%)")
    print()

    # Also write locally (admin/ and admin-site/ as backup copies)
    for local_dir in [ADMIN_DIR, ADMIN_SITE_DIR]:
        if local_dir.exists():
            (local_dir / "data.json").write_text(data_json)

    # Push to GitHub
    print(f"  Pushing to https://github.com/{GITHUB_USERNAME}/{ADMIN_REPO_NAME}...")

    # Try with token — fall back to local-only with git-push instructions
    try:
        token = get_token()
        ok = push_data_to_github(token, data_json)
        if ok:
            print()
            print(f"  🌐 Dashboard live at: https://admin.appsforhire.app")
    except KeyboardInterrupt:
        print("\n  Skipping GitHub push. Local files updated.")
        print(f"  To push manually:")
        print(f"    cd {ROOT_DIR}")
        print(f"    git add admin/data.json admin-site/data.json")
        print(f"    git commit -m 'Update admin data' && git push")

    print()


if __name__ == "__main__":
    main()
