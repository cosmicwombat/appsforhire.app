# AppsForHire — Build: insult me
**Client:** The Build company
**Slug:** `insultme`
**Live URL:** https://insultme.appsforhire.app
**Tier:** Starter
**API type:** Gemini only (Robert's shared key, rate-limited)

---

## Your Task

Build a polished, mobile-friendly single-page web app and save it to:

```
/app_for_hire/builds/insultme/index.html
```

The scaffold files are already there (template HTML, manifest.json, sw.js, icons).
**Replace `index.html` completely** — don't just edit the scaffold.

---

## What the App Does

Ask for a name, research insults that might go well with the name and display the insult. Use the "Forge & Fable" app as a "look" example and ensure that the insults are very monty python

---

## Brand & Design System

- **Business name:** The Build company
- **App title:** insult me
- **Subtitle / description:** AI Powered insults in seconds.
- **Brand accent color:** `#0d9488` (Teal) — use as `--accent`
- **Brand accent dark:** `#0f766e` — use as `--accent-dark`

All AppsForHire apps share a **unified dark design system**. Use exactly these CSS variables:

```css
:root {
  --bg:         #0f1117;
  --surface:    #1a1d27;
  --surface2:   #222536;
  --border:     #2e3147;
  --accent:     #0d9488;
  --accent-dark:#0f766e;
  --accent2:    #22d3ee;
  --green:      #34d399;
  --amber:      #fbbf24;
  --red:        #f87171;
  --text:       #e2e8f0;
  --muted:      #94a3b8;
  --dim:        #64748b;
  --radius:     12px;
}
```

**Design rules:** Dark background (`--bg`) with cards on `--surface`, inputs on `--surface2`. All borders: `1px solid var(--border)`. Buttons: `background: var(--accent)`, white text. Mobile-first; `max-width: 860px` centered layout.

---

## Architecture & Constraints

- **Single file:** Everything in `index.html`. No separate CSS or JS files.
- **No frameworks:** Vanilla HTML, CSS, JavaScript only. No npm, no build step.
- **PWA-ready:** `manifest.json` and `sw.js` are already there — register the service worker (`navigator.serviceWorker.register('sw.js')`).
- **No localStorage for auth/data** — just for run counters if needed.

---

### AI Calls — Gemini Only

Worker URL: `https://worker.appsforhire.app/ai`  Model param: `"gemini"`

> **Rate limit**: Starter app on Robert’s shared key. Worker enforces 50 AI calls/IP/24h.
> Include a **demo overlay** that triggers on 429, encouraging contact with AppsForHire.

Exact fetch pattern:

```javascript
const WORKER_URL = 'https://worker.appsforhire.app/ai';

async function callAI(system, userMessage) {
  const res  = await fetch(WORKER_URL, {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ model: 'gemini', system, message: userMessage }),
  });
  const data = await res.json();
  if (res.status === 429) { document.getElementById('demoOverlay').classList.add('show'); return null; }
  if (!res.ok) throw new Error(data.error || 'AI error');
  return data.response;
}
```

The worker returns `{ "response": "...", "calls_used": N, "remaining": N }`.
Show a soft overlay when `remaining` reaches 1–2.

---

## Required UI Elements

1. **Header** — sticky, brand color background, shows `The Build company` + `insult me`. Right side must have two pill elements: a **`← My Apps` back link** (`<a href="/portal/" class="back-link">← My Apps</a>`, `background:rgba(0,0,0,.2)`, `border:1px solid rgba(255,255,255,.2)`, `border-radius:100px`) and a **"Secure App" badge** (`background:rgba(255,255,255,.18)`, `border:1px solid rgba(255,255,255,.3)`). Wrap both in `<div class="header-right" style="display:flex;align-items:center;gap:.6rem">`.
2. **Input form** — clean card, labeled fields, submit button in brand color.
3. **AI response area** — card that appears after AI responds, with copy-to-clipboard button.
4. **Loading state** — spinner or animated dots while waiting for AI.
5. **Error state** — friendly message if the call fails.
6. **Demo overlay** — full-screen modal on 429, encouraging user to contact AppsForHire.

---

## Code Quality

- Semantic HTML (`<main>`, `<section>`, `<label>`, etc.)
- All form fields must have matching `<label>` elements
- Button disabled while loading (prevent double-submit)
- Handle empty/whitespace input — don't call AI if nothing typed
- CSS variables for all colors — no hardcoded hex in rules

---

## What to Deliver

Write the complete `index.html` to:
```
/app_for_hire/builds/insultme/index.html
```

Then confirm you've written it and show me the first 30 lines so I can verify.