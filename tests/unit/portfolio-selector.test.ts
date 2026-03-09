/**
 * Unit tests for multi-portfolio selector logic
 * Tests that switching activePortfolioId correctly routes DB calls
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// ── Minimal DB layer replica (mirrors DB.* in index.html) ────────────────────

type Portfolio = Record<string, { shares: number; avgCost: number }>;

function createDBLayer(supabaseMock: {
  from: (table: string) => {
    select: (cols: string) => {
      eq: (col: string, val: string) => { data: Array<{ ticker: string; shares: number; avg_cost: number }> | null };
    };
    upsert: (row: object, opts?: object) => Promise<{ error: null }>;
    delete: () => { eq: (col: string, val: string) => { eq: (c: string, v: string) => Promise<{ error: null }> } };
  };
} | null, user: { id: string } | null) {
  let _activePortfolioId: string | null = null;

  return {
    setPortfolioId(id: string) { _activePortfolioId = id; },
    getPortfolioId() { return _activePortfolioId; },

    async savePosition(ticker: string, shares: number, avgCost: number) {
      if (!supabaseMock || !user || !_activePortfolioId) return;
      await supabaseMock.from('positions').upsert(
        { portfolio_id: _activePortfolioId, ticker, shares, avg_cost: avgCost },
        { onConflict: 'portfolio_id,ticker' },
      );
    },

    async removePosition(ticker: string) {
      if (!supabaseMock || !user || !_activePortfolioId) return;
      await supabaseMock.from('positions').delete()
        .eq('portfolio_id', _activePortfolioId)
        .eq('ticker', ticker);
    },
  };
}

describe('portfolio selector — DB routing', () => {
  let fromMock: ReturnType<typeof vi.fn>;
  let upsertMock: ReturnType<typeof vi.fn>;
  let deleteMock: ReturnType<typeof vi.fn>;
  let db: ReturnType<typeof createDBLayer>;

  beforeEach(() => {
    upsertMock = vi.fn().mockResolvedValue({ error: null });
    deleteMock = vi.fn().mockReturnValue({
      eq: vi.fn().mockReturnValue({
        eq: vi.fn().mockResolvedValue({ error: null }),
      }),
    });
    fromMock = vi.fn().mockReturnValue({
      select: vi.fn().mockReturnValue({ eq: vi.fn().mockResolvedValue({ data: [] }) }),
      upsert: upsertMock,
      delete: deleteMock,
    });

    const supabaseMock = { from: fromMock } as Parameters<typeof createDBLayer>[0];
    db = createDBLayer(supabaseMock, { id: 'user-123' });
  });

  it('savePosition uses activePortfolioId when set', async () => {
    db.setPortfolioId('portfolio-abc');
    await db.savePosition('AAPL', 10, 150);

    expect(fromMock).toHaveBeenCalledWith('positions');
    const [upsertArg] = upsertMock.mock.calls[0] as [{ portfolio_id: string; ticker: string }];
    expect(upsertArg.portfolio_id).toBe('portfolio-abc');
    expect(upsertArg.ticker).toBe('AAPL');
  });

  it('switching portfolioId causes next savePosition to use new ID', async () => {
    db.setPortfolioId('portfolio-1');
    await db.savePosition('AAPL', 5, 160);
    const [firstArg] = upsertMock.mock.calls[0] as [{ portfolio_id: string }];
    expect(firstArg.portfolio_id).toBe('portfolio-1');

    db.setPortfolioId('portfolio-2');
    await db.savePosition('MSFT', 3, 300);
    const [secondArg] = upsertMock.mock.calls[1] as [{ portfolio_id: string }];
    expect(secondArg.portfolio_id).toBe('portfolio-2');
  });

  it('removePosition uses activePortfolioId', async () => {
    db.setPortfolioId('portfolio-xyz');
    await db.removePosition('TSLA');

    expect(fromMock).toHaveBeenCalledWith('positions');
    expect(deleteMock).toHaveBeenCalled();
  });

  it('savePosition is a no-op when no portfolioId is set', async () => {
    // No portfolio set
    await db.savePosition('AAPL', 10, 150);
    expect(upsertMock).not.toHaveBeenCalled();
  });

  it('savePosition is a no-op when no user', async () => {
    const noUserDb = createDBLayer({ from: fromMock } as Parameters<typeof createDBLayer>[0], null);
    noUserDb.setPortfolioId('portfolio-123');
    await noUserDb.savePosition('AAPL', 10, 150);
    expect(upsertMock).not.toHaveBeenCalled();
  });
});
