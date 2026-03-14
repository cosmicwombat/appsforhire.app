/**
 * ============================================================
 *  AppsForHire — Cloudflare Worker
 * ============================================================
 * Secure backend for the AppsForHire platform.
 *
 * Routes:
 *   GET  /health                  → Status check (all keys configured?)
 *   POST /ai                      → AI proxy — routes to correct key per client tier
 *   POST /webhook                 → Stripe event handler
 *   POST /admin/set-client-keys   → Store per-client API keys in KV (admin only)
 *   GET  /admin/get-client/:slug  → Read a client's config from KV (admin only)
 *
 * Tier behavior:
 *   Starter  → uses Robert's shared CLAUDE_API_KEY, 10-call / 7-day rate limit
 *   Custom   → uses client's own claude_key OR gemini_key stored in CLIENT_CONFIG KV
 *   Pro      → same as Custom, no rate limit
 *
 * How to add a new Custom/Pro client's keys (no redeploy needed):
 *   curl -X POST https://worker.appsforhire.app/admin/set-client-keys \
 *     -H "Authorization: Bearer <ADMIN_SECRET>" \
 *     -H "Content-Type: application/json" \
 *     -d '{"client":"smithsbakery","tier":"custom","claude_key":"sk-ant-..."}'
 *
 * Secrets (set via: npx wrangler secret put <NAME>):
 *   CLAUDE_API_KEY       — Robert's Anthropic key (Starter fallback)
 *   GEMINI_API_KEY       — Robert's Google key (Starter Gemini fallback)
 *   ADMIN_SECRET         — Token to protect /admin/* endpoints
 *   STRIPE_WEBHOOK_SECRET
 *   RESEND_API_KEY
 *   ADMIN_EMAIL
 *   CF_API_TOKEN
 *   GITHUB_TOKEN
 *
 * KV Namespaces:
 *   RATE_LIMIT     — tracks per-IP call counts for Starter/demo traffic
 *   CLIENT_CONFIG  — stores per-client config JSON (tier + API keys)
 * ============================================================
 */

// ── AI model constants ────────────────────────────────────────────────────────
const CLAUDE_MODEL  = "claude-haiku-4-5-20251001"; // fast + cheap
const GEMINI_MODEL  = "gemini-2.5-flash";
const DEMO_AI_LIMIT = 100;                         // calls per IP per window (lower in production)
const DEMO_AI_TTL   = 7 * 24 * 60 * 60;           // 7 days in seconds

// ── CORS ──────────────────────────────────────────────────────────────────────
// Allows any *.appsforhire.app subdomain automatically — new clients just work.
// Also allows null/empty origin so local file:// testing works without CORS errors.
function isAllowedOrigin(origin) {
  if (!origin || origin === "null") return true; // local file:// or no-origin caller
  if (/^https:\/\/[a-z0-9-]+\.appsforhire\.app$/.test(origin)) return true;
  if (origin === "https://appsforhire.app") return true;
  if (/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin)) return true;
  return false;
}

function corsHeaders(origin) {
  const allowed = isAllowedOrigin(origin) ? origin : "";
  return {
    "Access-Control-Allow-Origin":  allowed,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age":       "86400",
  };
}

function jsonResponse(data, status = 200, origin = "") {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(origin) },
  });
}

// ── Per-client key routing ────────────────────────────────────────────────────

/**
 * Extract client slug from the Origin header.
 * "https://smithsbakery.appsforhire.app" → "smithsbakery"
 * Returns null for demo, admin, apex, and localhost origins.
 */
function getClientSlug(request) {
  const origin = request.headers.get("Origin") || "";
  const match  = origin.match(/^https:\/\/([a-z0-9-]+)\.appsforhire\.app$/i);
  if (!match) return null;
  const sub = match[1].toLowerCase();
  // These subdomains are platform-owned, not client apps
  if (["demo", "admin", "www", "worker"].includes(sub)) return null;
  return sub;
}

/**
 * Fetch a client's config from the CLIENT_CONFIG KV namespace.
 * Key pattern: "client:smithsbakery"
 * Value: JSON  { tier, claude_key, gemini_key, use_gemini, updated }
 *
 * Returns null if no config exists (caller treats as Starter/demo).
 */
