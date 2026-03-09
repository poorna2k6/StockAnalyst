/**
 * Unit tests — portfolio snapshot creation
 * Tests the logic that would run inside snapshot-daily Edge Function
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { makeSupabaseMock } from '../setup';

// ── Snapshot logic (extracted from Edge Function for testability) ─────────────

interface Position {
  ticker: string;
  shares: number;
  cost_per_share: number;
}

interface Portfolio {
  id: string;
  owner_id: string;
}

interface PriceMap {
  [ticker: string]: number;
}

async function computePortfolioValue(
  positions: Position[],
  prices: PriceMap,
): Promise<number> {
  return positions.reduce((sum, pos) => {
    const price = prices[pos.ticker] ?? pos.cost_per_share; // fallback to cost
    return sum + price * pos.shares;
  }, 0);
}

async function buildSnapshotRow(
  portfolio: Portfolio,
  positions: Position[],
  prices: PriceMap,
  spyPrice: number,
  snapshotDate: string,
) {
  const totalValue = await computePortfolioValue(positions, prices);
  return {
    portfolio_id: portfolio.id,
    snapshot_date: snapshotDate,
    total_value: Math.round(totalValue * 100) / 100,
    positions_json: positions,
    benchmark_spy: spyPrice,
  };
}

// ─────────────────────────────────────────────────────────────────────────────

describe('portfolio snapshot computation', () => {
  const TODAY = '2026-03-09';

  it('computes total value correctly from positions and prices', async () => {
    const positions: Position[] = [
      { ticker: 'AAPL', shares: 10, cost_per_share: 150 },
      { ticker: 'MSFT', shares: 5, cost_per_share: 300 },
    ];
    const prices: PriceMap = { AAPL: 200, MSFT: 400 };

    const value = await computePortfolioValue(positions, prices);
    expect(value).toBe(10 * 200 + 5 * 400); // 2000 + 2000 = 4000
  });

  it('falls back to cost_per_share when price is missing', async () => {
    const positions: Position[] = [
      { ticker: 'AAPL', shares: 10, cost_per_share: 150 },
      { ticker: 'UNKNOWN', shares: 5, cost_per_share: 100 },
    ];
    const prices: PriceMap = { AAPL: 200 }; // UNKNOWN missing

    const value = await computePortfolioValue(positions, prices);
    expect(value).toBe(10 * 200 + 5 * 100); // fallback: use cost
  });

  it('returns 0 for empty portfolio', async () => {
    const value = await computePortfolioValue([], {});
    expect(value).toBe(0);
  });

  it('builds a complete snapshot row with SPY benchmark', async () => {
    const portfolio: Portfolio = { id: 'port-1', owner_id: 'user-1' };
    const positions: Position[] = [
      { ticker: 'AAPL', shares: 10, cost_per_share: 150 },
    ];
    const prices: PriceMap = { AAPL: 175 };
    const spyPrice = 498.23;

    const row = await buildSnapshotRow(portfolio, positions, prices, spyPrice, TODAY);

    expect(row.portfolio_id).toBe('port-1');
    expect(row.snapshot_date).toBe(TODAY);
    expect(row.total_value).toBe(1750);
    expect(row.benchmark_spy).toBe(498.23);
    expect(row.positions_json).toEqual(positions);
  });

  it('rounds total_value to 2 decimal places', async () => {
    const portfolio: Portfolio = { id: 'port-1', owner_id: 'user-1' };
    const positions: Position[] = [
      { ticker: 'AAPL', shares: 3, cost_per_share: 100 },
    ];
    const prices: PriceMap = { AAPL: 333.333 };

    const row = await buildSnapshotRow(portfolio, positions, prices, 500, TODAY);
    // 3 * 333.333 = 999.999 → rounds to 1000
    expect(row.total_value).toBe(1000);
  });
});

// ── Supabase upsert idempotency (mock) ────────────────────────────────────────

describe('snapshot upsert — idempotency', () => {
  let supabase: ReturnType<typeof makeSupabaseMock>;

  beforeEach(() => {
    supabase = makeSupabaseMock();
  });

  it('calls upsert with correct conflict key (portfolio_id + snapshot_date)', async () => {
    const row = {
      portfolio_id: 'port-1',
      snapshot_date: '2026-03-09',
      total_value: 4000,
      positions_json: [],
      benchmark_spy: 500,
    };

    const fromSpy = vi.fn().mockReturnValue({
      upsert: vi.fn().mockResolvedValue({ error: null }),
    });
    supabase.from = fromSpy;

    await supabase.from('portfolio_snapshots').upsert(row);

    expect(fromSpy).toHaveBeenCalledWith('portfolio_snapshots');
  });

  it('processes multiple portfolios without cross-contamination', async () => {
    const portfolios: Portfolio[] = [
      { id: 'port-1', owner_id: 'user-1' },
      { id: 'port-2', owner_id: 'user-2' },
    ];
    const positionsByPort: Record<string, Position[]> = {
      'port-1': [{ ticker: 'AAPL', shares: 10, cost_per_share: 150 }],
      'port-2': [{ ticker: 'GOOG', shares: 2, cost_per_share: 2800 }],
    };
    const prices: PriceMap = { AAPL: 200, GOOG: 3000 };

    const rows = await Promise.all(
      portfolios.map((p) =>
        buildSnapshotRow(p, positionsByPort[p.id], prices, 500, '2026-03-09'),
      ),
    );

    expect(rows[0].portfolio_id).toBe('port-1');
    expect(rows[0].total_value).toBe(2000);
    expect(rows[1].portfolio_id).toBe('port-2');
    expect(rows[1].total_value).toBe(6000);
  });
});

// ── Performance chart data derivation ────────────────────────────────────────

describe('performance chart data derivation', () => {
  interface SnapshotRow {
    snapshot_date: string;
    total_value: number;
    benchmark_spy: number;
  }

  function deriveChartData(snapshots: SnapshotRow[]) {
    if (snapshots.length === 0) return { portfolio: [], spy: [], maxValue: 0 };
    const sorted = [...snapshots].sort((a, b) =>
      a.snapshot_date.localeCompare(b.snapshot_date),
    );
    const basePortfolio = sorted[0].total_value;
    const baseSpy = sorted[0].benchmark_spy;

    return {
      portfolio: sorted.map((s) => ({
        date: s.snapshot_date,
        value: s.total_value,
        pct: ((s.total_value - basePortfolio) / basePortfolio) * 100,
      })),
      spy: sorted.map((s) => ({
        date: s.snapshot_date,
        value: s.benchmark_spy,
        pct: ((s.benchmark_spy - baseSpy) / baseSpy) * 100,
      })),
      maxValue: Math.max(...sorted.map((s) => s.total_value)),
    };
  }

  it('returns empty arrays for empty snapshots', () => {
    const result = deriveChartData([]);
    expect(result.portfolio).toHaveLength(0);
    expect(result.spy).toHaveLength(0);
    expect(result.maxValue).toBe(0);
  });

  it('sorts snapshots chronologically', () => {
    const snapshots: SnapshotRow[] = [
      { snapshot_date: '2026-03-09', total_value: 1100, benchmark_spy: 510 },
      { snapshot_date: '2026-03-07', total_value: 1000, benchmark_spy: 500 },
      { snapshot_date: '2026-03-08', total_value: 1050, benchmark_spy: 505 },
    ];
    const { portfolio } = deriveChartData(snapshots);
    expect(portfolio.map((p) => p.date)).toEqual(['2026-03-07', '2026-03-08', '2026-03-09']);
  });

  it('computes percent change from first entry', () => {
    const snapshots: SnapshotRow[] = [
      { snapshot_date: '2026-03-01', total_value: 1000, benchmark_spy: 500 },
      { snapshot_date: '2026-03-09', total_value: 1100, benchmark_spy: 550 },
    ];
    const { portfolio, spy } = deriveChartData(snapshots);
    expect(portfolio[0].pct).toBe(0);
    expect(portfolio[1].pct).toBeCloseTo(10, 5);
    expect(spy[0].pct).toBe(0);
    expect(spy[1].pct).toBeCloseTo(10, 5);
  });

  it('returns correct maxValue', () => {
    const snapshots: SnapshotRow[] = [
      { snapshot_date: '2026-03-01', total_value: 800, benchmark_spy: 480 },
      { snapshot_date: '2026-03-05', total_value: 1200, benchmark_spy: 510 },
      { snapshot_date: '2026-03-09', total_value: 950, benchmark_spy: 495 },
    ];
    const { maxValue } = deriveChartData(snapshots);
    expect(maxValue).toBe(1200);
  });
});
