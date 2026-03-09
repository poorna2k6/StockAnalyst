/**
 * ai-proxy — Supabase Edge Function (Deno)
 *
 * Proxies Claude / Gemini API calls server-side so API keys never touch the browser.
 * The browser sends its Supabase JWT; this function:
 *   1. Verifies the JWT via supabase.auth.getUser()
 *   2. Reads the user's preferred AI provider from profiles
 *   3. Retrieves the decrypted API key from Vault (or uses env fallback for advisor tiers)
 *   4. Pipes the SSE stream back to the browser
 *   5. Decrements AI credits for free-tier users
 *
 * POST /functions/v1/ai-proxy
 * Headers: Authorization: Bearer <supabase-jwt>
 * Body: { systemPrompt, messages, maxTokens, provider? }
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

// Optional server-side fallback keys (for advisor tier — they don't supply their own)
const SERVER_CLAUDE_KEY = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
const SERVER_GEMINI_KEY = Deno.env.get("GEMINI_API_KEY") ?? "";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve(async (req: Request) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: CORS_HEADERS });
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  // ── 1. Verify JWT ────────────────────────────────────────────────────────────
  const authHeader = req.headers.get("Authorization");
  if (!authHeader?.startsWith("Bearer ")) {
    return new Response(JSON.stringify({ error: "Missing authorization" }), {
      status: 401,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  const token = authHeader.slice(7);

  // Use service role client to bypass RLS for vault queries
  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

  // Verify user identity
  const { data: { user }, error: authError } = await supabase.auth.getUser(token);
  if (authError || !user) {
    return new Response(JSON.stringify({ error: "Invalid token" }), {
      status: 401,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  // ── 2. Read user profile ─────────────────────────────────────────────────────
  const { data: profile } = await supabase
    .from("profiles")
    .select("subscription_tier, ai_provider, ai_credits_remaining")
    .eq("id", user.id)
    .single();

  if (!profile) {
    return new Response(JSON.stringify({ error: "Profile not found" }), {
      status: 404,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  // ── 3. Parse request body ────────────────────────────────────────────────────
  let body: {
    systemPrompt?: string;
    messages: Array<{ role: string; content: string }>;
    maxTokens?: number;
    provider?: string;
  };
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  const { systemPrompt, messages, maxTokens = 1024 } = body;

  // Determine provider: request override → user pref → auto (claude)
  const requestedProvider = body.provider ?? profile.ai_provider ?? "auto";
  const provider = requestedProvider === "auto" ? "claude" : requestedProvider;

  // ── 4. Check & consume credits for free tier ─────────────────────────────────
  if (profile.subscription_tier === "free") {
    const { data: remaining } = await supabase.rpc("consume_ai_credit", {
      p_user_id: user.id,
    });
    if (remaining === 0) {
      return new Response(
        JSON.stringify({ error: "AI credit limit reached. Upgrade to Pro for unlimited access." }),
        {
          status: 402,
          headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
        }
      );
    }
  }

  // ── 5. Retrieve API key from Vault ───────────────────────────────────────────
  let apiKey = "";

  // Advisor tier can use server-side keys (no user-supplied key required)
  if (profile.subscription_tier === "advisor") {
    apiKey = provider === "claude" ? SERVER_CLAUDE_KEY : SERVER_GEMINI_KEY;
  }

  // All tiers: try user's own stored key (overrides server key if present)
  if (!apiKey) {
    const { data: vaultKey } = await supabase.rpc("get_user_api_key", {
      p_user_id: user.id,
      p_provider: provider,
    });
    apiKey = vaultKey ?? "";
  }

  if (!apiKey) {
    return new Response(
      JSON.stringify({ error: `No API key found for provider '${provider}'. Please add your key in Settings.` }),
      {
        status: 422,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      }
    );
  }

  // ── 6. Proxy to AI provider ──────────────────────────────────────────────────
  if (provider === "claude") {
    return proxyClaude({ apiKey, systemPrompt, messages, maxTokens });
  } else if (provider === "gemini") {
    return proxyGemini({ apiKey, systemPrompt, messages, maxTokens });
  } else {
    return new Response(JSON.stringify({ error: `Unknown provider: ${provider}` }), {
      status: 400,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }
});

// ── Claude SSE proxy ──────────────────────────────────────────────────────────

async function proxyClaude(opts: {
  apiKey: string;
  systemPrompt?: string;
  messages: Array<{ role: string; content: string }>;
  maxTokens: number;
}): Promise<Response> {
  const body: Record<string, unknown> = {
    model: "claude-sonnet-4-6",
    max_tokens: opts.maxTokens,
    stream: true,
    messages: opts.messages,
  };
  if (opts.systemPrompt) {
    body.system = opts.systemPrompt;
  }

  const upstream = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": opts.apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify(body),
  });

  if (!upstream.ok) {
    const errText = await upstream.text();
    return new Response(errText, {
      status: upstream.status,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  // Pipe SSE stream directly to browser
  return new Response(upstream.body, {
    headers: {
      ...CORS_HEADERS,
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
    },
  });
}

// ── Gemini SSE proxy ──────────────────────────────────────────────────────────

async function proxyGemini(opts: {
  apiKey: string;
  systemPrompt?: string;
  messages: Array<{ role: string; content: string }>;
  maxTokens: number;
}): Promise<Response> {
  // Convert messages to Gemini format
  const contents = opts.messages.map((m) => ({
    role: m.role === "assistant" ? "model" : "user",
    parts: [{ text: m.content }],
  }));

  const body: Record<string, unknown> = {
    contents,
    generationConfig: { maxOutputTokens: opts.maxTokens },
  };

  if (opts.systemPrompt) {
    body.systemInstruction = { parts: [{ text: opts.systemPrompt }] };
  }

  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:streamGenerateContent?key=${opts.apiKey}&alt=sse`;

  const upstream = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!upstream.ok) {
    const errText = await upstream.text();
    return new Response(errText, {
      status: upstream.status,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  // Transform Gemini SSE format to match Claude SSE format expected by the frontend
  const { readable, writable } = new TransformStream();
  const writer = writable.getWriter();
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();

  (async () => {
    const reader = upstream.body!.getReader();
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        // Re-emit as SSE data lines compatible with frontend's existing parser
        const lines = chunk.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;
              if (text) {
                // Emit in a Claude-compatible format so the frontend can use one parser
                const out = JSON.stringify({ type: "content_block_delta", delta: { type: "text_delta", text } });
                await writer.write(encoder.encode(`data: ${out}\n\n`));
              }
            } catch {
              // Skip malformed lines
            }
          }
        }
      }
    } finally {
      await writer.close();
    }
  })();

  return new Response(readable, {
    headers: {
      ...CORS_HEADERS,
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
    },
  });
}
