#!/usr/bin/env python3
"""
AppsForHire - Update Admin Dashboard Data
------------------------------------------
Run this after adding or updating any customer to refresh
the admin dashboard at appsforhire.app/admin/

Usage:
  python3 scripts/update_admin_data.py
"""

import json
from pathlib import Path
import datetime

scripts_dir = Path(__file__).parent
root_dir    = scripts_dir.parent
admin_dir   = root_dir / "admin"

customers = json.loads((scripts_dir / "customers.json").read_text())

hosting   = {'starter': 15, 'custom': 20, 'pro': 29}
active    = [c for c in customers if c.get('status') == 'active']
mrr       = sum(hosting.get(c['tier'], 0) for c in active)

data = {
    "customers":  customers,
    "mrr":        mrr,
    "capacity":   100,
    "generated":  datetime.date.today().isoformat(),
}

(admin_dir / "data.json").write_text(json.dumps(data, indent=2))

print(f"✓ admin/data.json updated")
print(f"  Customers: {len(customers)}  |  Active: {len(active)}  |  MRR: ${mrr}/mo")
print(f"\nNow run:")
print(f"  git add admin/data.json && git commit -m 'Update admin data' && git push")
