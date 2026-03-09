/**
 * Global test setup
 * - Polyfills IndexedDB with fake-indexeddb for service worker unit tests
 * - Provides Supabase mock utilities
 */

import 'fake-indexeddb/auto';

// Silence console.warn in tests unless explicitly needed
const originalWarn = console.warn;
beforeAll(() => {
  console.warn = (...args: unknown[]) => {
    // Allow test-authored warnings through; suppress library noise
    if (String(args[0]).includes('[MSA]') || String(args[0]).includes('SW')) return;
    originalWarn(...args);
  };
});
afterAll(() => {
  console.warn = originalWarn;
});

/** Build a minimal Supabase client mock for unit tests */
export function makeSupabaseMock(overrides: Record<string, unknown> = {}) {
  return {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }),
      signInWithOAuth: vi.fn().mockResolvedValue({ data: {}, error: null }),
      signInWithOtp: vi.fn().mockResolvedValue({ data: {}, error: null }),
      signOut: vi.fn().mockResolvedValue({ error: null }),
      onAuthStateChange: vi.fn().mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } }),
    },
    from: vi.fn().mockReturnValue({
      select: vi.fn().mockReturnThis(),
      insert: vi.fn().mockReturnThis(),
      upsert: vi.fn().mockReturnThis(),
      update: vi.fn().mockReturnThis(),
      delete: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      limit: vi.fn().mockReturnThis(),
      order: vi.fn().mockReturnThis(),
      single: vi.fn().mockResolvedValue({ data: null, error: null }),
      then: vi.fn().mockResolvedValue({ data: [], error: null }),
    }),
    rpc: vi.fn().mockResolvedValue({ data: -1, error: null }),
    ...overrides,
  };
}
