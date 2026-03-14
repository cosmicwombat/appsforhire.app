# Co-Author Onboarding — AppsForHire

Everything a new co-author needs to get set up and productive.

---

## What You'll Need

Before starting, get these from Robert via [onetimesecret.com](https://onetimesecret.com) (burn-after-read links):
- `ADMIN_SECRET` — the shared Worker secret that authorizes admin actions
- Your Cloudflare API token (Robert creates one for you — see below)

Everything else you generate yourself.

---

## Step 1 — GitHub Setup

1. Create a GitHub account if you don't have one, or use your existing one
2. Send Robert your GitHub username — he'll add you as a collaborator on:
   - `cosmicwombat/app_for_hire` (the main project repo)
   - `cosmicwombat/appsforhire-admin` (the admin panel repo)
   - All existing `client-*` repos
3. Generate a **Personal Access Token** in GitHub:
   - Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Scopes needed: `repo` (full), `workflow`
   - Set expiration to your preference (90 days is fine)
   - Copy it — you'll paste it into the admin panel once

---

## Step 2 — Cloudflare Access

Robert will create a dedicated CF API token for you:
- Dashboard → My Profile → API Tokens → Create Token
- Permissions: `Zone DNS Edit`, `Access: Apps and Policies Edit`, `Workers KV Storage Edit`
- This is your token — don't share it

Robert will also add your email to the Cloudflare Access policies for the admin panel and any customer apps you'll be working on.

---

## Step 3 — Clone the Repo

```bash
git clone https://github.com/cosmicwombat/app_for_hire.git
cd app_for_hire
```

This becomes your local workspace folder. Mount this folder in Cowork.

---

## Step 4 — Install the Plugin

1. In Cowork, go to Plugins
2. Install `appsforhire.plugin` (find it in the `app_for_hire` root folder after cloning)
3. The plugin gives you the full platform context, commands, and skills

---

## Step 5 — Connect the Admin Panel

1. Open [appsforhire-admin.pages.dev](https://appsforhire-admin.pages.dev) (or the GitHub Pages URL)
2. Go to Settings (gear icon)
3. Paste your **GitHub token** → Connect
4. Paste the **Admin Secret** (from Robert via onetimesecret) → Connect
5. Both should show green — you now have full admin access

---

## Step 6 — First Git Pull

Always do this before starting any session:

```bash
cd ~/app_for_hire
git stash && git pull --rebase && git stash pop
```

---

## How We Work Together

**Coordination rules (important):**

- **Own your slugs** — each co-author works on separate app slugs. Don't edit the same slug at the same time.
- **Announce publishes** — send a quick message before running a publish, `setup_admin_site.py`, or any script that writes to `admin-site/data.json`. The admin panel has a preflight check but a heads-up is still good practice.
- **Pull before every session** — use the stash/pull/rebase/push sequence every time (the admin panel will warn you if recent activity is detected).
- **Commit often, push when done** — small commits are fine; just push before ending a session so the other person can pull.

**Cowork workflow per app:**
1. Open a new Cowork session
2. Mount your local `app_for_hire` folder
3. The plugin loads automatically and gives Claude full context
4. Build or edit the app, commit, push
5. Mark ready in admin panel → publish

---

## Key Scripts

All scripts live in `scripts/`. Run from the `app_for_hire` root:

| Script | What it does | Command |
|--------|-------------|---------|
| `setup_admin_site.py` | Push admin panel to GitHub | `GITHUB_TOKEN=xxx python3 scripts/setup_admin_site.py` |
| `push_portals.py` | Push portal files to client repos | `GITHUB_TOKEN=xxx python3 scripts/push_portals.py {slug}` |
| `check_access_emails.py` | Verify CF Access emails for apps | `CF_API_TOKEN=xxx CF_ACCOUNT_ID=xxx python3 scripts/check_access_emails.py {slug}` |
| `add_access_email.py` | Add a user to CF Access policies | `CF_API_TOKEN=xxx CF_ACCOUNT_ID=xxx python3 scripts/add_access_email.py email {slug}` |

---

## Troubleshooting

**Git push rejected ("fetch first"):**
```bash
git stash && git pull --rebase && git stash pop && git push
```

**Admin panel shows "Could not load data.json":**
```bash
GITHUB_TOKEN=xxx python3 scripts/setup_admin_site.py --force-data
```

**App not updating after edits:**
```bash
GITHUB_TOKEN=xxx python3 scripts/push_portals.py {slug}
```

**Rate limit hit during testing:**
```bash
npx wrangler kv key delete --binding=RATE_LIMIT "demo_ai:$(curl -s ifconfig.me)"
```

---

Questions? Ping Robert or open a session in Cowork — the plugin has full context on everything.
