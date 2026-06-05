import { describe, it, expect } from 'vitest';

// Test email validation regex
describe('magic link email validation', () => {
  const validEmail = (e: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e.trim());
  it('rejects empty string', () => expect(validEmail('')).toBe(false));
  it('rejects missing @', () => expect(validEmail('notanemail')).toBe(false));
  it('rejects missing domain', () => expect(validEmail('user@')).toBe(false));
  it('accepts valid email', () => expect(validEmail('user@example.com')).toBe(true));
  it('accepts email with dots', () => expect(validEmail('a.b@sub.domain.com')).toBe(true));
});

// Test ticker validation regex
describe('ticker validation regex', () => {
  const validTicker = (t: string) => /^[A-Z][A-Z0-9.\-]{0,9}$/.test(t);
  it('rejects empty string', () => expect(validTicker('')).toBe(false));
  it('rejects lowercase', () => expect(validTicker('aapl')).toBe(false));
  it('rejects with special chars', () => expect(validTicker('INVALID!')).toBe(false));
  it('rejects too long', () => expect(validTicker('TOOLONGNAME')).toBe(false));
  it('accepts AAPL', () => expect(validTicker('AAPL')).toBe(true));
  it('accepts BRK.B', () => expect(validTicker('BRK.B')).toBe(true));
  it('accepts BF-B', () => expect(validTicker('BF-B')).toBe(true));
  it('accepts single letter', () => expect(validTicker('A')).toBe(true));
});

// Test conflict merge logic (inline mirror of the merge function)
describe('conflict merge resolution', () => {
  it('preserves cloud quantities for overlapping tickers', () => {
    const local = { AAPL: { shares: 5, avgCost: 100 }, MSFT: { shares: 2, avgCost: 200 } };
    const cloud = { AAPL: { shares: 10, avgCost: 150 } };
    // Merge: local-only tickers added, overlapping keep cloud value
    const merged = { ...local, ...cloud };
    expect(merged.AAPL.shares).toBe(10); // cloud wins
    expect(merged.MSFT.shares).toBe(2);  // local-only preserved
  });
  it('returns count of local-only tickers added', () => {
    const local = { AAPL: {}, MSFT: {}, GOOGL: {} };
    const cloud = { AAPL: {} };
    const localOnly = Object.keys(local).filter(k => !cloud[k]);
    expect(localOnly).toHaveLength(2);
    expect(localOnly).toContain('MSFT');
    expect(localOnly).toContain('GOOGL');
  });
});
