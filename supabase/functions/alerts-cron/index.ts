/**
 * alerts-cron — Supabase Edge Function (Deno)
 *
 * Checks all active price alerts against current market prices.
 * Should be triggered via Supabase Cron (pg_cron) or Supabase Dashboard Cron.
 *
 * Suggested schedule: Every 5 minutes during market hours (weekdays 9:30 AM – 4 PM ET)
 *
 * To register: In Supabase Dashboard → Edge Functions → Schedule
 *   Path: /functions/v1/alerts-cron
 *   Schedule: */5 13-20 * * 1-5   (UTC = ET + 4/5 hours)
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL         = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

// Fallback CORS proxy for Yahoo Finance (same pattern as frontend)
const CORS_PROXIES = [
  (t: string) => `https://query1.finance.yahoo.com/v8/finance/chart/${t}?range=1d&interval=1m`,
];

interface PriceAlert {
  id: string;
  user_id: string;
  ticker: string;
  condition: "above" | "below";
  target_price: number;
}

Deno.serve(async (_req: Request) => {
  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

  // Fetch all active alerts
  const { data: alerts, error } = await supabase
    .from("price_alerts")
    .select("id, user_id, ticker, condition, target_price")
    .eq("is_active", true)
    .is("triggered_at", null);

  if (error || !alerts?.length) {
    return new Response(JSON.stringify({ checked: 0, triggered: 0 }), { status: 200 });
  }

  // Deduplicate tickers for efficient API calls
  const tickers = [...new Set((alerts as PriceAlert[]).map((a) => a.ticker))];
  const prices: Record<string, number> = {};

  // Fetch prices in parallel (respects Yahoo's rate limits)
  await Promise.allSettled(
    tickers.map(async (ticker) => {
      try {
        const price = await fetchCurrentPrice(ticker);
        if (price !== null) prices[ticker] = price;
      } catch {
        // Skip ticker if price unavailable
      }
    }),
  );

  // Check each alert
  let triggered = 0;
  const now = new Date().toISOString();

  for (const alert of alerts as PriceAlert[]) {
    const currentPrice = prices[alert.ticker];
    if (currentPrice === undefined) continue;

    const shouldTrigger =
      (alert.condition === "above" && currentPrice >= alert.target_price) ||
      (alert.condition === "below" && currentPrice <= alert.target_price);

    if (shouldTrigger) {
      // Mark alert as triggered
      await supabase
        .from("price_alerts")
        .update({ triggered_at: now, last_fired_at: now, is_active: false })
        .eq("id", alert.id);

      // Send push notification
      try {
        await fetch(`${SUPABASE_URL}/functions/v1/push-notify`, {
          method: "POST",
          headers: {
            "Content-Type":  "application/json",
            "Authorization": `Bearer ${SUPABASE_SERVICE_KEY}`,
          },
          body: JSON.stringify({
            userId: alert.user_id,
            title:  `${alert.ticker} price alert!`,
            body:   `${alert.ticker} is now $${currentPrice.toFixed(2)} (${alert.condition} $${alert.target_price})`,
            ticker: alert.ticker,
          }),
        });
      } catch (err) {
        console.warn(`Push notify failed for user ${alert.user_id}:`, err);
      }

      triggered++;
    }
  }

  console.log(`[alerts-cron] Checked ${alerts.length} alerts, triggered ${triggered}`);
  return new Response(JSON.stringify({ checked: alerts.length, triggered }), { status: 200 });
});

/** Fetch the current price for a ticker from Yahoo Finance */
async function fetchCurrentPrice(ticker: string): Promise<number | null> {
  const url = CORS_PROXIES[0](ticker);
  const res = await fetch(url, {
    headers: { "User-Agent": "Mozilla/5.0" },
    signal: AbortSignal.timeout(8000),
  });
  if (!res.ok) return null;
  const data = await res.json();
  const meta = data?.chart?.result?.[0]?.meta;
  return meta?.regularMarketPrice ?? meta?.previousClose ?? null;
}
