/**
 * stripe-webhook — Supabase Edge Function (Deno)
 *
 * Handles Stripe webhook events to keep profile subscription state in sync.
 * Listens for: customer.subscription.created/updated/deleted
 *
 * Register this URL in Stripe Dashboard → Webhooks:
 *   https://YOUR_PROJECT.supabase.co/functions/v1/stripe-webhook
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const STRIPE_SECRET_KEY      = Deno.env.get("STRIPE_SECRET_KEY")!;
const STRIPE_WEBHOOK_SECRET  = Deno.env.get("STRIPE_WEBHOOK_SECRET")!;
const SUPABASE_URL           = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_KEY   = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

// Map Stripe Price IDs to internal subscription tiers
const PRICE_TO_TIER: Record<string, string> = {
  [Deno.env.get("STRIPE_PRO_PRICE_ID") ?? ""]:     "pro",
  [Deno.env.get("STRIPE_ADVISOR_PRICE_ID") ?? ""]: "advisor",
};

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "stripe-signature, content-type",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: CORS_HEADERS });
  }

  // ── Verify Stripe signature ────────────────────────────────────────────────
  const signature = req.headers.get("stripe-signature");
  if (!signature) {
    return new Response("Missing stripe-signature", { status: 400 });
  }

  const body = await req.text();

  let event: {
    type: string;
    data: {
      object: {
        id: string;
        customer: string;
        status: string;
        items?: { data: Array<{ price: { id: string } }> };
      };
    };
  };

  try {
    event = await verifyStripeWebhook(body, signature, STRIPE_WEBHOOK_SECRET);
  } catch (err) {
    console.error("Stripe signature verification failed:", err);
    return new Response("Invalid signature", { status: 400 });
  }

  // ── Handle subscription events ─────────────────────────────────────────────
  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

  const subscription = event.data.object;

  if (
    event.type === "customer.subscription.created" ||
    event.type === "customer.subscription.updated"
  ) {
    const priceId = subscription.items?.data?.[0]?.price?.id ?? "";
    const tier = PRICE_TO_TIER[priceId] ?? "free";
    const status = subscription.status; // 'active', 'past_due', etc.

    await supabase.rpc("update_subscription_from_stripe", {
      p_stripe_customer_id: subscription.customer,
      p_subscription_id:    subscription.id,
      p_tier:               tier,
      p_status:             status,
    });

    console.log(`Subscription updated: customer=${subscription.customer} tier=${tier} status=${status}`);

  } else if (event.type === "customer.subscription.deleted") {
    // Subscription canceled — downgrade to free
    await supabase.rpc("update_subscription_from_stripe", {
      p_stripe_customer_id: subscription.customer,
      p_subscription_id:    subscription.id,
      p_tier:               "free",
      p_status:             "canceled",
    });

    console.log(`Subscription canceled: customer=${subscription.customer}`);
  }

  return new Response(JSON.stringify({ received: true }), {
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
});

/**
 * Verify Stripe webhook signature using HMAC-SHA256.
 * Deno does not have the Stripe SDK, so we implement verification manually.
 */
async function verifyStripeWebhook(
  payload: string,
  signature: string,
  secret: string,
): Promise<{ type: string; data: { object: Record<string, unknown> } }> {
  // Parse timestamp and signatures from header
  const parts = Object.fromEntries(signature.split(",").map((p) => p.split("=")));
  const timestamp = parts["t"];
  const v1 = parts["v1"];

  if (!timestamp || !v1) throw new Error("Malformed stripe-signature header");

  // Compute expected signature
  const signedPayload = `${timestamp}.${payload}`;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(signedPayload));
  const expected = Array.from(new Uint8Array(mac))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  if (expected !== v1) throw new Error("Signature mismatch");

  // Check timestamp tolerance (5 minutes)
  const diff = Math.abs(Date.now() / 1000 - parseInt(timestamp, 10));
  if (diff > 300) throw new Error("Timestamp too old");

  return JSON.parse(payload);
}
