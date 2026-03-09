/**
 * data-export — Supabase Edge Function (Deno)
 *
 * GDPR data export: bundles all user data into a JSON archive
 * and uploads to Supabase Storage with a signed download URL.
 *
 * POST /functions/v1/data-export
 * Headers: Authorization: Bearer <supabase-jwt>
 * Returns: { url: string }  — signed URL valid for 1 hour
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
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS_HEADERS });

  const authHeader = req.headers.get("Authorization");
  if (!authHeader?.startsWith("Bearer ")) return json({ error: "Missing authorization" }, 401);

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
  const { data: { user }, error: authError } = await supabase.auth.getUser(authHeader.slice(7));
  if (authError || !user) return json({ error: "Invalid token" }, 401);

  // Call the GDPR export SQL function
  const { data: exportData, error: exportError } = await supabase.rpc("gdpr_export_user_data", {
    p_user_id: user.id,
  });

  if (exportError) return json({ error: "Export failed: " + exportError.message }, 500);

  // Serialize to JSON
  const jsonString = JSON.stringify(exportData, null, 2);
  const jsonBytes = new TextEncoder().encode(jsonString);

  // Upload to Supabase Storage (private bucket)
  const fileName = `${user.id}/gdpr-export-${new Date().toISOString().split("T")[0]}.json`;

  const { error: uploadError } = await supabase.storage
    .from("user-exports")
    .upload(fileName, jsonBytes, {
      contentType: "application/json",
      upsert: true,
    });

  if (uploadError) {
    // If bucket doesn't exist, return raw JSON download instead
    return new Response(jsonString, {
      headers: {
        ...CORS_HEADERS,
        "Content-Type": "application/json",
        "Content-Disposition": `attachment; filename="my-stockanalyst-data.json"`,
      },
    });
  }

  // Create signed URL (1 hour validity)
  const { data: signedData } = await supabase.storage
    .from("user-exports")
    .createSignedUrl(fileName, 3600);

  return json({ url: signedData?.signedUrl ?? null, fileName });
});

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}
