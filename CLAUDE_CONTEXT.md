# AppsForHire — Claude Session Context
> Read this at the start of every session before touching any code.

## What This Is
AppsForHire (Ghost Kitchen LI LLC) is a boutique PWA-as-a-service platform.
Robert builds bespoke single-page web apps for small businesses, hosts them on
GitHub Pages behind Cloudflare Access (email OTP), and charges a monthly hosting fee.

**Live URL:** https://appsforhire.app
**Admin portal:** https://admin.appsforhire.app
**Worker:** https://worker.appsforhire.app
**GitHub org:** cosmicwombat
**Main repo:** cosmicwombat/appsforhire.app
**Admin repo:** cosmicwombat/appsforhire-admin

---

## Repo Layout
```
app_for_hire/
  admin-site/          ← Admin portal source (push via setup_admin_site.py)
    index.html
    data.json
  admin/               ← Older admin data copy (keep in sync)
  builds/              ← One folder per client app
    builds.json        ← Registry: slug, status (in_progress|ready|published)
    {slug}/
      index.html       ← The app
      manifest.json
      sw.js
      portal/
        index.html     ← Customer "My Apps" portal
        customer-config.js  ← Filled-in customer data
  scripts/             ← Python utilities
  template/            ← Shared icons and portal base
  worker/              ← Cloudflare Worker (AI proxy + CF proxy + Stripe)
    worker.js
    wrangler.toml
```

---

## Active Customers
| Client | Slug | URL | Theme |
|--------|------|-----|-------|
| Smith Bakery | smithbakery | smithbakery.appsforhire.app | #0d9488 teal |
| The Gathering Place | thegatheringplace | thegatheringplace.appsforhire.app | #d97706 amber |
| The Ghost Interpreter | theghostinterpreter | theghostinterpreter.appsforhire.app | #7c3aed violet |

---

## Unified Dark Design System
Every app uses these CSS variables — never deviate:
```css
:root {
  --bg:       #0f1117;
  --surface:  #1a1d27;
  --surface2: #222536;
  --border:   #2e3147;
  --text:     #e2e8f0;
  --muted:    #94a3b8;
  --dim:      #64748b;
  --accent:   /* client brand color */;
  --accent2:  #22d3ee;  /* cyan highlight */
}
```

---

## Required UI Elements (Every App)
**1. Header with back-link:**
```html
<header class="app-header">
  <a href="/portal/" class="back-link">← My Apps</a>
  <div class="header-right">
    <span class="header-badge">🔒 Secure App</span>
  </div>
</header>
```
```css
.app-header   { display:flex; justify-content:space-between; align-items:center;
                padding:12px 20px; background:var(--surface); border-bottom:1px solid var(--border); }
.back-link    { color:var(--muted); text-decoration:none; font-size:13px; }
.back-link:hover { color:var(--text); }
.header-badge { font-size:11px; color:var(--muted); background:var(--surface2);
                padding:3px 8px; border-radius:20px; border:1px solid var(--border); }
```

**2. AI call pattern:**
```js
const res = await fetch('https://worker.appsforhire.app/ai', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ model: 'gemini', message: userPrompt, system: systemPrompt })
});
const data = await res.json();
if (res.status === 429) { /* show demo overlay */ }
```

**3. Demo limit overlay** (shown on 429):
```html
<div id="demoOverlay" style="display:none; position:fixed; inset:0; background:rgba(15,17,23,0.95);
  z-index:100; display:flex; flex-direction:column; align-items:center; justify-content:center;">
  <div style="font-size:48px">🚀</div>
  <h2>Want your own app?</h2>
  <p>You've hit the free demo limit.</p>
  <a href="https://appsforhire.app/#contact" style="...">Get Your Build →</a>
</div>
```

**4. Soft warning** at `calls_remaining <= 2`.

---

## Pre-Vetted Free APIs (CORS-Friendly, Reliable)
| Source | URL | Response field |
|--------|-----|----------------|
| Quote | `https://dummyjson.com/quotes/random` | `.quote`, `.author` |
| Joke | `https://official-joke-api.appspot.com/random_joke` | `.setup`, `.punchline` |
| Advice | `https://api.adviceslip.com/advice` | `.slip.advice` |
| Cat Fact | `https://catfact.ninja/fact` | `.fact` |
| Useless Fact | `https://uselessfacts.jsph.pl/api/v2/facts/random?language=en` | `.text` |
| Dad Joke | `https://icanhazdadjoke.com/` (Accept: application/json) | `.joke` |
| Trivia | `https://opentdb.com/api.php?amount=1&type=multiple` | `.results[0]` |

⚠️ **Dead/unreliable — never use:** api.quotable.io

---

## Worker API
**Base:** `https://worker.appsforhire.app`

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/ai` | POST | none | AI proxy (Claude/Gemini, rate-limited for Starter) |
| `/health` | GET | none | Check all secrets are configured |
| `/admin/cf-proxy` | POST | Bearer ADMIN_SECRET | Cloudflare DNS, Access, cache purge |
| `/admin/set-client-keys` | POST | Bearer ADMIN_SECRET | Store per-client API keys in KV |
| `/webhook` | POST | Stripe sig | Stripe events |

**CF proxy ops:** `dns-create`, `access-app-create`, `access-policy-create`, `cache-purge`

---

## New App Workflow
1. `python3 scripts/new_build.py` → creates `builds/{slug}/` + prints Cowork prompt
2. Open new Cowork session → paste prompt → Claude builds app
3. Review app, commit, push: `git add builds/ && git commit && git push`
4. Admin portal → connect GitHub + enter Admin Secret → Builds tab → Mark Ready
5. Customers tab → Publish → enter client email
6. Portal auto-handles: repo create, file push, Pages enable, DNS, CF Access

---

## Key Scripts
| Script | Purpose |
|--------|---------|
| `scripts/new_build.py` | Scaffold new build + generate Cowork prompt |
| `scripts/new_customer.py` | Add customer to data.json |
| `scripts/setup_admin_site.py` | Push admin-site/ to appsforhire-admin repo |
| `scripts/push_portal.py` | Push portal/ files to a client repo |
| `scripts/update_admin_data.py` | Sync data.json from customers.json |

---

## Common Gotchas
- **CF Access token needs** `Access: Apps and Policies` permission — often missing from API token
- **One-Time PIN** must be enabled in Zero Trust → Settings → Authentication
- **Portal files** (`portal/index.html`, `portal/customer-config.js`) must be pushed separately — publish flow handles this now
- **Admin portal token** clears on every page refresh — reconnect GitHub + Admin Secret each session
- **Rate limit reset:** `npx wrangler kv key delete --binding=RATE_LIMIT "demo_ai:$(curl -s ifconfig.me)"`
- **Push admin site after any changes:** `GITHUB_TOKEN=xxx python3 scripts/setup_admin_site.py`
- **builds.json status** values: `in_progress` → `ready` → `published`

---

## Tier System
| Tier | Monthly | AI Key | Rate Limit |
|------|---------|--------|------------|
| Starter | $15 | Robert's shared Gemini key | 100 calls / 7 days (testing), 10 in production |
| Custom | $20 | Client's own key (stored in Worker KV) | None |
| Pro | $29 | Client's own key | None |
