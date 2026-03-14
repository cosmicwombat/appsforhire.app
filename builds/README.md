# builds/

This is the **working directory** for in-progress client apps.

When you run `scripts/new_build.py`, it creates a subfolder here:
```
builds/
└── smithbakery/       ← active build
    ├── index.html
    ├── manifest.json
    └── sw.js
```

## Rules

- **Do NOT commit** the `builds/` folder to the main appsforhire repo.
  Each build eventually lives in its own private GitHub repo (e.g. `cosmicwombat/client-smithbakery`).
- Once a build is live (pushed via `new_customer.py`), you can delete the local folder here.
- If a build is in progress and you need to pause, it stays here safely.

## How a build goes live

1. `python3 scripts/new_build.py`    ← creates builds/{slug}/, prints Cowork prompt
2. Open a **new Cowork session** and paste the printed prompt
3. Claude builds index.html in builds/{slug}/
4. Review and approve the result
5. `python3 scripts/new_customer.py` ← creates GitHub repo, pushes files, sets up Pages
6. Add Cloudflare DNS CNAME (printed by new_customer.py)
7. **Custom/Pro only:** register API keys in worker KV (curl command printed by new_build.py)
8. Verify at https://{slug}.appsforhire.app
