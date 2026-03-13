/**
 * ============================================================
 *  AppsForHire — Cloudflare Worker
 * ============================================================
 * Secure backend for the AppsForHire platform.
 *
 * Routes:
 *   GET  /health    → Status check (all keys configured?)
 *   POST /ai        → AI proxy for demo apps (Claude or Gemini)
 *                     Rate-limited: 10 AI calls per IP per 7 days
 *   POST /webhook   → Stripe event handler
 *
 * Secrets (set via: npx wrangler secret put <NAME>):
 *   CLAUDE_API_KEY, GEMINI_API_KEY,
 *   STRIPE_WEBHOOK_SECRET, RESEND_API_KEY,
 *   ADMIN_EMAIL, CF_API_TOKEN, GITHUB_TOKEN
 * ============================================================
 */

// ── Origins allowed to call this worker ──────────────────────────────────────
const ALLOWED_ORIGINS = new Set([
  "https://demo.appsforhire.app",
  "https://appsforhire.app",
  "https://admin.appsforhire.app",
  "http://localhost:8080",
  "http://localhost:3000",
  "http://127.0.0.1:8080",
]);

// ── AI config ─────────────────────────────────────────────────────────────────
const CLAUDE_MODEL   = "claude-haiku-4-5-20251001"; // fast + cheap, great for demos
const GEMINI_MODEL   = "gemini-1.5-flash";
const DEMO_AI_LIMIT  = 10;   // AI calls per IP per 7-day window
const DEMO_AI_TTL    = 7 * 24 * 60 * 60; // 7 days in seconds

// ── CORS helpers ──────────────────────────────────────────────────────────────
function corsHeaders(origin) {
  const allowed = ALLOWED_ORIGINS.has(origin) ? origin : "";
  return {
    "Access-Control-Allow-Origin":  allowed,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age":       "86400",
  };
}

function jsonResponse(data, status = 200, origin = "") {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(origin) },
  });
}

// ── Rate limiting via KV ──────────────────────────────────────────────────────
// Key: demo_ai:<ip>  Value: call count  TTL: 7 days (matches demo window)
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
  const fullMessage = systemPrompt
    ? `${systemPrompt}\n\n${userMessage}`
    : userMessage;

  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${apiKey}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents:         [{ parts: [{ text: fullMessage }] }],
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
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";

  // Rate limit check
  const limit = await checkRateLimit(env.RATE_LIMIT, ip);
  if (!limit.allowed) {
    return jsonResponse({
      error:     "demo_limit_reached",
      message:   "You've hit the 10-call demo limit. Ready for an app of your own?",
      cta_url:   "https://appsforhire.app/#contact",
      cta_label: "Request Your Build →",
    }, 429, origin);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "Invalid JSON body" }, 400, origin);
  }

  const { message, system, model = "claude" } = body;
  if (!message) return jsonResponse({ error: "'message' is required" }, 400, origin);

  try {
    let response;
    if (model === "gemini" && env.GEMINI_API_KEY) {
      response = await callGemini(env.GEMINI_API_KEY, system || "", message);
    } else if (env.CLAUDE_API_KEY) {
      response = await callClaude(env.CLAUDE_API_KEY, system || "", message);
    } else {
      return jsonResponse({ error: "No AI key configured on server" }, 500, origin);
    }

    return jsonResponse({
      response,
      calls_used:      limit.count,
      calls_remaining: limit.remaining,
    }, 200, origin);

  } catch (e) {
    return jsonResponse({ error: "AI call failed", detail: e.message }, 500, origin);
  }
}

// ── Stripe signature verification ─────────────────────────────────────────────
async function verifyStripeSignature(payload, sigHeader, secret) {
  try {
    const parts = Object.fromEntries(
      sigHeader.split(",").map(p => p.split("="))
    );
    const { t: timestamp, v1: signature } = parts;
    if (!timestamp || !signature) return false;

    const encoder    = new TextEncoder();
    const key        = await crypto.subtle.importKey(
      "raw", encoder.encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false, ["sign"]
    );
    const signed     = await crypto.subtle.sign("HMAC", key, encoder.encode(`${timestamp}.${payload}`));
    const expected   = Array.from(new Uint8Array(signed))
      .map(b => b.toString(16).padStart(2, "0")).join("");

    return expected === signature;
  } catch {
    return false;
  }
}

// ── Stripe event handlers ─────────────────────────────────────────────────────

async function handleBuildFeePaid(session, env) {
  const email  = session.customer_details?.email || "unknown";
  const name   = session.customer_details?.name  || "Someone";
  const amount = ((session.amount_total || 0) / 100).toFixed(2);

  // Check if promo code FIRSTAPP2026 was used
  const discounts  = session.total_details?.breakdown?.discounts || [];
  const usedPromo  = discounts.some(d =>
    d.discount?.promotion_code?.code === "FIRSTAPP2026"
  );
  const promoNote  = usedPromo ? "\n⚠️  FIRSTAPP2026 promo used — one slot claimed." : "";

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

  // Notify you
  await sendEmail(env, {
    to:      env.ADMIN_EMAIL,
    subject: `⚠️  Subscription cancelled — ${email}`,
    text:    `${email} cancelled their hosting subscription.\n\nSubscription ID: ${sub.id}\n\nAction needed:\n1. Remove their Cloudflare Access policy (provision_demo.py --revoke)\n2. Run update_admin_data.py`,
  });

  // Notify customer
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

  const valid = await verifyStripeSignature(rawBody, sig, env.STRIPE_WEBHOOK_SECRET);
  if (!valid) {
    return jsonResponse({ error: "Signature verification failed" }, 401, origin);
  }

  const event = JSON.parse(rawBody);
  console.log(`Stripe event: ${event.type}`);

  try {
    switch (event.type) {
      case "checkout.session.completed":
        await handleBuildFeePaid(event.data.object, env);
        break;
      case "customer.subscription.created":
        await handleSubscriptionCreated(event.data.object, env);
        break;
      case "customer.subscription.deleted":
        await handleSubscriptionCancelled(event.data.object, env);
        break;
      case "invoice.payment_failed":
        await handlePaymentFailed(event.data.object, env);
        break;
      default:
        console.log(`Unhandled event type: ${event.type}`);
    }
  } catch (e) {
    // Log but still return 200 — Stripe will retry on non-200
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

// ── /health handler ───────────────────────────────────────────────────────────
function handleHealth(env, origin) {
  return jsonResponse({
    status:  "ok",
    service: "appsforhire-worker",
    keys: {
      claude:  !!env.CLAUDE_API_KEY,
      gemini:  !!env.GEMINI_API_KEY,
      stripe:  !!env.STRIPE_WEBHOOK_SECRET,
      resend:  !!env.RESEND_API_KEY,
      cf:      !!env.CF_API_TOKEN,
      github:  !!env.GITHUB_TOKEN,
    },
    rate_limit_kv: !!env.RATE_LIMIT,
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

    // Origin check — only allow our own sites (and localhost for dev)
    if (origin && !ALLOWED_ORIGINS.has(origin)) {
      return jsonResponse({ error: "Origin not allowed" }, 403, origin);
    }

    try {
      if (request.method === "GET"  && path === "/health")  return handleHealth(env, origin);
      if (request.method === "POST" && path === "/ai")      return handleAI(request, env, origin);
      if (request.method === "POST" && path === "/webhook") return handleWebhook(request, env, origin);

      return jsonResponse({ error: "Not found" }, 404, origin);

    } catch (e) {
      console.error(`Unhandled error: ${e.message}`);
      return jsonResponse({ error: "Internal server error" }, 500, origin);
    }
  },
};
