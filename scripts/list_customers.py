#!/usr/bin/env python3
"""
AppsForHire — Customer List
Lists all customers with their status, tier, and subdomain.

Usage:
  python3 scripts/list_customers.py
"""

import json
from pathlib import Path

log_file = Path(__file__).parent / "customers.json"

if not log_file.exists():
    print("\nNo customers yet. Run new_customer.py to add your first one!\n")
    exit()

customers = json.loads(log_file.read_text())

if not customers:
    print("\nNo customers yet.\n")
    exit()

print(f"\n{'─'*70}")
print(f"  AppsForHire — {len(customers)} Customer(s)")
print(f"{'─'*70}")
print(f"  {'Client':<22} {'Tier':<10} {'Subdomain':<30} {'Since'}")
print(f"{'─'*70}")

for c in customers:
    status_icon = "✅" if c.get("status") == "active" else "⏸️ "
    print(f"  {status_icon} {c['client_name']:<20} {c['tier'].capitalize():<10} {c['subdomain']:<30} {c.get('created','—')}")

print(f"{'─'*70}\n")
