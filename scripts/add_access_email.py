#!/usr/bin/env python3
"""
Add an email address to existing Cloudflare Access policies.

Handles both app-scoped policies and reusable (account-level) policies automatically.

Usage:
  CF_API_TOKEN=xxx CF_ACCOUNT_ID=xxx python3 scripts/add_access_email.py tony.fast@gmail.com thegatheringplace tgpscripture tgpquake isitopen
"""

import os, sys, requests

API     = "https://api.cloudflare.com/client/v4"
TOKEN   = os.environ["CF_API_TOKEN"]
ACCOUNT = os.environ["CF_ACCOUNT_ID"]
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def cf(method, path, **kwargs):
    r = requests.request(method, f"{API}{path}", headers=HEADERS, **kwargs)
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"{method} {path} failed: {data.get('errors')}")
    return data["result"]

def get_all_access_apps():
    return cf("GET", f"/accounts/{ACCOUNT}/access/apps")

def get_policies(app_uid):
    return cf("GET", f"/accounts/{ACCOUNT}/access/apps/{app_uid}/policies")

def update_app_policy(app_uid, policy_id, body):
    """Update an app-scoped policy."""
    return cf("PUT", f"/accounts/{ACCOUNT}/access/apps/{app_uid}/policies/{policy_id}", json=body)

def update_reusable_policy(policy_id, body):
    """Update a reusable (account-level) policy."""
    return cf("PUT", f"/accounts/{ACCOUNT}/access/policies/{policy_id}", json=body)

def add_email_to_app(app, new_email):
    uid  = app["uid"]
    name = app.get("name", app.get("domain", uid))
    policies = get_policies(uid)
    if not policies:
        print(f"  ⚠  No policies found for {name}")
        return

    for policy in policies:
        pid   = policy["id"]
        pname = policy.get("name", pid)

        # Build updated include list
        include = policy.get("include", [])
        existing_emails = [r["email"]["email"] for r in include if r.get("email")]
        if new_email in existing_emails:
            print(f"  ✓  {name} / {pname} — {new_email} already in policy, skipped")
            continue

        include.append({"email": {"email": new_email}})
        body = {
            "name":             policy["name"],
            "decision":         policy["decision"],
            "include":          include,
            "require":          policy.get("require", []),
            "exclude":          policy.get("exclude", []),
            "session_duration": policy.get("session_duration", "6h"),
        }

        # Try app-scoped endpoint first; fall back to account-level for reusable policies
        try:
            update_app_policy(uid, pid, body)
            print(f"  ✓  {name} / {pname} — added {new_email}")
        except RuntimeError as e:
            if "reusable" in str(e).lower() or "12130" in str(e):
                update_reusable_policy(pid, body)
                print(f"  ✓  {name} / {pname} (reusable) — added {new_email}")
            else:
                raise

def main():
    if len(sys.argv) < 3:
        print("Usage: add_access_email.py <email> <slug1> [slug2 ...]")
        sys.exit(1)

    new_email = sys.argv[1]
    slugs     = sys.argv[2:]

    print("Fetching Access apps…")
    all_apps = get_all_access_apps()
    lookup = {}
    for app in all_apps:
        domain = app.get("domain", "")
        for slug in slugs:
            if slug in domain:
                lookup[slug] = app

    for slug in slugs:
        app = lookup.get(slug)
        if not app:
            print(f"  ⚠  No Access app found matching slug '{slug}'")
            continue
        add_email_to_app(app, new_email)

    print("\nDone.")

if __name__ == "__main__":
    main()