async function getClientConfig(kv, slug) {
  if (!kv || !slug) return null;
  try {
    const raw = await kv.get(`client:${slug}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

// ── Rate limiting via KV ──────────────────────────────────────────────────────
// Only applied when using Robert's shared keys (Starter / demo traffic).
async function checkRateLimit(kv, ip) {
  if (!kv) return { allowed: true, count: 0, remaining: DEMO_AI_LIMIT };

  const key     = `demo_ai:${ip}`;
  const current = parseInt(await kv.get(key) || "0", 10);

  if (current >= DEMO_AI_LIMIT) {
    return { allowed: false, count: current, remaining: 0 };
  }

  await kv.put(key, String(current + 1), { expirationTtl: DEMO_AI_TTL });
  return { allowed: true, count: current + 1, remaining: DEMO_AI_LIMIT - (current + 1) };
}

// ── Claude API ────────────────────────────────────────────────────────────────
async function callClaude(apiKey, systemPrompt, userMessage) {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key":         apiKey,
      "anthropic-version": "2023-06-01",
      "content-type":      "application/json",
    },
    body: JSON.stringify({
      model:      CLAUDE_MODEL,
      max_tokens: 1024,
      system:     systemPrompt || "You are a helpful assistant for a small business.",
      messages:   [{ role: "user", content: userMessage }],
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Claude API ${res.status}: ${err.slice(0, 200)}`);
  }

  const data = await res.json();
  return data.content[0].text;
}

