#!/usr/bin/env python3
"""
AppsForHire — New Customer Setup Script
----------------------------------------
Run this once when a new client is ready for their app to go live.

What it does:
  1. Creates a new private GitHub repo for the customer
  2. Copies the app template into it
  3. Sets up GitHub Pages
  4. Adds the CNAME file for their subdomain
  5. Generates the icons with their brand color
  6. Prints the Cloudflare DNS + Access steps to complete manually

Usage:
  python3 scripts/new_customer.py

Requirements:
  pip install PyGithub Pillow requests
"""

import os
import sys
import json
import shutil
import base64
import subprocess
from pathlib import Path

# ── Try to import dependencies ──────────────────────────────────────────────
try:
    from github import Github, GithubException
except ImportError:
    print("Installing PyGithub...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyGithub", "--break-system-packages", "-q"])
    from github import Github, GithubException

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Installing Pillow...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "--break-system-packages", "-q"])
    from PIL import Image, ImageDraw


# ── Config ───────────────────────────────────────────────────────────────────
GITHUB_USERNAME   = "cosmicwombat"
BASE_DOMAIN       = "appsforhire.app"
TEMPLATE_DIR      = Path(__file__).parent.parent / "template"
SCRIPTS_DIR       = Path(__file__).parent


def get_github_token():
    """Get GitHub token from env var or prompt."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("\n🔑 GitHub Personal Access Token needed.")
        print("   (Set GITHUB_TOKEN env var to skip this prompt next time)\n")
        token = input("   Paste your GitHub token: ").strip()
    return token


def collect_customer_info():
    """Prompt for all customer details."""
    print("\n" + "="*55)
    print("  AppsForHire — New Customer Setup")
    print("="*55 + "\n")

    info = {}

    info["client_name"]  = input("Client / business name (e.g. Smith Bakery): ").strip()
    info["client_slug"]  = input("URL slug — lowercase, no spaces (e.g. smithbakery): ").strip().lower().replace(" ", "-")
    info["app_title"]    = input("App title (e.g. Order Tracker): ").strip()
    info["app_desc"]     = input("One-line description: ").strip()

    print("\nTheme color options:")
    print("  1. Indigo  #4f46e5   2. Sky    #0ea5e9   3. Teal   #0d9488")
    print("  4. Green   #16a34a   5. Violet #7c3aed   6. Custom")
    colors = {
        "1": ("#4f46e5", "#3730a3"),
        "2": ("#0ea5e9", "#0284c7"),
        "3": ("#0d9488", "#0f766e"),
        "4": ("#16a34a", "#15803d"),
        "5": ("#7c3aed", "#6d28d9"),
    }
    choice = input("Choose (1-6): ").strip()
    if choice in colors:
        info["theme_color"], info["theme_dark"] = colors[choice]
    else:
        info["theme_color"] = input("  Enter hex color (e.g. #e11d48): ").strip()
        info["theme_dark"]  = input("  Enter darker shade (e.g. #be123c): ").strip()

    info["tier"] = input("\nTier (starter/custom/pro): ").strip().lower()

    print("\n── Customize Template Fields ──")
    print("(These are the {{PLACEHOLDERS}} in the template — press Enter to use defaults)\n")

    info["stat1_label"] = input("Stat 1 label (default: Total Items): ").strip() or "Total Items"
    info["stat2_label"] = input("Stat 2 label (default: This Week): ").strip() or "This Week"
    info["stat3_label"] = input("Stat 3 label (default: Active): ").strip() or "Active"
    info["table_title"] = input("Table title (default: Records): ").strip() or "Records"
    info["col1"]        = input("Column 1 header (default: Name): ").strip() or "Name"
    info["col2"]        = input("Column 2 header (default: Value): ").strip() or "Value"
    info["col3"]        = input("Column 3 header (default: Notes): ").strip() or "Notes"
    info["item_name"]   = input("Item name for form (default: Record): ").strip() or "Record"
    info["field1"]      = input("Field 1 label (default: Name): ").strip() or "Name"
    info["field1_ph"]   = input("Field 1 placeholder (default: Enter name): ").strip() or "Enter name"
    info["field2"]      = input("Field 2 label (default: Value): ").strip() or "Value"
    info["field2_ph"]   = input("Field 2 placeholder (default: Enter value): ").strip() or "Enter value"

    info["subdomain"] = f"{info['client_slug']}.{BASE_DOMAIN}"
    info["repo_name"] = f"client-{info['client_slug']}"

    return info


def render_template(content, info):
    """Replace {{PLACEHOLDERS}} with actual values."""
    replacements = {
        "{{CLIENT_NAME}}":          info["client_name"],
        "{{CLIENT_SHORT}}":         info["client_name"].split()[0],
        "{{CLIENT_SLUG}}":          info["client_slug"],
        "{{APP_TITLE}}":            info["app_title"],
        "{{APP_DESCRIPTION}}":      info["app_desc"],
        "{{THEME_COLOR}}":          info["theme_color"],
        "{{THEME_COLOR_DARK}}":     info["theme_dark"],
        "{{STAT_1_LABEL}}":         info["stat1_label"],
        "{{STAT_2_LABEL}}":         info["stat2_label"],
        "{{STAT_3_LABEL}}":         info["stat3_label"],
        "{{TABLE_TITLE}}":          info["table_title"],
        "{{COL_1}}":                info["col1"],
        "{{COL_2}}":                info["col2"],
        "{{COL_3}}":                info["col3"],
        "{{ITEM_NAME}}":            info["item_name"],
        "{{FIELD_1_LABEL}}":        info["field1"],
        "{{FIELD_1_PLACEHOLDER}}":  info["field1_ph"],
        "{{FIELD_2_LABEL}}":        info["field2"],
        "{{FIELD_2_PLACEHOLDER}}":  info["field2_ph"],
    }
    for key, val in replacements.items():
        content = content.replace(key, val)
    return content


def generate_icon(size, color_hex, path):
    """Generate a branded app icon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(color_hex.lstrip("#"), 16)
    color = ((r >> 16) & 0xFF, (r >> 8) & 0xFF, r & 0xFF, 255)
    dark = tuple(max(0, c - 40) for c in color[:3]) + (255,)
    radius = size // 7
    d.rounded_rectangle([0, 0, size-1, size-1], radius=radius, fill=dark)
    cx, cy, rad = size//2, size//2, int(size * 0.32)
    for i in range(rad, 0, -1):
        alpha = int(80 * (i / rad))
        d.ellipse([cx-i, cy-i, cx+i, cy+i], fill=color[:3] + (alpha,))
    sw = max(2, size // 20)
    p1 = (int(size*.28), int(size*.52))
    p2 = (int(size*.44), int(size*.68))
    p3 = (int(size*.72), int(size*.34))
    d.line([p1, p2], fill=(255,255,255,255), width=sw)
    d.line([p2, p3], fill=(255,255,255,255), width=sw)
    img.save(path, "PNG")


def create_github_repo(g, info):
    """Create GitHub repo and push all template files."""
    user = g.get_user()
    repo_name = info["repo_name"]

    print(f"\n📁 Creating GitHub repo: {GITHUB_USERNAME}/{repo_name}...")
    try:
        repo = user.create_repo(
            repo_name,
            description=f"{info['client_name']} — {info['app_title']} (AppsForHire)",
            private=True,
            auto_init=False
        )
        print(f"   ✓ Repo created: {repo.html_url}")
    except GithubException as e:
        if "already exists" in str(e):
            print(f"   ⚠ Repo already exists — using existing repo.")
            repo = user.get_repo(repo_name)
        else:
            raise

    # Build file list from template
    files = {}
    tmp = Path("/tmp") / f"afh_{info['client_slug']}"
    tmp.mkdir(exist_ok=True)
    icons_dir = tmp / "icons"
    icons_dir.mkdir(exist_ok=True)

    # Generate icons
    print("   🎨 Generating branded icons...")
    generate_icon(192, info["theme_color"], icons_dir / "icon-192.png")
    generate_icon(512, info["theme_color"], icons_dir / "icon-512.png")

    # Render template files
    for tmpl_file in ["index.html", "manifest.json", "sw.js"]:
        src = TEMPLATE_DIR / tmpl_file
        content = src.read_text()
        rendered = render_template(content, info)
        files[tmpl_file] = rendered

    # CNAME
    files["CNAME"] = info["subdomain"] + "\n"

    # Push files to GitHub
    print("   📤 Pushing files to GitHub...")
    for filename, content in files.items():
        try:
            repo.create_file(filename, f"Initial setup: {filename}", content)
        except GithubException:
            existing = repo.get_contents(filename)
            repo.update_file(filename, f"Update {filename}", content, existing.sha)

    # Push icons
    for icon_name in ["icon-192.png", "icon-512.png"]:
        icon_path = icons_dir / icon_name
        with open(icon_path, "rb") as f:
            icon_bytes = f.read()
        try:
            repo.create_file(f"icons/{icon_name}", f"Add {icon_name}", icon_bytes)
        except GithubException:
            existing = repo.get_contents(f"icons/{icon_name}")
            repo.update_file(f"icons/{icon_name}", f"Update {icon_name}", icon_bytes, existing.sha)

    print("   ✓ All files pushed")
    return repo


def enable_github_pages(repo, info):
    """Enable GitHub Pages via API."""
    print("\n🌐 Enabling GitHub Pages...")
    try:
        # Use PyGithub's pages API
        repo._requester.requestJsonAndCheck(
            "POST",
            repo.url + "/pages",
            input={"source": {"branch": "main", "path": "/"}}
        )
        print("   ✓ GitHub Pages enabled")
    except Exception as e:
        print(f"   ⚠ Pages may already be enabled or needs manual setup: {e}")
        print(f"   → Go to: {repo.html_url}/settings/pages")
        print(f"     Set Source: main / (root) and Custom Domain: {info['subdomain']}")


def save_customer_record(info, repo):
    """Save customer info to a local JSON log."""
    log_file = SCRIPTS_DIR / "customers.json"
    customers = []
    if log_file.exists():
        customers = json.loads(log_file.read_text())

    record = {
        "client_name":  info["client_name"],
        "client_slug":  info["client_slug"],
        "subdomain":    info["subdomain"],
        "repo":         repo.html_url,
        "tier":         info["tier"],
        "theme_color":  info["theme_color"],
        "created":      __import__("datetime").date.today().isoformat(),
        "stripe_hosting": None,   # Fill in after subscription starts
        "status": "active"
    }
    customers.append(record)
    log_file.write_text(json.dumps(customers, indent=2))
    print(f"\n   ✓ Customer record saved to scripts/customers.json")


def print_next_steps(info, repo):
    """Print the manual Cloudflare steps."""
    slug = info["client_slug"]
    subdomain = info["subdomain"]

    print("\n" + "="*55)
    print("  ✅ GitHub setup complete!")
    print("="*55)
    print(f"""
  Repo:      {repo.html_url}
  App URL:   https://{subdomain}

  ── Manual Steps Remaining ──────────────────────────

  1. CLOUDFLARE DNS
     Go to: cloudflare.com → {BASE_DOMAIN} → DNS → Add record

     Type:  CNAME
     Name:  {slug}
     Value: {GITHUB_USERNAME}.github.io
     Proxy: OFF (grey cloud)

  2. CLOUDFLARE ACCESS (2FA protection)
     Go to: one.dash.cloudflare.com → Access → Applications
     → Add an Application → Self-hosted

     App name:    {info['client_name']}
     Domain:      {subdomain}
     Policy:      Allow — Emails — add client's email address(es)
     Auth method: One-time PIN (email 2FA)

  3. GITHUB PAGES CUSTOM DOMAIN
     Go to: {repo.html_url}/settings/pages
     Custom domain: {subdomain}
     ✓ Enforce HTTPS

  4. STRIPE — Start hosting subscription
     Send the client their subscription link:
     Starter → https://buy.stripe.com/aFafZh2Nk24Ye7X7r62880c
     Custom  → https://buy.stripe.com/9B628r5ZwdNG5BrcLq2880d
     Pro     → https://buy.stripe.com/14AaEX73A24Yfc1bHm2880e

  ────────────────────────────────────────────────────
  App will be live at https://{subdomain}
  once DNS propagates (5–15 min).
""")


def main():
    token = get_github_token()
    g = Github(token)

    # Verify token works
    try:
        user = g.get_user()
        print(f"\n✓ Authenticated as: {user.login}")
    except Exception:
        print("❌ Invalid token — check and try again.")
        sys.exit(1)

    info = collect_customer_info()

    print(f"\n── Summary ─────────────────────────────────")
    print(f"  Client:    {info['client_name']}")
    print(f"  App:       {info['app_title']}")
    print(f"  Subdomain: {info['subdomain']}")
    print(f"  Repo:      github.com/{GITHUB_USERNAME}/{info['repo_name']}")
    print(f"  Tier:      {info['tier'].capitalize()}")
    print(f"────────────────────────────────────────────")

    confirm = input("\nLooks good? Create the app now? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        sys.exit(0)

    repo = create_github_repo(g, info)
    enable_github_pages(repo, info)
    save_customer_record(info, repo)
    print_next_steps(info, repo)


if __name__ == "__main__":
    main()
