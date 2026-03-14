# AppsForHire Worker — Deployment Guide

## Prerequisites
- Node.js 18+ installed
- A Cloudflare account (free tier works)
- Wrangler CLI (installed below)

---

## Step 1 — Install dependencies

```bash
cd worker
npm install
```

---

## Step 2 — Log in to Cloudflare

```bash
npx wrangler login
```

This opens a browser window. Log in with your Cloudflare account.

---

## Step 3 — Create the KV namespaces

The `RATE_LIMIT` namespace is already created (ID is in `wrangler.toml`).

Create the new `CLIENT_CONFIG` namespace (stores per-client API keys):

```bash
npx wrangler kv namespace create "CLIENT_CONFIG"
```

You'll get output like:
```
✅  Created namespace with ID "xyz789abc123..."
```

Open `wrangler.toml` and replace `REPLACE_WITH_CLIENT_CONFIG_KV_ID` with that ID:

```toml
[[kv_namespaces]]
binding = "CLIENT_CONFIG"
id      = "xyz789abc123..."   # ← paste here
```

---

## Step 4 — Set secrets (encrypted, never in code)

Run each of these one at a time. You'll be prompted to paste the value:

```bash
npx wrangler secret put CLAUDE_API_KEY
npx wrangler secret put GEMINI_API_KEY
npx wrangler secret put ADMIN_SECRET
npx wrangler secret put STRIPE_WEBHOOK_SECRET
npx wrangler secret put RESEND_API_KEY
npx wrangler secret put ADMIN_EMAIL
npx wrangler secret put CF_API_TOKEN
npx wrangler secret put GITHUB_TOKEN
```

**Where to get each value:**
| Secret | Source |
|---|---|
| `CLAUDE_API_KEY` | console.anthropic.com → API Keys (Robert's shared key) |
| `GEMINI_API_KEY` | aistudio.google.com → Get API key (Robert's shared key) |
| `ADMIN_SECRET` | Make one up: run `openssl rand -hex 32` in your terminal |
| `STRIPE_WEBHOOK_SECRET` | Stripe dashboard → Developers → Webhooks (after Step 6) |
| `RESEND_API_KEY` | resend.com → API Keys |
| `ADMIN_EMAIL` | Your email — cosmicwombat@gmail.com |
| `CF_API_TOKEN` | Cloudflare dashboard → My Profile → API Tokens |
| `GITHUB_TOKEN` | github.com → Settings → Developer settings → Personal access tokens |

> You can skip `GEMINI_API_KEY`, `CF_API_TOKEN`, and `GITHUB_TOKEN` for now — the worker runs fine without them.
> `ADMIN_SECRET` is important — it protects the `/admin/set-client-keys` endpoint.

---

## Step 5 — Deploy

```bash
npx wrangler deploy
```

Your worker will be live at a URL like:
`https://appsforhire-worker.<your-subdomain>.workers.dev`

---

## Step 6 — Add custom domain

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com) → **Workers & Pages**
2. Click `appsforhire-worker` → **Settings** → **Triggers**
3. Under **Custom Domains**, click **Add Custom Domain**
4. Enter: `worker.appsforhire.app`
5. Cloudflare auto-creates the DNS record

Once active, your worker is at: `https://worker.appsforhire.app`

---

## Step 7 — Set up Stripe webhook

1. Go to [Stripe Dashboard](https://dashboard.stripe.com) → **Developers** → **Webhooks**
2. Click **Add endpoint**
3. URL: `https://worker.appsforhire.app/webhook`
4. Select events:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
5. Copy the **Signing secret** (starts with `whsec_`)
6. Run: `npx wrangler secret put STRIPE_WEBHOOK_SECRET` and paste it

---

## Step 8 — Set up Resend

1. Sign up at [resend.com](https://resend.com) (free: 3,000 emails/month)
2. Go to **Domains** → **Add Domain** → `appsforhire.app`
3. Add the DNS records Resend gives you in Cloudflare
4. Go to **API Keys** → **Create API Key**
5. Run: `npx wrangler secret put RESEND_API_KEY` and paste it

---

## Step 9 — Verify everything

```bash
curl https://worker.appsforhire.app/health
```

Expected response:
```json
{
  "status": "ok",
  "service": "appsforhire-worker",
  "keys": {
    "claude": true,
    "gemini": true,
    "stripe": true,
    "resend": true,
    "cf": true,
    "github": true
  },
  "rate_limit_kv": true
}
```

Any `false` values mean that secret isn't set yet.

---

## Step 10 — Push git changes to GitHub

```bash
git push origin main
```

The demo apps (`demo/app1` and `demo/app2`) will automatically start using the worker once it's live at `worker.appsforhire.app`.

---

## Day-to-day commands

```bash
# Watch logs in real time
npx wrangler tail

# Test locally (uses real KV, real secrets)
npx wrangler dev

# Redeploy after any changes to worker.js
npx wrangler deploy
```

---

## How the rate limit works

- Key: `demo_ai:<visitor-ip>` stored in RATE_LIMIT KV
- Limit: 10 AI calls per IP per 7 days
- When limit is hit: 429 response with CTA to contact page
- Only applies to **Starter** clients and demo apps (using Robert's shared key)
- Custom / Pro clients using their own API key have **no rate limit**

---

## How per-client API key routing works

When a client app at `smithsbakery.appsforhire.app` calls `/ai`:

1. Worker reads the `Origin` header → extracts slug `smithsbakery`
2. Looks up `client:smithsbakery` in the `CLIENT_CONFIG` KV namespace
3. **If the client has their own key** → uses it, no rate limit
4. **If no config found (Starter)** → uses Robert's `CLAUDE_API_KEY`, rate limited

### Adding a new Custom/Pro client's API keys (no redeploy needed)

After receiving the client's key via OneTimeSecret link:

```bash
curl -X POST https://worker.appsforhire.app/admin/set-client-keys \
  -H "Authorization: Bearer YOUR_ADMIN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "client":     "smithsbakery",
    "tier":       "custom",
    "claude_key": "sk-ant-api03-...",
    "gemini_key": null,
    "use_gemini": false
  }'
```

To switch a client to Gemini instead of Claude:

```bash
-d '{
  "client":     "smithsbakery",
  "tier":       "custom",
  "claude_key": null,
  "gemini_key": "AIzaSy...",
  "use_gemini": true
}'
```

### Checking a client's config

```bash
curl https://worker.appsforhire.app/admin/get-client/smithsbakery \
  -H "Authorization: Bearer YOUR_ADMIN_SECRET"
```

Keys are masked in the response (first 8 chars + `...`) for safety.

### Tier summary

| Tier | API Key Used | Rate Limited? |
|---|---|---|
| Starter (default) | Robert's shared `CLAUDE_API_KEY` | Yes — 10 calls / 7 days |
| Custom / Pro | Client's own key from KV | No |