// ── Gemini API ────────────────────────────────────────────────────────────────
async function callGemini(apiKey, systemPrompt, userMessage) {
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${apiKey}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        system_instruction: systemPrompt
          ? { parts: [{ text: systemPrompt }] }
          : undefined,
        contents:         [{ role: "user", parts: [{ text: userMessage }] }],
        generationConfig: { maxOutputTokens: 1024 },
      }),
    }
  );

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Gemini API ${res.status}: ${err.slice(0, 200)}`);
  }

  const data = await res.json();
  return data.candidates[0].content.parts[0].text;
}

// ── /ai handler ───────────────────────────────────────────────────────────────
async function handleAI(request, env, origin) {
  // ── 1. Who is calling? ───────────────────────────────────────────────────
  const slug         = getClientSlug(request);
  const clientConfig = slug ? await getClientConfig(env.CLIENT_CONFIG, slug) : null;

  // ── 2. Pick the right key ─────────────────────────────────────────────────
  //   Custom/Pro clients store their own keys in KV.
  //   Starter clients (and demo site) fall back to Robert's shared keys.
  const clientClaudeKey  = clientConfig?.claude_key  || null;
  const clientGeminiKey  = clientConfig?.gemini_key  || null;
  const isOwnKey         = !!(clientClaudeKey || clientGeminiKey);

  // ── 3. Rate limit ONLY for shared-key (Starter / demo) calls ─────────────
  let limit = { allowed: true, count: 0, remaining: DEMO_AI_LIMIT };
  if (!isOwnKey) {
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    limit = await checkRateLimit(env.RATE_LIMIT, ip);
    if (!limit.allowed) {
      return jsonResponse({
        error:     "demo_limit_reached",
        message:   "You've hit the 10-call demo limit. Ready for an app of your own?",
        cta_url:   "https://appsforhire.app/#contact",
        cta_label: "Request Your Build →",
      }, 429, origin);
    }
  }

  // ── 4. Parse request body ─────────────────────────────────────────────────
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "Invalid JSON body" }, 400, origin);
  }

  const { message, system, model = "claude" } = body;
  if (!message) return jsonResponse({ error: "'message' is required" }, 400, origin);

  // ── 5. Call the AI ────────────────────────────────────────────────────────
  try {
    let response;

    const useGemini = (model === "gemini") || (clientConfig?.use_gemini === true);
    const geminiKey = clientGeminiKey || env.GEMINI_API_KEY;
    const claudeKey = clientClaudeKey || env.CLAUDE_API_KEY;

    if (useGemini && geminiKey) {
      response = await callGemini(geminiKey, system || "", message);
    } else if (claudeKey) {
      response = await callClaude(claudeKey, system || "", message);
    } else {
      return jsonResponse({ error: "No AI key configured on server" }, 500, origin);
    }

    return jsonResponse({
      response,
      // Only surface rate-limit counters for shared-key calls
      ...(isOwnKey ? {} : {
        calls_used:      limit.count,
        calls_remaining: limit.remaining,
      }),
    }, 200, origin);

  } catch (e) {
    return jsonResponse({ error: "AI call failed", detail: e.message }, 500, origin);
  }
}

// ── /admin/set-client-keys ────────────────────────────────────────────────────
// Stores or updates a client's config in CLIENT_CONFIG KV.
// Protected by ADMIN_SECRET bearer token.
//
// Body: {
//   client:     "smithsbakery",       ← required (the subdomain slug)
//   tier:       "custom",             ← "starter" | "custom" | "pro"
//   claude_key: "sk-ant-...",         ← null to remove / use shared key
//   gemini_key: "AIza...",            ← null if not using Gemini
//   use_gemini: false                 ← true to default this client to Gemini
// }
async function handleSetClientKeys(request, env, origin) {
  // Auth
  const auth = request.headers.get("Authorization") || "";
  if (!env.ADMIN_SECRET || auth !== `Bearer ${env.ADMIN_SECRET}`) {
    return jsonResponse({ error: "Unauthorized" }, 401, origin);
  }

  let body;
  try { body = await request.json(); }
  catch { return jsonResponse({ error: "Invalid JSON" }, 400, origin); }

  const { client, tier, claude_key, gemini_key, use_gemini } = body;
  if (!client) return jsonResponse({ error: "'client' slug is required" }, 400, origin);
  if (!env.CLIENT_CONFIG) return jsonResponse({ error: "CLIENT_CONFIG KV not bound" }, 500, origin);

  const config = {
    tier:       tier       || "custom",
    claude_key: claude_key || null,
    gemini_key: gemini_key || null,
    use_gemini: !!use_gemini,
    updated:    new Date().toISOString(),
  };

  await env.CLIENT_CONFIG.put(`client:${client}`, JSON.stringify(config));

  console.log(`[admin] set-client-keys: ${client} → tier=${config.tier}, claude=${!!config.claude_key}, gemini=${!!config.gemini_key}`);

  return jsonResponse({ ok: true, client, tier: config.tier }, 200, origin);
}

// ── /admin/get-client/:slug ───────────────────────────────────────────────────
// Returns a client's config. Keys are masked for safety (first 8 + "...").
async function handleGetClientConfig(slug, env, origin) {
  const auth = (arguments[3] || ""); // passed as extra arg from router
  // auth check handled in router, re-check here for safety
  if (!env.ADMIN_SECRET) {
    return jsonResponse({ error: "ADMIN_SECRET not configured" }, 500, origin);
  }

  if (!env.CLIENT_CONFIG) return jsonResponse({ error: "CLIENT_CONFIG KV not bound" }, 500, origin);

  const config = await getClientConfig(env.CLIENT_CONFIG, slug);
  if (!config) return jsonResponse({ error: "Client not found", slug }, 404, origin);

  // Mask key values — never return raw keys via the API
  const masked = {
    ...config,
    claude_key: config.claude_key ? config.claude_key.slice(0, 8) + "..." : null,
    gemini_key: config.gemini_key ? config.gemini_key.slice(0, 8) + "..." : null,
  };

  return jsonResponse({ ok: true, slug, config: masked }, 200, origin);
}

// ── Stripe signature verification ─────────────────────────────────────────────
async function verifyStripeSignature(payload, sigHeader, secret) {
  try {
    const parts = Object.fromEntries(
      sigHeader.split(",").map(p => p.split("="))
    );
    const { t: timestamp, v1: signature } = parts;
    if (!timestamp || !signature) return false;

    const encoder = new TextEncoder();
    const key     = await crypto.subtle.importKey(
      "raw", encoder.encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false, ["sign"]
    );
    const signed   = await crypto.subtle.sign("HMAC", key, encoder.encode(`${timestamp}.${payload}`));
    const expected = Array.from(new Uint8Array(signed))
      .map(b => b.toString(16).padStart(2, "0")).join("");

    return expected === signature;
  } catch {
    return false;
  }
}

// ── Stripe event handlers ─────────────────────────────────────────────────────

async function handleBuildFeePaid(session, env) {
  const email   = session.customer_details?.email || "unknown";
  const name    = session.customer_details?.name  || "Someone";
  const amount  = ((session.amount_total || 0) / 100).toFixed(2);

  const discounts = session.total_details?.breakdown?.discounts || [];
  const usedPromo = discounts.some(d =>
    d.discount?.promotion_code?.code === "FIRSTAPP2026"
  );
  const promoNote = usedPromo ? "\n⚠️  FIRSTAPP2026 promo used — one slot claimed." : "";

  await sendEmail(env, {
    to:      env.ADMIN_EMAIL,
    subject: `💰 Build fee paid — ${name} ($${amount})${usedPromo ? " [PROMO]" : ""}`,
    text:    `${name} (${email}) just paid $${amount} for a build.${promoNote}\n\nStripe session: ${session.id}\n\nTime to kick off the build!`,
  });
}

async function handleSubscriptionCreated(sub, env) {
  const email = sub.customer_email || "unknown";
  const plan  = sub.items?.data?.[0]?.price?.nickname || "hosting";

  await sendEmail(env, {
    to:      env.ADMIN_EMAIL,
    subject: `📋 New hosting subscription — ${email}`,
    text:    `${email} started a ${plan} hosting subscription.\n\nSubscription ID: ${sub.id}\n\nRun update_admin_data.py to refresh the dashboard.`,
  });
}

async function handleSubscriptionCancelled(sub, env) {
  const email = sub.customer_email || "";

  await sendEmail(env, {
    to:      env.ADMIN_EMAIL,
    subject: `⚠️  Subscription cancelled — ${email}`,
    text:    `${email} cancelled their hosting subscription.\n\nSubscription ID: ${sub.id}\n\nAction needed:\n1. Remove their Cloudflare Access policy\n2. Run update_admin_data.py`,
  });

  if (email) {
    await sendEmail(env, {
      to:      email,
      subject: "Your AppsForHire app is going offline",
      text:    `Hi,\n\nYour AppsForHire hosting subscription has been cancelled and your app will go offline shortly.\n\nWant to keep it? You can resubscribe at appsforhire.app, or buy out the source code and host it yourself.\n\nThanks for being a customer.\n\n— AppsForHire`,
    });
  }
}

async function handlePaymentFailed(invoice, env) {
  const email = invoice.customer_email || "";

  if (email) {
    await sendEmail(env, {
      to:      email,
      subject: "Action needed — AppsForHire payment failed",
      text:    `Hi,\n\nWe couldn't process your latest hosting payment. Your app stays online while you sort it out — please update your payment method:\n\nhttps://billing.stripe.com\n\nQuestions? Just reply to this email.\n\n— AppsForHire`,
    });
  }

  await sendEmail(env, {
    to:      env.ADMIN_EMAIL,
    subject: `💳 Payment failed — ${email}`,
    text:    `Payment failed for ${email}.\nInvoice: ${invoice.id}\nAttempt: ${invoice.attempt_count}`,
  });
}

