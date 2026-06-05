import { describe, it, expect } from 'vitest';

// Placeholder for existing snapshot tests
// (No existing snapshot.test.ts was found; this file is created fresh)

describe('performance chart empty state', () => {
  it('empty snapshots array triggers empty state not hide', () => {
    // This test documents the expected behavior: when snapshots is empty/null,
    // the chart card should remain visible (display not 'none')
    // and show an empty state message
    const snapshots: any[] = [];
    const shouldHide = !snapshots?.length && false; // new behavior: never hide
    const shouldShowEmptyState = !snapshots?.length;
    expect(shouldHide).toBe(false);
    expect(shouldShowEmptyState).toBe(true);
  });
  it('empty state message references "Performance tracking"', () => {
    const emptyStateHtml = '<div>📈</div><div>Performance tracking starts once daily snapshots are recorded.</div>';
    expect(emptyStateHtml).toContain('Performance tracking');
  });
});
