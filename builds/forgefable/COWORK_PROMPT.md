# AppsForHire — Build: Forge & Fable
**Client:** Radish Tricks
**Slug:** `forgefable`
**Live URL:** https://forgefable.appsforhire.app
**Tier:** Starter
**API type:** Both — Gemini + Claude (shared keys, with model picker)

---

## Your Task

Build a polished, mobile-friendly single-page web app and save it to:

```
/app_for_hire/builds/forgefable/index.html
```

The scaffold files are already there (template HTML, manifest.json, sw.js, icons).
**Replace `index.html` completely** — don't just edit the scaffold.

---

## What the App Does

## FEATURE 1: Fantasy Name Generator

- Display a grid of selectable world region "cards" (e.g. Norse, Celtic, Japanese, Arabic, 
  African Savanna, Elvish/High Fantasy, Orcish/Dark, Slavic, Aztec/Mesoamerican, Eastern 
  European). User can pick one or more regions.
- A "Generate Name" button calls the Claude API with a prompt like: 
  "Generate a fantasy character name appropriate for a [selected regions] inspired setting. 
  Return only the name and a 1-sentence lore blurb."
- Display the generated name large and styled, with the lore blurb beneath it.
- Include a "Copy Name" button and a "Regenerate" button.

---

## FEATURE 2: Building Sketch Generator

- A "Generate Building" button calls the Gemini API (gemini-2.0-flash or imagen if available) 
  to generate a fantasy building illustration — a simple architectural sketch style, black ink 
  on parchment, for D&D use.
- Each generated building gets a card with:
  - The generated image
  - An auto-generated building name and 2-sentence description (use Claude API for this)
  - A small editable textarea labeled "DM Notes"
  - The card is stored in session state (up to 10 buildings)
- A horizontal scrollable "Building Vault" at the bottom shows thumbnails of all stored 
  buildings (up to 10). Clicking a thumbnail brings that building into focus.
- A "Clear All" button resets the vault.

---

## Tech Requirements

- PWA with a manifest.json and a basic service worker for offline caching of the shell
- API keys will be injected via a simple settings modal (gear icon) where the user pastes 
  in their Claude API key and Gemini API key — store them in localStorage
- Responsive layout that works on tablet and desktop
- Navigation between the two features via a bottom tab bar or sidebar

Start by scaffolding the full file structure and the core layout/navigation, 
then implement Feature 1, then Feature 2.

---

## Brand & Design System

- **Business name:** Radish Tricks
- **App title:** Forge & Fable
- **Subtitle / description:** A D&D Swiss Army Knife.
- **Brand accent color:** `#d97706` (Amber) — use as `--accent`
- **Brand accent dark:** `#b45309` — use as `--accent-dark`

All AppsForHire apps share a **unified dark design system**. Use exactly these CSS variables:

```css
:root {
  --bg:         #0f1117;
  --surface:    #1a1d27;
  --surface2:   #222536;
  --border:     #2e3147;
  --accent:     #d97706;
  --accent-dark:#b45309;
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

### AI Calls — Both Models (with model picker)

Use Robert’s shared keys via the Worker. Include a model picker (Gemini / Claude toggle) so the user can choose.
> **Rate limit**: Starter app on Robert’s shared key. Worker enforces 50 AI calls/IP/24h.
> Include a **demo overlay** that triggers on 429, and a soft warning when `remaining <= 2`.


```javascript
const WORKER_URL = 'https://worker.appsforhire.app/ai';

async function callAI(model, system, userMessage) {
  const res  = await fetch(WORKER_URL, {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ model, system, message: userMessage }),
  });
  const data = await res.json();
  if (res.status === 429) { document.getElementById('demoOverlay').classList.add('show'); return null; }
  if (!res.ok) throw new Error(data.error || 'AI error');
  return data.response;
}
```

Pass `model: 'gemini'` or `model: 'claude'` based on the picker selection.
The worker returns `{ "response": "...", "calls_used": N, "remaining": N }`.

---

## Required UI Elements

1. **Header** — sticky, brand color background, shows `Radish Tricks` + `Forge & Fable`. Right side must have two pill elements: a **`← My Apps` back link** (`<a href="/portal/" class="back-link">← My Apps</a>`, `background:rgba(0,0,0,.2)`, `border:1px solid rgba(255,255,255,.2)`, `border-radius:100px`) and a **"Secure App" badge** (`background:rgba(255,255,255,.18)`, `border:1px solid rgba(255,255,255,.3)`). Wrap both in `<div class="header-right" style="display:flex;align-items:center;gap:.6rem">`.
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
/app_for_hire/builds/forgefable/index.html
```

Then confirm you've written it and show me the first 30 lines so I can verify.