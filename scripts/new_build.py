#!/usr/bin/env python3
"""
AppsForHire — New Build Setup Script
--------------------------------------
Run this FIRST when a new client app is ordered.

What it does:
  1. Asks for client info (name, slug, tier, API type, app concept)
  2. Creates builds/{slug}/ with template files as a starting point
  3. Prints a ready-to-paste Cowork prompt for Claude to build the app
  4. Prints the KV registration curl command (Custom/Pro only)

Usage:
  python3 scripts/new_build.py

After running:
  1. Copy the printed Cowork prompt
  2. Open a NEW Cowork session and paste it
  3. Claude builds the app in builds/{slug}/
  4. Review, then run scripts/new_customer.py to deploy
"""

import os
import sys
import shutil
from pathlib import Path

SCRIPTS_DIR  = Path(__file__).parent
ROOT_DIR     = SCRIPTS_DIR.parent
TEMPLATE_DIR = ROOT_DIR / "template"
BUILDS_DIR   = ROOT_DIR / "builds"
WORKER_URL   = "https://worker.appsforhire.app/ai"
BASE_DOMAIN  = "appsforhire.app"

COLORS = {
    "1": ("#4f46e5", "#3730a3", "Indigo"),
    "2": ("#0ea5e9", "#0284c7", "Sky Blue"),
    "3": ("#0d9488", "#0f766e", "Teal"),
    "4": ("#16a34a", "#15803d", "Green"),
    "5": ("#7c3aed", "#6d28d9", "Violet"),
    "6": ("#e11d48", "#be123c", "Rose"),
    "7": ("#d97706", "#b45309", "Amber"),
    "8": ("#0f172a", "#1e293b", "Slate/Dark"),
}

API_TYPES = {
    "starter-claude":  "Claude only (Robert's shared key, rate-limited)",
    "starter-gemini":  "Gemini only (Robert's shared key, rate-limited)",
    "custom-claude":   "Claude only (client's own key, no rate limit)",
    "custom-gemini":   "Gemini only (client's own key, no rate limit)",
    "custom-both":     "Both Claude + Gemini (client's own keys, can compare)",
}


def hr(char="─", width=60):
    return char * width


def print_banner():
    print("\n" + hr("═"))
    print("  AppsForHire — New Build Setup")
    print(hr("═") + "\n")


def ask(prompt, default=None):
    display = f"  {prompt}"
    if default:
        display += f" [{default}]"
    display += ": "
    val = input(display).strip()
    return val if val else default


def collect_info():
    print("── Client Info " + "─" * 46)
    name = ask("Client / business name (e.g. Smith Bakery)")
    while not name:
        print("  ✗ Name is required.")
        name = ask("Client / business name")

    slug = ask("URL slug — lowercase, no spaces (e.g. smithbakery)")
    slug = slug.lower().replace(" ", "-")
    while not slug:
        print("  ✗ Slug is required.")
        slug = ask("URL slug").lower().replace(" ", "-")

    build_dir = BUILDS_DIR / slug
    if build_dir.exists():
        print(f"\n  ⚠️  builds/{slug}/ already exists.")
        overwrite = ask("Overwrite it? (y/N)", "N").upper()
        if overwrite != "Y":
            print("  Exiting — choose a different slug or delete the existing folder first.")
            sys.exit(0)

    print("\n── Tier & AI Type " + "─" * 42)
    print("  Tiers:")
    print("    starter  — Robert's shared API keys, rate-limited (10 calls/day/IP)")
    print("    custom   — Client's own API keys, unlimited")
    print("    pro      — Client's own API keys, unlimited, advanced features\n")
    tier = ask("Tier (starter / custom / pro)", "starter").lower()
    if tier not in ("starter", "custom", "pro"):
        tier = "starter"

    print("\n  AI model options:")
    if tier == "starter":
        print("    1. Claude only  (robert's claude key — good for writing tasks)")
        print("    2. Gemini only  (robert's gemini key — slightly cheaper, good for Q&A)")
        api_choice = ask("Choose (1/2)", "1")
        api_type = "starter-claude" if api_choice == "1" else "starter-gemini"
    else:
        print("    1. Claude only  (client provides claude key)")
        print("    2. Gemini only  (client provides gemini key)")
        print("    3. Both         (client provides both — enables model comparison features)")
        api_choice = ask("Choose (1/2/3)", "1")
        api_type = {"1": "custom-claude", "2": "custom-gemini", "3": "custom-both"}.get(api_choice, "custom-claude")

    print("\n── App Details " + "─" * 46)
    app_title = ask("App name / title (e.g. Daily Menu Writer)")
    while not app_title:
        app_title = ask("App name / title")

    app_desc = ask("One-line description (shown as subtitle in header)")
    while not app_desc:
        app_desc = ask("One-line description")

    print("\n  What does the app DO? Describe the workflow in plain English.")
    print("  This goes directly into the Cowork prompt.")
    print("  Example: 'User pastes a customer complaint, AI writes a calm professional reply.'")
    app_concept = ask("App concept")
    while not app_concept:
        app_concept = ask("App concept")

    print("\n── Brand Color " + "─" * 46)
    for k, (hex_val, _, label) in COLORS.items():
        print(f"    {k}. {label:12}  {hex_val}")
    print("    9. Custom hex")
    color_choice = ask("Choose (1-9)", "1")
    if color_choice in COLORS:
        theme_color, theme_dark, color_name = COLORS[color_choice]
    else:
        theme_color = ask("Primary hex (e.g. #4f46e5)", "#4f46e5")
        theme_dark  = ask("Darker shade (e.g. #3730a3)", "#3730a3")
        color_name  = "Custom"

    return {
        "name":        name,
        "slug":        slug,
        "tier":        tier,
        "api_type":    api_type,
        "app_title":   app_title,
        "app_desc":    app_desc,
        "app_concept": app_concept,
        "theme_color": theme_color,
        "theme_dark":  theme_dark,
        "color_name":  color_name,
        "subdomain":   f"{slug}.{BASE_DOMAIN}",
        "build_dir":   build_dir,
    }


