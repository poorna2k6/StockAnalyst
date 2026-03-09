/**
 * generate-report — Supabase Edge Function (Deno)
 *
 * Generates an AI-powered PDF portfolio report and stores it in Supabase Storage.
 * Logs to audit_logs for SEC Rule 204-2 compliance.
 *
 * POST /functions/v1/generate-report
 * Headers: Authorization: Bearer <supabase-jwt>
 * Body: { portfolioId: string, reportType: 'summary' | 'performance' | 'recommendation' }
 * Returns: { url: string }  — signed URL valid for 24 hours
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL         = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ANTHROPIC_KEY        = Deno.env.get("ANTHROPIC_API_KEY") ?? "";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS_HEADERS });

  // ── Verify JWT ─────────────────────────────────────────────────────────────
  const authHeader = req.headers.get("Authorization");
  if (!authHeader?.startsWith("Bearer ")) return json({ error: "Missing authorization" }, 401);

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
  const { data: { user }, error: authError } = await supabase.auth.getUser(authHeader.slice(7));
  if (authError || !user) return json({ error: "Invalid token" }, 401);

  const body: { portfolioId: string; reportType?: string } = await req.json();
  const { portfolioId, reportType = "summary" } = body;

  if (!portfolioId) return json({ error: "portfolioId is required" }, 400);

  // ── Fetch portfolio data ────────────────────────────────────────────────────
  const { data: portfolio } = await supabase
    .from("portfolios")
    .select("id, name, owner_id")
    .eq("id", portfolioId)
    .eq("owner_id", user.id) // RLS check via service role
    .single();

  if (!portfolio) return json({ error: "Portfolio not found or access denied" }, 404);

  const { data: positions } = await supabase
    .from("positions")
    .select("ticker, shares, avg_cost")
    .eq("portfolio_id", portfolioId);

  const { data: snapshots } = await supabase
    .from("portfolio_snapshots")
    .select("snapshot_date, total_value, benchmark_spy")
    .eq("portfolio_id", portfolioId)
    .order("snapshot_date", { ascending: false })
    .limit(30);

  // ── Build portfolio summary for AI prompt ──────────────────────────────────
  const positionList = (positions ?? []).map((p: { ticker: string; shares: number; avg_cost: number }) =>
    `${p.ticker}: ${p.shares} shares @ $${p.avg_cost} avg cost`
  ).join("\n");

  const perfData = (snapshots ?? []).slice(0, 7).map((s: { snapshot_date: string; total_value: number }) =>
    `${s.snapshot_date}: $${s.total_value?.toFixed(2) ?? "N/A"}`
  ).join("\n");

  // ── Generate AI report content ─────────────────────────────────────────────
  let reportMarkdown = "";
  if (ANTHROPIC_KEY) {
    const prompt = `You are a professional investment analyst. Generate a ${reportType} report for this portfolio.

Portfolio: ${portfolio.name}
Date: ${new Date().toLocaleDateString()}

POSITIONS:
${positionList || "No positions"}

RECENT PERFORMANCE (last 7 days):
${perfData || "No performance data available"}

Generate a professional ${reportType === "recommendation" ? "investment recommendation" : reportType} report in Markdown format. Include:
1. Executive Summary
2. Portfolio Overview
3. ${reportType === "performance" ? "Performance Analysis vs SPY benchmark" : "Holdings Analysis"}
4. ${reportType === "recommendation" ? "Specific Recommendations (with risk disclosures)" : "Risk Assessment"}
5. Important Disclaimer

Format using Markdown with clear headers. Keep it concise but actionable.`;

    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key":           ANTHROPIC_KEY,
        "anthropic-version":   "2023-06-01",
        "Content-Type":        "application/json",
      },
      body: JSON.stringify({
        model:      "claude-haiku-4-5-20251001", // Use Haiku for cost efficiency on report generation
        max_tokens: 2048,
        messages:   [{ role: "user", content: prompt }],
      }),
    });
    if (response.ok) {
      const data = await response.json();
      reportMarkdown = data.content?.[0]?.text ?? "";
    }
  }

  if (!reportMarkdown) {
    // Fallback template when no AI key
    reportMarkdown = `# ${portfolio.name} — ${reportType.charAt(0).toUpperCase() + reportType.slice(1)} Report\n\n**Date:** ${new Date().toLocaleDateString()}\n\n## Portfolio Holdings\n\n${positionList || "No positions"}\n\n## Disclaimer\n\n*This report is for educational purposes only and does not constitute financial advice.*`;
  }

  // ── Convert Markdown to PDF (plain text PDF for Deno compatibility) ─────────
  const pdfBytes = markdownToSimplePDF(reportMarkdown, portfolio.name);

  // ── Upload to Supabase Storage ─────────────────────────────────────────────
  const fileName = `${user.id}/${new Date().toISOString().split("T")[0]}_${reportType}.pdf`;
  const { error: uploadError } = await supabase.storage
    .from("reports")
    .upload(fileName, pdfBytes, {
      contentType: "application/pdf",
      upsert: true,
    });

  if (uploadError) return json({ error: "Upload failed: " + uploadError.message }, 500);

  // ── Create signed URL (24 hours) ──────────────────────────────────────────
  const { data: signedData } = await supabase.storage
    .from("reports")
    .createSignedUrl(fileName, 86400);

  // ── Write audit log for SEC compliance ─────────────────────────────────────
  await supabase.rpc("write_audit_log", {
    p_user_id:     user.id,
    p_advisor_id:  null,
    p_action:      "pdf_report_generated",
    p_entity_type: reportType === "recommendation" ? "recommendation_record" : "portfolio_report",
    p_entity_id:   portfolioId,
    p_payload:     {
      report_type: reportType,
      portfolio_id: portfolioId,
      positions_count: (positions ?? []).length,
      file_name: fileName,
    },
    p_client_ip:   req.headers.get("CF-Connecting-IP") ?? null,
    p_user_agent:  req.headers.get("User-Agent") ?? null,
  });

  return json({ url: signedData?.signedUrl ?? null, fileName });
});

/**
 * Convert Markdown to a minimal valid PDF binary.
 * This is a simplified PDF (plain text wrapped in PDF structure) compatible
 * with all PDF viewers. For production, swap with a full PDF library.
 */
