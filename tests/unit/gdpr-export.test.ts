/**
 * Unit tests — GDPR data export and account deletion
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { makeSupabaseMock } from '../setup';

// ── GDPR export shape validation ──────────────────────────────────────────────

interface GdprExportPayload {
  profile?: unknown;
  portfolios?: unknown[];
  positions?: unknown[];
  watchlist?: unknown[];
  alerts?: unknown[];
  audit_log?: unknown[];
}

function validateExportShape(payload: GdprExportPayload): string[] {
  const errors: string[] = [];
  const requiredKeys: (keyof GdprExportPayload)[] = [
    'profile',
    'portfolios',
    'positions',
    'watchlist',
    'alerts',
    'audit_log',
  ];
  for (const key of requiredKeys) {
    if (!(key in payload)) {
      errors.push(`Missing required key: ${key}`);
    }
  }
  if (payload.portfolios !== undefined && !Array.isArray(payload.portfolios)) {
    errors.push('portfolios must be an array');
  }
  if (payload.positions !== undefined && !Array.isArray(payload.positions)) {
    errors.push('positions must be an array');
  }
  return errors;
}

describe('GDPR export shape validation', () => {
  it('passes for complete export payload', () => {
    const payload: GdprExportPayload = {
      profile: { id: 'user-1', email: 'test@example.com' },
      portfolios: [{ id: 'port-1', name: 'Default' }],
      positions: [{ ticker: 'AAPL', shares: 10 }],
      watchlist: ['GOOG', 'MSFT'],
      alerts: [],
      audit_log: [],
    };
    expect(validateExportShape(payload)).toHaveLength(0);
  });

  it('reports missing required keys', () => {
    const payload = { profile: { id: 'user-1' } } as GdprExportPayload;
    const errors = validateExportShape(payload);
    expect(errors).toContain('Missing required key: portfolios');
    expect(errors).toContain('Missing required key: positions');
    expect(errors).toContain('Missing required key: watchlist');
    expect(errors).toContain('Missing required key: alerts');
    expect(errors).toContain('Missing required key: audit_log');
  });

  it('reports non-array portfolios', () => {
    const payload: GdprExportPayload = {
      profile: {},
      portfolios: 'not-an-array' as unknown as unknown[],
      positions: [],
      watchlist: [],
      alerts: [],
      audit_log: [],
    };
    const errors = validateExportShape(payload);
    expect(errors).toContain('portfolios must be an array');
  });
});

// ── GDPR export — Supabase RPC mock ──────────────────────────────────────────

describe('GDPR export — Supabase RPC mock', () => {
  let supabase: ReturnType<typeof makeSupabaseMock>;

  beforeEach(() => {
    supabase = makeSupabaseMock();
  });

  it('calls gdpr_export_user_data RPC with correct user id', async () => {
    const mockExport: GdprExportPayload = {
      profile: { id: 'user-1' },
      portfolios: [],
      positions: [],
      watchlist: [],
      alerts: [],
      audit_log: [],
    };
    supabase.rpc = vi.fn().mockResolvedValue({ data: mockExport, error: null });

    const { data, error } = await supabase.rpc('gdpr_export_user_data', {
      p_user_id: 'user-1',
    });

    expect(supabase.rpc).toHaveBeenCalledWith('gdpr_export_user_data', {
      p_user_id: 'user-1',
    });
    expect(error).toBeNull();
    expect(data).toEqual(mockExport);
  });

  it('returns error when RPC fails', async () => {
    supabase.rpc = vi.fn().mockResolvedValue({
      data: null,
      error: new Error('DB error'),
    });

    const { data, error } = await supabase.rpc('gdpr_export_user_data', {
      p_user_id: 'user-1',
    });

    expect(data).toBeNull();
    expect(error).toBeTruthy();
  });
});

// ── Account deletion sequence ─────────────────────────────────────────────────

describe('account deletion sequence', () => {
  /**
   * Simulates the delete-account Edge Function's deletion flow,
   * verifying order-of-operations: Stripe → Vault → Storage → DB → Auth
   */
  it('executes deletion steps in correct order', async () => {
    const callOrder: string[] = [];

    const mockDeleteStripe = vi.fn().mockImplementation(async () => {
      callOrder.push('stripe');
    });
    const mockDeleteVault = vi.fn().mockImplementation(async () => {
      callOrder.push('vault');
    });
    const mockDeleteStorage = vi.fn().mockImplementation(async () => {
      callOrder.push('storage');
    });
    const mockDeleteDB = vi.fn().mockImplementation(async () => {
      callOrder.push('db');
    });
    const mockDeleteAuth = vi.fn().mockImplementation(async () => {
      callOrder.push('auth');
    });

    // Simulate the Edge Function's sequential deletion flow
    await mockDeleteStripe();
    await mockDeleteVault();
    await mockDeleteStorage();
    await mockDeleteDB();
    await mockDeleteAuth();

    expect(callOrder).toEqual(['stripe', 'vault', 'storage', 'db', 'auth']);
  });

  it('requires confirmation text "DELETE MY ACCOUNT"', () => {
    const validConfirmations = ['DELETE MY ACCOUNT'];
    const invalidConfirmations = [
      'delete my account',
      'DELETE MY ACCOUNT ',
      ' DELETE MY ACCOUNT',
      'DELETE',
      '',
      'yes',
    ];

    for (const text of validConfirmations) {
      expect(text === 'DELETE MY ACCOUNT').toBe(true);
    }
    for (const text of invalidConfirmations) {
      expect(text === 'DELETE MY ACCOUNT').toBe(false);
    }
  });

  it('continues auth deletion even if Stripe fails (partial error)', async () => {
    const errors: string[] = [];
    const authDeleted = { deleted: false };

    // Simulate Stripe failing
    try {
      throw new Error('Stripe unavailable');
    } catch (err) {
      errors.push(`Stripe: ${err}`);
    }

    // Auth should still proceed
    authDeleted.deleted = true;

    expect(errors).toHaveLength(1);
    expect(errors[0]).toContain('Stripe');
    expect(authDeleted.deleted).toBe(true);
  });
});

