# AppsForHire — Build: Daily Offerations
**Client:** The Gathering Place
**Slug:** `thegatheringplace`
**Live URL:** https://thegatheringplace.appsforhire.app
**Tier:** Starter
**API type:** Gemini only (Robert's shared key, rate-limited)

---

## Your Task

Build a polished, mobile-friendly single-page web app and save it to:

```
/app_for_hire/builds/thegatheringplace/index.html
```

The scaffold files are already there (template HTML, manifest.json, sw.js, icons).
**Replace `index.html` completely** — don't just edit the scaffold.

---

## What the App Does

You put in your name and the app posts a random picture of Nick Offerman that is overlarlayed with a randomly generate affermation but something Nick Offerman would say

---

## Brand & Design System

- **Business name:** The Gathering Place
- **App title:** Daily Offerations
- **Subtitle / description:** Things Nick Offerman might say to you on a daily basis
- **Brand accent color:** `#0f172a` (Slate/Dark) — use as `--accent`
- **Brand accent dark:** `#1e293b` — use as `--accent-dark`

All AppsForHire apps share a **unified dark design system**. Use exactly these CSS variables:

```css
:root {
  --bg:         #0f1117;   /* Page background */
  --surface:    #1a1d27;   /* Cards, panels, header */
  --surface2:   #222536;   /* Inputs, secondary surfaces */
  --border:     #2e3147;   /* All borders */
  --accent:     #0f172a;   /* Client brand — buttons, active states */
  --accent-dark:#1e293b;   /* Hover/pressed state for accent */
  --accent2:    #22d3ee;   /* Links, highlights, secondary accents (cyan) */
  --green:      #34d399;   /* Success badges */
  --amber:      #fbbf24;   /* Warnings */
  --red:        #f87171;   /* Errors */
  --text:       #e2e8f0;   /* Primary text */
  --muted:      #94a3b8;   /* Secondary text */
  --dim:        #64748b;   /* Tertiary / disabled text */
  --radius:     12px;      /* Card border radius */
}
```

**Design rules:**
- Dark background (`--bg`) with cards on `--surface`, inputs on `--surface2`
- All borders: `1px solid var(--border)` — no box shadows
- Buttons: `background: var(--accent)`, white text
- Status badges: transparent bg with matching border + text
- Links and hover accents: `var(--accent2)` (cyan)
- Mobile-first; use `max-width: 860px` centered layout

---

## Architecture & Constraints

- **Single file:** Everything in `index.html`. No separate CSS or JS files.
- **No frameworks:** Vanilla HTML, CSS, JavaScript only. No npm, no build step.
- **PWA-ready:** The `manifest.json` and `sw.js` are already in the folder —
  just register the service worker (`navigator.serviceWorker.register('sw.js')`).
- **Mobile-first:** Must look good on a phone screen. Use `max-width: 860px` centered layout.
- **No localStorage for auth/data** — just for run counters if needed.

---

### AI Calls — Gemini Only

Worker URL: `https://worker.appsforhire.app/ai`
Model param: `"gemini"`

> **Rate limit**: This is a Starter app using Robert's shared key. The worker
> enforces 10 AI calls per IP per day. Include a **demo overlay** that triggers
> on 429 responses, encouraging the user to contact AppsForHire.

Exact fetch pattern:

```javascript
const WORKER_URL = 'https://worker.appsforhire.app/ai';

async function callAI(system, userMessage) {
  const res  = await fetch(WORKER_URL, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      model:   'gemini',
      system:  system,
      message: userMessage,
    }),
  });
  const data = await res.json();
  if (res.status === 429) {
    // Show overlay — user hit demo limit
    document.getElementById('demoOverlay').classList.add('show');
    return null;
  }
  if (!res.ok) throw new Error(data.error || 'AI error');
  return data.response;
}
```

The worker returns `{ "response": "...", "calls_used": N, "remaining": N }`.
Show a soft overlay (not a hard block) when `remaining` reaches 1-2.

## Required UI Elements

1. **Header** — sticky, brand color background, shows `The Gathering Place` + `Daily Offerations`. The right side of the header must include two pill-shaped elements side by side:
   - A **`← My Apps` back link** (`<a href="/portal/" class="back-link">← My Apps</a>`) — `background: rgba(0,0,0,.2)`, `border: 1px solid rgba(255,255,255,.2)`, `border-radius: 100px`, `padding: .3rem .8rem`, `font-size: .75rem`, `font-weight: 600`, white text, no underline. Hover: `background: rgba(0,0,0,.35)`. This lets customers navigate back to their app portal.
   - A **"Secure App" badge** (`<div class="header-badge">Secure App</div>`) with `background: rgba(255,255,255,.18)`, `border: 1px solid rgba(255,255,255,.3)`.
   - Wrap both in a `<div class="header-right">` with `display: flex; align-items: center; gap: .6rem`.
2. **Input form** — clean card, labeled fields, submit button in brand color
3. **AI response area** — card that appears after the AI responds, with a copy-to-clipboard button
4. **Loading state** — spinner or animated dots while waiting for AI
5. **Error state** — friendly message if the call fails (network error, etc.)
6. **Demo overlay** — full-screen modal on 429 response, encouraging user to contact AppsForHire

---

## Code Quality

- Use semantic HTML (`<main>`, `<section>`, `<label>`, etc.)
- All form fields must have matching `<label>` elements
- Button must be disabled while loading (prevent double-submit)
- Handle empty/whitespace input — don't call the AI if nothing is typed
- CSS variables for all colors and spacing — no hardcoded hex values in rules

---

## What to Deliver

Write the complete `index.html` to:
```
/app_for_hire/builds/thegatheringplace/index.html
```

Then confirm you've written it and show me the first 30 lines so I can verify
the file was created correctly.