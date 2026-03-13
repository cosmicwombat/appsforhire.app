#!/usr/bin/env python3
"""
expire_demos.py
AppsForHire — Demo Access Expiry Manager

Checks demo_customers.json for expired demo accounts (past 7-day window)
and removes their email from the Cloudflare Access demo policy.

Run this daily (cron, manual, or scheduled task) to keep demo access clean.

Usage:
    python expire_demos.py

    # Dry run (see what WOULD expire without making changes):
    python expire_demos.py --dry-run

    # Mark a prospect as converted (won't expire, just removes demo access):
    python expire_demos.py --convert user@example.com

Environment:
    CF_API_TOKEN, CF_ACCOUNT_ID, CF_DEMO_APP_ID, CF_DEMO_POLICY_ID
    (same as provision_demo.py)
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DEMO_DB    = SCRIPT_DIR / "demo_customers.json"
CF_BASE    = "https://api.cloudflare.com/client/v4"

def cf_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def get_env(key, prompt):
    val = os.environ.get(key)
    if not val:
        val = input(f"{prompt}: ").strip()
    return val

def get_policy(token, account_id, app_id, policy_id):
    url = f"{CF_BASE}/accounts/{account_id}/access/apps/{app_id}/policies/{policy_id}"
    r = requests.get(url, headers=cf_headers(token))
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"Cloudflare error: {data.get('errors')}")
    return data["result"]

def remove_email_from_policy(token, account_id, app_id, policy_id, email):
    """Remove a single email from the policy's include rules."""
    policy = get_policy(token, account_id, app_id, policy_id)

    current_emails = []
    for rule in policy.get("include", []):
        if "email" in rule:
            e = rule["email"]["email"]
            if e.lower() != email.lower():
                current_emails.append(e)

    new_include = [{"email": {"email": e}} for e in current_emails]

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

def load_db():
    with open(DEMO_DB) as f:
        return json.load(f)

def save_db(data):
    with open(DEMO_DB, "w") as f:
        json.dump(data, f, indent=2)

def main():
    dry_run  = "--dry-run" in sys.argv
    convert  = None
    if "--convert" in sys.argv:
        idx = sys.argv.index("--convert")
        if idx + 1 < len(sys.argv):
            convert = sys.argv[idx + 1].lower()

    print("\n── AppsForHire Demo Expiry Manager ───────────────────────────")
    if dry_run:
        print("  DRY RUN — no changes will be made\n")

    db  = load_db()
    now = datetime.now(timezone.utc)

    active    = [c for c in db["demo_customers"] if c["status"] == "active"]
    to_expire = []
    to_convert = []

    for customer in active:
        expires = datetime.fromisoformat(customer["expires_at"])
        if convert and customer["email"].lower() == convert:
            to_convert.append(customer)
        elif expires < now:
            days_over = (now - expires).days
            to_expire.append((customer, days_over))

    # ── Report ────────────────────────────────────────────────────────────────
    print(f"  Active demo accounts:  {len(active)}")
    print(f"  To expire:             {len(to_expire)}")
    print(f"  To convert:            {len(to_convert)}")
    print()

    if not to_expire and not to_convert:
        print("  ✅  Nothing to do — all demos are current.\n")

        # Show upcoming expirations
        upcoming = sorted(active, key=lambda c: c["expires_at"])
        if upcoming:
            print("  Upcoming expirations:")
            for c in upcoming:
                exp = datetime.fromisoformat(c["expires_at"])
                days_left = (exp - now).days
                print(f"    {c['name']} <{c['email']}> — {days_left}d remaining")
        print()
        return

    # Get CF credentials only if we need to make changes
    if not dry_run and (to_expire or to_convert):
        print("  Cloudflare credentials needed to revoke access:")
        token     = get_env("CF_API_TOKEN",       "CF_API_TOKEN")
        account   = get_env("CF_ACCOUNT_ID",      "CF_ACCOUNT_ID")
        app_id    = get_env("CF_DEMO_APP_ID",      "CF_DEMO_APP_ID")
        policy_id = get_env("CF_DEMO_POLICY_ID",   "CF_DEMO_POLICY_ID")
        print()

    # ── Process conversions ───────────────────────────────────────────────────
    for customer in to_convert:
        print(f"  🎉  Converting: {customer['name']} <{customer['email']}>")
        if not dry_run:
            try:
                remove_email_from_policy(token, account, app_id, policy_id, customer["email"])
                customer["status"]    = "converted"
                customer["converted"] = True
                print(f"       ✅  Removed from demo policy — now a paying customer.")
            except Exception as e:
                print(f"       ❌  Cloudflare error: {e}")

    # ── Process expirations ───────────────────────────────────────────────────
    for customer, days_over in to_expire:
        print(f"  ⏰  Expiring: {customer['name']} <{customer['email']}> ({days_over}d overdue)")
        if not dry_run:
            try:
                remove_email_from_policy(token, account, app_id, policy_id, customer["email"])
                customer["status"] = "expired"
                print(f"       ✅  Removed from demo policy.")
            except Exception as e:
                print(f"       ❌  Cloudflare error: {e}")

    # Save changes
    if not dry_run:
        save_db(db)
        print()
        print(f"  💾  demo_customers.json updated.")

    print()
    print("══════════════════════════════════════════════════════════════")
    if dry_run:
        print("  Dry run complete. Re-run without --dry-run to apply changes.")
    else:
        print("  Done. Run again tomorrow (or set up a daily cron job).")
    print()

    # Cron tip
    if not dry_run:
        print("  💡  Tip — add a daily cron to automate this:")
        print(f"      0 9 * * * cd {SCRIPT_DIR} && python expire_demos.py >> expire_demos.log 2>&1")
        print()

if __name__ == "__main__":
    main()