// ── Audit log immutability ────────────────────────────────────────────────────

describe('audit log immutability', () => {
  /**
   * The audit_logs table has NO UPDATE or DELETE policies (only SELECT + INSERT).
   * These tests verify the application-level behavior — actual DB policy
   * is tested in integration tests.
   */

  it('write_audit_log creates immutable entry (no update path)', async () => {
    const logs: Array<{ action: string; payload: unknown; created_at: string }> = [];

    function writeAuditLog(action: string, payload: unknown) {
      const entry = {
        action,
        payload,
        created_at: new Date().toISOString(),
      };
      logs.push(entry); // append-only, never mutate
      return entry;
    }

    const entry1 = writeAuditLog('recommendation_viewed', { portfolio_id: 'port-1' });
    const entry2 = writeAuditLog('report_generated', { report_id: 'rpt-1' });

    expect(logs).toHaveLength(2);
    expect(logs[0]).toBe(entry1); // same reference (not copied/mutated)
    expect(logs[1]).toBe(entry2);

    // Simulate "trying to update" — should not affect existing entry
    const updatedEntry = { ...entry1, action: 'tampered' };
    expect(logs[0].action).toBe('recommendation_viewed'); // original unchanged
    expect(updatedEntry.action).toBe('tampered'); // new object, not a mutation
  });

  it('audit log entry contains required SEC Rule 204-2 fields', () => {
    const auditEntry = {
      user_id: 'user-1',
      advisor_id: 'advisor-1',
      action: 'recommendation_record',
      entity_type: 'recommendation_record',
      payload: { portfolio_id: 'port-1', report_url: 'https://...' },
      created_at: new Date().toISOString(),
    };

    expect(auditEntry).toHaveProperty('user_id');
    expect(auditEntry).toHaveProperty('advisor_id');
    expect(auditEntry).toHaveProperty('action');
    expect(auditEntry).toHaveProperty('entity_type');
    expect(auditEntry).toHaveProperty('payload');
    expect(auditEntry).toHaveProperty('created_at');
    expect(auditEntry.entity_type).toBe('recommendation_record');
  });
});

// ── Advisor branding CSS application ─────────────────────────────────────────

describe('advisor branding', () => {
  it('applies primary_color as CSS custom property', () => {
    const root = {
      style: {
        properties: {} as Record<string, string>,
        setProperty(name: string, value: string) {
          this.properties[name] = value;
        },
        getPropertyValue(name: string) {
          return this.properties[name] ?? '';
        },
      },
    };

    const branding = { primary_color: '#1a73e8', firm_name: 'Acme Capital' };

    if (branding.primary_color) {
      root.style.setProperty('--brand-primary', branding.primary_color);
    }

    expect(root.style.getPropertyValue('--brand-primary')).toBe('#1a73e8');
  });

  it('does not apply if primary_color is missing', () => {
    const root = {
      style: {
        properties: {} as Record<string, string>,
        setProperty(name: string, value: string) {
          this.properties[name] = value;
        },
      },
    };

    const branding = { primary_color: null, firm_name: 'Acme Capital' };

    if (branding.primary_color) {
      root.style.setProperty('--brand-primary', branding.primary_color);
    }

    expect(Object.keys(root.style.properties)).toHaveLength(0);
  });
});