def scaffold_build(info):
    """Copy template files into builds/{slug}/."""
    build_dir = info["build_dir"]
    build_dir.mkdir(parents=True, exist_ok=True)

    # Copy template files (not the portal subdirectory)
    for item in TEMPLATE_DIR.iterdir():
        if item.name == "portal":
            continue
        dest = build_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    print(f"\n  ✅  Scaffolded: builds/{info['slug']}/")
    print(f"      Files: index.html, manifest.json, sw.js, icons/")


def build_ai_instructions(info):
    """Return the AI call section of the Cowork prompt based on api_type."""
    api_type   = info["api_type"]
    worker_url = WORKER_URL

    shared_fetch = f"""
```javascript
const WORKER_URL = '{worker_url}';

async function callAI(system, userMessage) {{
  const res  = await fetch(WORKER_URL, {{
    method:  'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body:    JSON.stringify({{
      model:   '{("gemini" if "gemini" in api_type else "claude")}',
      system:  system,
      message: userMessage,
    }}),
  }});
  const data = await res.json();
  if (res.status === 429) {{
    // Show overlay — user hit demo limit
    document.getElementById('demoOverlay').classList.add('show');
    return null;
  }}
  if (!res.ok) throw new Error(data.error || 'AI error');
  return data.response;
}}
```"""

    both_fetch = f"""
```javascript
const WORKER_URL = '{worker_url}';

// Call one AI model
async function callAI(model, system, userMessage) {{
  const res  = await fetch(WORKER_URL, {{
    method:  'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body:    JSON.stringify({{ model, system, message: userMessage }}),
  }});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'AI error');
  return data.response;
}}

// Call both at once (for comparison features)
async function callBoth(system, userMessage) {{
  const [claude, gemini] = await Promise.all([
    callAI('claude', system, userMessage),
    callAI('gemini', system, userMessage),
  ]);
  return {{ claude, gemini }};
}}
```"""

    if api_type == "custom-both":
        ai_block = f"""
### AI Calls — Both Models Available

The worker will use the client's own Claude AND Gemini keys (no rate limit).
Use `Promise.all()` for parallel calls. Here is the exact fetch pattern:
{both_fetch}

You can show both responses side-by-side or let the user choose a model.
"""
    else:
        model_name = "Gemini" if "gemini" in api_type else "Claude"
        limit_note = "" if api_type.startswith("custom") else """
> **Rate limit**: This is a Starter app using Robert's shared key. The worker
> enforces 10 AI calls per IP per day. Include a **demo overlay** that triggers
> on 429 responses, encouraging the user to contact AppsForHire.
"""
        ai_block = f"""
### AI Calls — {model_name} Only

Worker URL: `{worker_url}`
Model param: `"{("gemini" if "gemini" in api_type else "claude")}"`
{limit_note}
Exact fetch pattern:
{shared_fetch}

The worker returns `{{ "response": "...", "calls_used": N, "remaining": N }}`.
Show a soft overlay (not a hard block) when `remaining` reaches 1-2.
"""

    return ai_block


