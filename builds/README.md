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

- **DO commit** `builds/` to the main repo — the admin portal reads build files
  from GitHub to power the in-browser Publish workflow.
- `builds.json` is the registry. It is always committed.
- Individual build folders (`builds/{slug}/`) should be committed once the app
  is ready to review. After publishing, they can be deleted from the repo.
- `git add builds/` after each `new_build.py` run so the admin portal can see it.

## How a build goes live

1. `python3 scripts/new_build.py`    ← creates builds/{slug}/, prints Cowork prompt
2. Open a **new Cowork session** and paste the printed prompt
3. Claude builds index.html in builds/{slug}/
4. Review and approve the result
5. `python3 scripts/new_customer.py` ← creates GitHub repo, pushes files, sets up Pages
6. Add Cloudflare DNS CNAME (printed by new_customer.py)
7. **Custom/Pro only:** register API keys in worker KV (curl command printed by new_build.py)
8. Verify at https://{slug}.appsforhire.app
