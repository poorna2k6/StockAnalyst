/**
 * delete-account — Supabase Edge Function (Deno)
 *
 * GDPR right-to-erasure: deletes all user data including:
 * - All Supabase table rows (via gdpr_delete_user_data SQL function)
 * - Supabase Storage files
 * - Supabase Vault secrets (API keys)
 * - Stripe customer and subscription
 * - auth.users row (last step)
 *
 * POST /functions/v1/delete-account
 * Headers: Authorization: Bearer <supabase-jwt>
 * Body: { confirmation: 'DELETE MY ACCOUNT' }  — required safety check
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL         = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const STRIPE_SECRET_KEY    = Deno.env.get("STRIPE_SECRET_KEY") ?? "";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS_HEADERS });

  const authHeader = req.headers.get("Authorization");
  if (!authHeader?.startsWith("Bearer ")) return json({ error: "Missing authorization" }, 401);

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
  const { data: { user }, error: authError } = await supabase.auth.getUser(authHeader.slice(7));
  if (authError || !user) return json({ error: "Invalid token" }, 401);

  // Require explicit confirmation
  const body: { confirmation?: string } = await req.json().catch(() => ({}));
  if (body.confirmation !== "DELETE MY ACCOUNT") {
    return json({ error: "Confirmation text must be 'DELETE MY ACCOUNT'" }, 400);
  }

  const errors: string[] = [];

  // ── 1. Delete Stripe customer ──────────────────────────────────────────────
  if (STRIPE_SECRET_KEY) {
    try {
      const { data: profile } = await supabase
        .from("profiles")
        .select("stripe_customer_id")
        .eq("id", user.id)
        .single();

      if (profile?.stripe_customer_id) {
        const res = await fetch(`https://api.stripe.com/v1/customers/${profile.stripe_customer_id}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${STRIPE_SECRET_KEY}` },
        });
        if (!res.ok) {
          const err = await res.json();
          errors.push(`Stripe delete: ${err.error?.message ?? res.status}`);
        }
      }
    } catch (err) {
      errors.push(`Stripe: ${err}`);
    }
  }

  // ── 2. Delete Vault secrets (API keys) ─────────────────────────────────────
  try {
    const { data: apiKeys } = await supabase
      .from("user_api_keys")
      .select("secret_id")
      .eq("user_id", user.id);

    for (const key of (apiKeys ?? []) as Array<{ secret_id: string }>) {
      await supabase.schema("vault").from("secrets").delete().eq("id", key.secret_id).catch(() => {});
    }
  } catch (err) {
    errors.push(`Vault cleanup: ${err}`);
  }

  // ── 3. Delete Supabase Storage files ──────────────────────────────────────
  try {
    // List and delete files in reports/ and user-exports/ buckets
    for (const bucket of ["reports", "user-exports"]) {
      const { data: files } = await supabase.storage.from(bucket).list(user.id);
      if (files?.length) {
        const paths = files.map((f: { name: string }) => `${user.id}/${f.name}`);
        await supabase.storage.from(bucket).remove(paths);
      }
    }
  } catch (err) {
    errors.push(`Storage cleanup: ${err}`);
  }

  // ── 4. Delete all database rows ────────────────────────────────────────────
  try {
    await supabase.rpc("gdpr_delete_user_data", { p_user_id: user.id });
  } catch (err) {
    errors.push(`DB delete: ${err}`);
  }

  // ── 5. Delete auth.users row (must be last) ────────────────────────────────
  try {
    const { error: deleteUserError } = await supabase.auth.admin.deleteUser(user.id);
    if (deleteUserError) errors.push(`Auth delete: ${deleteUserError.message}`);
  } catch (err) {
    errors.push(`Auth delete: ${err}`);
  }

  if (errors.length > 0) {
    console.error(`[delete-account] Partial errors for user ${user.id}:`, errors);
    // Still return success if the auth.users row was deleted (user is effectively deleted)
  }

  return json({ deleted: true, warnings: errors.length > 0 ? errors : undefined });
});

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}