// ── /webhook handler ──────────────────────────────────────────────────────────
async function handleWebhook(request, env, origin) {
  const sig = request.headers.get("stripe-signature");
  if (!sig || !env.STRIPE_WEBHOOK_SECRET) {
    return jsonResponse({ error: "Missing signature or secret" }, 400, origin);
  }

  const rawBody = await request.text();
  const valid   = await verifyStripeSignature(rawBody, sig, env.STRIPE_WEBHOOK_SECRET);
  if (!valid) {
    return jsonResponse({ error: "Signature verification failed" }, 401, origin);
  }

  const event = JSON.parse(rawBody);
  console.log(`Stripe event: ${event.type}`);

  try {
    switch (event.type) {
      case "checkout.session.completed":
        await handleBuildFeePaid(event.data.object, env); break;
      case "customer.subscription.created":
        await handleSubscriptionCreated(event.data.object, env); break;
      case "customer.subscription.deleted":
        await handleSubscriptionCancelled(event.data.object, env); break;
      case "invoice.payment_failed":
        await handlePaymentFailed(event.data.object, env); break;
      default:
        console.log(`Unhandled event type: ${event.type}`);
    }
  } catch (e) {
    console.error(`Handler error for ${event.type}: ${e.message}`);
  }

  return jsonResponse({ received: true }, 200, origin);
}