def build_cowork_prompt(info):
    is_starter = info["tier"] == "starter"
    ai_block   = build_ai_instructions(info)

    prompt = f"""# AppsForHire — Build: {info['app_title']}
**Client:** {info['name']}
**Slug:** `{info['slug']}`
**Live URL:** https://{info['subdomain']}
**Tier:** {info['tier'].capitalize()}
**API type:** {API_TYPES[info['api_type']]}

---

## Your Task

Build a polished, mobile-friendly single-page web app and save it to:

```
/app_for_hire/builds/{info['slug']}/index.html
```

The scaffold files are already there (template HTML, manifest.json, sw.js, icons).
**Replace `index.html` completely** — don't just edit the scaffold.

---

## What the App Does

{info['app_concept']}

---

## Brand

- **Business name:** {info['name']}
- **App title:** {info['app_title']}
- **Subtitle / description:** {info['app_desc']}
- **Primary color:** `{info['theme_color']}` ({info['color_name']})
- **Darker shade:** `{info['theme_dark']}`

Use these as CSS custom properties `--primary` and `--primary-dark`.

---

## Architecture & Constraints

- **Single file:** Everything in `index.html`. No separate CSS or JS files.
- **No frameworks:** Vanilla HTML, CSS, JavaScript only. No npm, no build step.
- **PWA-ready:** The `manifest.json` and `sw.js` are already in the folder —
  just register the service worker (`navigator.serviceWorker.register('sw.js')`).
- **Mobile-first:** Must look good on a phone screen. Use `max-width: 860px` centered layout.
- **No localStorage for auth/data** — just for run counters if needed.

---
{ai_block}
## Required UI Elements

1. **Header** — sticky, brand color background, shows `{info['name']}` + `{info['app_title']}`
2. **Input form** — clean card, labeled fields, submit button in brand color
3. **AI response area** — card that appears after the AI responds, with a copy-to-clipboard button
4. **Loading state** — spinner or animated dots while waiting for AI
5. **Error state** — friendly message if the call fails (network error, etc.)
{"6. **Demo overlay** — full-screen modal on 429 response, encouraging user to contact AppsForHire" if is_starter else ""}

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
/app_for_hire/builds/{info['slug']}/index.html
```

Then confirm you've written it and show me the first 30 lines so I can verify
the file was created correctly.
"""
    return prompt.strip()


def build_kv_commands(info):
    if info["tier"] == "starter":
        return None

    api_type = info["api_type"]
    slug     = info["slug"]

    if api_type == "custom-claude":
        data = f'{{"client":"{slug}","tier":"{info["tier"]}","claude_key":"PASTE_CLAUDE_KEY_HERE","use_gemini":false}}'
    elif api_type == "custom-gemini":
        data = f'{{"client":"{slug}","tier":"{info["tier"]}","gemini_key":"PASTE_GEMINI_KEY_HERE","use_gemini":true}}'
    else:  # both
        data = f'{{"client":"{slug}","tier":"{info["tier"]}","claude_key":"PASTE_CLAUDE_KEY_HERE","gemini_key":"PASTE_GEMINI_KEY_HERE","use_gemini":false}}'

    return f"""curl -X POST https://worker.appsforhire.app/admin/set-client-keys \\
  -H "Authorization: Bearer YOUR_ADMIN_SECRET" \\
  -H "Content-Type: application/json" \\
  -d '{data}'"""


def main():
    print_banner()
    info = collect_info()

    print("\n" + hr())
    scaffold_build(info)

    cowork_prompt = build_cowork_prompt(info)
    kv_cmd        = build_kv_commands(info)

    # Save the prompt to a file too
    prompt_file = info["build_dir"] / "COWORK_PROMPT.md"
    prompt_file.write_text(cowork_prompt)
    print(f"  ✅  Cowork prompt saved: builds/{info['slug']}/COWORK_PROMPT.md")

    print("\n" + hr("═"))
    print("  NEXT STEPS")
    print(hr("═"))
    print(f"""
  1. ┌─ Open a NEW Cowork session in the Claude desktop app
     └─ Paste the prompt below (or open builds/{info['slug']}/COWORK_PROMPT.md)

  2. ┌─ Claude will build index.html in builds/{info['slug']}/
     └─ Review it, request tweaks in the same session

  3. ┌─ When happy with the build, run from your terminal:
     └─ python3 scripts/new_customer.py

  4. ┌─ Follow the DNS steps printed by new_customer.py
     └─ Add CNAME in Cloudflare Dashboard""")

    if kv_cmd:
        print(f"""
  5. ┌─ Register the client's API keys in the worker (after you receive them):
     └─ {kv_cmd}

     Verify with:
       curl https://worker.appsforhire.app/admin/get-client/{info['slug']} \\
         -H "Authorization: Bearer YOUR_ADMIN_SECRET"
""")
    else:
        print(f"""
  (Starter tier — no KV registration needed. Worker uses Robert's shared keys.)
""")

    print(hr("═"))
    print("  COWORK PROMPT — copy everything between the dashes below")
    print(hr("─"))
    print()
    print(cowork_prompt)
    print()
    print(hr("─"))
    print("  End of prompt. Paste into a new Cowork session.")
    print(hr("═") + "\n")


if __name__ == "__main__":
    main()
