/**
 * Unit tests for auth state management
 * Tests that streamAI routing (proxy vs. direct) depends on session state
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { makeSupabaseMock } from '../setup.js';

// ── Minimal in-memory replica of the auth state from index.html ──────────────

const SUPABASE_URL = 'https://test.supabase.co';
const SUPABASE_ANON = 'test-anon-key';

function createAppState() {
  let _supabaseUser: object | null = null;
  let _supabaseSession: { access_token: string; user: object } | null = null;
  let _supabase: ReturnType<typeof makeSupabaseMock> | null = null;
  let apiKey = '';
  let geminiKey = '';

  function getActiveAI(): 'claude' | 'gemini' | null {
    if (apiKey) return 'claude';
    if (geminiKey) return 'gemini';
    return null;
  }

  async function streamAI(
    systemPrompt: string,
    messages: Array<{ role: string; content: string }>,
    maxTokens: number,
    onChunk: (text: string) => void,
    fetchFn: typeof fetch,
  ): Promise<string> {
    // Authenticated path — proxy
    if (_supabase && _supabaseSession) {
      const resp = await fetchFn(`${SUPABASE_URL}/functions/v1/ai-proxy`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${_supabaseSession.access_token}`,
          apikey: SUPABASE_ANON,
        },
        body: JSON.stringify({ systemPrompt, messages, maxTokens }),
      });
      if (!resp.ok) throw new Error(`AI proxy error ${resp.status}`);
      return 'proxy';
    }

    // Anonymous path — direct browser call
    const ai = getActiveAI();
    if (!ai) throw new Error('No API key found.');

    if (ai === 'claude') {
      await fetchFn('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: { 'x-api-key': apiKey, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
        body: JSON.stringify({ messages }),
      });
      return 'direct-claude';
    } else {
      await fetchFn(`https://generativelanguage.googleapis.com/v1beta/models/gemini:streamGenerateContent?key=${geminiKey}`, {
        method: 'POST',
        body: JSON.stringify({ contents: messages }),
      });
      return 'direct-gemini';
    }
  }

  return {
    set supabase(v: ReturnType<typeof makeSupabaseMock> | null) { _supabase = v; },
    set session(v: { access_token: string; user: object } | null) { _supabaseSession = v; _supabaseUser = v?.user ?? null; },
    set apiKey(v: string) { apiKey = v; },
    set geminiKey(v: string) { geminiKey = v; },
    streamAI,
  };
}

describe('streamAI routing', () => {
  let app: ReturnType<typeof createAppState>;
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    app = createAppState();
    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: { getReader: () => ({ read: async () => ({ done: true, value: undefined }) }) },
    });
  });

  it('routes to Edge Function proxy when session is present', async () => {
    app.supabase = makeSupabaseMock() as ReturnType<typeof makeSupabaseMock>;
    app.session = { access_token: 'jwt-token', user: { id: 'user-123' } };

    const route = await app.streamAI('sys', [{ role: 'user', content: 'hello' }], 100, () => {}, fetchMock);

    expect(route).toBe('proxy');
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, opts] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/functions/v1/ai-proxy');
    expect((opts.headers as Record<string, string>)['Authorization']).toBe('Bearer jwt-token');
  });

  it('routes to direct Claude call when no session but Claude key present', async () => {
    app.session = null;
    app.apiKey = 'sk-ant-test-key';

    const route = await app.streamAI('sys', [{ role: 'user', content: 'hello' }], 100, () => {}, fetchMock);

    expect(route).toBe('direct-claude');
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe('https://api.anthropic.com/v1/messages');
  });

  it('routes to direct Gemini call when no session but Gemini key present', async () => {
    app.session = null;
    app.geminiKey = 'AIza-test-key';

    const route = await app.streamAI('sys', [{ role: 'user', content: 'hello' }], 100, () => {}, fetchMock);

    expect(route).toBe('direct-gemini');
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('generativelanguage.googleapis.com');
  });

  it('throws when no session and no API key', async () => {
    app.session = null;
    // No API key set

    await expect(
      app.streamAI('sys', [{ role: 'user', content: 'hello' }], 100, () => {}, fetchMock),
    ).rejects.toThrow('No API key found.');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('proxy takes precedence over direct key when session is active', async () => {
    // Both session AND local key present — proxy should win
    app.supabase = makeSupabaseMock() as ReturnType<typeof makeSupabaseMock>;
    app.session = { access_token: 'jwt-token', user: {} };
    app.apiKey = 'sk-ant-should-not-be-used';

    const route = await app.streamAI('sys', [{ role: 'user', content: 'hi' }], 100, () => {}, fetchMock);

    expect(route).toBe('proxy');
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain('/functions/v1/ai-proxy');
    // Direct Anthropic endpoint must NOT have been called
    expect(url).not.toContain('anthropic.com');
  });

  it('proxy returns 402 for credit exhausted — throws with helpful message', async () => {
    app.supabase = makeSupabaseMock() as ReturnType<typeof makeSupabaseMock>;
    app.session = { access_token: 'jwt-token', user: {} };
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 402,
      json: async () => ({ error: 'AI credit limit reached. Upgrade to Pro for unlimited access.' }),
    });

    await expect(
      app.streamAI('sys', [{ role: 'user', content: 'hi' }], 100, () => {}, fetchMock),
    ).rejects.toThrow('AI credit limit reached');
  });
});