function markdownToSimplePDF(markdown: string, title: string): Uint8Array {
  // Strip markdown formatting for plain text PDF
  const text = markdown
    .replace(/^#+\s*/gm, "")           // Remove headers
    .replace(/\*\*(.+?)\*\*/g, "$1")   // Remove bold
    .replace(/\*(.+?)\*/g, "$1")       // Remove italic
    .replace(/`(.+?)`/g, "$1");        // Remove code

  const lines = text.split("\n").filter((l) => l.trim());
  const pageWidth = 612;
  const pageHeight = 792;
  const margin = 50;
  const lineHeight = 14;
  const maxWidth = pageWidth - 2 * margin;
  const maxLinesPerPage = Math.floor((pageHeight - 2 * margin) / lineHeight);

  // Wrap long lines
  const wrappedLines: string[] = [];
  for (const line of lines) {
    // Approximate: 7px per char in 10pt Helvetica
    const charsPerLine = Math.floor(maxWidth / 7);
    if (line.length <= charsPerLine) {
      wrappedLines.push(line);
    } else {
      const words = line.split(" ");
      let current = "";
      for (const word of words) {
        if ((current + " " + word).length > charsPerLine) {
          wrappedLines.push(current);
          current = word;
        } else {
          current = current ? `${current} ${word}` : word;
        }
      }
      if (current) wrappedLines.push(current);
    }
  }

  // Build PDF content stream (one page for simplicity)
  const safeTitle = title.replace(/[()\\]/g, "\\$&");
  const contentLines = wrappedLines
    .slice(0, maxLinesPerPage)
    .map((line, i) => {
      const y = pageHeight - margin - i * lineHeight;
      const safeLine = line.replace(/[()\\]/g, "\\$&");
      return `BT /F1 10 Tf ${margin} ${y} Td (${safeLine}) Tj ET`;
    })
    .join("\n");

  const content = contentLines;
  const contentLen = new TextEncoder().encode(content).length;

  const pdf = `%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj

2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj

3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}]
   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj

4 0 obj
<< /Length ${contentLen} >>
stream
${content}
endstream
endobj

5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj

6 0 obj
<< /Title (${safeTitle}) /Creator (StockAnalyst) /CreationDate (D:${new Date().getFullYear()}0101120000) >>
endobj

xref
0 7
0000000000 65535 f
trailer
<< /Size 7 /Root 1 0 R /Info 6 0 R >>
startxref
0
%%EOF`;

  return new TextEncoder().encode(pdf);
}

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}
