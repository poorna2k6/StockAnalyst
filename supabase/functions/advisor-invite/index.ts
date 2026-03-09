/**
 * advisor-invite — Supabase Edge Function (Deno)
 *
 * Handles portfolio sharing invites and collaborator accept flows.
 *
 * POST /functions/v1/advisor-invite
 * Headers: Authorization: Bearer <supabase-jwt>
 * Body (send invite):  { action: 'invite', portfolioId: string, email: string, role: 'viewer'|'editor' }
 * Body (accept invite): { action: 'accept', token: string }
 * Body (revoke):        { action: 'revoke', collaboratorId: string }
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL         = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

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
    return json({ error: "Missing authorization" }, 401);
  }

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
  const { data: { user }, error: authError } = await supabase.auth.getUser(authHeader.slice(7));
  if (authError || !user) {
    return json({ error: "Invalid token" }, 401);
  }

  const body: {
    action: "invite" | "accept" | "revoke";
    portfolioId?: string;
    email?: string;
    role?: "viewer" | "editor";
    token?: string;
    collaboratorId?: string;
  } = await req.json();

  // ── Route by action ───────────────────────────────────────────────────────

  if (body.action === "invite") {
    return handleInvite(supabase, user.id, body);
  } else if (body.action === "accept") {
    return handleAccept(supabase, user.id, body.token);
  } else if (body.action === "revoke") {
    return handleRevoke(supabase, user.id, body.collaboratorId);
  }

  return json({ error: "Unknown action" }, 400);
});

async function handleInvite(
  supabase: ReturnType<typeof createClient>,
  userId: string,
  body: { portfolioId?: string; email?: string; role?: string },
) {
  if (!body.portfolioId || !body.email) {
    return json({ error: "portfolioId and email are required" }, 400);
  }

  // Verify the user owns this portfolio
  const { data: portfolio } = await supabase
    .from("portfolios")
    .select("id")
    .eq("id", body.portfolioId)
    .eq("owner_id", userId)
    .single();

  if (!portfolio) {
    return json({ error: "Portfolio not found or not owned by you" }, 403);
  }

  // Create the collaborator invite row
  const { data: invite, error } = await supabase
    .from("portfolio_collaborators")
    .insert({
      portfolio_id:  body.portfolioId,
      invited_email: body.email,
      role:          body.role ?? "viewer",
    })
    .select("id, invite_token")
    .single();

  if (error) {
    return json({ error: error.message }, 500);
  }

  // Return the invite link (frontend builds the full URL)
  const inviteLink = `?invite=${invite.invite_token}`;
  return json({ success: true, inviteToken: invite.invite_token, inviteLink });
}

async function handleAccept(
  supabase: ReturnType<typeof createClient>,
  userId: string,
  token?: string,
) {
  if (!token) return json({ error: "token is required" }, 400);

  const { data: result, error } = await supabase.rpc("accept_portfolio_invite", {
    p_token: token,
  });

  if (error || result?.error) {
    return json({ error: result?.error ?? error?.message ?? "Accept failed" }, 404);
  }

  return json({ success: true, portfolioId: result.portfolio_id, role: result.role });
}

async function handleRevoke(
  supabase: ReturnType<typeof createClient>,
  userId: string,
  collaboratorId?: string,
) {
  if (!collaboratorId) return json({ error: "collaboratorId is required" }, 400);

  // Only the portfolio owner can revoke
  const { error } = await supabase
    .from("portfolio_collaborators")
    .delete()
    .eq("id", collaboratorId)
    .in("portfolio_id",
      supabase.from("portfolios").select("id").eq("owner_id", userId),
    );

  if (error) return json({ error: error.message }, 500);
  return json({ success: true });
}

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Content-Type": "application/json",
    },
  });
}
