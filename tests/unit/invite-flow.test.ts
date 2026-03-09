/**
 * Unit tests for portfolio sharing invite flow
 * Tests invite creation, acceptance, and revocation logic
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// ── Minimal invite logic replica ──────────────────────────────────────────────

type InviteRecord = {
  id: string;
  portfolio_id: string;
  user_id: string | null;
  invited_email: string | null;
  role: 'viewer' | 'editor';
  invite_token: string;
  accepted_at: string | null;
};

function generateToken() {
  return Math.random().toString(36).substring(2, 18);
}

// In-memory invite store for tests
function createInviteStore() {
  const store: Map<string, InviteRecord> = new Map();

  return {
    createInvite(portfolioId: string, email: string, role: 'viewer' | 'editor'): InviteRecord {
      const token = generateToken();
      const record: InviteRecord = {
        id: generateToken(),
        portfolio_id: portfolioId,
        user_id: null,
        invited_email: email,
        role,
        invite_token: token,
        accepted_at: null,
      };
      store.set(token, record);
      return record;
    },

    acceptInvite(token: string, userId: string): { error?: string; portfolio_id?: string; role?: string } {
      const record = store.get(token);
      if (!record) return { error: 'Invite not found' };
      if (record.accepted_at) return { error: 'Invite already accepted' };
      record.user_id = userId;
      record.accepted_at = new Date().toISOString();
      store.set(token, record);
      return { portfolio_id: record.portfolio_id, role: record.role };
    },

    revokeInvite(collaboratorId: string, ownerPortfolioIds: string[]): { error?: string; success?: boolean } {
      for (const [token, record] of store.entries()) {
        if (record.id === collaboratorId && ownerPortfolioIds.includes(record.portfolio_id)) {
          store.delete(token);
          return { success: true };
        }
      }
      return { error: 'Collaborator not found or not authorized' };
    },

    getAll() { return [...store.values()]; },
  };
}

describe('invite flow — create', () => {
  let invites: ReturnType<typeof createInviteStore>;

  beforeEach(() => {
    invites = createInviteStore();
  });

  it('creates an invite with a unique token', () => {
    const invite = invites.createInvite('portfolio-1', 'alice@example.com', 'viewer');
    expect(invite.invite_token).toBeTruthy();
    expect(invite.accepted_at).toBeNull();
    expect(invite.role).toBe('viewer');
  });

  it('creates viewer and editor invites with different tokens', () => {
    const viewerInvite = invites.createInvite('portfolio-1', 'alice@example.com', 'viewer');
    const editorInvite = invites.createInvite('portfolio-1', 'bob@example.com', 'editor');
    expect(viewerInvite.invite_token).not.toBe(editorInvite.invite_token);
  });

  it('stores invite with null accepted_at initially', () => {
    invites.createInvite('portfolio-1', 'charlie@example.com', 'editor');
    const all = invites.getAll();
    expect(all[0].accepted_at).toBeNull();
  });
});

describe('invite flow — accept', () => {
  let invites: ReturnType<typeof createInviteStore>;

  beforeEach(() => {
    invites = createInviteStore();
  });

  it('accepts a valid invite and sets accepted_at', () => {
    const invite = invites.createInvite('portfolio-1', 'alice@example.com', 'viewer');
    const result = invites.acceptInvite(invite.invite_token, 'user-alice');
    expect(result.error).toBeUndefined();
    expect(result.portfolio_id).toBe('portfolio-1');
    expect(result.role).toBe('viewer');

    const all = invites.getAll();
    expect(all[0].accepted_at).not.toBeNull();
    expect(all[0].user_id).toBe('user-alice');
  });

  it('returns error for invalid token', () => {
    const result = invites.acceptInvite('nonexistent-token', 'user-bob');
    expect(result.error).toBe('Invite not found');
  });

  it('returns error when already accepted', () => {
    const invite = invites.createInvite('portfolio-1', 'alice@example.com', 'viewer');
    invites.acceptInvite(invite.invite_token, 'user-alice');
    const secondAccept = invites.acceptInvite(invite.invite_token, 'user-alice');
    expect(secondAccept.error).toBe('Invite already accepted');
  });

  it('preserves the correct role after acceptance', () => {
    const invite = invites.createInvite('portfolio-1', 'bob@example.com', 'editor');
    const result = invites.acceptInvite(invite.invite_token, 'user-bob');
    expect(result.role).toBe('editor');
  });
});

describe('invite flow — revoke', () => {
  let invites: ReturnType<typeof createInviteStore>;

  beforeEach(() => {
    invites = createInviteStore();
  });

  it('revokes an invite when called by the portfolio owner', () => {
    const invite = invites.createInvite('portfolio-1', 'alice@example.com', 'viewer');
    const result = invites.revokeInvite(invite.id, ['portfolio-1']);
    expect(result.success).toBe(true);
    expect(invites.getAll()).toHaveLength(0);
  });

  it('cannot revoke an invite for a portfolio the caller does not own', () => {
    const invite = invites.createInvite('portfolio-1', 'alice@example.com', 'viewer');
    const result = invites.revokeInvite(invite.id, ['portfolio-999']); // different portfolio
    expect(result.error).toBeTruthy();
    expect(invites.getAll()).toHaveLength(1); // Still present
  });

  it('returns error for nonexistent collaborator', () => {
    const result = invites.revokeInvite('nonexistent-id', ['portfolio-1']);
    expect(result.error).toBeTruthy();
  });
});
