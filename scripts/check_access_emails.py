#!/usr/bin/env python3
"""
Show allowed emails for each Access app matching the given slugs.

Usage:
  CF_API_TOKEN=xxx CF_ACCOUNT_ID=xxx python3 scripts/check_access_emails.py thegatheringplace tgpscripture tgpquake isitopen
"""

import os, sys, requests

API     = "https://api.cloudflare.com/client/v4"
TOKEN   = os.environ["CF_API_TOKEN"]
ACCOUNT = os.environ["CF_ACCOUNT_ID"]
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

def cf(path):
    r = requests.get(f"{API}{path}", headers=HEADERS)
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"GET {path} failed: {data.get('errors')}")
    return data["result"]

def extract_emails(rules):
    emails = []
    for rule in rules:
        if "email" in rule:
            emails.append(rule["email"]["email"])
        if "emails" in rule:
            emails.extend(rule["emails"].get("emails", []))
    return emails

def main():
    slugs = sys.argv[1:] if len(sys.argv) > 1 else []
    if not slugs:
        print("Usage: check_access_emails.py <slug1> [slug2 ...]")
        sys.exit(1)

    print("Fetching Access apps…\n")
    all_apps = cf(f"/accounts/{ACCOUNT}/access/apps")

    for slug in slugs:
        app = next((a for a in all_apps if slug in a.get("domain", "")), None)
        if not app:
            print(f"[{slug}] ✗ No Access app found\n")
            continue

        print(f"[{slug}] {app['domain']}")
        policies = cf(f"/accounts/{ACCOUNT}/access/apps/{app['uid']}/policies")

        if not policies:
            print("  (no policies)\n")
            continue

        for p in policies:
            emails = extract_emails(p.get("include", []))
            print(f"  Policy: {p['name']}")
            if emails:
                for e in emails:
                    print(f"    ✓  {e}")
            else:
                print("    (no email rules — may be a reusable policy, check CF dashboard)")
        print()

if __name__ == "__main__":
    main()