// ── Email via Resend ──────────────────────────────────────────────────────────
async function sendEmail(env, { to, subject, text }) {
  if (!env.RESEND_API_KEY) {
    console.log(`[email] No RESEND_API_KEY — skipping: ${subject}`);
    return;
  }

  const res = await fetch("https://api.resend.com/emails", {
    method:  "POST",
    headers: {
      "Authorization": `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type":  "application/json",
    },
    body: JSON.stringify({
      from:    "AppsForHire <hello@appsforhire.app>",
      to:      [to],
      subject,
      text,
    }),
  });

  if (!res.ok) {
    console.error(`[email] Resend error ${res.status}: ${await res.text()}`);
  }
}

// ── /admin/cf-proxy ───────────────────────────────────────────────────────────
// Proxies Cloudflare API calls from the admin portal.
// Auth is the same ADMIN_SECRET bearer token used by all /admin/* routes.
// Secrets used: CF_API_TOKEN, CF_ZONE_ID, CF_ACCOUNT_ID
//
// Body: { op: "dns-create" | "access-app-create" | "access-policy-create" | "cache-purge", ...params }
async function handleCFProxy(request, env, origin) {
  if (!env.CF_API_TOKEN) {
    return jsonResponse({ error: "CF_API_TOKEN not configured in Worker secrets" }, 500, origin);
  }
  if (!env.CF_ZONE_ID || !env.CF_ACCOUNT_ID) {
    return jsonResponse({ error: "CF_ZONE_ID / CF_ACCOUNT_ID not configured in Worker secrets" }, 500, origin);
  }

  let body;
  try { body = await request.json(); }
  catch { return jsonResponse({ error: "Invalid JSON body" }, 400, origin); }

  const { op } = body;
  const CF = "https://api.cloudflare.com/client/v4";
  const headers = {
    "Authorization": `Bearer ${env.CF_API_TOKEN}`,
    "Content-Type":  "application/json",
  };

  try {
    let cfUrl, cfBody;

    if (op === "dns-create") {
      // Create a proxied CNAME for a new client subdomain
      const { subdomain } = body;
      if (!subdomain) return jsonResponse({ error: "'subdomain' required" }, 400, origin);
      // Extract just the subdomain name (e.g. "theghostinterpreter" from "theghostinterpreter.appsforhire.app")
      const name = subdomain.replace(".appsforhire.app", "");
      cfUrl  = `${CF}/zones/${env.CF_ZONE_ID}/dns_records`;
      cfBody = JSON.stringify({
        type:    "CNAME",
        name,
        content: "cosmicwombat.github.io",
        proxied: true,
        ttl:     1,
      });

    } else if (op === "access-app-create") {
      // Create a Cloudflare Access self-hosted application
      const { subdomain } = body;
      if (!subdomain) return jsonResponse({ error: "'subdomain' required" }, 400, origin);
      cfUrl  = `${CF}/accounts/${env.CF_ACCOUNT_ID}/access/apps`;
      cfBody = JSON.stringify({
        name:              subdomain,
        domain:            subdomain,
        type:              "self_hosted",
        session_duration:  "24h",
        allowed_idps:      [],
        auto_redirect_to_identity: false,
      });

    } else if (op === "access-policy-create") {
      // Create an email OTP policy on an existing Access app
      const { appId, email } = body;
      if (!appId || !email) return jsonResponse({ error: "'appId' and 'email' required" }, 400, origin);
      cfUrl  = `${CF}/accounts/${env.CF_ACCOUNT_ID}/access/apps/${appId}/policies`;
      cfBody = JSON.stringify({
        name:       "Client email OTP",
        decision:   "allow",
        include:    [{ email: { email } }],
        precedence: 1,
      });

    } else if (op === "cache-purge") {
      // Purge everything for a subdomain's zone
      const { subdomain } = body;
      if (!subdomain) return jsonResponse({ error: "'subdomain' required" }, 400, origin);
      cfUrl  = `${CF}/zones/${env.CF_ZONE_ID}/purge_cache`;
      cfBody = JSON.stringify({ prefixes: [`https://${subdomain}/`] });

    } else {
      return jsonResponse({ error: `Unknown op: ${op}` }, 400, origin);
    }

    const cfRes  = await fetch(cfUrl, { method: "POST", headers, body: cfBody });
    const cfData = await cfRes.json();

    if (!cfRes.ok || !cfData.success) {
      const msg = cfData.errors?.[0]?.message || JSON.stringify(cfData.errors);
      return jsonResponse({ error: `CF API error: ${msg}`, details: cfData }, cfRes.status, origin);
    }

    return jsonResponse({ ok: true, result: cfData.result }, 200, origin);

  } catch (e) {
    return jsonResponse({ error: "CF proxy error", detail: e.message }, 500, origin);
  }
}

// ── /health handler ───────────────────────────────────────────────────────────
function handleHealth(env, origin) {
  return jsonResponse({
    status:  "ok",
    service: "appsforhire-worker",
    keys: {
      claude:        !!env.CLAUDE_API_KEY,
      gemini:        !!env.GEMINI_API_KEY,
      admin_secret:  !!env.ADMIN_SECRET,
      stripe:        !!env.STRIPE_WEBHOOK_SECRET,
      resend:        !!env.RESEND_API_KEY,
      cf_token:      !!env.CF_API_TOKEN,
      cf_zone:       !!env.CF_ZONE_ID,
      cf_account:    !!env.CF_ACCOUNT_ID,
      github:        !!env.GITHUB_TOKEN,
    },
    kv: {
      rate_limit:    !!env.RATE_LIMIT,
      client_config: !!env.CLIENT_CONFIG,
    },
  }, 200, origin);
}

// ── Main entry ────────────────────────────────────────────────────────────────
export default {
  async fetch(request, env, ctx) {
    const url    = new URL(request.url);
    const path   = url.pathname;
    const origin = request.headers.get("Origin") || "";

    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }

    // Origin check — allow any *.appsforhire.app subdomain or localhost
    // Webhook from Stripe has no Origin header — that's fine, signature protects it
    if (origin && !isAllowedOrigin(origin) && path !== "/webhook") {
      return jsonResponse({ error: "Origin not allowed" }, 403, origin);
    }

    // Admin endpoints — require ADMIN_SECRET bearer token
    if (path.startsWith("/admin/")) {
      const auth = request.headers.get("Authorization") || "";
      if (!env.ADMIN_SECRET || auth !== `Bearer ${env.ADMIN_SECRET}`) {
        return jsonResponse({ error: "Unauthorized" }, 401, origin);
      }
    }

    try {
      // ── Public routes ──────────────────────────────────────────────────
      if (request.method === "GET"  && path === "/health")  return handleHealth(env, origin);
      if (request.method === "POST" && path === "/ai")      return handleAI(request, env, origin);
      if (request.method === "POST" && path === "/webhook") return handleWebhook(request, env, origin);

      // ── Admin routes ───────────────────────────────────────────────────
      if (request.method === "POST" && path === "/admin/set-client-keys")
        return handleSetClientKeys(request, env, origin);

      if (request.method === "GET" && path.startsWith("/admin/get-client/")) {
        const slug = path.replace("/admin/get-client/", "").replace(/\//g, "");
        return handleGetClientConfig(slug, env, origin);
      }

      if (request.method === "POST" && path === "/admin/cf-proxy")
        return handleCFProxy(request, env, origin);

      return jsonResponse({ error: "Not found" }, 404, origin);

    } catch (e) {
      console.error(`Unhandled error: ${e.message}`);
      return jsonResponse({ error: "Internal server error" }, 500, origin);
    }
  },
};
