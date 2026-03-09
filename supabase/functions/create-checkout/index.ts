/**
 * create-checkout — Supabase Edge Function (Deno)
 *
 * Creates a Stripe Checkout session for Pro or Advisor tier upgrade.
 *
 * POST /functions/v1/create-checkout
 * Headers: Authorization: Bearer <supabase-jwt>
 * Body: { tier: 'pro' | 'advisor', successUrl: string, cancelUrl: string }
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const STRIPE_SECRET_KEY      = Deno.env.get("STRIPE_SECRET_KEY")!;
const SUPABASE_URL           = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_KEY   = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const PRICE_IDS: Record<string, string> = {
  pro:     Deno.env.get("STRIPE_PRO_PRICE_ID") ?? "",
  advisor: Deno.env.get("STRIPE_ADVISOR_PRICE_ID") ?? "",
};

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: CORS_HEADERS });
  }

  // ── Verify JWT ────────────────────────────────────────────────────────────
  const authHeader = req.headers.get("Authorization");
  if (!authHeader?.startsWith("Bearer ")) {
    return new Response(JSON.stringify({ error: "Missing authorization" }), {
      status: 401, headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
  const { data: { user }, error: authError } = await supabase.auth.getUser(authHeader.slice(7));
  if (authError || !user) {
    return new Response(JSON.stringify({ error: "Invalid token" }), {
      status: 401, headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  const body: { tier: string; successUrl: string; cancelUrl: string } = await req.json();
  const priceId = PRICE_IDS[body.tier];
  if (!priceId) {
    return new Response(JSON.stringify({ error: `Unknown tier: ${body.tier}` }), {
      status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  // ── Get or create Stripe customer ─────────────────────────────────────────
  const { data: profile } = await supabase.from("profiles").select("stripe_customer_id, email").eq("id", user.id).single();
  let customerId = profile?.stripe_customer_id;

  if (!customerId) {
    const customerRes = await stripePost("customers", {
      email: profile?.email ?? user.email,
      metadata: { supabase_user_id: user.id },
    });
    customerId = customerRes.id;
    await supabase.from("profiles").update({ stripe_customer_id: customerId }).eq("id", user.id);
  }

  // ── Create Checkout session ────────────────────────────────────────────────
  const session = await stripePost("checkout/sessions", {
    customer:              customerId,
    mode:                  "subscription",
    line_items:            [{ price: priceId, quantity: 1 }],
    success_url:           body.successUrl || `${req.headers.get("origin") ?? ""}?checkout=success`,
    cancel_url:            body.cancelUrl  || `${req.headers.get("origin") ?? ""}?checkout=canceled`,
    allow_promotion_codes: true,
  });

  return new Response(JSON.stringify({ url: session.url }), {
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
});

async function stripePost(endpoint: string, data: Record<string, unknown>): Promise<Record<string, string>> {
  const body = new URLSearchParams();
  for (const [key, value] of Object.entries(data)) {
    if (Array.isArray(value)) {
      value.forEach((item, i) => {
        if (typeof item === "object" && item !== null) {
          for (const [k, v] of Object.entries(item as Record<string, unknown>)) {
            body.append(`${key}[${i}][${k}]`, String(v));
          }
        }
      });
    } else if (typeof value === "object" && value !== null) {
      for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
        body.append(`${key}[${k}]`, String(v));
      }
    } else {
      body.append(key, String(value));
    }
  }
  const res = await fetch(`https://api.stripe.com/v1/${endpoint}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${STRIPE_SECRET_KEY}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: body.toString(),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error?.message ?? `Stripe error ${res.status}`);
  }
  return res.json();
}
