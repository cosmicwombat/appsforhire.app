# AppsForHire — Cross-Project Context for PWA Development

## What This Project Is
AppsForHire is a boutique PWA-as-a-service platform. Each client gets a single-page PWA app hosted on GitHub Pages at `[slug].appsforhire.app`, protected by Cloudflare Access (OTP email gate), with AI features proxied through a Cloudflare Worker at `worker.appsforhire.app`.

## Architecture Summary

### Hosting & Delivery
- **Static hosting**: GitHub Pages (one private repo per client: `client-[slug]`)
- **DNS & CDN**: Cloudflare (CNAME `[slug]` → `cosmicwombat.github.io`, proxy ON)
- **Auth**: Cloudflare Access (self-hosted app per client, email-based OTP)
- **Custom domain**: `[slug].appsforhire.app`

### AI Proxy Worker (`worker.appsforhire.app`)
- **Runtime**: Cloudflare Workers
- **Config**: `worker/wrangler.toml` + `worker/worker.js`
- **Models**: Gemini 2.5 Flash (`gemini-2.5-flash` via `v1beta/models` endpoint), Claude (Anthropic API)
- **Key routing**: Starter/demo clients use Robert's shared keys; Custom/Pro clients store their own keys in `CLIENT_CONFIG` KV
- **Rate limiting**: 10 calls per IP per 7-day window via `RATE_LIMIT` KV (Starter/demo only)
- **CORS**: Allows `*.appsforhire.app`, `appsforhire.app`, and `localhost`
- **Endpoints**:
  - `POST /ai` — AI proxy (accepts `{model: "gemini"|"claude", system, message}`)
  - `POST /admin/set-client-keys` — Store client API keys (admin-only, bearer token)
  - `GET /admin/get-client/:slug` — Read client config (admin-only)
  - `GET /health` — Health check
- **KV Namespaces**:
  - `RATE_LIMIT` (ID: `bf759cd2061a4370b93f0bbbd0a5aea5`)
  - `CLIENT_CONFIG` (ID: `cf6d8d35fbec4e7db1846312f5fe5139`)

### App Structure
Each client app is a **single `index.html` file** (all HTML/CSS/JS inline) plus `manifest.json`, `sw.js`, and `icons/`. Apps are PWA-capable with service worker registration.

### Build Pipeline
1. `scripts/new_build.py` — Scaffolds a build folder in `builds/[slug]/` with a `COWORK_PROMPT.md`
2. Cowork session (or manual dev) builds the app using the prompt
3. `scripts/new_customer.py` — Creates GitHub repo, pushes files from `builds/[slug]/`, enables Pages
4. Manual: Cloudflare DNS + Access setup
5. `scripts/update_admin_data.py` — Pushes `data.json` to admin repo to update dashboard

### Design System (Established March 2026)
All AppsForHire interfaces now use a unified dark theme inspired by the tek-intel project:

```css
:root {
  --bg:       #0f1117;      /* Page background */
  --surface:  #1a1d27;      /* Cards, panels */
  --surface2: #222536;      /* Inputs, secondary surfaces */
  --border:   #2e3147;      /* All borders */
  --accent:   #6366f1;      /* Primary buttons, active states (indigo) */
  --accent2:  #22d3ee;      /* Links, highlights, hover states (cyan) */
  --green:    #34d399;      /* Success, active badges */
  --amber:    #fbbf24;      /* Warnings */
  --red:      #f87171;      /* Errors */
  --text:     #e2e8f0;      /* Primary text */
  --muted:    #94a3b8;      /* Secondary text */
  --dim:      #64748b;      /* Tertiary/disabled text */
  --radius:   12px;         /* Card border radius */
}
```

**Design principles:**
- Dark background with subtle surface elevation via borders (no box shadows)
- Indigo (`#6366f1`) for primary actions and buttons
- Cyan (`#22d3ee`) for links, hover accents, and highlights
- Badges use transparent backgrounds with matching border+text color (e.g., `rgba(52,211,153,.12)` bg + `#34d399` text for success)
- Inputs: `--surface2` background, `--border` border, `--accent` focus border
- Cards: `--surface` background, `1px solid var(--border)`, `var(--radius)` corners
- Typography: System font stack, no custom fonts
- Mobile-first responsive

### Files Modified in This Session
- `builds/thegatheringplace/index.html` — Daily Offerations app (dark theme, CSS scene backgrounds)
- `demo/daily-offerations/index.html` — Demo copy of the app
- `demo/index.html` — Added Daily Offerations card to demo portal
- `admin/index.html` — Admin dashboard (restyled to dark theme)
- `template/portal/index.html` — User portal template (restyled to dark theme + logout button)
- `scripts/customers.json` — Added The Gathering Place client record
- `worker/worker.js` — Updated Gemini model to `gemini-2.5-flash`
- `worker/wrangler.toml` — Added CLIENT_CONFIG KV binding
- `scripts/new_customer.py` — Patched to prefer `builds/[slug]/` files over templates

### Key Decisions
- **No external image dependencies**: The Daily Offerations app uses CSS gradient "scene" backgrounds (wood, amber, forest, leather, steel) instead of external image URLs to avoid hotlinking failures
- **Single-file apps**: Everything in one `index.html` for simplicity and GitHub Pages compatibility
- **Shared worker**: One Cloudflare Worker handles all client AI calls, routing by Origin header
- **Logout via Cloudflare Access**: `/cdn-cgi/access/logout` endpoint handles sign-out
- **Rate limiting is per-IP, not per-client**: All Starter/demo traffic shares the same 10-call/7-day limit per IP

### Environment
- GitHub org: `cosmicwombat`
- Domain: `appsforhire.app`
- Admin: `admin.appsforhire.app`
- Demo: `demo.appsforhire.app`
- Worker: `worker.appsforhire.app`
- Client apps: `[slug].appsforhire.app`
