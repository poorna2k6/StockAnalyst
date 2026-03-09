/**
 * Unit tests for billing tier enforcement
 * Tests requireTier() logic: free/pro/advisor access gates
 */

import { describe, it, expect, vi } from 'vitest';

// ── Inline tier guard logic (mirrors requireTier in index.html) ───────────────

type Tier = 'free' | 'pro' | 'advisor';

interface MockUser {
  user_metadata: {
    subscription_tier?: Tier;
    account_type?: string;
  };
}

function requireTier(
  minTier: Tier,
  user: MockUser | null,
  onUpgrade: (tier: Tier) => void,
): boolean {
  const tiers: Record<Tier, number> = { free: 0, pro: 1, advisor: 2 };
  const userTier = (user?.user_metadata?.subscription_tier ?? 'free') as Tier;
  if ((tiers[userTier] ?? 0) < (tiers[minTier] ?? 0)) {
    onUpgrade(minTier);
    return false;
  }
  return true;
}

describe('requireTier — free user', () => {
  const freeUser: MockUser = { user_metadata: { subscription_tier: 'free' } };
  const onUpgrade = vi.fn();

  it('grants access to free features', () => {
    const result = requireTier('free', freeUser, onUpgrade);
    expect(result).toBe(true);
    expect(onUpgrade).not.toHaveBeenCalled();
  });

  it('blocks access to pro features', () => {
    const result = requireTier('pro', freeUser, onUpgrade);
    expect(result).toBe(false);
    expect(onUpgrade).toHaveBeenCalledWith('pro');
  });

  it('blocks access to advisor features', () => {
    const result = requireTier('advisor', freeUser, onUpgrade);
    expect(result).toBe(false);
    expect(onUpgrade).toHaveBeenCalledWith('advisor');
  });
});

describe('requireTier — pro user', () => {
  const proUser: MockUser = { user_metadata: { subscription_tier: 'pro' } };
  const onUpgrade = vi.fn();

  it('grants access to free features', () => {
    expect(requireTier('free', proUser, onUpgrade)).toBe(true);
  });

  it('grants access to pro features', () => {
    expect(requireTier('pro', proUser, onUpgrade)).toBe(true);
    expect(onUpgrade).not.toHaveBeenCalled();
  });

  it('blocks access to advisor features', () => {
    const result = requireTier('advisor', proUser, onUpgrade);
    expect(result).toBe(false);
    expect(onUpgrade).toHaveBeenCalledWith('advisor');
  });
});

describe('requireTier — advisor user', () => {
  const advisorUser: MockUser = { user_metadata: { subscription_tier: 'advisor' } };
  const onUpgrade = vi.fn();

  it('grants access to all tiers', () => {
    expect(requireTier('free', advisorUser, onUpgrade)).toBe(true);
    expect(requireTier('pro', advisorUser, onUpgrade)).toBe(true);
    expect(requireTier('advisor', advisorUser, onUpgrade)).toBe(true);
    expect(onUpgrade).not.toHaveBeenCalled();
  });
});

describe('requireTier — no user (anonymous)', () => {
  const onUpgrade = vi.fn();

  it('grants access to free features when no user', () => {
    expect(requireTier('free', null, onUpgrade)).toBe(true);
  });

  it('blocks pro features for anonymous user', () => {
    expect(requireTier('pro', null, onUpgrade)).toBe(false);
    expect(onUpgrade).toHaveBeenCalledWith('pro');
  });
});

describe('requireTier — missing subscription_tier defaults to free', () => {
  const noTierUser: MockUser = { user_metadata: {} };
  const onUpgrade = vi.fn();

  it('treats missing tier as free', () => {
    expect(requireTier('free', noTierUser, onUpgrade)).toBe(true);
    expect(requireTier('pro', noTierUser, onUpgrade)).toBe(false);
  });
});
