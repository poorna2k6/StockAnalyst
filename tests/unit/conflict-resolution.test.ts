/**
 * Unit tests for portfolio conflict resolution logic
 * Tests the merge/keep-local/keep-cloud paths
 */

import { describe, it, expect } from 'vitest';

// Inline the merge logic (mirrors resolveConflict in index.html) for testability
type Portfolio = Record<string, { shares: number; avgCost: number }>;

type ConflictChoice = 'local' | 'cloud' | 'merge';

async function resolveConflict(
  choice: ConflictChoice,
  local: Portfolio,
  cloud: Portfolio,
): Promise<Portfolio> {
  if (choice === 'local') {
    // Keep local — push to cloud (returns local unchanged)
    return { ...local };
  } else if (choice === 'cloud') {
    // Keep cloud — overwrite local with cloud
    return { ...cloud };
  } else {
    // Merge — add local tickers that don't exist in cloud
    const merged = { ...cloud };
    for (const [ticker, position] of Object.entries(local)) {
      if (!merged[ticker]) {
        merged[ticker] = position;
      }
    }
    return merged;
  }
}

const LOCAL: Portfolio = {
  AAPL: { shares: 10, avgCost: 150 },
  MSFT: { shares: 5, avgCost: 300 },
};

const CLOUD: Portfolio = {
  AAPL: { shares: 8, avgCost: 155 }, // Different shares (conflict)
  NVDA: { shares: 3, avgCost: 500 }, // Only in cloud
};

describe('conflict resolution — keep local', () => {
  it('returns the local portfolio unchanged', async () => {
    const result = await resolveConflict('local', LOCAL, CLOUD);
    expect(result).toEqual(LOCAL);
  });

  it('local data has correct shares', async () => {
    const result = await resolveConflict('local', LOCAL, CLOUD);
    expect(result.AAPL.shares).toBe(10);
  });
});

describe('conflict resolution — keep cloud', () => {
  it('returns the cloud portfolio', async () => {
    const result = await resolveConflict('cloud', LOCAL, CLOUD);
    expect(result).toEqual(CLOUD);
  });

  it('cloud data replaces local AAPL', async () => {
    const result = await resolveConflict('cloud', LOCAL, CLOUD);
    expect(result.AAPL.shares).toBe(8);
    expect(result.AAPL.avgCost).toBe(155);
  });

  it('local-only MSFT is gone after cloud resolution', async () => {
    const result = await resolveConflict('cloud', LOCAL, CLOUD);
    expect(result.MSFT).toBeUndefined();
  });
});

describe('conflict resolution — merge', () => {
  it('contains cloud tickers', async () => {
    const result = await resolveConflict('merge', LOCAL, CLOUD);
    expect(result.AAPL).toBeDefined();
    expect(result.NVDA).toBeDefined();
  });

  it('adds local-only tickers not in cloud', async () => {
    const result = await resolveConflict('merge', LOCAL, CLOUD);
    // MSFT is in local but not in cloud — should appear in merged result
    expect(result.MSFT).toBeDefined();
    expect(result.MSFT.shares).toBe(5);
  });

  it('cloud version of AAPL wins (not overwritten by local)', async () => {
    const result = await resolveConflict('merge', LOCAL, CLOUD);
    // Cloud had AAPL with 8 shares, local had 10 — merge keeps cloud
    expect(result.AAPL.shares).toBe(8);
  });

  it('total positions = union of both portfolios', async () => {
    const result = await resolveConflict('merge', LOCAL, CLOUD);
    // AAPL (both) + MSFT (local only) + NVDA (cloud only) = 3
    expect(Object.keys(result)).toHaveLength(3);
  });
});

describe('edge cases', () => {
  it('empty local + non-empty cloud: merge returns cloud', async () => {
    const result = await resolveConflict('merge', {}, CLOUD);
    expect(result).toEqual(CLOUD);
  });

  it('non-empty local + empty cloud: merge returns local', async () => {
    const result = await resolveConflict('merge', LOCAL, {});
    expect(result).toEqual(LOCAL);
  });

  it('both empty: merge returns empty', async () => {
    const result = await resolveConflict('merge', {}, {});
    expect(result).toEqual({});
  });
});
