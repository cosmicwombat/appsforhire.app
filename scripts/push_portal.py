#!/usr/bin/env python3
"""
AppsForHire - Push Portal to Existing Customer Repo
-----------------------------------------------------
Use this to add or update the customer portal on an
existing client repo that was created before the portal
template existed.

Usage:
  python3 scripts/push_portal.py
"""

import os
import sys
import json
import subprocess
from pathlib import Path

try:
    from github import Github, GithubException
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyGithub", "--break-system-packages", "-q"])
    from github import Github, GithubException

GITHUB_USERNAME = "cosmicwombat"
BASE_DOMAIN     = "appsforhire.app"
TEMPLATE_DIR    = Path(__file__).parent.parent / "template"
SCRIPTS_DIR     = Path(__file__).parent


def get_token():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        token = input("GitHub token: ").strip()
    return token


def main():
    token = get_token()
    g     = Github(token)
    user  = g.get_user()

    log   = json.loads((SCRIPTS_DIR / "customers.json").read_text())
    print("\nCustomers:")
    for i, c in enumerate(log):
        print(f"  {i+1}. {c['client_name']} ({c['subdomain']})")

    idx   = int(input("\nWhich customer? (number): ").strip()) - 1
    info  = log[idx]
    slug  = info["client_slug"]

    today = __import__("datetime").date.today().strftime("%B %Y")

    portal_index  = (TEMPLATE_DIR / "portal" / "index.html").read_text()
    portal_config = f"""// AppsForHire - Customer Portal Config
const CUSTOMER = {{
  name:          "{info['client_name']}",
  tier:          "{info['tier']}",
  since:         "{info.get('created', today)}",
  support_email: "hello@appsforhire.app",
  stripe_portal: "https://billing.stripe.com/p/login/YOUR_PORTAL_LINK",
  apps: [
    {{
      name:        "My App",
      description: "Your custom app — click to open.",
      url:         "https://{info['subdomain']}",
      icon:        "📱",
      status:      "active",
      launched:    "{today}",
    }},
  ]
}};
"""

    repo_name = f"client-{slug}"
    print(f"\nPushing portal to {GITHUB_USERNAME}/{repo_name}...")
    repo = user.get_repo(repo_name)

    for path, content in [
        ("portal/index.html",         portal_index),
        ("portal/customer-config.js", portal_config),
    ]:
        try:
            repo.create_file(path, f"Add {path}", content)
            print(f"  created {path}")
        except GithubException:
            existing = repo.get_contents(path)
            repo.update_file(path, f"Update {path}", content, existing.sha)
            print(f"  updated {path}")

    print(f"\nDone! Portal live at: https://{info['subdomain']}/portal/")


if __name__ == "__main__":
    main()
