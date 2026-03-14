---
name: appsforhire
description: Build a PWA app for an AppsForHire client. Use when asked to build, create, or scaffold a new app for a customer on the AppsForHire platform. Triggers on phrases like "build an app for", "new build", "create a PWA for", or any client app development request.
---

# AppsForHire App Builder Skill

## Step 1 — Read context
Always read `/sessions/awesome-dazzling-archimedes/mnt/app_for_hire/CLAUDE_CONTEXT.md` first.
It has the current customer list, design system, API patterns, and known gotchas.

## Step 2 — Understand the build
If a COWORK_PROMPT.md exists at `builds/{slug}/COWORK_PROMPT.md`, read it — it has the
client-specific brief, app concept, and any special requirements from Robert.

## Step 3 — Build the app

### File structure to create
```
builds/{slug}/
  index.html           ← The entire app (HTML + CSS + JS, single file)
  manifest.json        ← PWA manifest
  sw.js                ← Service worker (cache-first)
  portal/
    index.html         ← Customer portal (copy from template/portal/index.html)
    customer-config.js ← Filled in with real client data (NOT placeholders)
```

### App rules
1. **Single file** — all HTML, CSS, JS in one `index.html`. No external files except the Worker.
2. **Dark design system** — use CSS variables from CLAUDE_CONTEXT.md. Never hardcode colors.
3. **Back-link header** — every app needs `← My Apps` linking to `/portal/`.
4. **AI calls go through the Worker** — `POST https://worker.appsforhire.app/ai` with `model: 'gemini'`.
5. **Demo overlay on 429** — show a "Get your own app" CTA when rate limit is hit.
6. **Soft warning** — show remaining call count when `calls_remaining <= 2`.
7. **Copy button** — always include a copy-to-clipboard button on AI output.
8. **"Again →" button** — let users generate another result without reloading.
9. **Mobile-first** — max-width 480px centered, works on phone.
10. **No external images** — use CSS gradients, emoji, or Unicode for visuals.

### manifest.json template
```json
{
  "name": "{APP_TITLE}",
  "short_name": "{APP_SHORT}",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0f1117",
  "theme_color": "{THEME_COLOR}",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

### sw.js template
```js
const CACHE = 'v1';
const ASSETS = ['/', '/index.html', '/manifest.json'];
self.addEventListener('install', e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS))));
self.addEventListener('fetch', e => e.respondWith(
  caches.match(e.request).then(r => r || fetch(e.request))
));
```

### customer-config.js — ALWAYS fill in real values, never leave placeholders
```js
const CUSTOMER = {
  name:          "{CLIENT_NAME}",
  tier:          "starter",
  since:         "{MONTH YEAR}",
  support_email: "hello@appsforhire.app",
  stripe_portal: "https://billing.stripe.com/p/login/YOUR_PORTAL_LINK",
  apps: [{
    name:        "{APP_TITLE}",
    description: "{APP_DESC}",
    url:         "https://{SLUG}.appsforhire.app",
    icon:        "{EMOJI}",
    status:      "active",
    launched:    "{MONTH YEAR}",
  }]
};
```

---

## Pre-vetted APIs (safe to use, CORS-friendly)
| Source | Endpoint | Key field |
|--------|----------|-----------|
| Quote | `https://dummyjson.com/quotes/random` | `.quote`, `.author` |
| Joke | `https://official-joke-api.appspot.com/random_joke` | `.setup`, `.punchline` |
| Advice | `https://api.adviceslip.com/advice` | `.slip.advice` |
| Cat Fact | `https://catfact.ninja/fact` | `.fact` |
| Useless Fact | `https://uselessfacts.jsph.pl/api/v2/facts/random?language=en` | `.text` |
| Dad Joke | `https://icanhazdadjoke.com/` + `Accept: application/json` | `.joke` |
| Trivia | `https://opentdb.com/api.php?amount=1&type=multiple` | `.results[0]` |

⚠️ Never use `api.quotable.io` — it's dead.

---

## Gemini system prompt tips
- Keep system prompts under 200 words — Gemini 2.5 Flash is fast but verbose system prompts slow it down
- Be specific about voice, length, and format in the system prompt
- Pass the user's input + any API data as the `message` field
- Gemini handles multi-source weaving well — pass all API results in one message

---

## After building
1. Verify the app works by reading through the JS logic
2. Confirm all 4 required elements are present: header/back-link, AI call pattern, demo overlay, soft warning
3. Confirm `customer-config.js` has NO template placeholders — include ALL existing apps for that customer
4. Tell Robert: "Ready to commit — run `git add builds/{slug} && git commit -m '...' && git push`"

## After publishing (post-Publish workflow)
After any new app is published via the Admin portal:
1. **Update `admin-site/data.json`** — add new app as a nested entry in the customer's `apps[]` array
2. **Update `CLAUDE_CONTEXT.md`** — add new app row to the Active Customers & Apps table and update status
3. **Deploy admin site** — `GITHUB_TOKEN=xxx python3 scripts/setup_admin_site.py`
4. **Rebuild plugin** — update `appsforhire.plugin` in repo root (or flag for Robert to do so)
5. **Commit and push** all changed files

## CF Access — what the publish flow handles automatically
- Creates DNS CNAME (`{slug}` → `cosmicwombat.github.io`, proxied)
- Calls `access-full-setup` — runs three CF API saves in the required order:
  1. Create the app (session_duration: 6h)
  2. Attach the email OTP policy to the app
  3. PATCH the app with `allowed_idps: []` to enforce OTP-only
  This order is critical — setting IDP restriction before the policy is attached does not stick.
- ⚠️ Requires `Access: Apps and Policies → Edit` on the CF API token.
  If missing, create manually in CF Zero Trust dashboard using this exact order:
  1. Create the policy first (save)
  2. Create the app with the policy already selected (save)
  3. Uncheck "Accept all available identity providers" (save again)

**CF Access architecture — one Access app per slug (intentional):**
Each app slug gets its own CF Access application. This enables granular per-app access control —
a staff member can be given access to one app without getting access to all apps for that client.
Never consolidate multiple slugs into one Access app. Never reuse policies across customers.

---

## Current Active Customers (as of 2026-03-14)
| Client | Slug | App | Status |
|--------|------|-----|--------|
| Smith Bakery | smithbakery | Smith Bakery App | published |
| The Gathering Place | thegatheringplace | Daily Offerations | published |
| The Gathering Place | tgpscripture | Daily Word | published |
| The Gathering Place | tgpquake | Salish Shaker | published |
| The Ghost Interpreter | theghostinterpreter | Random Sentence Generator | published |
| The Ghost Interpreter | tgihorror | Ghost Story Generator | published |
