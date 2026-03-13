#!/usr/bin/env python3
"""
provision_demo.py
AppsForHire — Demo Access Provisioner

Adds a prospect's email to the Cloudflare Access policy for demo.appsforhire.app
and records their 7-day expiry window in demo_customers.json.

Usage:
    python provision_demo.py

Requirements:
    pip install requests --break-system-packages

Environment (set these before running, or paste values when prompted):
    CF_API_TOKEN   — Cloudflare API token with Access: Edit permission
    CF_ACCOUNT_ID  — Your Cloudflare Account ID
    CF_DEMO_APP_ID — Access Application ID for demo.appsforhire.app
    CF_DEMO_POLICY_ID — Policy ID inside that application (the "Allow by email" policy)

How to find CF_DEMO_APP_ID and CF_DEMO_POLICY_ID:
    1. Cloudflare dashboard → Zero Trust → Access → Applications
    2. Click on "demo.appsforhire.app" → Edit
    3. The URL will contain the app ID: .../apps/<APP_ID>/edit
    4. Click Policies tab → click the policy → URL contains the policy ID
"""

import os
import json
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR       = Path(__file__).parent
DEMO_DB          = SCRIPT_DIR / "demo_customers.json"
DEMO_EXPIRY_DAYS = 7

CF_BASE = "https://api.cloudflare.com/client/v4"

def get_env(key, prompt):
    val = os.environ.get(key)
    if not val:
        val = input(f"{prompt}: ").strip()
    return val

# ── Cloudflare Access helpers ─────────────────────────────────────────────────

def cf_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def get_policy(token, account_id, app_id, policy_id):
    """Fetch the current state of the Access policy."""
    url = f"{CF_BASE}/accounts/{account_id}/access/apps/{app_id}/policies/{policy_id}"
    r = requests.get(url, headers=cf_headers(token))
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"Cloudflare error: {data.get('errors')}")
    return data["result"]

def add_email_to_policy(token, account_id, app_id, policy_id, email):
    """
    Add a single email to the policy's 'include' rules.
    Fetches current policy first so we don't wipe existing emails.
    """
    policy = get_policy(token, account_id, app_id, policy_id)

    # Build current email list
    current_emails = []
    for rule in policy.get("include", []):
        if "email" in rule:
            current_emails.append(rule["email"]["email"])

    if email.lower() in [e.lower() for e in current_emails]:
        print(f"  ⚠️  {email} is already in the policy — no change needed.")
        return

    # Append new email
    current_emails.append(email)
    new_include = [{"email": {"email": e}} for e in current_emails]

    # PUT updated policy back
    url = f"{CF_BASE}/accounts/{account_id}/access/apps/{app_id}/policies/{policy_id}"
    payload = {
        "name": policy["name"],
        "decision": policy["decision"],
        "include": new_include,
        "exclude": policy.get("exclude", []),
        "require": policy.get("require", []),
    }
    r = requests.put(url, headers=cf_headers(token), json=payload)
    r.raise_for_status()
    result = r.json()
    if not result.get("success"):
        raise RuntimeError(f"Cloudflare PUT error: {result.get('errors')}")
    print(f"  ✅  {email} added to Cloudflare Access demo policy.")

# ── Database helpers ──────────────────────────────────────────────────────────

def load_db():
    with open(DEMO_DB) as f:
        return json.load(f)

def save_db(data):
    with open(DEMO_DB, "w") as f:
        json.dump(data, f, indent=2)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n── AppsForHire Demo Provisioner ──────────────────────────────")
    print(f"  Demo expires after {DEMO_EXPIRY_DAYS} days · 10 runs per demo app\n")

    # Gather prospect info
    name  = input("Prospect name: ").strip()
    email = input("Prospect email: ").strip().lower()

    if not name or not email:
        print("❌ Name and email are required.")
        return

    # Cloudflare credentials
    print()
    token     = get_env("CF_API_TOKEN",       "CF_API_TOKEN (Cloudflare API token)")
    account   = get_env("CF_ACCOUNT_ID",      "CF_ACCOUNT_ID")
    app_id    = get_env("CF_DEMO_APP_ID",     "CF_DEMO_APP_ID (demo app Access ID)")
    policy_id = get_env("CF_DEMO_POLICY_ID",  "CF_DEMO_POLICY_ID")

    print()
    print(f"  Provisioning demo access for {name} <{email}>...")

    # Add to Cloudflare Access
    try:
        add_email_to_policy(token, account, app_id, policy_id, email)
    except Exception as e:
        print(f"  ❌ Cloudflare API error: {e}")
        return

    # Record in local DB
    now     = datetime.now(timezone.utc)
    expires = now + timedelta(days=DEMO_EXPIRY_DAYS)

    db = load_db()
    db["demo_customers"].append({
        "name":           name,
        "email":          email,
        "provisioned_at": now.isoformat(),
        "expires_at":     expires.isoformat(),
        "status":         "active",
        "converted":      False
    })
    save_db(db)

    # Summary
    print()
    print("══════════════════════════════════════════════════════════════")
    print(f"  ✅  Demo access granted for {name}")
    print(f"  📧  {email}")
    print(f"  🗓️   Expires: {expires.strftime('%A, %B %d, %Y')} ({DEMO_EXPIRY_DAYS} days)")
    print(f"  🔗  Demo URL: https://demo.appsforhire.app")
    print()
    print("  Next steps:")
    print("  1. Email the prospect their demo link:")
    print(f"     https://demo.appsforhire.app")
    print(f"     (They'll enter {email} to receive their OTP code)")
    print(f"  2. Each demo app allows 10 runs before the upgrade prompt appears.")
    print(f"  3. Run expire_demos.py periodically (or daily) to clean up expired access.")
    print("══════════════════════════════════════════════════════════════\n")

if __name__ == "__main__":
    main()
