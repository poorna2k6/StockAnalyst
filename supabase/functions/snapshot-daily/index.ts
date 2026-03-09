/**
 * snapshot-daily — Supabase Edge Function (Deno)
 *
 * Takes daily portfolio snapshots for all active portfolios.
 * Runs at market close (21:00 UTC = 4 PM ET) via Supabase Cron.
 *
 * Cron schedule: 0 21 * * 1-5   (weekdays only)
 *
 * For each portfolio:
 *   1. Fetches current prices for all positions
 *   2. Calculates total_value and total_cost
 *   3. Writes a portfolio_snapshots row (upsert on portfolio_id + date)
 *   4. Also records SPY close price for benchmark comparison
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL         = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

interface Position { portfolio_id: string; ticker: string; shares: number; avg_cost: number; }
interface Portfolio { id: string; owner_id: string; }

Deno.serve(async (_req: Request) => {
  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
  const today = new Date().toISOString().split("T")[0]; // YYYY-MM-DD

  // Fetch all portfolios with positions
  const { data: portfolios } = await supabase
    .from("portfolios")
    .select("id, owner_id");

  if (!portfolios?.length) {
    return new Response(JSON.stringify({ snapshotted: 0 }), { status: 200 });
  }

  // Fetch SPY price for benchmark
  const spyPrice = await fetchPrice("SPY");

  let snapshotted = 0;
  const errors: string[] = [];

  for (const portfolio of portfolios as Portfolio[]) {
    try {
      const { data: positions } = await supabase
        .from("positions")
        .select("ticker, shares, avg_cost")
        .eq("portfolio_id", portfolio.id);

      if (!positions?.length) continue;

      // Fetch prices for all tickers in parallel
      const tickers = (positions as { ticker: string }[]).map((p) => p.ticker);
      const prices: Record<string, number> = {};
      await Promise.allSettled(
        tickers.map(async (ticker) => {
          const price = await fetchPrice(ticker);
          if (price !== null) prices[ticker] = price;
        }),
      );

      // Calculate totals
      let totalValue = 0;
      let totalCost = 0;
      for (const pos of positions as Position[]) {
        const price = prices[pos.ticker];
        if (price !== undefined) {
          totalValue += price * pos.shares;
        }
        totalCost += pos.avg_cost * pos.shares;
      }

      // Write snapshot
      await supabase.from("portfolio_snapshots").upsert(
        {
          portfolio_id:   portfolio.id,
          snapshot_date:  today,
          total_value:    totalValue,
          total_cost:     totalCost,
          positions_json: positions,
          benchmark_spy:  spyPrice,
        },
        { onConflict: "portfolio_id,snapshot_date" },
      );

      snapshotted++;
    } catch (err) {
      errors.push(`Portfolio ${portfolio.id}: ${err}`);
    }
  }

  console.log(`[snapshot-daily] Snapshotted ${snapshotted}/${portfolios.length} portfolios for ${today}`);
  if (errors.length) console.warn("Errors:", errors);

  return new Response(JSON.stringify({ snapshotted, total: portfolios.length, date: today }), { status: 200 });
});

async function fetchPrice(ticker: string): Promise<number | null> {
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}?range=1d&interval=1d`;
    const res = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0" },
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data?.chart?.result?.[0]?.meta?.regularMarketPrice ?? null;
  } catch {
    return null;
  }
}
